# ============================================
# UTILS.PY - YANGILANGAN QIDIRUV FUNKSIYALARI
# ============================================

import re
from rapidfuzz import process, fuzz
from typing import List, Dict, Optional, Tuple
from .models import Product, Category


def normalize_text(text: str) -> str:
    """Matnni normalizatsiya qiladi"""
    if not text:
        return ""

    text = text.lower().strip()
    text = re.sub(r'\s+', ' ', text)

    return text


def find_category_by_name(query: str) -> Tuple[Optional[Category], int]:
    """
    Kategoriyani nom bo'yicha qidiradi (fuzzy matching)

    YANGILANGAN: Parent kategoriyalarni ham qidiradi
    """
    categories = Category.objects.all()

    if not categories.exists():
        return None, 0

    normalized_query = normalize_text(query)

    # Kategoriya nomlari dictionary
    category_dict = {}
    for cat in categories:
        normalized_cat = normalize_text(cat.name)
        category_dict[normalized_cat] = cat

    best_match = None
    best_score = 0

    # 1. TO'LIQ MOS KELISH
    if normalized_query in category_dict:
        return category_dict[normalized_query], 100

    # 2. FUZZY MATCHING
    choices = list(category_dict.keys())
    match_result = process.extractOne(
        normalized_query,
        choices,
        scorer=fuzz.token_sort_ratio
    )

    if match_result:
        matched_name, score = match_result
        if score >= 70:  # Threshold
            return category_dict[matched_name], score

    return None, 0


def get_category_and_subcategories(category: Category) -> List[int]:
    """
    Kategoriya va uning barcha child kategoriyalari ID larini qaytaradi

    Misol:
    - "Noutbuklar va kompyuterlar" (423)
      - "Ноутбуки" (430)
        - "Ноутбуки ASUS" (439)
        - "Ноутбуки HP" (436)
        - ...

    RETURN: [423, 430, 435, 436, 437, ...]
    """
    category_ids = [category.id]

    # Child kategoriyalarni topish
    children = Category.objects.filter(parent_id=category.id)
    for child in children:
        category_ids.append(child.id)

        # Grandchildren
        grandchildren = Category.objects.filter(parent_id=child.id)
        for grandchild in grandchildren:
            category_ids.append(grandchild.id)

    return category_ids


def search_products_by_category(category_name: str, limit: int = 5) -> Dict:
    """
    Kategoriya bo'yicha mahsulotlarni qidiradi

    YANGILANGAN: Parent va child kategoriyalardan ham qidiradi
    """
    try:
        # Kategoriyani topish
        category, score = find_category_by_name(category_name)

        if not category or score < 70:
            return {
                "found": False,
                "products": [],
                "total_count": 0,
                "search_type": "none"
            }

        print(f"✅ Kategoriya topildi: {category.name} (score: {score})")

        # Kategoriya va barcha child kategoriyalari
        category_ids = get_category_and_subcategories(category)

        print(f"📋 Qidirilayotgan kategoriyalar: {category_ids}")

        # Mahsulotlarni qidirish
        products = Product.objects.filter(
            category_id__in=category_ids,
            current_stock__gt=0
        ).order_by('-id')[:limit]

        if not products.exists():
            return {
                "found": False,
                "products": [],
                "total_count": 0,
                "search_type": "category"
            }

        # Natijalarni formatlash
        products_list = []
        for product in products:
            products_list.append({
                "name": product.name,
                "price": float(product.unit_price) if product.unit_price else 0,
                "price_formatted": f"{product.unit_price:,.0f} so'm" if product.unit_price else "Narx yo'q",
                "stock": product.current_stock if product.current_stock else 0,
                "details": product.details if product.details else "",
                "category": category.name
            })

        total_count = Product.objects.filter(
            category_id__in=category_ids,
            current_stock__gt=0
        ).count()

        print(f"✅ {len(products_list)} ta mahsulot topildi (jami: {total_count})")

        return {
            "found": True,
            "products": products_list,
            "total_count": total_count,
            "search_type": "category",
            "category_name": category.name
        }

    except Exception as e:
        print(f"❌ search_products_by_category xatolik: {e}")
        import traceback
        traceback.print_exc()
        return {
            "found": False,
            "products": [],
            "error": str(e)
        }


def search_products_by_name(query: str, limit: int = 5) -> Dict:
    """
    Mahsulot nomi bo'yicha qidiradi
    """
    try:
        normalized_query = normalize_text(query)

        # Mahsulotlarni qidirish (nom bo'yicha)
        products = Product.objects.filter(
            name__icontains=query,
            current_stock__gt=0
        )[:limit]

        if not products.exists():
            return {
                "found": False,
                "products": [],
                "total_count": 0,
                "search_type": "none"
            }

        products_list = []
        for product in products:
            products_list.append({
                "name": product.name,
                "price": float(product.unit_price) if product.unit_price else 0,
                "price_formatted": f"{product.unit_price:,.0f} so'm" if product.unit_price else "Narx yo'q",
                "stock": product.current_stock if product.current_stock else 0,
                "details": product.details if product.details else ""
            })

        return {
            "found": True,
            "products": products_list,
            "total_count": len(products_list),
            "search_type": "name"
        }

    except Exception as e:
        print(f"❌ search_products_by_name xatolik: {e}")
        return {
            "found": False,
            "products": [],
            "error": str(e)
        }


def get_products_from_db(query: str) -> Dict[str, any]:
    """
    YANGILANGAN: Database dan mahsulotlarni qidiradi

    1. Avval kategoriya bo'yicha qidiradi
    2. Agar topilmasa, mahsulot nomi bo'yicha qidiradi
    """
    try:
        if not query or len(query.strip()) < 2:
            return {
                "found": False,
                "products": [],
                "total_count": 0,
                "search_type": "none"
            }

        print(f"\n{'=' * 60}")
        print(f"🔍 get_products_from_db: {query}")
        print(f"{'=' * 60}")

        # 1. KATEGORIYA BO'YICHA QIDIRISH
        category_result = search_products_by_category(query, limit=5)

        if category_result["found"] and category_result["products"]:
            print(f"✅ Kategoriya bo'yicha topildi!")
            return category_result

        # 2. MAHSULOT NOMI BO'YICHA QIDIRISH
        name_result = search_products_by_name(query, limit=5)

        if name_result["found"] and name_result["products"]:
            print(f"✅ Nom bo'yicha topildi!")
            return name_result

        # 3. HECH NARSA TOPILMADI
        print(f"❌ Hech narsa topilmadi")
        return {
            "found": False,
            "products": [],
            "total_count": 0,
            "search_type": "none"
        }

    except Exception as e:
        print(f"❌ get_products_from_db xatolik: {e}")
        import traceback
        traceback.print_exc()
        return {
            "found": False,
            "products": [],
            "error": str(e)
        }