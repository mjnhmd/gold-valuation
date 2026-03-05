"""
GET /api/cron/sync — Vercel Cron Job 定时同步数据
每天自动调用，也可手动触发
新增：写入折扣率/优惠券/降价额/销量 + 记录价格历史 + 判断近期新低
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

# 近期新低对比天数
PRICE_HISTORY_DAYS = 30


def upsert_products(products: list[dict]) -> dict:
    """批量 upsert 商品到数据库，记录价格历史，判断近期新低"""
    conn = get_conn()
    cur = conn.cursor()
    inserted, updated, lowest_count = 0, 0, 0
    now = datetime.utcnow()

    for p in products:
        cur.execute("SELECT id, final_price FROM products WHERE item_id = %s", (p["item_id"],))
        existing = cur.fetchone()

        # 判断是否为近期最低价
        is_lowest = True  # 新商品默认是最低
        if existing:
            product_id = existing["id"]
            # 查询近 N 天历史最低价
            cur.execute("""
                SELECT MIN(final_price) AS min_price FROM price_history
                WHERE product_id = %s
                  AND recorded_at >= NOW() - INTERVAL '%s days'
            """, (product_id, PRICE_HISTORY_DAYS))
            hist = cur.fetchone()
            if hist and hist["min_price"] is not None:
                is_lowest = p["final_price"] <= hist["min_price"]
            # 即使没有历史记录，也和当前价对比
            elif existing["final_price"]:
                is_lowest = p["final_price"] <= existing["final_price"]

        if is_lowest:
            lowest_count += 1

        if existing:
            cur.execute("""
                UPDATE products SET
                    platform=%s, title=%s, cover_image=%s, affiliate_url=%s,
                    original_price=%s, final_price=%s, weight_grams=%s,
                    price_per_gram=%s, discount_rate=%s, coupon_amount=%s,
                    discount_amount=%s, monthly_sales=%s, is_price_lowest=%s,
                    update_time=%s
                WHERE item_id=%s
            """, (
                p["platform"], p["title"], p["cover_image"], p["affiliate_url"],
                p["original_price"], p["final_price"], p["weight_grams"],
                p["price_per_gram"], p["discount_rate"], p["coupon_amount"],
                p["discount_amount"], p["monthly_sales"], is_lowest,
                now, p["item_id"],
            ))
            updated += 1
            # 记录价格历史
            cur.execute("""
                INSERT INTO price_history (product_id, final_price, original_price, coupon_amount, recorded_at)
                VALUES (%s, %s, %s, %s, %s)
            """, (product_id, p["final_price"], p["original_price"], p["coupon_amount"], now))
        else:
            cur.execute("""
                INSERT INTO products
                    (item_id, platform, title, cover_image, affiliate_url,
                     original_price, final_price, weight_grams, price_per_gram,
                     discount_rate, coupon_amount, discount_amount, monthly_sales,
                     is_price_lowest, update_time)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                RETURNING id
            """, (
                p["item_id"], p["platform"], p["title"], p["cover_image"],
                p["affiliate_url"], p["original_price"], p["final_price"],
                p["weight_grams"], p["price_per_gram"],
                p["discount_rate"], p["coupon_amount"], p["discount_amount"],
                p["monthly_sales"], is_lowest, now,
            ))
            new_id = cur.fetchone()["id"]
            inserted += 1
            # 记录首条价格历史
            cur.execute("""
                INSERT INTO price_history (product_id, final_price, original_price, coupon_amount, recorded_at)
                VALUES (%s, %s, %s, %s, %s)
            """, (new_id, p["final_price"], p["original_price"], p["coupon_amount"], now))

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