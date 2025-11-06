"""
VENU AI Configuration
"""
import os

# ============================================
# OPENAI API SETTINGS
# ============================================
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "your-api-key-here")
AI_MODEL = "gpt-4"
AI_TEMPERATURE = 0.7

# AI javoblarini qisqartirish uchun
AI_MAX_TOKENS = 400  # Kamaytirildi: 1000 -> 400
MAX_MESSAGE_LENGTH = 800  # Kamaytirildi: uzunroq javoblarni qisqartiradi
MAX_PRODUCTS_PER_MESSAGE = 3  # Bir xabarda maksimal 3 ta mahsulot

# ============================================
# INSTAGRAM API SETTINGS
# ============================================
ACCESS_TOKEN = os.getenv("INSTAGRAM_ACCESS_TOKEN", "")
VENU_PAGE_ID = os.getenv("VENU_PAGE_ID", "")
WEBHOOK_VERIFY_TOKEN = os.getenv("WEBHOOK_VERIFY_TOKEN", "venu_webhook_2024")

# ============================================
# CONVERSATION SETTINGS
# ============================================
CONVERSATIONS_DIR = os.getenv("CONVERSATIONS_DIR", "conversations")
MAX_HISTORY_LINES = 10

# ============================================
# FASTAPI INTEGRATION
# ============================================
FASTAPI_BASE_URL = os.getenv("FASTAPI_URL", "http://localhost:8000")
API_URL_CATEGORIES = f"{FASTAPI_BASE_URL}/categories/"
API_URL_PRODUCTS = f"{FASTAPI_BASE_URL}/products/"

HEADERS = {
    "Content-Type": "application/json",
    "Accept": "application/json"
}

# ============================================
# SEARCH THRESHOLDS
# ============================================
CATEGORY_MATCH_THRESHOLD = 70
PRODUCT_MATCH_THRESHOLD = 60
QA_MATCH_THRESHOLD = 65
MAX_PRODUCTS_TO_SHOW = 10

# ============================================
# TEXT PROCESSING
# ============================================
UZBEK_SUFFIXES = [
    "lar", "lar", "dan", "dan", "ga", "ga", "ni", "ni",
    "ning", "ning", "da", "da", "mi", "mi", "chi", "chi"
]

STOP_WORDS = [
    "kerak", "bor", "yo'q", "yoq", "iltimos", "qanday",
    "qancha", "narxi", "nechta", "sotib", "olish"
]

# ============================================
# VENU CONTACT INFO
# ============================================
VENU_CONTACT = """
📞 Bizning kontaktlar:
• Telefon: +998 XX XXX XX XX
• Instagram: @venu.uz
• Ish vaqti: 9:00 - 20:00
""".strip()

# ============================================
# SYSTEM PROMPT - Qisqa javoblar uchun
# ============================================
SYSTEM_PROMPT = """Sen VENU marketplace yordamchisisisan.

MUHIM QOIDALAR:
1. Javoblarni QISQA va aniq ber (maksimal 3-4 jumla)
2. Faqat zarur ma'lumotni yoz
3. Mahsulotlar ro'yxati berishda maksimal 3 ta ko'rsat
4. Ortiqcha gapirma, to'g'ridan-to'g'ri javob ber
5. Emoji ishlatishda o'rtacha bo'l (1-2 ta)

Format:
- Salom: 2 jumla
- Mahsulot topilmasa: 2-3 jumla + kategoriyalar
- Mahsulot topilsa: Qisqa taqdimot + 3 ta mahsulot

Har doim qisqa va professional bo'l!
""".strip()
