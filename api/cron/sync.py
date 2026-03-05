"""
GET /api/cron/sync — Vercel Cron Job 定时同步数据
优化：使用 ON CONFLICT 批量 upsert + 批量记录价格历史 + 批量判断新低
"""
import json
import os
import sys
from http.server import BaseHTTPRequestHandler
from datetime import datetime

# ── 确保能导入 api/ 目录下的 _db 和 _fetch 模块 ──
_API_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _API_DIR not in sys.path:
    sys.path.insert(0, _API_DIR)

from _db import get_conn, init_db
from _fetch import fetch_all

def upsert_products(products: list[dict]) -> dict:
    """批量 upsert 商品 — 用 ON CONFLICT 一条SQL搞定，避免逐条查询"""
    conn = get_conn()
    cur = conn.cursor()
    now = datetime.utcnow()

    inserted, updated = 0, 0

    for p in products:
        cur.execute("""
            INSERT INTO products
                (item_id, platform, title, cover_image, affiliate_url,
                 original_price, final_price, weight_grams, price_per_gram,
                 discount_rate, coupon_amount, discount_amount, monthly_sales,
                 is_price_lowest, update_time)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,TRUE,%s)
            ON CONFLICT (item_id) DO UPDATE SET
                platform=EXCLUDED.platform, title=EXCLUDED.title,
                cover_image=EXCLUDED.cover_image, affiliate_url=EXCLUDED.affiliate_url,
                original_price=EXCLUDED.original_price, final_price=EXCLUDED.final_price,
                weight_grams=EXCLUDED.weight_grams, price_per_gram=EXCLUDED.price_per_gram,
                discount_rate=EXCLUDED.discount_rate, coupon_amount=EXCLUDED.coupon_amount,
                discount_amount=EXCLUDED.discount_amount, monthly_sales=EXCLUDED.monthly_sales,
                update_time=EXCLUDED.update_time
            RETURNING (xmax = 0) AS is_insert
        """, (
            p["item_id"], p["platform"], p["title"], p["cover_image"],
            p["affiliate_url"], p["original_price"], p["final_price"],
            p["weight_grams"], p["price_per_gram"],
            p["discount_rate"], p["coupon_amount"], p["discount_amount"],
            p["monthly_sales"], now,
        ))
        row = cur.fetchone()
        if row and row["is_insert"]:
            inserted += 1
        else:
            updated += 1

    conn.commit()

    # ── 批量记录价格历史（一条 INSERT ... SELECT）──
    cur.execute("""
        INSERT INTO price_history (product_id, final_price, original_price, coupon_amount, recorded_at)
        SELECT id, final_price, original_price, coupon_amount, %s
        FROM products
        WHERE update_time = %s
    """, (now, now))

    # ── 批量更新近期新低标记 ──
    cur.execute("""
        UPDATE products p SET is_price_lowest = (
            p.final_price <= COALESCE(
                (SELECT MIN(ph.final_price) FROM price_history ph
                 WHERE ph.product_id = p.id
                   AND ph.recorded_at >= NOW() - INTERVAL '30 days'
                   AND ph.recorded_at < %s),
                p.final_price
            )
        )
        WHERE p.update_time = %s
    """, (now, now))

    # 统计新低数
    cur.execute("SELECT COUNT(*) AS cnt FROM products WHERE is_price_lowest = TRUE")
    lowest_count = cur.fetchone()["cnt"]

    conn.commit()
    cur.close()
    conn.close()
    return {"inserted": inserted, "updated": updated, "price_lowest": lowest_count}


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        try:
            # 验证 Cron 密钥（可选，防止外部调用）
            cron_secret = os.environ.get("CRON_SECRET")
            if cron_secret:
                auth = self.headers.get("Authorization")
                if auth != f"Bearer {cron_secret}":
                    self._send_json(401, '{"error":"Unauthorized"}')
                    return

            init_db()

            # 拉取全部数据
            products = fetch_all()
            if not products:
                body = json.dumps({"status": "warning", "message": "未获取到商品数据"})
                self._send_json(200, body)
                return

            # 入库
            result = upsert_products(products)

            body = json.dumps({
                "status": "success",
                "total_fetched": len(products),
                "inserted": result["inserted"],
                "updated": result["updated"],
                "price_lowest": result["price_lowest"],
                "time": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC"),
            }, ensure_ascii=False)

            self._send_json(200, body)

        except Exception as e:
            body = json.dumps({"error": str(e)}, ensure_ascii=False)
            self._send_json(500, body)

    def _send_json(self, status, body):
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body.encode("utf-8"))