import json
import re
import threading
from openai import OpenAI
from typing import Dict, Any, List, Optional
from .utils import get_answer_from_file, get_products_from_db, send_telegram_order_to_channel
from .config import SYSTEM_PROMPT, OPENAI_API_KEY, VENU_TELEGRAM_TOKEN, VENU_CHANNEL_ID

# OpenAI client
client = OpenAI(api_key=OPENAI_API_KEY)


def format_product_for_ai(product_data: Dict[str, Any]) -> str:
    """Mahsulot ma'lumotlarini AI uchun formatda tayyorlaydi."""
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


def build_conversation_context(sender_id):
    """Fayldan suhbat tarixini o'qib, AI uchun context yaratadi"""
    import os
    from .config import CONVERSATIONS_DIR, VENU_PAGE_ID

    try:
        file_path = os.path.join(CONVERSATIONS_DIR, f"{VENU_PAGE_ID}_{sender_id}.txt")

        if not os.path.exists(file_path):
            return []

        with open(file_path, "r", encoding="utf-8") as f:
            lines = f.readlines()

        # Oxirgi 20 ta xabarni olish
        recent_lines = lines[-20:] if len(lines) > 20 else lines

        # AI uchun context formatga o'tkazish
        messages = []
        for line in recent_lines:
            line = line.strip()
            if not line:
                continue

            if " User:" in line or " Client:" in line:
                text = line.split("User:")[-1].split("Client:")[-1].strip()
                messages.append({"role": "user", "content": text})
            elif " AI:" in line:
                text = line.split("AI:")[-1].strip()
                messages.append({"role": "assistant", "content": text})

        return messages

    except Exception as e:
        print(f"❌ Context yuklashda xatolik: {e}")
        return []


def extract_number_from_message(message: str) -> Optional[int]:
    """Xabardan mahsulot raqamini ajratib oladi"""
    message_lower = message.lower().strip()

    # Turli formatdagi raqamlar
    patterns = {
        1: [r'\b1\b', "1-chi", "1 chi", "1-ni", "1chi", "birinchi", "bitta", "1-dagi"],
        2: [r'\b2\b', "2-chi", "2 chi", "2-ni", "2chi", "ikkinchi", "ikkita", "2-dagi"],
        3: [r'\b3\b', "3-chi", "3 chi", "3-ni", "3chi", "uchinchi", "uchta", "3-dagi"],
        4: [r'\b4\b', "4-chi", "4 chi", "4-ni", "4chi", "to'rtinchi", "to'rtta", "4-dagi", "tortinchi"],
        5: [r'\b5\b', "5-chi", "5 chi", "5-ni", "5chi", "beshinchi", "beshta", "5-dagi"]
    }

    for num, keywords in patterns.items():
        for keyword in keywords:
            if keyword.startswith(r'\b'):
                if re.search(keyword, message_lower):
                    return num
            else:
                if keyword in message_lower:
                    return num

    return None


def find_last_product_list(conversation_history: List[Dict]) -> Optional[str]:
    """Oxirgi mahsulot ro'yxatini topadi"""
    try:
        ai_messages = [msg for msg in reversed(conversation_history) if msg["role"] == "assistant"][:5]

        for msg in ai_messages:
            content = msg["content"]

            has_product_emoji = "📦" in content
            has_question = "Qaysini tanlaysiz?" in content or "😊" in content
            product_count = content.count("📦")

            if has_product_emoji and has_question and product_count >= 3:
                print(f"✅ Oxirgi mahsulot ro'yxati topildi ({product_count} ta mahsulot)")
                return content

        print(f"❌ Mahsulot ro'yxati topilmadi")
        return None

    except Exception as e:
        print(f"❌ find_last_product_list xatolik: {e}")
        return None


def extract_product_from_list(product_list: str, product_number: int) -> Optional[str]:
    """Mahsulot ro'yxatidan ma'lum raqamdagi mahsulotni ajratib oladi"""
    try:
        lines = product_list.split("\n")

        for i, line in enumerate(lines):
            if f"📦 {product_number}." in line:
                product_name = line.split(f"📦 {product_number}.")[1].strip()

                if "💰" in product_name:
                    product_name = product_name.split("💰")[0].strip()
                if "   " in product_name:
                    product_name = product_name.split("   ")[0].strip()

                product_name = product_name.strip()

                if product_name:
                    print(f"✅ {product_number}-chi mahsulot: {product_name}")
                    return product_name

        print(f"❌ {product_number}-chi mahsulot topilmadi")
        return None

    except Exception as e:
        print(f"❌ extract_product_from_list xatolik: {e}")
        return None


def is_product_selection(message: str, conversation_history: List[Dict]) -> bool:
    """User mahsulot tanlayotganini tekshiradi"""
    try:
        message_lower = message.lower().strip()

        # 1. Raqam bormi?
        number = extract_number_from_message(message)
        if not number:
            print(f"❌ is_product_selection: Raqam yo'q")
            return False

        # 2. Mahsulot ro'yxati bormi?
        product_list = find_last_product_list(conversation_history)
        if not product_list:
            print(f"❌ is_product_selection: Product list yo'q")
            return False

        # 3. Tanlash iboralari yoki faqat raqam
        selection_keywords = [
            "chi", "ni", "dagi", "dagini", "olaman", "kerak", "tanladim",
            "tanlash", "san bergan", "bergan"
        ]

        has_selection_keyword = any(kw in message_lower for kw in selection_keywords)
        is_just_number = message.strip() in ["1", "2", "3", "4", "5"]

        result = has_selection_keyword or is_just_number

        print(f"\n{'=' * 60}")
        print(f"🔍 MAHSULOT TANLASH TEKSHIRUVI")
        print(f"Message: {message}")
        print(f"Raqam: {number} ✅")
        print(f"Product list: ✅")
        print(f"Selection keywords: {'✅' if has_selection_keyword else '❌'}")
        print(f"Just number: {'✅' if is_just_number else '❌'}")
        print(f"NATIJA: {'✅ MAHSULOT TANLASH' if result else '❌ BOSHQA'}")
        print(f"{'=' * 60}\n")

        return result

    except Exception as e:
        print(f"❌ is_product_selection xatolik: {e}")
        return False


def ask_ai(message: str, user_id: str = None, receiver_id: str = None) -> str:
    """MUKAMMAL AI - Context'dan maksimal foydalanadi"""

    if not message or len(message.strip()) < 1:
        return "Iltimos, savolingizni yozing 😊"

    try:
        # Context yuklash
        conversation_history = build_conversation_context(user_id) if user_id else []

        print(f"\n{'=' * 70}")
        print(f"💬 USER: {message}")
        print(f"📚 History: {len(conversation_history)} messages")
        print(f"{'=' * 70}\n")

        # ========================================
        # 1. MAHSULOT TANLASH (BIRINCHI TEKSHIRISH!)
        # ========================================
        if is_product_selection(message, conversation_history):
            number = extract_number_from_message(message)
            product_list = find_last_product_list(conversation_history)

            if number and product_list:
                product_name = extract_product_from_list(product_list, number)

                if product_name:
                    print(f"✅ MAHSULOT TANLANDI: {product_name}")
                    return f"Ajoyib! {product_name} ni tanladingiz. 😊\n\nIsmingiz?"
                else:
                    return f"❌ {number}-chi mahsulotni topolmadim. Iltimos, qaytadan tanlang."

        # ========================================
        # 2. STANDART AI JAVOBI
        # ========================================

        system_message = {
            "role": "system",
            "content": """Sen VENU marketplace yordamchisisisan. Do'stona va professional bo'l.

QOIDALAR:
1. UMUMIY SAVOLLAR ("qanday mahsulotlar bor?") → O'zing javob ber:
   "VENU - texnika marketplace! 🛍

   Bizda mavjud:
   📱 Smartfonlar (Samsung, iPhone, Xiaomi...)
   💻 Noutbuklar (ASUS, HP, Lenovo, Dell...)
   📺 Televizorlar (Samsung, LG, Sony...)
   🎧 Audio texnika
   🏠 Uy texnikasi

   Qaysi kategoriyadan qidirayapsiz?"

2. KATEGORIYA/BREND ("Noutbuk", "iPhone", "Samsung") → get_products_from_db chaqir

3. LEAD YARATISH → register_lead chaqir (barcha ma'lumotlar to'planganda)

MUHIM:
- Qisqa javob (2-4 jumla)
- 1-2 ta emoji
- Context'ni eslab tur"""
        }

        messages = [system_message]
        messages.extend(conversation_history)
        messages.append({"role": "user", "content": message})

        response = client.chat.completions.create(
            model="gpt-4",
            messages=messages,
            tools=[
                {
                    "type": "function",
                    "function": {
                        "name": "get_products_from_db",
                        "description": "Database dan mahsulot qidiradi (kategoriya yoki brend bo'yicha)",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "query": {"type": "string",
                                          "description": "Qidiruv so'rovi (kategoriya yoki brend nomi)"}
                            },
                            "required": ["query"]
                        }
                    }
                },
                {
                    "type": "function",
                    "function": {
                        "name": "get_answer_from_file",
                        "description": "VENU xizmatlari haqida ma'lumot (QA faylidan)",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "question": {"type": "string"}
                            },
                            "required": ["question"]
                        }
                    }
                },
                {
                    "type": "function",
                    "function": {
                        "name": "register_lead",
                        "description": "Lead yaratish (ism, telefon, mahsulot, vaqt to'planganda)",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "full_name": {"type": "string"},
                                "phone_number": {"type": "string"},
                                "product_name": {"type": "string"},
                                "call_time": {"type": "string"}
                            },
                            "required": ["full_name", "phone_number", "product_name", "call_time"]
                        }
                    }
                }
            ],
            tool_choice="auto",
            temperature=0.7,
            max_tokens=500
        )

        response_message = response.choices[0].message
        tool_calls = response_message.tool_calls

        if tool_calls:
            tool_call = tool_calls[0]
            function_name = tool_call.function.name
            function_args = json.loads(tool_call.function.arguments)

            # MAHSULOT QIDIRISH
            if function_name == "get_products_from_db":
                query = function_args.get("query", message)

                print(f"🔍 get_products_from_db chaqirildi: {query}")

                db_result = get_products_from_db(query)

                if db_result["found"] and db_result["products"]:
                    products_info = ""
                    for idx, product in enumerate(db_result["products"], 1):
                        products_info += f"\n{idx}. {format_product_for_ai(product)}\n"

                    context = f"Qidiruv: \"{query}\"\nTopildi: {len(db_result['products'])} ta\n\nMAHSULOTLAR:\n{products_info}"

                    final_response = client.chat.completions.create(
                        model="gpt-4",
                        messages=[
                            {
                                "role": "system",
                                "content": """Mahsulotlarni QISQA formatda ko'rsat:

📦 1. [Nomi]
   💰 [Narx]
   📊 [Ombor]

OXIRIDA: "😊 Qaysini tanlaysiz?" yoz!"""
                            },
                            {"role": "user", "content": f"Topilgan:\n{context}"},
                        ],
                        temperature=0.8,
                        max_tokens=400
                    )

                    return final_response.choices[0].message.content
                else:
                    return (
                        f"😔 '{query}' bo'yicha mahsulot topilmadi.\n\n"
                        f"Boshqa kategoriya tanlang:\n"
                        f"📱 Smartfon | 💻 Noutbuk | 📺 Televizor"
                    )

            # VENU XIZMATLARI
            elif function_name == "get_answer_from_file":
                question = function_args.get("question", message)
                qa_result = get_answer_from_file(question)

                if qa_result["found"] and qa_result["answer"]:
                    return f"✨ {qa_result['answer'][:300]}"
                else:
                    return "Bu savol bo'yicha ma'lumot yo'q. Qo'llab-quvvatlash: +998334004443 📞"

            # LEAD YARATISH
            elif function_name == "register_lead":
                full_name = function_args.get("full_name", "").strip()
                phone_number = function_args.get("phone_number", "").strip()
                product_name_from_ai = function_args.get("product_name", "").strip()
                call_time = function_args.get("call_time", "").strip()

                # Context'dan aniq nomni olish
                product_name = product_name_from_ai

                product_list = find_last_product_list(conversation_history)
                if product_list:
                    for msg in reversed(conversation_history[-5:]):
                        if msg["role"] == "user":
                            num = extract_number_from_message(msg["content"])
                            if num:
                                found_product = extract_product_from_list(product_list, num)
                                if found_product:
                                    product_name = found_product
                                    break

                # Validatsiya
                if not full_name:
                    return "❌ Ismingizni kiriting."
                if not phone_number:
                    return "❌ Telefon raqamingizni kiriting."
                if not product_name:
                    return "❌ Qaysi mahsulot kerakligini aniq ayting."
                if not call_time:
                    return "❌ Qachon qo'ng'iroq qilishimizni ayting."

                # Telefon formatlash
                if not phone_number.startswith("+998"):
                    phone_number = phone_number.replace(" ", "").replace("-", "").replace("(", "").replace(")", "")
                    if phone_number.startswith("998"):
                        phone_number = "+" + phone_number
                    elif len(phone_number) == 9:
                        phone_number = "+998" + phone_number

                # Telegram ga yuborish
                msg = (
                    f"🎯 YANGI LEAD - VENU\n\n"
                    f"👤 Ism: {full_name}\n"
                    f"📱 Telefon: {phone_number}\n"
                    f"🛒 Mahsulot: {product_name}\n"
                    f"⏰ Qo'ng'iroq vaqti: {call_time}\n"
                )

                if user_id and receiver_id:
                    threading.Thread(
                        target=send_telegram_order_to_channel,
                        args=(VENU_TELEGRAM_TOKEN, VENU_CHANNEL_ID, msg, user_id, receiver_id)
                    ).start()

                return (
                    f"✅ Ajoyib, {full_name}!\n\n"
                    f"Buyurtmangiz qabul qilindi:\n"
                    f"📦 {product_name}\n"
                    f"⏰ Qo'ng'iroq: {call_time}\n\n"
                    f"Operatorimiz bog'lanadi! 📞"
                )

        # AI o'zi javob berdi
        if response_message.content:
            return response_message.content

        return "Savolingizni tushunmadim 🤔"

    except Exception as e:
        print(f"❌ AI error: {e}")
        import traceback
        traceback.print_exc()
        return "Texnik muammo yuz berdi. Keyinroq urinib ko'ring."