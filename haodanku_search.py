"""
好单库超级搜索 API 调用脚本
功能：通过关键词搜索商品，提取并展示关键商品信息
"""

import requests
import json
import sys

# ========================
# 配置区
# ========================
API_KEY = "9945FDC4E9E5"
BASE_URL = "https://v2.api.haodanku.com/supersearch"


def search_gold_items(keyword: str = "周大福", back: int = 20, min_id: int = 1, tb_p: int = 1) -> list[dict]:
    """
    调用好单库超级搜索 API，按关键词搜索商品。

    Args:
        keyword: 搜索关键词，默认为"周大福"
        back:    每页返回的商品数量，默认 20
        min_id:  翻页参数（最小 ID），默认 1
        tb_p:    淘宝页码，默认 1

    Returns:
        包含商品信息字典的列表
    """
    # 拼接请求 URL
    url = (
        f"{BASE_URL}"
        f"/apikey/{API_KEY}"
        f"/keyword/{keyword}"
        f"/back/{back}"
        f"/min_id/{min_id}"
        f"/tb_p/{tb_p}"
    )

    print(f"🔍 正在搜索关键词: 「{keyword}」...")
    print(f"📡 请求地址: {url}\n")

    try:
        # 发送 GET 请求，设置 10 秒超时
        response = requests.get(url, timeout=10)
        # 检查 HTTP 状态码，非 2xx 会抛出异常
        response.raise_for_status()
    except requests.exceptions.Timeout:
        print("❌ 请求超时，请检查网络连接后重试。")
        return []
    except requests.exceptions.ConnectionError:
        print("❌ 网络连接失败，请检查网络设置。")
        return []
    except requests.exceptions.HTTPError as e:
        print(f"❌ HTTP 错误: {e}")
        return []
    except requests.exceptions.RequestException as e:
        print(f"❌ 请求异常: {e}")
        return []

    # 解析 JSON 响应
    try:
        data = response.json()
    except json.JSONDecodeError:
        print("❌ 返回数据不是有效的 JSON 格式。")
        print(f"原始响应内容: {response.text[:500]}")
        return []

    # 检查 API 返回状态
    # 好单库 API 通常用 code=1 表示成功，具体以实际返回为准
    code = data.get("code")
    msg = data.get("msg", "")

    if code != 1:
        print(f"⚠️ API 返回异常 — code: {code}, msg: {msg}")
        return []

    # 提取商品列表
    items = data.get("data", [])
    if not items:
        print("📭 未找到相关商品。")
        return []

    print(f"✅ 共找到 {len(items)} 条商品信息：\n")
    return items


def extract_and_print(items: list[dict]) -> None:
    """
    从商品列表中提取关键字段并格式化打印。

    提取字段：
        - itemid:       商品 ID
        - itemtitle:    商品标题
        - itempic:      商品主图 URL
        - itemprice:    商品原价
        - itemendprice: 券后最终价
        - couponmoney:  优惠券金额
    """
    # 需要提取的字段及其中文标签
    fields = [
        ("itemid", "商品ID"),
        ("itemtitle", "商品标题"),
        ("itempic", "商品主图"),
        ("itemprice", "商品原价"),
        ("itemendprice", "券后价格"),
        ("couponmoney", "优惠券金额"),
    ]

    for idx, item in enumerate(items, start=1):
        print(f"{'=' * 60}")
        print(f"  📦 第 {idx} 件商品")
        print(f"{'=' * 60}")

        for field_key, field_label in fields:
            value = item.get(field_key, "N/A")
            # 价格类字段加上 ¥ 符号
            if field_key in ("itemprice", "itemendprice", "couponmoney") and value != "N/A":
                print(f"  {field_label:　<6}:  ¥{value}")
            else:
                print(f"  {field_label:　<6}:  {value}")

        print()  # 空行分隔


def main():
    """主入口：支持命令行传入关键词，默认搜索"周大福"。"""
    # 支持命令行参数：python haodanku_search.py 黄金
    keyword = sys.argv[1] if len(sys.argv) > 1 else "周大福"

    # 1. 调用超级搜索 API
    items = search_gold_items(keyword=keyword)

    # 2. 提取并打印关键信息
    if items:
        extract_and_print(items)
    else:
        print("🔚 没有可展示的商品数据。")


if __name__ == "__main__":
    main()
