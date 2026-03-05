"""
GET /api/stats — 统计概览
"""
import json
import os
import sys
from http.server import BaseHTTPRequestHandler

# ── 确保能导入同目录下的 _db 模块 ──
_API_DIR = os.path.dirname(os.path.abspath(__file__))
if _API_DIR not in sys.path:
    sys.path.insert(0, _API_DIR)

from _db import get_conn, init_db


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        try:
            init_db()
            conn = get_conn()
            cur = conn.cursor()
            cur.execute("""
                SELECT
                    COUNT(*) AS total,
                    MIN(price_per_gram) FILTER (WHERE price_per_gram > 0) AS min_ppg,
                    MAX(price_per_gram) AS max_ppg,
                    AVG(price_per_gram) FILTER (WHERE price_per_gram > 0) AS avg_ppg,
                    MAX(update_time) AS last_update
                FROM products
            """)
            r = cur.fetchone()
            cur.close()
            conn.close()

            body = json.dumps({
                "total_products": r["total"] or 0,
                "lowest_price_per_gram": round(r["min_ppg"], 2) if r["min_ppg"] else 0,
                "highest_price_per_gram": round(r["max_ppg"], 2) if r["max_ppg"] else 0,
                "avg_price_per_gram": round(r["avg_ppg"], 2) if r["avg_ppg"] else 0,
                "last_update_time": r["last_update"].strftime("%Y-%m-%d %H:%M:%S") if r["last_update"] else None,
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
