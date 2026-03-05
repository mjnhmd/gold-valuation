"""
黄金商品克价监控后端服务
技术栈: FastAPI + SQLAlchemy (SQLite) + APScheduler
功能: 定时拉取好单库周大福黄金数据 → 正则提取克重 → 计算克价 → 入库 → API 查询
"""

import re
import json
import logging
from datetime import datetime
from contextlib import asynccontextmanager
from typing import Optional

import requests as http_requests  # 避免与 FastAPI 的 Request 冲突
from fastapi import FastAPI, Query, Depends
from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, event
from sqlalchemy.orm import declarative_base, sessionmaker, Session
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

# ============================================================
# 日志配置
# ============================================================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

# ============================================================
# 好单库 API 配置（复用 haodanku_search.py 中的参数）
# ============================================================
API_KEY = "9945FDC4E9E5"
HAODANKU_BASE_URL = "https://v2.api.haodanku.com/supersearch"

# 克价上限阈值：超过此值视为一口价商品，不入库
MAX_PRICE_PER_GRAM = 1000.0

# ============================================================
# 数据库配置
# ============================================================
DATABASE_URL = "sqlite:///./gold_products.db"

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})


@event.listens_for(engine, "connect")
def _set_sqlite_pragma(dbapi_conn, connection_record):
    """启用 SQLite WAL 模式，提升并发读写性能"""
    cursor = dbapi_conn.cursor()
    cursor.execute("PRAGMA journal_mode=WAL;")
    cursor.close()


SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


# ============================================================
# 数据库模型
# ============================================================
class Product(Base):
    __tablename__ = "products"

    id            = Column(Integer, primary_key=True, index=True, autoincrement=True)
    item_id       = Column(String,  unique=True, nullable=False, index=True)   # 商品ID（唯一）
    title         = Column(String,  nullable=False)                             # 商品标题
    cover_image   = Column(String,  nullable=True)                              # 主图 URL
    original_price = Column(Float,  nullable=False)                             # 原价
    final_price   = Column(Float,   nullable=False)                             # 券后价
    weight_grams  = Column(Float,   nullable=False)                             # 黄金克重 (克)
    price_per_gram = Column(Float,  nullable=False)                             # 每克单价 (元/克)
    update_time   = Column(DateTime, default=datetime.now)                      # 最后更新时间


# 建表
Base.metadata.create_all(bind=engine)


# ============================================================
# FastAPI 数据库会话依赖
# ============================================================
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ============================================================
# 工具函数：从标题中正则提取克重
# ============================================================
def extract_weight_from_title(title: str) -> Optional[float]:
    """
    从商品标题中提取黄金克重。

    匹配示例:
        "约2.5g"  →  2.5
        "约3.15克" →  3.15
        "2g"      →  2.0
        "0.8克"   →  0.8
        "约 1.2 克" → 1.2

    正则说明:
        约?\\s*        → 可选的「约」字 + 可选空格
        (\\d+\\.?\\d*) → 数字（整数或小数）
        \\s*           → 可选空格
        [gG克]         → 单位: g / G / 克
    """
    pattern = r"约?\s*(\d+\.?\d*)\s*[gG克]"
    match = re.search(pattern, title)
    if match:
        weight = float(match.group(1))
        if 0.1 <= weight <= 500:   # 过滤不合理值
            return weight
    return None


# ============================================================
# 好单库 API 请求（复用 haodanku_search.py 的逻辑）
# ============================================================
def fetch_items_from_haodanku(
    keyword: str = "周大福",
    back: int = 100,
    min_id: int = 1,
    tb_p: int = 1,
) -> list[dict]:
    """
    调用好单库超级搜索 API，返回商品列表。
    接口逻辑完全复用 haodanku_search.py 中的 search_gold_items()。
    """
    url = (
        f"{HAODANKU_BASE_URL}"
        f"/apikey/{API_KEY}"
        f"/keyword/{keyword}"
        f"/back/{back}"
        f"/min_id/{min_id}"
        f"/tb_p/{tb_p}"
    )
    logger.info(f"📡 请求好单库 API — keyword={keyword}, back={back}, tb_p={tb_p}")

    try:
        resp = http_requests.get(url, timeout=15)
        resp.raise_for_status()
    except http_requests.exceptions.Timeout:
        logger.error("❌ 请求超时")
        return []
    except http_requests.exceptions.ConnectionError:
        logger.error("❌ 网络连接失败")
        return []
    except http_requests.exceptions.HTTPError as e:
        logger.error(f"❌ HTTP 错误: {e}")
        return []
    except http_requests.exceptions.RequestException as e:
        logger.error(f"❌ 请求异常: {e}")
        return []

    try:
        data = resp.json()
    except json.JSONDecodeError:
        logger.error(f"❌ 返回非 JSON: {resp.text[:300]}")
        return []

    if data.get("code") != 1:
        logger.warning(f"⚠️ API 异常 — code={data.get('code')}, msg={data.get('msg', '')}")
        return []

    items = data.get("data", [])
    logger.info(f"✅ 返回 {len(items)} 条商品")
    return items


# ============================================================
# 核心：数据拉取 → 清洗 → 入库
# ============================================================
def fetch_and_process_gold_data():
    """
    定时任务核心函数:
      1. 多页拉取好单库「周大福」商品
      2. 正则提取标题中的克重
      3. 计算克价 = final_price / weight_grams
      4. 过滤：无克重 → 丢弃；克价 > 1000 → 丢弃（一口价）
      5. 按 item_id 去重入库：存在则更新，不存在则新增
    """
    logger.info("🚀 ===== 开始数据拉取与清洗 =====")

    # ---- 1. 多页拉取 ----
    all_items: list[dict] = []
    for page in range(1, 6):                       # 最多拉 5 页
        items = fetch_items_from_haodanku(keyword="周大福", back=100, tb_p=page)
        all_items.extend(items)
        if len(items) < 100:                        # 不足一页 → 无更多数据
            break

    if not all_items:
        logger.warning("📭 未获取到任何商品，任务结束")
        return

    # ---- 2 & 3. 清洗 + 过滤 ----
    valid_products: list[dict] = []
    skip_no_weight = 0
    skip_high_price = 0

    for item in all_items:
        title   = item.get("itemtitle", "")
        item_id = item.get("itemid", "")
        if not item_id or not title:
            continue

        # 提取克重
        weight = extract_weight_from_title(title)
        if weight is None:
            skip_no_weight += 1
            continue

        # 解析价格
        try:
            original_price = float(item.get("itemprice", 0))
            final_price    = float(item.get("itemendprice", 0))
        except (ValueError, TypeError):
            continue
        if final_price <= 0:
            continue

        # 计算克价（无论计价黄金还是一口价，统一用 总价 / 克重）
        price_per_gram = round(final_price / weight, 2)

        # 过滤一口价（克价 > 1000 元/克 → 不入库）
        if price_per_gram > MAX_PRICE_PER_GRAM:
            skip_high_price += 1
            continue

        valid_products.append({
            "item_id":        str(item_id),
            "title":          title,
            "cover_image":    item.get("itempic", ""),
            "original_price": original_price,
            "final_price":    final_price,
            "weight_grams":   weight,
            "price_per_gram": price_per_gram,
        })

    logger.info(
        f"📊 清洗完成 — 有效 {len(valid_products)} 条 | "
        f"无克重跳过 {skip_no_weight} 条 | 克价过高跳过 {skip_high_price} 条"
    )

    # ---- 4. 入库（upsert） ----
    db = SessionLocal()
    inserted, updated = 0, 0
    try:
        for prod in valid_products:
            existing = db.query(Product).filter(Product.item_id == prod["item_id"]).first()
            now = datetime.now()

            if existing:
                existing.title          = prod["title"]
                existing.cover_image    = prod["cover_image"]
                existing.original_price = prod["original_price"]
                existing.final_price    = prod["final_price"]
                existing.weight_grams   = prod["weight_grams"]
                existing.price_per_gram = prod["price_per_gram"]
                existing.update_time    = now
                updated += 1
            else:
                db.add(Product(
                    item_id        = prod["item_id"],
                    title          = prod["title"],
                    cover_image    = prod["cover_image"],
                    original_price = prod["original_price"],
                    final_price    = prod["final_price"],
                    weight_grams   = prod["weight_grams"],
                    price_per_gram = prod["price_per_gram"],
                    update_time    = now,
                ))
                inserted += 1

        db.commit()
        logger.info(f"💾 入库完成 — 新增 {inserted} 条, 更新 {updated} 条")
    except Exception as e:
        db.rollback()
        logger.error(f"❌ 数据库写入失败: {e}")
    finally:
        db.close()

    logger.info("🏁 ===== 数据拉取与清洗任务结束 =====\n")


# ============================================================
# 定时调度器
# ============================================================
scheduler = BackgroundScheduler()


def setup_scheduler():
    """每天 08:00 / 12:00 / 20:00 各执行一次数据拉取"""
    scheduler.add_job(
        func=fetch_and_process_gold_data,
        trigger=CronTrigger(hour="8,12,20", minute=0),
        id="fetch_gold_data",
        name="定时拉取好单库黄金数据",
        replace_existing=True,
    )
    scheduler.start()
    logger.info("⏰ 调度器已启动 — 每天 08:00 / 12:00 / 20:00 执行")


# ============================================================
# FastAPI 应用
# ============================================================
@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期：启动时拉取一次数据 + 启动调度器，关闭时停止调度器"""
    setup_scheduler()
    logger.info("🔄 首次启动，立即执行一次数据拉取...")
    fetch_and_process_gold_data()
    yield
    scheduler.shutdown(wait=False)
    logger.info("🛑 调度器已关闭")


app = FastAPI(
    title="黄金克价监控 API",
    description="定时拉取好单库周大福黄金数据，提取克重计算克价，提供按克价排序查询",
    version="1.0.0",
    lifespan=lifespan,
)


# ============================================================
# API 接口
# ============================================================
@app.get("/api/products", summary="获取商品列表（按克价升序）")
def get_products(
    limit: int = Query(default=50, ge=1, le=500, description="返回数量，默认 50"),
    db: Session = Depends(get_db),
):
    """
    返回数据库中所有黄金商品，按 price_per_gram 从低到高排序。
    """
    products = (
        db.query(Product)
        .order_by(Product.price_per_gram.asc())
        .limit(limit)
        .all()
    )
    return {
        "total": len(products),
        "data": [
            {
                "id":             p.id,
                "item_id":        p.item_id,
                "title":          p.title,
                "cover_image":    p.cover_image,
                "original_price": p.original_price,
                "final_price":    p.final_price,
                "weight_grams":   p.weight_grams,
                "price_per_gram": p.price_per_gram,
                "update_time":    p.update_time.strftime("%Y-%m-%d %H:%M:%S") if p.update_time else None,
            }
            for p in products
        ],
    }


@app.get("/api/products/stats", summary="统计概览")
def get_stats(db: Session = Depends(get_db)):
    """返回总数、最低/最高/平均克价"""
    from sqlalchemy import func

    row = db.query(
        func.count(Product.id).label("total"),
        func.min(Product.price_per_gram).label("min_ppg"),
        func.max(Product.price_per_gram).label("max_ppg"),
        func.avg(Product.price_per_gram).label("avg_ppg"),
    ).first()

    return {
        "total_products":    row.total or 0,
        "min_price_per_gram": round(row.min_ppg, 2) if row.min_ppg else 0,
        "max_price_per_gram": round(row.max_ppg, 2) if row.max_ppg else 0,
        "avg_price_per_gram": round(row.avg_ppg, 2) if row.avg_ppg else 0,
    }


@app.post("/api/products/refresh", summary="手动触发数据刷新")
def refresh_data():
    """立即执行一次数据拉取与清洗"""
    try:
        fetch_and_process_gold_data()
        return {"status": "success", "message": "数据刷新完成"}
    except Exception as e:
        return {"status": "error", "message": str(e)}


# ============================================================
# 启动入口
# ============================================================
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)