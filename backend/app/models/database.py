"""
SQLAlchemy Database Models
黄金商品数据库模型定义
"""
from datetime import datetime
from typing import Optional

from sqlalchemy import Column, Integer, String, Float, DateTime, create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker


class Base(DeclarativeBase):
    """SQLAlchemy 声明式基类"""
    pass


class GoldProduct(Base):
    """
    黄金商品表
    存储从京东/淘宝抓取的黄金饰品优惠信息
    """
    __tablename__ = "gold_products"

    id = Column(Integer, primary_key=True, autoincrement=True)
    platform = Column(String(20), nullable=False, index=True, comment="平台: JD, TAOBAO")
    item_id = Column(String(100), nullable=False, unique=True, comment="平台商品唯一ID")
    title = Column(String(255), nullable=False, comment="商品标题")
    cover_image = Column(String(500), comment="商品主图 URL")
    affiliate_url = Column(String(1000), comment="带推广计费的跳转链接")
    original_price = Column(Float, comment="页面原价")
    final_price = Column(Float, nullable=False, comment="券后/活动后最终到手价")
    weight_grams = Column(Float, nullable=False, comment="黄金克重")
    price_per_gram = Column(Float, nullable=False, index=True, comment="单克价")
    discount_tags = Column(String(255), comment="优惠信息标签 JSON")
    update_time = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, comment="最后更新时间")

    def __repr__(self) -> str:
        return f"<GoldProduct(id={self.id}, title={self.title[:20]}..., price_per_gram={self.price_per_gram})>"


# Database configuration
DATABASE_URL = "sqlite:///./gold_valuation.db"

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},  # SQLite specific
    echo=False  # Set to True for SQL debugging
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def init_db() -> None:
    """初始化数据库，创建所有表"""
    Base.metadata.create_all(bind=engine)


def get_db():
    """获取数据库会话依赖"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
