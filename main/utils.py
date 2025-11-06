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
    MAX_PRODUCTS_TO_SHOW, MyDomain
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
# DATABASE SEARCH FUNCTIONS
# ============================================

def find_category_by_name(query: str) -> Tuple[Optional[Category], int]:
    """
    Kategoriyani nom bo'yicha qidiradi (fuzzy matching).

    Args:
        query: Qidiruv so'rovi

    Returns:
        (Category object, confidence_score) yoki (None, 0)
    """
    categories = Category.objects.all()

    if not categories.exists():
        return None, 0

    normalized_query = normalize_text(query)
    query_words = normalized_query.split()

    best_match = None
    best_score = 0

    for category in categories:
        normalized_cat = normalize_text(category.name)
        cat_words = normalized_cat.split()

        # 1. TO'LIQ MOS KELISH
        if normalized_query in normalized_cat or normalized_cat in normalized_query:
            return category, 100

        # 2. SO'Z BOSHLANISHI
        for q_word in query_words:
            if len(q_word) < 3:
                continue
            for cat_word in cat_words:
                if cat_word.startswith(q_word) or q_word.startswith(cat_word):
                    if 95 > best_score:
                        best_score = 95
                        best_match = category

        # 3. FUZZY MATCHING
        similarity = fuzz.partial_ratio(normalized_query, normalized_cat)
        if similarity > best_score:
            best_score = similarity
            best_match = category

    return best_match, best_score


def find_products_by_query(query: str, limit: int = MAX_PRODUCTS_TO_SHOW) -> List[Dict]:
    """
    Mahsulotlarni qidiradi (nom, tavsif, kategoriya bo'yicha).

    Args:
        query: Qidiruv so'rovi
        limit: Maksimal natijalar soni

    Returns:
        Topilgan mahsulotlar ro'yxati:
        [
            {
                "product": Product object,
                "score": confidence_score,
                "match_type": "exact" | "category" | "partial"
            }
        ]
    """
    results = []
    products = Product.objects.all()

    if not products.exists():
        return results

    normalized_query = normalize_text(query)
    query_keywords = extract_keywords(query)

    # 1. TO'GRIDAN-TO'GRI MAHSULOT NOMI
    for product in products:
        product_name_clean = clean_product_name(product.name)
        normalized_product = normalize_text(product_name_clean)

        # To'liq mos kelish
        if normalized_query in normalized_product or normalized_product in normalized_query:
            results.append({
                "product": product,
                "score": 100,
                "match_type": "exact"
            })
            continue

        # Fuzzy matching
        similarity = fuzz.ratio(normalized_query, normalized_product)
        if similarity >= PRODUCT_MATCH_THRESHOLD:
            results.append({
                "product": product,
                "score": similarity,
                "match_type": "exact"
            })

    # 2. KATEGORIYA BO'YICHA
    if not results:
        category, cat_score = find_category_by_name(query)

        if category and cat_score >= CATEGORY_MATCH_THRESHOLD:
            category_products = Product.objects.filter(category_id=category.id)[:limit]

            for product in category_products:
                results.append({
                    "product": product,
                    "score": cat_score,
                    "match_type": "category",
                    "category_name": category.name
                })

    # 3. PARTIAL SEARCH (kalit so'zlar)
    if not results and query_keywords:
        for product in products:
            product_name_clean = clean_product_name(product.name)
            normalized_product = normalize_text(product_name_clean)

            # Kalit so'zlar bor-yo'qligini tekshirish
            match_score = 0
            for keyword in query_keywords:
                if keyword in normalized_product:
                    match_score += 25
                else:
                    # Partial matching
                    for word in normalized_product.split():
                        if fuzz.ratio(keyword, word) > 80:
                            match_score += 15
                            break

            if match_score > 30:
                results.append({
                    "product": product,
                    "score": min(match_score, 95),
                    "match_type": "partial"
                })

    # Score bo'yicha saralash
    results.sort(key=lambda x: x["score"], reverse=True)

    return results[:limit]


def get_products_from_db(query: str) -> Dict[str, any]:
    """
    DB dan mahsulotlarni qidiradi va natijani qaytaradi.

    Args:
        query: Qidiruv so'rovi

    Returns:
        {
            "found": True/False,
            "products": [...],
            "total_count": int,
            "category_name": str (agar kategoriya bo'yicha qidirilsa),
            "search_type": "exact" | "category" | "partial" | "none"
        }
    """
    result = {
        "found": False,
        "products": [],
        "total_count": 0,
        "category_name": None,
        "search_type": "none"
    }

    try:
        # Validatsiya
        if not query or len(query.strip()) < 2:
            return result

        # Database mavjudligini tekshirish
        if not Product.objects.exists() and not Category.objects.exists():
            return result

        # Qidirish
        search_results = find_products_by_query(query)

        if search_results:
            result["found"] = True
            result["search_type"] = search_results[0]["match_type"]

            # Mahsulotlar ma'lumotini to'plash
            for item in search_results:
                product = item["product"]

                product_data = {
                    "name": clean_product_name(product.name),
                    "price": float(product.unit_price) if product.unit_price else 0,
                    "price_formatted": format_price(product.unit_price),
                    "stock": product.current_stock if product.current_stock else 0,
                    "details": product.details[:200] if product.details else "",
                    "code": product.code,
                    "confidence": item["score"]
                }

                result["products"].append(product_data)

            # Kategoriya nomi (agar kategoriya bo'yicha qidirilsa)
            if result["search_type"] == "category" and search_results:
                result["category_name"] = search_results[0].get("category_name")

            # Umumiy soni
            if result["search_type"] == "category" and result["category_name"]:
                category = Category.objects.filter(name=result["category_name"]).first()
                if category:
                    result["total_count"] = Product.objects.filter(category_id=category.id).count()
            else:
                result["total_count"] = len(result["products"])

        return result

    except Exception as e:
        print(f"❌ get_products_from_db error: {e}")
        return result


# ============================================
# SYNC FUNCTIONS
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




def send_telegram_order_to_channel(token,channel_id,message,user_id,receiver_id):
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    keyboard = [
        [InlineKeyboardButton("🗂 Suhbatni ko‘rish", url=f"{MyDomain}/chats?user_id={user_id}&receiver_id={receiver_id}")]
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
