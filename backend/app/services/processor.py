"""
Data Processor - 数据清洗与处理服务
核心逻辑：计算多维优惠指标，记录价格历史
"""

import re
import logging
from typing import Optional, List
from datetime import datetime, timedelta

from sqlalchemy.orm import Session
from sqlalchemy import func

from app.scrapers import RawProductData
from app.models import GoldProduct, PriceHistory

logger = logging.getLogger(__name__)

# 克重提取正则表达式
# 支持格式: "约3.5g", "3.5克", "约 2.15 g", "重量2.5克"
WEIGHT_PATTERNS = [
    r"约?\s*(\d+\.?\d*)\s*[gG克]",  # 约3.5g, 3.5克, 约 2.15 g
    r"(\d+\.?\d*)\s*克重",  # 5.8克重
    r"重量[：:\s]*(\d+\.?\d*)\s*[gG克]?",  # 重量：3.5克
    r"(\d+\.?\d*)\s*[gG]\b",  # 单独的 5.8G
]

# 一口价/非计价黄金关键词（用于过滤）
FIXED_PRICE_KEYWORDS = [
    "一口价",
    "定价",
    "固定价",
]

# 非纯金关键词（用于过滤）
NON_PURE_GOLD_KEYWORDS = [
    "18K",
    "18k",
    "白金",
    "铂金",
    "K金",
    "k金",
    "镀金",
    "包金",
    "合金",
]

# 历史价格对比天数
PRICE_HISTORY_DAYS = 30


def extract_weight(title: str) -> Optional[float]:
    """
    从商品标题中提取黄金克重

    Args:
        title: 商品标题

    Returns:
        克重数值，无法提取返回 None

    Examples:
        >>> extract_weight("周大福 足金手链 约3.5g")
        3.5
        >>> extract_weight("周大福 黄金项链 约5.8克")
        5.8
        >>> extract_weight("周大福 一口价黄金吊坠")
        None
    """
    for pattern in WEIGHT_PATTERNS:
        match = re.search(pattern, title)
        if match:
            try:
                weight = float(match.group(1))
                # 合理性校验：黄金饰品克重一般在 0.3g ~ 100g 之间
                if 0.3 <= weight <= 100.0:
                    return weight
            except (ValueError, IndexError):
                continue

    return None


def is_fixed_price_product(title: str) -> bool:
    """
    判断是否为一口价商品

    Args:
        title: 商品标题

    Returns:
        True 表示是一口价商品
    """
    return any(keyword in title for keyword in FIXED_PRICE_KEYWORDS)


def is_non_pure_gold(title: str) -> bool:
    """
    判断是否为非纯金（18K金等）

    Args:
        title: 商品标题

    Returns:
        True 表示是非纯金商品
    """
    return any(keyword in title for keyword in NON_PURE_GOLD_KEYWORDS)


def calculate_price_per_gram(final_price: float, weight_grams: float) -> float:
    """计算单克价"""
    if weight_grams <= 0:
        return 0
    return round(final_price / weight_grams, 2)


def calculate_discount_rate(original_price: float, final_price: float) -> float:
    """
    计算折扣率

    Args:
        original_price: 原价
        final_price: 券后价

    Returns:
        折扣率 (0~1之间)，例如 0.15 表示打了85折/优惠了15%
    """
    if original_price <= 0 or final_price <= 0:
        return 0
    if final_price >= original_price:
        return 0
    return round((original_price - final_price) / original_price, 4)


def calculate_discount_amount(original_price: float, final_price: float) -> float:
    """
    计算降价金额

    Args:
        original_price: 原价
        final_price: 券后价

    Returns:
        降价金额 = 原价 - 券后价
    """
    if original_price <= 0 or final_price <= 0:
        return 0
    diff = original_price - final_price
    return round(max(diff, 0), 2)


def check_is_price_lowest(db: Session, item_id: str, current_price: float) -> bool:
    """
    检查当前价格是否为近 N 天内最低价

    Args:
        db: 数据库会话
        item_id: 商品ID
        current_price: 当前券后价

    Returns:
        True 表示是近期最低价
    """
    # 查找商品
    product = db.query(GoldProduct).filter(GoldProduct.item_id == item_id).first()
    if not product:
        return True  # 新商品默认是最低价

    # 查询近 N 天的历史价格
    cutoff_date = datetime.utcnow() - timedelta(days=PRICE_HISTORY_DAYS)
    historical_min = db.query(func.min(PriceHistory.final_price)).filter(
        PriceHistory.product_id == product.id,
        PriceHistory.recorded_at >= cutoff_date,
    ).scalar()

    if historical_min is None:
        return True  # 没有历史记录，当前价就是最低
    return current_price <= historical_min


def record_price_history(db: Session, product: GoldProduct) -> None:
    """
    记录当前价格到历史表

    Args:
        db: 数据库会话
        product: 商品对象
    """
    history = PriceHistory(
        product_id=product.id,
        final_price=product.final_price,
        original_price=product.original_price,
        coupon_amount=product.coupon_amount,
        recorded_at=datetime.utcnow(),
    )
    db.add(history)


def process_raw_product(raw: RawProductData) -> Optional[dict]:
    """
    处理单个原始商品数据，计算多维优惠指标
    """
    title = raw.title

    # 1. 过滤一口价商品
    if is_fixed_price_product(title):
        logger.debug(f"过滤一口价商品: {title}")
        return None

    # 2. 过滤非纯金商品
    if is_non_pure_gold(title):
        logger.debug(f"过滤非纯金商品: {title}")
        return None

    # 3. 提取克重（允许为空）
    weight = extract_weight(title)

    # 4. 计算单克价（无克重时设为0）
    if weight and weight > 0:
        price_per_gram = calculate_price_per_gram(raw.final_price, weight)
    else:
        weight = 0
        price_per_gram = 0

    # 5. 计算折扣率
    discount_rate = calculate_discount_rate(raw.original_price, raw.final_price)

    # 6. 计算降价金额
    discount_amount = calculate_discount_amount(raw.original_price, raw.final_price)

    # 7. 优惠券金额
    coupon_amount = raw.coupon_amount

    # 8. 月销量
    monthly_sales = raw.monthly_sales

    return {
        "platform": raw.platform,
        "item_id": raw.item_id,
        "title": raw.title,
        "cover_image": raw.cover_image,
        "affiliate_url": raw.affiliate_url,
        "original_price": raw.original_price,
        "final_price": raw.final_price,
        "weight_grams": weight,
        "price_per_gram": price_per_gram,
        "discount_tags": raw.discount_tags,
        "discount_rate": discount_rate,
        "coupon_amount": coupon_amount,
        "discount_amount": discount_amount,
        "monthly_sales": monthly_sales,
        "is_price_lowest": False,  # 先设为 False，后续在 save 时判断
        "update_time": datetime.utcnow(),
    }


def process_and_save_products(raw_products: List[RawProductData], db: Session) -> dict:
    """
    批量处理并保存商品数据

    Args:
        raw_products: 原始商品数据列表
        db: 数据库会话

    Returns:
        处理结果统计
    """
    stats = {
        "total": len(raw_products),
        "processed": 0,
        "filtered": 0,
        "saved": 0,
        "updated": 0,
        "price_lowest": 0,
    }

    for raw in raw_products:
        processed = process_raw_product(raw)

        if processed is None:
            stats["filtered"] += 1
            continue

        stats["processed"] += 1

        # 检查是否为近期最低价
        is_lowest = check_is_price_lowest(db, processed["item_id"], processed["final_price"])
        processed["is_price_lowest"] = is_lowest
        if is_lowest:
            stats["price_lowest"] += 1

        # 查找是否已存在
        existing = (
            db.query(GoldProduct)
            .filter(GoldProduct.item_id == processed["item_id"])
            .first()
        )

        if existing:
            # 更新现有记录
            for key, value in processed.items():
                setattr(existing, key, value)
            stats["updated"] += 1
            # 记录价格历史
            record_price_history(db, existing)
        else:
            # 创建新记录
            product = GoldProduct(**processed)
            db.add(product)
            db.flush()  # 获取 product.id
            stats["saved"] += 1
            # 记录首条价格历史
            record_price_history(db, product)

    db.commit()

    logger.info(
        f"数据处理完成: 总计 {stats['total']}, "
        f"有效 {stats['processed']}, "
        f"过滤 {stats['filtered']}, "
        f"新增 {stats['saved']}, "
        f"更新 {stats['updated']}, "
        f"近期新低 {stats['price_lowest']}"
    )

    return stats