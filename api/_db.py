"""
数据库连接模块
Vercel 部署时使用 POSTGRES_URL 环境变量连接 Vercel Postgres
"""
import os
import psycopg2
from psycopg2.extras import RealDictCursor

def get_conn():
    """获取 PostgreSQL 连接"""
    url = os.environ.get("POSTGRES_URL")
    if not url:
        raise RuntimeError("POSTGRES_URL 环境变量未设置")
    return psycopg2.connect(url, cursor_factory=RealDictCursor)


def init_db():
    """建表（如果不存在）"""
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS products (
            id              SERIAL PRIMARY KEY,
            item_id         VARCHAR(128) UNIQUE NOT NULL,
            platform        VARCHAR(16) NOT NULL DEFAULT 'TAOBAO',
            title           TEXT NOT NULL,
            cover_image     TEXT,
            affiliate_url   TEXT,
            original_price  DOUBLE PRECISION NOT NULL DEFAULT 0,
            final_price     DOUBLE PRECISION NOT NULL DEFAULT 0,
            weight_grams    DOUBLE PRECISION NOT NULL DEFAULT 0,
            price_per_gram  DOUBLE PRECISION NOT NULL DEFAULT 0,
            update_time     TIMESTAMP DEFAULT NOW()
        );
        CREATE INDEX IF NOT EXISTS idx_products_item_id ON products (item_id);
        CREATE INDEX IF NOT EXISTS idx_products_platform ON products (platform);
        CREATE INDEX IF NOT EXISTS idx_products_ppg ON products (price_per_gram);
    """)
    conn.commit()
    cur.close()
    conn.close()
