"""
API Routes - RESTful 接口定义
"""
from datetime import datetime, timedelta
from typing import Optional, Literal

from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func, desc, asc

from app.models import get_db, GoldProduct
from app.api.schemas import (
    ProductResponse,
    ProductListResponse,
    StatsResponse,
    SyncResponse,
)
from app.scrapers import JDScraper, TaobaoScraper
from app.services import process_and_save_products

router = APIRouter(prefix="/api", tags=["products"])


@router.get("/products", response_model=ProductListResponse)
async def get_products(
    platform: Optional[Literal["JD", "TAOBAO"]] = Query(
        None, description="平台筛选: JD 或 TAOBAO"
    ),
    sort_by: Literal[
        "price_per_gram", "final_price", "weight_grams", "update_time",
        "discount_rate", "coupon_amount", "discount_amount", "monthly_sales"
    ] = Query(
        "discount_rate", description="排序字段"
    ),
    sort_order: Literal["asc", "desc"] = Query(
        "desc", description="排序方向"
    ),
    only_lowest: bool = Query(False, description="仅显示近期最低价商品"),
    limit: int = Query(50, ge=1, le=200, description="返回数量限制"),
    offset: int = Query(0, ge=0, description="偏移量"),
    db: Session = Depends(get_db),
):
    """
    获取商品列表

    - **platform**: 可选，筛选平台 (JD/TAOBAO)
    - **sort_by**: 排序字段，默认按折扣率降序
    - **sort_order**: 排序方向 (asc/desc)
    - **only_lowest**: 仅显示近期最低价商品
    - **limit**: 返回数量，默认 50，最大 200
    - **offset**: 分页偏移量
    """
    query = db.query(GoldProduct)

    # 平台筛选
    if platform:
        query = query.filter(GoldProduct.platform == platform)

    # 仅显示近期最低价
    if only_lowest:
        query = query.filter(GoldProduct.is_price_lowest == True)

    # 获取总数
    total = query.count()

    # 排序
    sort_column = getattr(GoldProduct, sort_by)
    if sort_order == "desc":
        query = query.order_by(desc(sort_column))
    else:
        query = query.order_by(asc(sort_column))

    # 分页
    products = query.offset(offset).limit(limit).all()

    return ProductListResponse(
        total=total,
        products=[ProductResponse.model_validate(p) for p in products]
    )


@router.get("/stats", response_model=StatsResponse)
async def get_stats(db: Session = Depends(get_db)):
    """
    获取全站统计信息

    返回：
    - 收录商品总数
    - 今日更新商品数
    - 最低克价及对应商品
    - 最高折扣率及对应商品
    - 最大优惠券金额
    - 近期新低商品数
    - 最后更新时间
    """
    # 总商品数
    total_products = db.query(GoldProduct).count()

    # 今日更新数（UTC 今天）
    today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    today_products = db.query(GoldProduct).filter(
        GoldProduct.update_time >= today_start
    ).count()

    # 最低克价商品 (排除克价为0的)
    lowest_product = db.query(GoldProduct).filter(
        GoldProduct.price_per_gram > 0
    ).order_by(
        asc(GoldProduct.price_per_gram)
    ).first()

    # 最高折扣率商品
    best_discount_product = db.query(GoldProduct).filter(
        GoldProduct.discount_rate > 0
    ).order_by(
        desc(GoldProduct.discount_rate)
    ).first()

    # 最大优惠券金额
    max_coupon = db.query(func.max(GoldProduct.coupon_amount)).scalar() or 0

    # 近期新低商品数
    price_lowest_count = db.query(GoldProduct).filter(
        GoldProduct.is_price_lowest == True
    ).count()

    # 最后更新时间
    last_update = db.query(func.max(GoldProduct.update_time)).scalar()

    return StatsResponse(
        total_products=total_products,
        today_products=today_products,
        lowest_price_per_gram=lowest_product.price_per_gram if lowest_product else None,
        lowest_price_product=ProductResponse.model_validate(lowest_product) if lowest_product else None,
        best_discount_rate=best_discount_product.discount_rate if best_discount_product else None,
        best_discount_product=ProductResponse.model_validate(best_discount_product) if best_discount_product else None,
        max_coupon_amount=max_coupon,
        price_lowest_count=price_lowest_count,
        last_update_time=last_update,
    )


@router.post("/sync", response_model=SyncResponse)
async def sync_products(db: Session = Depends(get_db)):
    """
    手动触发数据同步

    从京东和淘宝抓取最新数据并处理入库
    """
    try:
        all_stats = {"total": 0, "processed": 0, "filtered": 0, "saved": 0, "updated": 0, "price_lowest": 0}

        # 京东数据
        jd_scraper = JDScraper()
        jd_products = await jd_scraper.fetch_products()
        jd_stats = process_and_save_products(jd_products, db)

        # 淘宝数据
        tb_scraper = TaobaoScraper()
        tb_products = await tb_scraper.fetch_products()
        tb_stats = process_and_save_products(tb_products, db)

        # 合并统计
        for key in all_stats:
            all_stats[key] = jd_stats.get(key, 0) + tb_stats.get(key, 0)

        return SyncResponse(
            success=True,
            message=f"同步完成: 新增 {all_stats['saved']} 条, 更新 {all_stats['updated']} 条, 近期新低 {all_stats['price_lowest']} 条",
            stats=all_stats,
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"同步失败: {str(e)}")


@router.get("/products/{item_id}", response_model=ProductResponse)
async def get_product_detail(item_id: str, db: Session = Depends(get_db)):
    """
    获取单个商品详情

    - **item_id**: 商品唯一 ID
    """
    product = db.query(GoldProduct).filter(
        GoldProduct.item_id == item_id
    ).first()

    if not product:
        raise HTTPException(status_code=404, detail="商品不存在")

    return ProductResponse.model_validate(product)
