# utils.py
import json
import logging
import os
import re
import requests
from pathlib import Path
from rapidfuzz import process, fuzz
from typing import List, Dict, Optional, Tuple
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from .models import Product, Category
from .config import (
    API_URL_CATEGORIES,
    API_URL_PRODUCTS,
    HEADERS,
    CATEGORY_MATCH_THRESHOLD,
    PRODUCT_MATCH_THRESHOLD,
    QA_MATCH_THRESHOLD,
    UZBEK_SUFFIXES,
    STOP_WORDS,
    MAX_PRODUCTS_TO_SHOW,
    MyDomain
)

BASE_DIR = Path(__file__).resolve().parent
QA_FILE = os.path.join(BASE_DIR, "qa.txt")


# ============================================
# TEXT PROCESSING FUNCTIONS
# ============================================

def normalize_text(text: str) -> str:
    """
    Matnni normalizatsiya qiladi.

    - Kichik harfga o'tkazadi
    - Ortiqcha bo'shliqlarni olib tashlaydi
    - O'zbek tilida qo'shimchalarni olib tashlaydi

    Args:
        text: Asl matn

    Returns:
        Normalizatsiya qilingan matn
    """
    if not text:
        return ""

    # Kichik harfga va tozalash
    text = text.lower().strip()
    text = re.sub(r'\s+', ' ', text)  # Ortiqcha bo'shliqlarni olib tashlash

    # Har bir so'zdan qo'shimchalarni olib tashlash
    words = text.split()
    normalized_words = []

    for word in words:
        # Qo'shimchalarni tekshirish
        for suffix in UZBEK_SUFFIXES:
            if word.endswith(suffix) and len(word) > len(suffix) + 2:
                word = word[:-len(suffix)]
                break
        normalized_words.append(word)

    return ' '.join(normalized_words)


def extract_keywords(text: str) -> List[str]:
    """
    Matndan kalit so'zlarni ajratib oladi (stop words ni o'tkazib yuboradi).

    Args:
        text: Asl matn

    Returns:
        Kalit so'zlar ro'yxati
    """
    words = normalize_text(text).split()
    keywords = [w for w in words if w not in STOP_WORDS and len(w) > 2]
    return keywords


def clean_product_name(name: str) -> str:
    """
    Mahsulot nomini tozalaydi (HTML teglar, ortiqcha belgilarni olib tashlash).

    Args:
        name: Mahsulot nomi

    Returns:
        Tozalangan nom
    """
    if not name:
        return ""

    # HTML teglarni olib tashlash
    name = re.sub(r'<[^>]+>', '', name)

    # Ortiqcha belgilarni olib tashlash
    name = name.replace('\n', ' ').replace('\r', '')
    name = re.sub(r'\s+', ' ', name)

    return name.strip()


def format_price(price: float) -> str:
    """
    Narxni chiroyli formatda qaytaradi.

    Args:
        price: Narx (float)

    Returns:
        Formatlangan narx (masalan: "835,000 so'm")
    """
    if not price or price <= 0:
        return "Narx belgilanmagan"

    return f"{price:,.0f} so'm"


# ============================================
# QA FILE FUNCTIONS
# ============================================

def get_answer_from_file(question: str, filepath: str = QA_FILE) -> Dict[str, any]:
    """
    QA.txt faylidan savolga javob qidiradi.

    Args:
        question: Foydalanuvchi savoli
        filepath: QA fayl yo'li

    Returns:
        {
            "found": True/False,
            "answer": "Javob matni" yoki None,
            "confidence": 0-100
        }
    """
    result = {
        "found": False,
        "answer": None,
        "confidence": 0
    }

    try:
        # QA faylni o'qish
        qa_dict = {}
        current_q = None
        current_a = []

        with open(filepath, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()

                if not line:
                    continue

                if line.endswith("?"):
                    if current_q and current_a:
                        qa_dict[current_q.lower()] = " ".join(current_a).strip()
                    current_q = line
                    current_a = []
                else:
                    current_a.append(line)

            if current_q and current_a:
                qa_dict[current_q.lower()] = " ".join(current_a).strip()

        if not qa_dict:
            return result

        # 1. TO'LIQ MOS KELISH
        user_q_lower = question.lower()
        for q_text, a_text in qa_dict.items():
            if user_q_lower in q_text or q_text in user_q_lower:
                result["found"] = True
                result["answer"] = a_text
                result["confidence"] = 100
                return result

        # 2. FUZZY MATCHING
        questions_list = list(qa_dict.keys())
        match, score = process.extractOne(
            user_q_lower,
            questions_list,
            scorer=fuzz.token_sort_ratio
        )

        if score >= QA_MATCH_THRESHOLD:
            result["found"] = True
            result["answer"] = qa_dict[match]
            result["confidence"] = score
            return result

        # 3. KALIT SO'ZLAR BO'YICHA
        keywords = extract_keywords(user_q_lower)
        if keywords:
            best_match = None
            best_score = 0

            for q_text, a_text in qa_dict.items():
                match_count = sum(1 for keyword in keywords if keyword in q_text)
                if match_count > best_score:
                    best_score = match_count
                    best_match = a_text

            if best_match and best_score > 0:
                result["found"] = True
                result["answer"] = best_match
                result["confidence"] = min(best_score * 30, 90)
                return result

        return result

    except FileNotFoundError:
        result["answer"] = "❌ QA fayli topilmadi"
        return result
    except Exception as e:
        result["answer"] = f"❌ Xatolik: {str(e)}"
        return result


# ============================================
# YANGILANGAN DATABASE SEARCH FUNCTIONS
# ============================================

def find_category_by_name(query: str) -> Tuple[Optional[Category], int]:
    """
    Kategoriyani nom bo'yicha qidiradi (fuzzy matching).

    YANGILANGAN: Parent kategoriyalarni ham qidiradi

    Args:
        query: Qidiruv so'rovi

    Returns:
        (Category object, confidence_score) yoki (None, 0)
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
    YANGI FUNKSIYA: Kategoriya va uning barcha child kategoriyalari ID larini qaytaradi

    Misol:
    - "Noutbuklar va kompyuterlar" (423)
      - "Ноутбуки" (430)
        - "Ноутбуки ASUS" (439)
        - "Ноутбуки HP" (436)
        - "Ноутбуки Dell" (441)
        - ...

    Args:
        category: Category object

    Returns:
        [423, 430, 435, 436, 437, 438, 439, 441, 442, ...]
    """
    category_ids = [category.id]

    # Child kategoriyalarni topish (1-darajali children)
    children = Category.objects.filter(parent_id=category.id)
    for child in children:
        category_ids.append(child.id)

        # Grandchildren (2-darajali children)
        grandchildren = Category.objects.filter(parent_id=child.id)
        for grandchild in grandchildren:
            category_ids.append(grandchild.id)

    return category_ids


def search_products_by_category(category_name: str, limit: int = 5) -> Dict:
    """
    YANGILANGAN: Kategoriya bo'yicha mahsulotlarni qidiradi

    Parent va child kategoriyalardan ham qidiradi

    Args:
        category_name: Kategoriya nomi
        limit: Maksimal natijalar soni

    Returns:
        {
            "found": True/False,
            "products": [...],
            "total_count": int,
            "search_type": "category",
            "category_name": str
        }
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
            current_stock__gt=0  # Faqat omborda bor mahsulotlar
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
                "name": clean_product_name(product.name),
                "price": float(product.unit_price) if product.unit_price else 0,
                "price_formatted": format_price(product.unit_price),
                "stock": product.current_stock if product.current_stock else 0,
                "details": product.details if product.details else "",
                "category": category.name
            })

        # Jami mahsulotlar soni
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

    Args:
        query: Qidiruv so'rovi
        limit: Maksimal natijalar soni

    Returns:
        {
            "found": True/False,
            "products": [...],
            "total_count": int,
            "search_type": "name"
        }
    """
    try:
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
                "name": clean_product_name(product.name),
                "price": float(product.unit_price) if product.unit_price else 0,
                "price_formatted": format_price(product.unit_price),
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

    1. Avval kategoriya bo'yicha qidiradi (parent + children)
    2. Agar topilmasa, mahsulot nomi bo'yicha qidiradi

    Args:
        query: Qidiruv so'rovi

    Returns:
        {
            "found": True/False,
            "products": [...],
            "total_count": int,
            "category_name": str (agar kategoriya bo'yicha qidirilsa),
            "search_type": "category" | "name" | "none"
        }
    """
    try:
        # Validatsiya
        if not query or len(query.strip()) < 2:
            return {
                "found": False,
                "products": [],
                "total_count": 0,
                "search_type": "none"
            }

        # Database mavjudligini tekshirish
        if not Product.objects.exists() and not Category.objects.exists():
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
        print(f"❌ get_products_from_db error: {e}")
        import traceback
        traceback.print_exc()
        return {
            "found": False,
            "products": [],
            "error": str(e)
        }


# ============================================
# SYNC FUNCTIONS (O'zgarishsiz)
# ============================================

def fetch_and_save_categories() -> int:
    """FastAPI dan kategoriyalarni yuklab oladi."""
    try:
        response = requests.get(API_URL_CATEGORIES, headers=HEADERS, timeout=15)
        response.raise_for_status()

        categories = response.json().get("categories", [])

        saved_count = 0
        for c in categories:
            _, created = Category.objects.update_or_create(
                id=c["id"],
                defaults={
                    "name": c.get("name", ""),
                    "slug": c.get("slug", ""),
                    "parent_id": c.get("parent_id"),
                }
            )
            if created:
                saved_count += 1

        print(f"✅ {saved_count} ta kategoriya saqlandi")
        return len(categories)

    except Exception as e:
        print(f"❌ Kategoriya yuklashda xatolik: {e}")
        return 0


def fetch_and_save_products() -> int:
    """FastAPI dan mahsulotlarni yuklab oladi."""
    try:
        response = requests.get(API_URL_PRODUCTS, headers=HEADERS, timeout=15)
        response.raise_for_status()

        products = response.json().get("products", [])

        saved_count = 0
        for p in products:
            _, created = Product.objects.update_or_create(
                id=p["id"],
                defaults={
                    "user_id": p.get("user_id"),
                    "added_by": p.get("added_by"),
                    "name": p.get("name", ""),
                    "code": p.get("code"),
                    "slug": p.get("slug"),
                    "category_id": p.get("category_id"),
                    "unit_price": p.get("unit_price"),
                    "discount": p.get("discount"),
                    "discount_type": p.get("discount_type"),
                    "details": p.get("details"),
                    "images": p.get("images"),
                    "colors": p.get("colors"),
                    "choice_options": p.get("choice_options"),
                    "variation": p.get("variation"),
                    "current_stock": p.get("current_stock"),
                    "product_type": p.get("product_type"),
                    "shipping_cost": p.get("shipping_cost"),
                    "brand_id": p.get("brand_id"),
                }
            )
            if created:
                saved_count += 1

        print(f"✅ {saved_count} ta mahsulot saqlandi")
        return len(products)

    except Exception as e:
        print(f"❌ Mahsulot yuklashda xatolik: {e}")
        return 0


def send_telegram_order_to_channel(token, channel_id, message, user_id, receiver_id):
    """Telegram kanalga buyurtma yuboradi (O'zgarishsiz)"""
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    keyboard = [
        [InlineKeyboardButton("🗂 Suhbatni ko'rish",
                              url=f"{MyDomain}/chats?user_id={user_id}&receiver_id={receiver_id}")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    payload = {
        'chat_id': channel_id,
        'text': message,
        'parse_mode': 'Markdown',
        'reply_markup': json.dumps(reply_markup.to_dict())
    }
    try:
        response = requests.post(url, data=payload)
        if response.status_code == 200:
            logging.info("✅ Buyurtma Telegram kanalga muvaffaqiyatli yuborildi")
        else:
            logging.error(f"❌ Buyurtma yuborilmadi: {response.status_code}, {response.text}")
    except Exception as e:
        logging.exception(f"❌ Telegramga yuborishda xatolik: {e}")