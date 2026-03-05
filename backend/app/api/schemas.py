"""
API Schemas - Pydantic 数据验证模型
"""
from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field


class ProductResponse(BaseModel):
    """商品响应模型"""
    id: int
    platform: str
    item_id: str
    title: str
    cover_image: Optional[str] = None
    affiliate_url: Optional[str] = None
    original_price: Optional[float] = None
    final_price: float
    weight_grams: float
    price_per_gram: float
    discount_tags: Optional[str] = None
    update_time: Optional[datetime] = None

    class Config:
        from_attributes = True


class ProductListResponse(BaseModel):
    """商品列表响应"""
    total: int
    products: List[ProductResponse]


class StatsResponse(BaseModel):
    """统计信息响应"""
    total_products: int = Field(..., description="收录商品总数")
    today_products: int = Field(..., description="今日更新商品数")
    lowest_price_per_gram: Optional[float] = Field(None, description="最低克价")
    lowest_price_product: Optional[ProductResponse] = Field(None, description="最低克价商品")
    last_update_time: Optional[datetime] = Field(None, description="最后更新时间")


class SyncResponse(BaseModel):
    """同步任务响应"""
    success: bool
    message: str
    stats: Optional[dict] = None
