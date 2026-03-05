"""
GET /api/products — 获取商品列表
支持 platform / sort_by / sort_order / limit / only_lowest 参数
"""
import json
import os
import sys
from http.server import BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

# ── 确保能导入同目录下的 _db 模块 ──
_API_DIR = os.path.dirname(os.path.abspath(__file__))
if _API_DIR not in sys.path:
    sys.path.insert(0, _API_DIR)

from _db import get_conn, init_db


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        try:
            init_db()

            # 解析查询参数
            qs = parse_qs(urlparse(self.path).query)
            limit = min(int(qs.get("limit", ["50"])[0]), 500)
            platform = qs.get("platform", [None])[0]
            sort_by = qs.get("sort_by", ["discount_rate"])[0]
            sort_order = qs.get("sort_order", ["desc"])[0]
            only_lowest = qs.get("only_lowest", ["false"])[0].lower() == "true"

            # 构建 SQL - 支持多维度排序
            allowed_sort = {
                "price_per_gram": "price_per_gram",
                "final_price": "final_price",
                "weight_grams": "weight_grams",
                "update_time": "update_time",
                "discount_rate": "discount_rate",
                "coupon_amount": "coupon_amount",
                "discount_amount": "discount_amount",
                "monthly_sales": "monthly_sales",
            }
            sort_col = allowed_sort.get(sort_by, "discount_rate")
            direction = "DESC" if sort_order == "desc" else "ASC"

            conditions = []
            params = []

            if platform:
                conditions.append("platform = %s")
                params.append(platform)

            if only_lowest:
                conditions.append("is_price_lowest = TRUE")

            sql = "SELECT * FROM products"
            if conditions:
                sql += " WHERE " + " AND ".join(conditions)
            sql += f" ORDER BY {sort_col} {direction} LIMIT %s"
            params.append(limit)

            conn = get_conn()
            cur = conn.cursor()
            cur.execute(sql, params)
            rows = cur.fetchall()

            # 获取总数
            count_sql = "SELECT COUNT(*) AS cnt FROM products"
            if conditions:
                count_sql += " WHERE " + " AND ".join(conditions)
            cur.execute(count_sql, params[:-1])  # 去掉 limit 参数
            total = cur.fetchone()["cnt"]

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
                    "discount_rate": r.get("discount_rate", 0) or 0,
                    "coupon_amount": r.get("coupon_amount", 0) or 0,
                    "discount_amount": r.get("discount_amount", 0) or 0,
                    "monthly_sales": r.get("monthly_sales", 0) or 0,
                    "is_price_lowest": r.get("is_price_lowest", False) or False,
                    "discount_tags": "[]",
                    "update_time": r["update_time"].strftime("%Y-%m-%d %H:%M:%S") if r["update_time"] else None,
                })

            body = json.dumps({"total": total, "products": products}, ensure_ascii=False)
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
