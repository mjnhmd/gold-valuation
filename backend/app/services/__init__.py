"""Services package"""
from .processor import (
    extract_weight,
    is_fixed_price_product,
    is_non_pure_gold,
    calculate_price_per_gram,
    calculate_discount_rate,
    calculate_discount_amount,
    process_raw_product,
    process_and_save_products,
)

__all__ = [
    "extract_weight",
    "is_fixed_price_product",
    "is_non_pure_gold",
    "calculate_price_per_gram",
    "calculate_discount_rate",
    "calculate_discount_amount",
    "process_raw_product",
    "process_and_save_products",
]