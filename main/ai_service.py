# ai_service.py
import json
from openai import OpenAI
from typing import Dict, Any
from .utils import get_answer_from_file, get_products_from_db
from .config import SYSTEM_PROMPT, OPENAI_API_KEY

# OpenAI client
client = OpenAI(api_key=OPENAI_API_KEY)


def format_product_for_ai(product_data: Dict[str, Any]) -> str:
    """
    Mahsulot ma'lumotlarini AI uchun formatda tayyorlaydi.
    """
    result = f"Mahsulot: {product_data['name']}\n"
    result += f"Narxi: {product_data['price_formatted']}\n"

    if product_data.get('stock', 0) > 0:
        result += f"Omborda: {product_data['stock']} dona\n"
    else:
        result += "Omborda: Mavjud emas\n"

    if product_data.get('details'):
        details = product_data['details'][:200]
        if len(product_data['details']) > 200:
            details += "..."
        result += f"Tavsif: {details}\n"

    return result


def ask_ai(message: str) -> str:
    """
    Asosiy AI funksiyasi - mahsulotlarni chiroyli formatda taqdim etadi.
    """

    if not message or len(message.strip()) < 1:
        return "Iltimos, savolingizni yozing 😊"

    try:
        # AI ga savol yuborish
        response = client.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": message}
            ],
            tools=[
                {
                    "type": "function",
                    "function": {
                        "name": "get_products_from_db",
                        "description": "Database dan mahsulot/kategoriya qidiradi",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "query": {"type": "string", "description": "Mahsulot/kategoriya nomi"}
                            },
                            "required": ["query"]
                        }
                    }
                },
                {
                    "type": "function",
                    "function": {
                        "name": "get_answer_from_file",
                        "description": "VENU xizmatlari haqida ma'lumot",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "question": {"type": "string", "description": "Savol"}
                            },
                            "required": ["question"]
                        }
                    }
                }
            ],
            tool_choice="auto",
            temperature=0.7,
            max_tokens=300  # Qisqartildi: juda uzun javoblar uchun
        )

        response_message = response.choices[0].message
        tool_calls = response_message.tool_calls

        # Funksiya chaqirilganmi?
        if tool_calls:
            tool_call = tool_calls[0]
            function_name = tool_call.function.name
            function_args = json.loads(tool_call.function.arguments)

            # MAHSULOT QIDIRISH
            if function_name == "get_products_from_db":
                query = function_args.get("query", message)
                db_result = get_products_from_db(query)

                # Mahsulotlar topildi - AI ga chiroyli taqdim qilishni topshiramiz
                if db_result["found"] and db_result["products"]:
                    products_info = ""
                    for idx, product in enumerate(db_result["products"], 1):
                        products_info += f"\n{idx}. {format_product_for_ai(product)}\n"

                    context = f"""
Qidiruv: "{query}"
Topildi: {len(db_result['products'])} ta
Jami: {db_result['total_count']} ta
{f"Kategoriya: {db_result['category_name']}" if db_result['category_name'] else ""}

MAHSULOTLAR:
{products_info}
"""

                    # AI ga chiroyli formatda taqdim qilishni so'raymiz
                    final_response = client.chat.completions.create(
                        model="gpt-4",
                        messages=[
                            {"role": "system", "content": """Sen VENU yordamchisisisan.

Mahsulotlarni QISQA va CHIROYLI formatda taqdim et:

🎯 1-2 jumla kirish

📦 1. [Nomi]
   💰 [Narx]
   📊 [Ombor]

📦 2. [Nomi]
   💰 [Narx]
   📊 [Ombor]

JUDA QISQA bo'lsin!"""},
                            {"role": "user", "content": f"So'rov: {message}"},
                            {"role": "assistant", "content": f"Topilgan ma'lumotlar:\n{context}"},
                            {"role": "user", "content": "Bu ma'lumotlarni yuqoridagi formatda QISQA taqdim et!"}
                        ],
                        temperature=0.8,
                        max_tokens=400  # Qisqartildi: 1000 -> 400
                    )

                    return final_response.choices[0].message.content

                # Mahsulot topilmadi
                else:
                    fallback = client.chat.completions.create(
                        model="gpt-4",
                        messages=[
                            {"role": "system", "content": "Sen VENU yordamchisisisan."},
                            {"role": "user", "content": message},
                            {"role": "assistant", "content": f"'{query}' bo'yicha mahsulot topilmadi."},
                            {"role": "user",
                             "content": "Do'stona javob ber va kategoriyalar taklif qil: Smartfonlar, Noutbuklar, Televizorlar, Audiotexnika, Uy texnikasi. Faqat 2-3 jumla!"}
                        ],
                        temperature=0.8,
                        max_tokens=200  # Qisqartildi: 300 -> 200
                    )
                    return fallback.choices[0].message.content

            # VENU XIZMATLARI
            elif function_name == "get_answer_from_file":
                question = function_args.get("question", message)
                qa_result = get_answer_from_file(question)

                if qa_result["found"] and qa_result["answer"]:
                    final_response = client.chat.completions.create(
                        model="gpt-4",
                        messages=[
                            {"role": "system", "content": "Sen VENU yordamchisisisan."},
                            {"role": "user", "content": message},
                            {"role": "assistant", "content": qa_result['answer']},
                            {"role": "user",
                             "content": "Bu javobni QISQA va chiroyli formatda taqdim et. Maksimal 3-4 jumla!"}
                        ],
                        temperature=0.7,
                        max_tokens=300  # Qisqartildi: 500 -> 300
                    )
                    return final_response.choices[0].message.content

                else:
                    return "Kechirasiz, bu savol bo'yicha ma'lumot yo'q. Boshqa savol bering yoki qo'llab-quvvatlash xizmatiga murojaat qiling 📞"

        # AI o'zi javob berdi
        if response_message.content:
            return response_message.content

        return "Savolingizni tushunmadim. Qaytadan yozib ko'ring 🤔"

    except Exception as e:
        print(f"❌ AI error: {e}")
        return "Texnik muammo yuz berdi. Iltimos, keyinroq urinib ko'ring."