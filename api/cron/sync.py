"""
GET /api/cron/sync — Vercel Cron Job 定时同步数据
每天 08:00 / 12:00 / 20:00 (UTC 00:00 / 04:00 / 12:00) 自动调用
也可手动触发
"""
from http.server import BaseHTTPRequestHandler
import json
import os
import sys
from datetime import datetime

# 将 api/ 目录加入 sys.path，以便导入 _db 和 _fetch
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from _db import get_conn, init_db
from _fetch import fetch_all


def upsert_products(products: list[dict]) -> dict:
    """批量 upsert 商品到数据库"""
    conn = get_conn()
    cur = conn.cursor()
    inserted, updated = 0, 0
    now = datetime.utcnow()

    for p in products:
        cur.execute("SELECT id FROM products WHERE item_id = %s", (p["item_id"],))
        existing = cur.fetchone()

        if existing:
            cur.execute("""
                UPDATE products SET
                    platform=%s, title=%s, cover_image=%s, affiliate_url=%s,
                    original_price=%s, final_price=%s, weight_grams=%s,
                    price_per_gram=%s, update_time=%s
                WHERE item_id=%s
            """, (
                p["platform"], p["title"], p["cover_image"], p["affiliate_url"],
                p["original_price"], p["final_price"], p["weight_grams"],
                p["price_per_gram"], now, p["item_id"],
            ))
            updated += 1
        else:
            cur.execute("""
                INSERT INTO products
                    (item_id, platform, title, cover_image, affiliate_url,
                     original_price, final_price, weight_grams, price_per_gram, update_time)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            """, (
                p["item_id"], p["platform"], p["title"], p["cover_image"],
                p["affiliate_url"], p["original_price"], p["final_price"],
                p["weight_grams"], p["price_per_gram"], now,
            ))
            inserted += 1

    conn.commit()
    cur.close()
    conn.close()
    return {"inserted": inserted, "updated": updated}


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        try:
            # 验证 Cron 密钥（可选，防止外部调用）
            cron_secret = os.environ.get("CRON_SECRET")
            if cron_secret:
                auth = self.headers.get("Authorization")
                if auth != f"Bearer {cron_secret}":
                    self.send_response(401)
                    self.send_header("Content-Type", "application/json")
                    self.end_headers()
                    self.wfile.write(b'{"error":"Unauthorized"}')
                    return

            init_db()

            # 拉取全部数据
            products = fetch_all()
            if not products:
                body = json.dumps({"status": "warning", "message": "未获取到商品数据"})
                self.send_response(200)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.end_headers()
                self.wfile.write(body.encode("utf-8"))
                return

            # 入库
            result = upsert_products(products)

            body = json.dumps({
                "status": "success",
                "total_fetched": len(products),
                "inserted": result["inserted"],
                "updated": result["updated"],
                "time": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC"),
            }, ensure_ascii=False)

            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()
            self.wfile.write(body.encode("utf-8"))

        except Exception as e:
            body = json.dumps({"error": str(e)}, ensure_ascii=False)
            self.send_response(500)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()
            self.wfile.write(body.encode("utf-8"))