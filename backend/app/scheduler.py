"""
Scheduler - APScheduler 定时任务配置
"""
import logging
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from app.models import SessionLocal
from app.scrapers import JDScraper, TaobaoScraper
from app.services import process_and_save_products

logger = logging.getLogger(__name__)

# 全局调度器实例
scheduler = AsyncIOScheduler()


async def sync_all_products():
    """
    同步所有平台的商品数据
    定时任务执行入口
    """
    logger.info("开始执行定时同步任务...")

    db = SessionLocal()
    try:
        # 京东数据
        logger.info("正在抓取京东数据...")
        jd_scraper = JDScraper()
        jd_products = await jd_scraper.fetch_products()
        jd_stats = process_and_save_products(jd_products, db)
        logger.info(f"京东数据同步完成: {jd_stats}")

        # 淘宝数据
        logger.info("正在抓取淘宝数据...")
        tb_scraper = TaobaoScraper()
        tb_products = await tb_scraper.fetch_products()
        tb_stats = process_and_save_products(tb_products, db)
        logger.info(f"淘宝数据同步完成: {tb_stats}")

        logger.info("定时同步任务执行完成")

    except Exception as e:
        logger.error(f"定时同步任务执行失败: {e}")
    finally:
        db.close()


def setup_scheduler():
    """
    配置定时任务
    每天 08:00、12:00、20:00 执行同步
    """
    # 08:00 执行
    scheduler.add_job(
        sync_all_products,
        CronTrigger(hour=8, minute=0),
        id="sync_08",
        name="早间同步",
        replace_existing=True,
    )

    # 12:00 执行
    scheduler.add_job(
        sync_all_products,
        CronTrigger(hour=12, minute=0),
        id="sync_12",
        name="午间同步",
        replace_existing=True,
    )

    # 20:00 执行
    scheduler.add_job(
        sync_all_products,
        CronTrigger(hour=20, minute=0),
        id="sync_20",
        name="晚间同步",
        replace_existing=True,
    )

    logger.info("定时任务已配置: 每日 08:00, 12:00, 20:00 执行同步")


def start_scheduler():
    """启动调度器"""
    setup_scheduler()
    scheduler.start()
    logger.info("APScheduler 调度器已启动")


def stop_scheduler():
    """停止调度器"""
    scheduler.shutdown()
    logger.info("APScheduler 调度器已停止")
