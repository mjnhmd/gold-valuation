"""
FastAPI Main Application
黄金优惠监控系统后端入口
"""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.models import init_db
from app.api import router
from app.scheduler import start_scheduler, stop_scheduler, sync_all_products

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    应用生命周期管理
    启动时初始化数据库和调度器
    关闭时停止调度器
    """
    # 启动
    logger.info("正在启动黄金优惠监控系统...")

    # 初始化数据库
    init_db()
    logger.info("数据库初始化完成")

    # 启动时先执行一次同步（获取初始数据）
    logger.info("正在执行首次数据同步...")
    await sync_all_products()

    # 启动定时任务调度器
    start_scheduler()

    yield

    # 关闭
    logger.info("正在关闭系统...")
    stop_scheduler()


# 创建 FastAPI 应用
app = FastAPI(
    title="黄金优惠监控系统",
    description="自动抓取京东/淘宝黄金饰品优惠信息，计算克价并展示",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS 配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 生产环境请配置具体域名
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册 API 路由
app.include_router(router)


@app.get("/")
async def root():
    """根路径健康检查"""
    return {
        "status": "ok",
        "message": "黄金优惠监控系统运行中",
        "docs": "/docs",
    }


@app.get("/health")
async def health_check():
    """健康检查接口"""
    return {"status": "healthy"}
