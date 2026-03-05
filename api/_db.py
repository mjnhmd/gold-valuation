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


def _add_column_if_not_exists(cur, col_name: str, col_type: str):
    """安全地给 products 表加列（如果不存在）"""
    cur.execute(
        """SELECT 1 FROM information_schema.columns WHERE table_name='products' AND column_name=%s""",
        (col_name,)
    )
    if not cur.fetchone():
        # col_name 和 col_type 都是我们硬编码的常量，安全
        cur.execute(f"ALTER TABLE products ADD COLUMN {col_name} {col_type}")


def init_db():
    """建表（如果不存在）+ 增量加列"""
    conn = get_conn()
    cur = conn.cursor()

    # ── 主表（仅新建时包含全部列）──
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
            discount_rate   DOUBLE PRECISION NOT NULL DEFAULT 0,
            coupon_amount   DOUBLE PRECISION NOT NULL DEFAULT 0,
            discount_amount DOUBLE PRECISION NOT NULL DEFAULT 0,
            monthly_sales   INTEGER NOT NULL DEFAULT 0,
            is_price_lowest BOOLEAN NOT NULL DEFAULT FALSE,
            update_time     TIMESTAMP DEFAULT NOW()
        );
    """)

    # ── 旧索引 ──
    cur.execute("""
        CREATE INDEX IF NOT EXISTS idx_products_item_id ON products (item_id);
        CREATE INDEX IF NOT EXISTS idx_products_platform ON products (platform);
        CREATE INDEX IF NOT EXISTS idx_products_ppg ON products (price_per_gram);
    """)

    # ── 增量加列（兼容已有表）──
    _add_column_if_not_exists(cur, "discount_rate",   "DOUBLE PRECISION NOT NULL DEFAULT 0")
    _add_column_if_not_exists(cur, "coupon_amount",   "DOUBLE PRECISION NOT NULL DEFAULT 0")
    _add_column_if_not_exists(cur, "discount_amount", "DOUBLE PRECISION NOT NULL DEFAULT 0")
    _add_column_if_not_exists(cur, "monthly_sales",   "INTEGER NOT NULL DEFAULT 0")
    _add_column_if_not_exists(cur, "is_price_lowest", "BOOLEAN NOT NULL DEFAULT FALSE")
    conn.commit()

    # ── 新列索引（列已确保存在后再建）──
    cur.execute("""
        CREATE INDEX IF NOT EXISTS idx_products_discount_rate ON products (discount_rate);
        CREATE INDEX IF NOT EXISTS idx_products_coupon ON products (coupon_amount);
        CREATE INDEX IF NOT EXISTS idx_products_discount_amt ON products (discount_amount);
        CREATE INDEX IF NOT EXISTS idx_products_sales ON products (monthly_sales);
    """)

    # ── 价格历史表 ──
    cur.execute("""
        CREATE TABLE IF NOT EXISTS price_history (
            id              SERIAL PRIMARY KEY,
            product_id      INTEGER NOT NULL REFERENCES products(id) ON DELETE CASCADE,
            final_price     DOUBLE PRECISION NOT NULL,
            original_price  DOUBLE PRECISION DEFAULT 0,
            coupon_amount   DOUBLE PRECISION DEFAULT 0,
            recorded_at     TIMESTAMP DEFAULT NOW()
        );
        CREATE INDEX IF NOT EXISTS idx_ph_product_id ON price_history (product_id);
        CREATE INDEX IF NOT EXISTS idx_ph_recorded_at ON price_history (recorded_at);
    """)

    conn.commit()
    cur.close()
    conn.close()