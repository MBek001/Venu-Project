import json
import threading
from openai import OpenAI
from typing import Dict, Any
from .utils import get_answer_from_file, get_products_from_db, send_telegram_order_to_channel
from .config import SYSTEM_PROMPT, OPENAI_API_KEY, VENU_TELEGRAM_TOKEN, VENU_CHANNEL_ID

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


def build_conversation_context(sender_id):
    """
    Fayldan suhbat tarixini o'qib, AI uchun context yaratadi
    """
    import os
    from .config import CONVERSATIONS_DIR, VENU_PAGE_ID

    try:
        file_path = os.path.join(CONVERSATIONS_DIR, f"{VENU_PAGE_ID}_{sender_id}.txt")

        if not os.path.exists(file_path):
            return []

        with open(file_path, "r", encoding="utf-8") as f:
            lines = f.readlines()

        # Oxirgi 10 ta xabarni olish
        recent_lines = lines[-10:] if len(lines) > 10 else lines

        # AI uchun context formatga o'tkazish
        messages = []
        for line in recent_lines:
            line = line.strip()
            if not line:
                continue

            # Timestamp'ni olib tashlash
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


def extract_product_from_context(conversation_history, user_message):
    """
    Context'dan tanlangan mahsulot nomini topadi
    """
    try:
        # Oxirgi AI xabaridan mahsulot ro'yxatini topish
        for msg in reversed(conversation_history):
            if msg["role"] == "assistant" and "📦" in msg["content"]:
                lines = msg["content"].split("\n")

                # Raqamni topish (1-chi, 5-chi, 2-chi)
                user_choice = user_message.lower().strip()

                # Raqamni ajratib olish
                choice_num = None
                if "1" in user_choice or "birinchi" in user_choice or "1-chi" in user_choice:
                    choice_num = 1
                elif "2" in user_choice or "ikkinchi" in user_choice or "2-chi" in user_choice:
                    choice_num = 2
                elif "3" in user_choice or "uchinchi" in user_choice or "3-chi" in user_choice:
                    choice_num = 3
                elif "4" in user_choice or "to'rtinchi" in user_choice or "4-chi" in user_choice:
                    choice_num = 4
                elif "5" in user_choice or "beshinchi" in user_choice or "5-chi" in user_choice:
                    choice_num = 5

                if choice_num:
                    # Tanlangan mahsulotni topish
                    for line in lines:
                        if f"📦 {choice_num}." in line:
                            # Mahsulot nomini ajratib olish
                            product_name = line.split(f"📦 {choice_num}.")[1].strip()
                            # Emoji va ortiqcha belgilarni tozalash
                            product_name = product_name.split("   ")[0].strip()
                            return product_name

                break

        return None

    except Exception as e:
        print(f"❌ Mahsulot nomini topishda xatolik: {e}")
        return None


def ask_ai(message: str, user_id: str = None, receiver_id: str = None) -> str:
    """
    Asosiy AI funksiyasi - context'ni eslab turadi va lead yaratadi.
    """

    if not message or len(message.strip()) < 1:
        return "Iltimos, savolingizni yozing 😊"

    try:
        # Context yuklash (oldingi suhbat)
        conversation_history = build_conversation_context(user_id) if user_id else []

        # System prompt
        system_message = {
            "role": "system",
            "content": """Sen VENU marketplace yordamchisisisan. Do'stona va professional bo'l.

═══════════════════════════════════════
🎯 ASOSIY QOIDALAR
═══════════════════════════════════════

1. UMUMIY SAVOLLAR ("Qanday mahsulotlar bor?", "Nima sotasiz?")
   → Funksiya chaqirma! O'zing javob ber:
   "VENU - texnika marketplace! 🛍

   Bizda mavjud:
   📱 Smartfonlar (Samsung, iPhone, Xiaomi, Realme...)
   💻 Noutbuklar (ASUS, HP, Lenovo, Dell, Acer...)
   📺 Televizorlar (Samsung, LG, Sony...)
   🎧 Audio texnika (Airpods, JBL, Sony...)
   🏠 Uy texnikasi

   Qaysi kategoriyadan qidirayapsiz?"

2. KATEGORIYA SAVOLLARI ("Noutbuk kerak", "Telefon bor?")
   → Funksiya chaqirma! Aniq parametrlarni so'ra:

   Noutbuk uchun: "Qaysi brend? (ASUS, HP, Lenovo...) va qancha RAM kerak? (8GB, 16GB...)"
   Telefon uchun: "Qaysi brend va model? (Samsung A54, iPhone 15, Xiaomi 13...)"

3. ANIQ SO'ROV ("Samsung A54", "ASUS Vivobook 16")
   → get_products_from_db chaqir va mahsulotlarni ko'rsat

4. MAHSULOT TANLASH ("5-chisi", "1-chini olaman")
   → Context'dan mahsulot nomini top
   → "Ajoyib! [ANIQ MAHSULOT NOMI] ni tanladingiz. Ismingiz?"

5. LEAD YARATISH
   → Ism + Telefon + Mahsulot + Vaqt to'plangandan keyin register_lead chaqir
   → Mahsulot nomini CONTEXT'dan ANIQ olib, noto'g'ri nom yozma!

═══════════════════════════════════════

MUHIM:
- Context'ni eslab tur!
- Mahsulot nomini o'zgartirma, context'dagi aniq nomni ishla!
- Qisqa javob ber (2-4 jumla)
- 1-2 ta emoji"""
        }

        # Messages list
        messages = [system_message]
        messages.extend(conversation_history)
        messages.append({"role": "user", "content": message})

        # AI ga savol yuborish
        response = client.chat.completions.create(
            model="gpt-4",
            messages=messages,
            tools=[
                {
                    "type": "function",
                    "function": {
                        "name": "get_products_from_db",
                        "description": "Database dan mahsulot qidiradi. FAQAT aniq brend/model kiritilganda chaqir! (Samsung A54, ASUS Vivobook, iPhone 15...)",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "query": {"type": "string", "description": "Aniq mahsulot/brend nomi"}
                            },
                            "required": ["query"]
                        }
                    }
                },
                {
                    "type": "function",
                    "function": {
                        "name": "get_answer_from_file",
                        "description": "VENU xizmatlari haqida ma'lumot (kafolat, yetkazib berish, to'lov)",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "question": {"type": "string", "description": "Savol"}
                            },
                            "required": ["question"]
                        }
                    }
                },
                {
                    "type": "function",
                    "function": {
                        "name": "register_lead",
                        "description": "Lead yaratish. FAQAT barcha ma'lumotlar to'planganda chaqir!",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "full_name": {"type": "string", "description": "Mijoz ismi"},
                                "phone_number": {"type": "string", "description": "Telefon (+998...)"},
                                "product_name": {"type": "string",
                                                 "description": "Tanlangan mahsulot ANIQ NOMI (context'dan ol!)"},
                                "call_time": {"type": "string", "description": "Qo'ng'iroq vaqti"}
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

        # Funksiya chaqirilganmi?
        if tool_calls:
            tool_call = tool_calls[0]
            function_name = tool_call.function.name
            function_args = json.loads(tool_call.function.arguments)

            # ========================================
            # 1. MAHSULOT QIDIRISH
            # ========================================
            if function_name == "get_products_from_db":
                query = function_args.get("query", message)
                db_result = get_products_from_db(query)

                # Mahsulotlar topildi
                if db_result["found"] and db_result["products"]:
                    products_info = ""
                    for idx, product in enumerate(db_result["products"], 1):
                        products_info += f"\n{idx}. {format_product_for_ai(product)}\n"

                    context = f"""
Qidiruv: "{query}"
Topildi: {len(db_result['products'])} ta

MAHSULOTLAR:
{products_info}
"""

                    # AI ga javob berish uchun qayta so'rov
                    final_response = client.chat.completions.create(
                        model="gpt-4",
                        messages=[
                            {
                                "role": "system",
                                "content": """Mahsulotlarni QISQA formatda ko'rsat:

📦 1. [Nomi]
   💰 [Narx]
   📊 [Ombor]

📦 2. [Nomi]
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

                # Mahsulot topilmadi
                else:
                    return (
                        "😔 Bu so'rov bo'yicha mahsulot topilmadi.\n\n"
                        "Aniqroq yozing (Samsung A54, ASUS Vivobook 16, iPhone 15...)"
                    )

            # ========================================
            # 2. VENU XIZMATLARI
            # ========================================
            elif function_name == "get_answer_from_file":
                question = function_args.get("question", message)
                qa_result = get_answer_from_file(question)

                if qa_result["found"] and qa_result["answer"]:
                    return f"✨ {qa_result['answer'][:300]}"
                else:
                    return "Bu savol bo'yicha ma'lumot yo'q. Qo'llab-quvvatlash: +998334004443 📞"

            # ========================================
            # 3. LEAD YARATISH
            # ========================================
            elif function_name == "register_lead":
                full_name = function_args.get("full_name", "").strip()
                phone_number = function_args.get("phone_number", "").strip()
                product_name_from_ai = function_args.get("product_name", "").strip()
                call_time = function_args.get("call_time", "").strip()

                # Context'dan mahsulot nomini olish (AI noto'g'ri yozgan bo'lishi mumkin)
                actual_product = extract_product_from_context(conversation_history, message)
                if actual_product:
                    product_name = actual_product
                    print(f"✅ Mahsulot nomi context'dan olindi: {product_name}")
                else:
                    product_name = product_name_from_ai
                    print(f"⚠️ Context'da topilmadi, AI yozgan nomi ishlatildi: {product_name}")

                # Validatsiya
                if not full_name:
                    return "❌ Ismingizni kiriting."

                if not phone_number:
                    return "❌ Telefon raqamingizni kiriting."

                if not product_name:
                    return "❌ Qaysi mahsulot kerakligini aniq ayting."

                if not call_time:
                    return "❌ Qachon qo'ng'iroq qilishimizni ayting."

                # Telefon raqamni formatlash
                if not phone_number.startswith("+998"):
                    phone_number = phone_number.replace(" ", "").replace("-", "").replace("(", "").replace(")", "")
                    if phone_number.startswith("998"):
                        phone_number = "+" + phone_number
                    elif len(phone_number) == 9:
                        phone_number = "+998" + phone_number
                    else:
                        return "❌ Telefon raqam noto'g'ri. +998XXXXXXXXX formatida yuboring."

                # Telegram kanalga yuborish
                msg = (
                    f"🎯 YANGI LEAD - VENU\n\n"
                    f"👤 Ism: {full_name}\n"
                    f"📱 Telefon: {phone_number}\n"
                    f"🛒 Mahsulot: {product_name}\n"
                    f"⏰ Qo'ng'iroq vaqti: {call_time}\n"
                )

                # Background thread da yuborish
                if user_id and receiver_id:
                    threading.Thread(
                        target=send_telegram_order_to_channel,
                        args=(VENU_TELEGRAM_TOKEN, VENU_CHANNEL_ID, msg, user_id, receiver_id)
                    ).start()

                    print(f"✅ LEAD CREATED: {full_name} - {phone_number} - {product_name}")
                else:
                    print(f"⚠️ user_id yoki receiver_id yo'q, Telegram ga yuborilmadi")

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