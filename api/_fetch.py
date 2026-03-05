"""
数据拉取与清洗逻辑 — 从好单库获取淘宝/京东黄金商品
"""
import re
import os
import requests
from typing import Optional

API_KEY = os.environ.get("HAODANKU_API_KEY", "9945FDC4E9E5")
TB_URL = "https://v2.api.haodanku.com/supersearch"
JD_URL = "https://v3.api.haodanku.com/jd_goods_search"


def extract_weight(title: str) -> Optional[float]:
    """从标题中正则提取克重"""
    match = re.search(r"约?\s*(\d+\.?\d*)\s*[gG克]", title)
    if match:
        w = float(match.group(1))
        if 0.1 <= w <= 500:
            return w
    return None


def _get(url: str, label: str) -> dict | None:
    try:
        resp = requests.get(url, timeout=15)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        print(f"[{label}] 请求失败: {e}")
        return None


# ── 淘宝 ──────────────────────────────────────────
def fetch_taobao(keyword="周大福", pages=5) -> list[dict]:
    all_items = []
    for page in range(1, pages + 1):
        url = f"{TB_URL}/apikey/{API_KEY}/keyword/{keyword}/back/100/min_id/1/tb_p/{page}"
        data = _get(url, f"TB p{page}")
        if not data or data.get("code") != 1:
            break
        items = data.get("data", [])
        all_items.extend(items)
        if len(items) < 100:
            break

    results = []
    for item in all_items:
        title = item.get("itemtitle", "")
        item_id = item.get("itemid", "")
        if not item_id or not title:
            continue
        try:
            orig = float(item.get("itemprice", 0))
            final = float(item.get("itemendprice", 0))
        except (ValueError, TypeError):
            continue
        if final <= 0:
            continue
        w = extract_weight(title) or 0
        ppg = round(final / w, 2) if w > 0 else 0
        results.append({
            "item_id": str(item_id),
            "platform": "TAOBAO",
            "title": title,
            "cover_image": item.get("itempic", ""),
            "affiliate_url": item.get("clickurl", ""),
            "original_price": orig,
            "final_price": final,
            "weight_grams": w,
            "price_per_gram": ppg,
        })
    return results


# ── 京东 ──────────────────────────────────────────
def fetch_jd(keyword="周大福黄金", pages=5) -> list[dict]:
    results = []
    min_id = 1
    for _ in range(pages):
        url = f"{JD_URL}?apikey={API_KEY}&keyword={keyword}&min_id={min_id}"
        data = _get(url, f"JD mid={min_id}")
        if not data:
            break
        code = data.get("code")
        if code != 200 and code != 1:
            break
        items = data.get("data", [])
        next_mid = data.get("min_id", 0)

        for item in items:
            title = item.get("goodsname", "")
            item_id = item.get("skuid", "") or item.get("itemid", "")
            if not item_id or not title:
                continue
            try:
                orig = float(item.get("itemprice", 0))
                final = float(item.get("itemendprice", 0))
            except (ValueError, TypeError):
                continue
            if final <= 0:
                continue
            w = extract_weight(title) or 0
            ppg = round(final / w, 2) if w > 0 else 0
            cover = item.get("itempic", "")
            if not cover and item.get("jd_image"):
                cover = item["jd_image"].split(",")[0]
            results.append({
                "item_id": f"jd_{item_id}",
                "platform": "JD",
                "title": title,
                "cover_image": cover,
                "affiliate_url": item.get("couponurl", ""),
                "original_price": orig,
                "final_price": final,
                "weight_grams": w,
                "price_per_gram": ppg,
            })

        if not items or not next_mid or next_mid <= min_id:
            break
        min_id = next_mid
    return results


def fetch_all() -> list[dict]:
    """拉取淘宝 + 京东全部数据"""
    return fetch_taobao() + fetch_jd()
