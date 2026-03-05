"""
GET /api/products — 获取商品列表
支持 platform / sort_by / sort_order / limit 参数
"""
from http.server import BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
import json
from _db import get_conn, init_db


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        try:
            init_db()

            # 解析查询参数
            qs = parse_qs(urlparse(self.path).query)
            limit = min(int(qs.get("limit", ["50"])[0]), 500)
            platform = qs.get("platform", [None])[0]
            sort_by = qs.get("sort_by", ["price_per_gram"])[0]
            sort_order = qs.get("sort_order", ["asc"])[0]

            # 构建 SQL
            allowed_sort = {
                "price_per_gram": "price_per_gram",
                "final_price": "final_price",
                "weight_grams": "weight_grams",
                "update_time": "update_time",
            }
            sort_col = allowed_sort.get(sort_by, "price_per_gram")
            direction = "DESC" if sort_order == "desc" else "ASC"

            sql = "SELECT * FROM products"
            params = []
            if platform:
                sql += " WHERE platform = %s"
                params.append(platform)
            sql += f" ORDER BY {sort_col} {direction} LIMIT %s"
            params.append(limit)

            conn = get_conn()
            cur = conn.cursor()
            cur.execute(sql, params)
            rows = cur.fetchall()
            cur.close()
            conn.close()

            products = []
            for r in rows:
                products.append({
                    "id": r["id"],
                    "item_id": r["item_id"],
                    "platform": r["platform"] or "TAOBAO",
                    "title": r["title"],
                    "cover_image": r["cover_image"],
                    "affiliate_url": r["affiliate_url"],
                    "original_price": r["original_price"],
                    "final_price": r["final_price"],
                    "weight_grams": r["weight_grams"],
                    "price_per_gram": r["price_per_gram"],
                    "discount_tags": "[]",
                    "update_time": r["update_time"].strftime("%Y-%m-%d %H:%M:%S") if r["update_time"] else None,
                })

            body = json.dumps({"total": len(products), "products": products}, ensure_ascii=False)
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(body.encode("utf-8"))

        except Exception as e:
            body = json.dumps({"error": str(e)}, ensure_ascii=False)
            self.send_response(500)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()
            self.wfile.write(body.encode("utf-8"))
