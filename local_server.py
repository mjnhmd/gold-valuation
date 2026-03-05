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
# 好单库 API 配置
# ============================================================
API_KEY = "9945FDC4E9E5"
HAODANKU_TB_URL = "https://v2.api.haodanku.com/supersearch"   # 淘宝超级搜索
HAODANKU_JD_URL = "https://v3.api.haodanku.com/jd_goods_search"  # 京东搜索

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
    platform      = Column(String,  nullable=False, default="TAOBAO")          # 平台: JD, TAOBAO
    title         = Column(String,  nullable=False)                             # 商品标题
    cover_image   = Column(String,  nullable=True)                              # 主图 URL
    affiliate_url = Column(String,  nullable=True)                              # 带推广计费的跳转链接
    original_price = Column(Float,  nullable=False)                             # 原价
    final_price   = Column(Float,   nullable=False)                             # 券后价
    weight_grams  = Column(Float,   nullable=False, default=0)                  # 黄金克重 (克)
    price_per_gram = Column(Float,  nullable=False, default=0)                  # 每克单价 (元/克)
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
# 好单库 API 请求
# ============================================================
def _safe_request(url: str, label: str) -> dict | None:
    """通用安全请求封装，返回 JSON dict 或 None"""
    logger.info(f"📡 请求 {label} — {url[:120]}...")
    try:
        resp = http_requests.get(url, timeout=15)
        resp.raise_for_status()
    except http_requests.exceptions.Timeout:
        logger.error(f"❌ [{label}] 请求超时")
        return None
    except http_requests.exceptions.ConnectionError:
        logger.error(f"❌ [{label}] 网络连接失败")
        return None
    except http_requests.exceptions.HTTPError as e:
        logger.error(f"❌ [{label}] HTTP 错误: {e}")
        return None
    except http_requests.exceptions.RequestException as e:
        logger.error(f"❌ [{label}] 请求异常: {e}")
        return None

    try:
        return resp.json()
    except json.JSONDecodeError:
        logger.error(f"❌ [{label}] 返回非 JSON: {resp.text[:300]}")
        return None


def fetch_items_from_taobao(
    keyword: str = "周大福",
    back: int = 100,
    min_id: int = 1,
    tb_p: int = 1,
) -> list[dict]:
    """调用好单库淘宝超级搜索 API，返回商品列表。"""
    url = (
        f"{HAODANKU_TB_URL}"
        f"/apikey/{API_KEY}"
        f"/keyword/{keyword}"
        f"/back/{back}"
        f"/min_id/{min_id}"
        f"/tb_p/{tb_p}"
    )
    data = _safe_request(url, f"淘宝搜索 page={tb_p}")
    if not data:
        return []

    if data.get("code") != 1:
        logger.warning(f"⚠️ 淘宝API异常 — code={data.get('code')}, msg={data.get('msg', '')}")
        return []

    items = data.get("data", [])
    logger.info(f"✅ 淘宝返回 {len(items)} 条商品")
    return items


def fetch_items_from_jd(
    keyword: str = "周大福黄金",
    min_id: int = 1,
) -> tuple[list[dict], int]:
    """
    调用好单库京东搜索 API，返回 (商品列表, 下一页min_id)。
    京东接口使用 v3 版本，参数风格为 query string。
    """
    url = f"{HAODANKU_JD_URL}?apikey={API_KEY}&keyword={keyword}&min_id={min_id}"
    data = _safe_request(url, f"京东搜索 min_id={min_id}")
    if not data:
        return [], 0

    code = data.get("code")
    if code != 200 and code != 1:
        logger.warning(f"⚠️ 京东API异常 — code={code}, msg={data.get('msg', '')}")
        return [], 0

    items = data.get("data", [])
    next_min_id = data.get("min_id", 0)
    logger.info(f"✅ 京东返回 {len(items)} 条商品, next_min_id={next_min_id}")
    return items, next_min_id


def normalize_jd_item(item: dict) -> dict:
    """
    将京东 API 返回的字段映射为统一的商品格式。

    京东字段映射:
      goodsname   → title        (商品标题)
      skuid       → item_id      (商品唯一ID)
      itempic     → cover_image  (主图)
      itemprice   → original_price(原价)
      itemendprice→ final_price   (券后价)
      couponurl   → affiliate_url (推广链接，京东用 couponurl；若空则构建京东链接)
    """
    title = item.get("goodsname", "")
    item_id = item.get("skuid", "") or item.get("itemid", "")
    if not item_id or not title:
        return {}

    try:
        original_price = float(item.get("itemprice", 0))
        final_price = float(item.get("itemendprice", 0))
    except (ValueError, TypeError):
        return {}
    if final_price <= 0:
        return {}

    # 克重
    weight = extract_weight_from_title(title)
    if weight is None:
        weight = 0
    price_per_gram = round(final_price / weight, 2) if weight > 0 else 0

    # 推广链接：优先 couponurl，否则用 itempic 同域的商品页
    affiliate_url = item.get("couponurl", "")
    if not affiliate_url:
        # 京东 skuid 可能是加密的，无法直接构建商品链接，留空由前端 fallback
        affiliate_url = ""

    cover_image = item.get("itempic", "") or item.get("jd_image", "").split(",")[0] if item.get("jd_image") else ""

    return {
        "item_id":        f"jd_{item_id}",  # 加 jd_ 前缀避免与淘宝 ID 冲突
        "platform":       "JD",
        "title":          title,
        "cover_image":    cover_image,
        "affiliate_url":  affiliate_url,
        "original_price": original_price,
        "final_price":    final_price,
        "weight_grams":   weight,
        "price_per_gram": price_per_gram,
    }


# ============================================================
# 核心：数据拉取 → 清洗 → 入库
# ============================================================
def _process_taobao_items(all_items: list[dict]) -> list[dict]:
    """清洗淘宝商品数据，返回统一格式列表"""
    valid = []
    no_weight = 0
    for item in all_items:
        title   = item.get("itemtitle", "")
        item_id = item.get("itemid", "")
        if not item_id or not title:
            continue

        weight = extract_weight_from_title(title)
        if weight is None:
            no_weight += 1
            weight = 0

        try:
            original_price = float(item.get("itemprice", 0))
            final_price    = float(item.get("itemendprice", 0))
        except (ValueError, TypeError):
            continue
        if final_price <= 0:
            continue

        price_per_gram = round(final_price / weight, 2) if weight > 0 else 0
        affiliate_url = item.get("clickurl", "")

        valid.append({
            "item_id":        str(item_id),
            "platform":       "TAOBAO",
            "title":          title,
            "cover_image":    item.get("itempic", ""),
            "affiliate_url":  affiliate_url,
            "original_price": original_price,
            "final_price":    final_price,
            "weight_grams":   weight,
            "price_per_gram": price_per_gram,
        })

    logger.info(f"  淘宝清洗: 有效 {len(valid)} 条, 无克重 {no_weight} 条")
    return valid


def fetch_and_process_gold_data():
    """
    定时任务核心函数:
      1. 多页拉取好单库「周大福」淘宝 + 京东商品
      2. 正则提取标题中的克重
      3. 计算克价 = final_price / weight_grams
      4. 按 item_id 去重入库：存在则更新，不存在则新增
    """
    logger.info("🚀 ===== 开始数据拉取与清洗 =====")

    valid_products: list[dict] = []

    # ---- 1a. 拉取淘宝数据（多页） ----
    logger.info("📦 [淘宝] 开始拉取...")
    tb_items: list[dict] = []
    for page in range(1, 6):                        # 最多拉 5 页
        items = fetch_items_from_taobao(keyword="周大福", back=100, tb_p=page)
        tb_items.extend(items)
        if len(items) < 100:                         # 不足一页 → 无更多数据
            break
    valid_products.extend(_process_taobao_items(tb_items))

    # ---- 1b. 拉取京东数据（多页） ----
    logger.info("📦 [京东] 开始拉取...")
    jd_min_id = 1
    jd_no_weight = 0
    jd_valid = 0
    for _ in range(5):                               # 最多拉 5 页
        jd_items, next_min_id = fetch_items_from_jd(keyword="周大福黄金", min_id=jd_min_id)
        for item in jd_items:
            normalized = normalize_jd_item(item)
            if normalized:
                if normalized["weight_grams"] == 0:
                    jd_no_weight += 1
                valid_products.append(normalized)
                jd_valid += 1
        if not jd_items or not next_min_id or next_min_id <= jd_min_id:
            break
        jd_min_id = next_min_id
    logger.info(f"  京东清洗: 有效 {jd_valid} 条, 无克重 {jd_no_weight} 条")

    if not valid_products:
        logger.warning("📭 未获取到任何商品，任务结束")
        return

    logger.info(f"📊 清洗完成 — 共 {len(valid_products)} 条 (淘宝+京东)")

    # ---- 4. 入库（upsert） ----
    db = SessionLocal()
    inserted, updated = 0, 0
    try:
        for prod in valid_products:
            existing = db.query(Product).filter(Product.item_id == prod["item_id"]).first()
            now = datetime.now()

            if existing:
                existing.platform       = prod["platform"]
                existing.title          = prod["title"]
                existing.cover_image    = prod["cover_image"]
                existing.affiliate_url  = prod["affiliate_url"]
                existing.original_price = prod["original_price"]
                existing.final_price    = prod["final_price"]
                existing.weight_grams   = prod["weight_grams"]
                existing.price_per_gram = prod["price_per_gram"]
                existing.update_time    = now
                updated += 1
            else:
                db.add(Product(
                    item_id        = prod["item_id"],
                    platform       = prod["platform"],
                    title          = prod["title"],
                    cover_image    = prod["cover_image"],
                    affiliate_url  = prod["affiliate_url"],
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
@app.get("/api/products", summary="获取商品列表")
def get_products(
    limit: int = Query(default=50, ge=1, le=500, description="返回数量，默认 50"),
    platform: Optional[str] = Query(default=None, description="平台筛选: JD / TAOBAO，为空返回全部"),
    sort_by: str = Query(default="price_per_gram", description="排序字段: price_per_gram / final_price / weight_grams / update_time"),
    sort_order: str = Query(default="asc", description="排序方向: asc / desc"),
    db: Session = Depends(get_db),
):
    """
    返回黄金商品列表，支持按平台筛选、多字段排序。
    """
    query = db.query(Product)

    # 平台筛选
    if platform:
        query = query.filter(Product.platform == platform)

    # 排序
    sort_column_map = {
        "price_per_gram": Product.price_per_gram,
        "final_price":    Product.final_price,
        "weight_grams":   Product.weight_grams,
        "update_time":    Product.update_time,
    }
    sort_col = sort_column_map.get(sort_by, Product.price_per_gram)
    if sort_order == "desc":
        query = query.order_by(sort_col.desc())
    else:
        query = query.order_by(sort_col.asc())

    products = query.limit(limit).all()
    return {
        "total": len(products),
        "products": [
            {
                "id":             p.id,
                "item_id":        p.item_id,
                "platform":       p.platform or "TAOBAO",
                "title":          p.title,
                "cover_image":    p.cover_image,
                "affiliate_url":  p.affiliate_url,
                "original_price": p.original_price,
                "final_price":    p.final_price,
                "weight_grams":   p.weight_grams,
                "price_per_gram": p.price_per_gram,
                "discount_tags":  "[]",
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