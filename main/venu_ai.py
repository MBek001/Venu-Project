"""
VENU AI Service
Mahsulotlarni qidiradi va chiroyli formatda taqdim etadi
"""

import json
import logging
from openai import OpenAI
from typing import Dict, List
from .models import Product, Category
from .utils import (
    normalize_text,
    extract_keywords,
    clean_product_name,
    format_price,
    get_answer_from_file,
    find_category_by_name,
    find_products_by_query
)
from .config import (
    OPENAI_API_KEY,
    AI_MODEL,
    AI_MAX_TOKENS,
    AI_TEMPERATURE,
    SYSTEM_PROMPT,
    MAX_PRODUCTS_PER_MESSAGE,
    MAX_MESSAGE_LENGTH,
    VENU_CONTACT
)

# OpenAI client
client = OpenAI(api_key=OPENAI_API_KEY)


def format_products_for_display(products_data: List[Dict], query: str = "") -> str:
    """
    Mahsulotlarni chiroyli formatda tayyorlaydi.
    Agar juda ko'p bo'lsa, faqat 3 tasini ko'rsatadi.
    """
    if not products_data:
        return ""

    # Maksimal 3 ta mahsulot
    display_products = products_data[:MAX_PRODUCTS_PER_MESSAGE]
    total_count = len(products_data)

    result = "🎯 Topildi:\n\n"  # Qisqartildi

    for idx, product in enumerate(display_products, 1):
        result += f"📦 {idx}. {product['name']}\n"
        result += f"   💰 Narxi: {product['price_formatted']}\n"

        if product.get('stock', 0) > 0:
            result += f"   📊 Omborda: {product['stock']} dona\n"
        else:
            result += "   📊 Omborda: Tugagan\n"

        if product.get('details'):
            details = product['details'][:80]  # Qisqartildi: 150 -> 80
            if len(product['details']) > 80:
                details += "..."
            result += f"   📝 {details}\n"

        result += "\n"

    # Agar ko'proq mahsulot bo'lsa
    if total_count > MAX_PRODUCTS_PER_MESSAGE:
        result += f"💬 +{total_count - MAX_PRODUCTS_PER_MESSAGE} ta boshqa mahsulot bor.\n\n"

    result += f"{VENU_CONTACT}"

    # Uzunlikni tekshirish
    if len(result) > MAX_MESSAGE_LENGTH:
        # Qisqartirish
        result = result[:MAX_MESSAGE_LENGTH - 100]
        result += f"\n\n...\n\n{VENU_CONTACT}"

    return result


def search_products(query: str) -> Dict:
    """
    Mahsulotlarni qidiradi va natijani qaytaradi
    """
    try:
        # 1. Kategoriya bo'yicha qidirish
        category, cat_score = find_category_by_name(query)

        if category and cat_score >= 70:
            # Kategoriyadan mahsulotlar
            category_products = Product.objects.filter(
                category_id=category.id
            ).exclude(current_stock__lte=0)[:10]

            products_list = []
            for product in category_products:
                products_list.append({
                    "name": clean_product_name(product.name),
                    "price": float(product.unit_price) if product.unit_price else 0,
                    "price_formatted": format_price(product.unit_price),
                    "stock": product.current_stock if product.current_stock else 0,
                    "details": product.details if product.details else "",
                    "category": category.name
                })

            return {
                "found": True,
                "products": products_list,
                "category_name": category.name,
                "total_count": len(category_products),
                "search_type": "category"
            }

        # 2. Mahsulot nomi bo'yicha qidirish
        search_results = find_products_by_query(query, limit=10)

        if search_results:
            products_list = []
            for item in search_results:
                product = item["product"]

                # Omborda yo'q mahsulotlarni o'tkazib yuborish
                if not product.current_stock or product.current_stock <= 0:
                    continue

                products_list.append({
                    "name": clean_product_name(product.name),
                    "price": float(product.unit_price) if product.unit_price else 0,
                    "price_formatted": format_price(product.unit_price),
                    "stock": product.current_stock,
                    "details": product.details if product.details else "",
                    "confidence": item["score"]
                })

            return {
                "found": True,
                "products": products_list,
                "total_count": len(products_list),
                "search_type": "product"
            }

        # Hech narsa topilmadi
        return {
            "found": False,
            "products": [],
            "total_count": 0,
            "search_type": "none"
        }

    except Exception as e:
        logging.error(f"❌ search_products error: {e}")
        return {
            "found": False,
            "products": [],
            "error": str(e)
        }


def get_ai_response(message: str) -> str:
    """
    Foydalanuvchi xabariga AI javob beradi
    """
    try:
        # Validatsiya
        if not message or len(message.strip()) < 1:
            return "😊 Savolingizni yozing"

        message = message.strip()

        # 1. Salom berish
        greetings = ["salom", "assalomu", "hello", "hi", "привет"]
        if any(word in message.lower() for word in greetings) and len(message) < 20:
            return (
                "Assalomu alaykum! 👋 VENU ga xush kelibsiz!\n\n"
                "Qanday mahsulot kerak? 📱💻"
            )

        # 2. Kontakt so'rash
        contact_words = ["aloqa", "telefon", "raqam", "manzil", "joylashuv", "contact"]
        if any(word in message.lower() for word in contact_words):
            return f"📞 Bizning kontaktlarimiz:\n\n{VENU_CONTACT}"

        # 3. Mahsulot qidirish
        product_keywords = ["kerak", "sotib", "narx", "qancha", "bor", "mavjud"]
        if any(word in message.lower() for word in product_keywords) or len(message) > 5:

            # Mahsulotlarni qidirish
            search_result = search_products(message)

            if search_result["found"] and search_result["products"]:
                # Mahsulotlar topildi - chiroyli ko'rsatish
                return format_products_for_display(search_result["products"], message)

            else:
                # Mahsulot topilmadi - QA dan qidirish
                qa_result = get_answer_from_file(message)

                if qa_result["found"] and qa_result["answer"]:
                    return f"✨ {qa_result['answer']}\n\n{VENU_CONTACT}"

                # Hech narsa topilmadi
                return (
                    "😔 Bu mahsulot topilmadi.\n\n"
                    "📋 Kategoriyalar: Noutbuk 💻, Smartfon 📱, Televizor 📺, Audio 🎧, Uy texnikasi 🏠\n\n"
                    f"{VENU_CONTACT}"
                )

        # 4. Boshqa savollar - QA fayldan qidirish
        qa_result = get_answer_from_file(message)

        if qa_result["found"] and qa_result["answer"]:
            return f"✨ {qa_result['answer']}\n\n{VENU_CONTACT}"

        # 5. Umumiy javob
        return (
            "🤔 Tushunmadim. Qanday mahsulot kerak?\n\n"
            f"{VENU_CONTACT}"
        )

    except Exception as e:
        logging.error(f"❌ get_ai_response error: {e}")
        return (
            "😓 Texnik xato. Operator bilan bog'laning:\n\n"
            f"{VENU_CONTACT}"
        )