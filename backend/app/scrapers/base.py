"""
Scraper Base Class and Implementations
数据抓取器基类与平台实现
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List, Optional
from datetime import datetime
import random


@dataclass
class RawProductData:
    """
    原始商品数据结构
    从 API 抓取后的未清洗数据
    """

    platform: str  # JD / TAOBAO
    item_id: str
    title: str
    cover_image: str
    affiliate_url: str
    original_price: float
    final_price: float
    discount_tags: Optional[str] = None


class BaseScraper(ABC):
    """
    数据抓取器基类
    定义抓取接口，子类实现具体平台的抓取逻辑
    """

    @property
    @abstractmethod
    def platform(self) -> str:
        """返回平台标识"""
        pass

    @abstractmethod
    async def fetch_products(self, keyword: str = "周大福") -> List[RawProductData]:
        """
        抓取商品数据

        Args:
            keyword: 搜索关键词，默认"周大福"

        Returns:
            原始商品数据列表
        """
        pass


class JDScraper(BaseScraper):
    """
    京东联盟数据抓取器
    V1 阶段使用 Mock 数据，后续对接真实 API
    """

    @property
    def platform(self) -> str:
        return "JD"

    def __init__(self, api_key: Optional[str] = None, api_secret: Optional[str] = None):
        """
        初始化京东抓取器

        Args:
            api_key: 京东联盟 API Key (V1 可为空)
            api_secret: 京东联盟 API Secret (V1 可为空)
        """
        self.api_key = api_key
        self.api_secret = api_secret

    async def fetch_products(self, keyword: str = "周大福") -> List[RawProductData]:
        """
        抓取京东商品数据
        V1 阶段返回 Mock 数据
        """
        # TODO: V2 对接真实京东联盟 API
        # 真实接口文档: https://union.jd.com/openplatform/api

        return self._get_mock_data()

    def _get_mock_data(self) -> List[RawProductData]:
        """生成京东 Mock 数据"""
        mock_products = [
            # 计价黄金 - 正常商品
            RawProductData(
                platform="JD",
                item_id="jd_10001",
                title="周大福 足金黄金手链 约3.5g F217574",
                cover_image="https://img14.360buyimg.com/n1/jfs/t1/gold_bracelet_1.jpg",
                affiliate_url="https://u.jd.com/mock_affiliate_1",
                original_price=2680.00,
                final_price=2450.00,
                discount_tags='["满2000减100", "PLUS会员95折"]',
            ),
            RawProductData(
                platform="JD",
                item_id="jd_10002",
                title="周大福 黄金项链 足金999 约5.8克 女款锁骨链",
                cover_image="https://img14.360buyimg.com/n1/jfs/t1/gold_necklace_1.jpg",
                affiliate_url="https://u.jd.com/mock_affiliate_2",
                original_price=4200.00,
                final_price=3850.00,
                discount_tags='["跨店满减"]',
            ),
            RawProductData(
                platform="JD",
                item_id="jd_10003",
                title="周大福 足金戒指 男女同款 约2.15g",
                cover_image="https://img14.360buyimg.com/n1/jfs/t1/gold_ring_1.jpg",
                affiliate_url="https://u.jd.com/mock_affiliate_3",
                original_price=1580.00,
                final_price=1420.00,
                discount_tags='["新人专享"]',
            ),
            RawProductData(
                platform="JD",
                item_id="jd_10004",
                title="周大福 传承系列古法黄金手镯 约18.6克",
                cover_image="https://img14.360buyimg.com/n1/jfs/t1/gold_bangle_1.jpg",
                affiliate_url="https://u.jd.com/mock_affiliate_4",
                original_price=13500.00,
                final_price=12800.00,
                discount_tags='["大额券"]',
            ),
            # 一口价黄金 - 应被过滤
            RawProductData(
                platform="JD",
                item_id="jd_10005",
                title="周大福 一口价黄金吊坠 可爱小兔子 精选好礼",
                cover_image="https://img14.360buyimg.com/n1/jfs/t1/gold_pendant_1.jpg",
                affiliate_url="https://u.jd.com/mock_affiliate_5",
                original_price=1288.00,
                final_price=1088.00,
                discount_tags="[]",
            ),
            # 18K金 - 应被过滤
            RawProductData(
                platform="JD",
                item_id="jd_10006",
                title="周大福 18K金项链 玫瑰金锁骨链 约1.2g",
                cover_image="https://img14.360buyimg.com/n1/jfs/t1/18k_necklace_1.jpg",
                affiliate_url="https://u.jd.com/mock_affiliate_6",
                original_price=1680.00,
                final_price=1480.00,
                discount_tags="[]",
            ),
            RawProductData(
                platform="JD",
                item_id="jd_10007",
                title="周大福 足金转运珠手链 约1.08克 红绳款",
                cover_image="https://img14.360buyimg.com/n1/jfs/t1/gold_bead_1.jpg",
                affiliate_url="https://u.jd.com/mock_affiliate_7",
                original_price=820.00,
                final_price=720.00,
                discount_tags='["限时秒杀"]',
            ),
            RawProductData(
                platform="JD",
                item_id="jd_10008",
                title="周大福 黄金耳钉 足金999 约0.8g 简约百搭",
                cover_image="https://img14.360buyimg.com/n1/jfs/t1/gold_earring_1.jpg",
                affiliate_url="https://u.jd.com/mock_affiliate_8",
                original_price=620.00,
                final_price=550.00,
                discount_tags="[]",
            ),
        ]
        return mock_products


class TaobaoScraper(BaseScraper):
    """
    淘宝/阿里妈妈数据抓取器
    使用好单库 API 获取真实数据
    """

    # 好单库 API 配置
    API_KEY = "9945FDC4E9E5"
    BASE_URL = "https://v2.api.haodanku.com/supersearch"

    @property
    def platform(self) -> str:
        return "TAOBAO"

    def __init__(self, app_key: Optional[str] = None, app_secret: Optional[str] = None):
        """
        初始化淘宝抓取器

        Args:
            app_key: 阿里妈妈 App Key (V1 可为空)
            app_secret: 阿里妈妈 App Secret (V1 可为空)
        """
        self.app_key = app_key
        self.app_secret = app_secret

    async def fetch_products(self, keyword: str = "周大福") -> List[RawProductData]:
        """
        抓取淘宝商品数据
        使用好单库 API 获取真实数据
        """
        import httpx

        url = (
            f"{self.BASE_URL}"
            f"/apikey/{self.API_KEY}"
            f"/keyword/{keyword}"
            f"/back/20"
            f"/min_id/1"
            f"/tb_p/1"
        )

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(url)
                data = response.json()

                if data.get("code") != 1:
                    # API 调用失败，返回空列表或回退到 Mock
                    return self._get_mock_data()

                items = data.get("data", [])
                if not items:
                    return self._get_mock_data()

                return self._convert_to_raw_products(items)

        except Exception as e:
            # API 调用异常，回退到 Mock 数据
            import logging

            logging.getLogger(__name__).warning(
                f"好单库 API 调用失败: {e}，使用 Mock 数据"
            )
            return self._get_mock_data()

    def _convert_to_raw_products(self, items: List[dict]) -> List[RawProductData]:
        """
        将好单库返回的数据转换为 RawProductData 格式
        """
        products = []
        for item in items:
            try:
                # 提取商品ID
                item_id = f"tb_{item.get('itemid', '')}"
                if not item_id:
                    continue

                # 标题
                title = item.get("itemtitle", "")
                if not title:
                    continue

                # 图片
                cover_image = item.get("itempic", "")

                # 价格
                original_price = float(item.get("itemprice", 0))
                final_price = float(item.get("itemendprice", 0))

                if original_price <= 0 or final_price <= 0:
                    continue

                # 优惠券金额
                coupon = item.get("couponmoney", "")
                discount_tags = (
                    f'["券{int(float(coupon))}元"]'
                    if coupon and float(coupon) > 0
                    else "[]"
                )

                # 联盟链接（使用淘宝官方转链接口的简化版本）
                item_url = item.get("itemurl", "")
                affiliate_url = (
                    f"https://s.click.taobao.com/{item_id}"
                    if not item_url
                    else item_url
                )

                products.append(
                    RawProductData(
                        platform="TAOBAO",
                        item_id=item_id,
                        title=title,
                        cover_image=cover_image,
                        affiliate_url=affiliate_url,
                        original_price=original_price,
                        final_price=final_price,
                        discount_tags=discount_tags,
                    )
                )
            except (ValueError, TypeError) as e:
                continue

        return products

    def _get_mock_data(self) -> List[RawProductData]:
        """生成淘宝 Mock 数据"""
        mock_products = [
            RawProductData(
                platform="TAOBAO",
                item_id="tb_20001",
                title="周大福官方旗舰店 足金手链 约4.2克 时尚女款",
                cover_image="https://img.alicdn.com/bao/gold_bracelet_tb_1.jpg",
                affiliate_url="https://s.click.taobao.com/mock_1",
                original_price=3100.00,
                final_price=2880.00,
                discount_tags='["88VIP立减", "店铺券"]',
            ),
            RawProductData(
                platform="TAOBAO",
                item_id="tb_20002",
                title="【天猫直送】周大福 黄金吊坠 约2.68g 心形挂坠",
                cover_image="https://img.alicdn.com/bao/gold_pendant_tb_1.jpg",
                affiliate_url="https://s.click.taobao.com/mock_2",
                original_price=2050.00,
                final_price=1880.00,
                discount_tags='["聚划算"]',
            ),
            RawProductData(
                platform="TAOBAO",
                item_id="tb_20003",
                title="周大福 古法黄金手镯 传承系列 约25.5克 龙凤呈祥",
                cover_image="https://img.alicdn.com/bao/gold_bangle_tb_1.jpg",
                affiliate_url="https://s.click.taobao.com/mock_3",
                original_price=18600.00,
                final_price=17500.00,
                discount_tags='["大促专享"]',
            ),
            RawProductData(
                platform="TAOBAO",
                item_id="tb_20004",
                title="周大福 足金耳环 约1.5g 水滴形 百搭气质",
                cover_image="https://img.alicdn.com/bao/gold_earring_tb_1.jpg",
                affiliate_url="https://s.click.taobao.com/mock_4",
                original_price=1150.00,
                final_price=1020.00,
                discount_tags="[]",
            ),
            # 一口价 - 应被过滤
            RawProductData(
                platform="TAOBAO",
                item_id="tb_20005",
                title="周大福 一口价定价黄金耳钉 小众设计款",
                cover_image="https://img.alicdn.com/bao/gold_earring_tb_2.jpg",
                affiliate_url="https://s.click.taobao.com/mock_5",
                original_price=899.00,
                final_price=799.00,
                discount_tags="[]",
            ),
            RawProductData(
                platform="TAOBAO",
                item_id="tb_20006",
                title="周大福 足金戒指 开口可调节 约3.08克",
                cover_image="https://img.alicdn.com/bao/gold_ring_tb_1.jpg",
                affiliate_url="https://s.click.taobao.com/mock_6",
                original_price=2280.00,
                final_price=2100.00,
                discount_tags='["粉丝专享"]',
            ),
            RawProductData(
                platform="TAOBAO",
                item_id="tb_20007",
                title="周大福 生肖蛇年黄金吊坠 约1.88克 本命年",
                cover_image="https://img.alicdn.com/bao/gold_snake_tb_1.jpg",
                affiliate_url="https://s.click.taobao.com/mock_7",
                original_price=1450.00,
                final_price=1320.00,
                discount_tags='["生肖特惠"]',
            ),
        ]
        return mock_products
