import json
import logging
import os
import time
import requests
from datetime import datetime
from django.http import HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from .ai_service import ask_ai  # ✅ ai_service dan import qildik
from .config import (
    ACCESS_TOKEN,
    VENU_PAGE_ID,
    WEBHOOK_VERIFY_TOKEN,
    CONVERSATIONS_DIR,
    MAX_HISTORY_LINES
)

# Duplicate messages cache
processed_messages = {}
MESSAGE_EXPIRY_TIME = 10  # seconds


def is_duplicate_message(sender_id, message_text):
    """
    Bir xil xabar 10 sekund ichida qayta kelsa, ignore qiladi
    """
    key = f"{sender_id}_{message_text}"
    current_time = time.time()

    # Eski xabarlarni tozalash
    expired_keys = [k for k, v in processed_messages.items() if current_time - v > MESSAGE_EXPIRY_TIME]
    for k in expired_keys:
        del processed_messages[k]

    # Duplicate check
    if key in processed_messages:
        print(f"⚠️ DUPLICATE MESSAGE IGNORED: {message_text[:50]}...")
        return True

    processed_messages[key] = current_time
    return False


def save_conversation(sender_id, sender_type, message_text):
    """
    Suhbatni faylga saqlash
    """
    try:
        os.makedirs(CONVERSATIONS_DIR, exist_ok=True)
        file_path = os.path.join(CONVERSATIONS_DIR, f"{VENU_PAGE_ID}_{sender_id}.txt")

        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        with open(file_path, "a", encoding="utf-8") as f:
            f.write(f"{timestamp} {sender_type}: {message_text}\n")

        print(f"✅ Conversation saved: {sender_type} - {message_text[:50]}")

    except Exception as e:
        logging.error(f"❌ save_conversation error: {e}")


def load_conversation(sender_id):
    """
    Suhbat tarixini yuklash (oxirgi N ta xabar)
    """
    try:
        file_path = os.path.join(CONVERSATIONS_DIR, f"{VENU_PAGE_ID}_{sender_id}.txt")

        if not os.path.exists(file_path):
            return []

        with open(file_path, "r", encoding="utf-8") as f:
            lines = f.readlines()

        # Oxirgi MAX_HISTORY_LINES ta xabar
        return lines[-MAX_HISTORY_LINES:] if len(lines) > MAX_HISTORY_LINES else lines

    except Exception as e:
        logging.error(f"❌ load_conversation error: {e}")
        return []


def send_instagram_message(recipient_id, message_text):
    """
    Instagram ga xabar yuborish
    """
    url = "https://graph.instagram.com/v21.0/me/messages"

    headers = {
        "Authorization": f"Bearer {ACCESS_TOKEN}",
        "Content-Type": "application/json"
    }

    # Xabar uzunligini tekshirish
    if len(message_text) > 800:
        print(f"⚠️ Message too long ({len(message_text)} chars), truncating...")
        message_text = message_text[:797] + "..."

    data = {
        "messaging_product": "instagram",
        "recipient": {"id": recipient_id},
        "message": {"text": message_text}
    }

    try:
        response = requests.post(url, headers=headers, json=data, timeout=10)

        if response.status_code == 200:
            print(f"✅ Message sent to {recipient_id} ({len(message_text)} chars)")
            return True
        else:
            print(f"❌ Instagram API Error {response.status_code}: {response.text}")
            logging.error(f"Instagram API Error: {response.status_code} - {response.text}")
            return False

    except Exception as e:
        logging.error(f"❌ send_instagram_message error: {e}")
        return False


@csrf_exempt
@require_http_methods(["GET", "POST"])
def webhook(request):
    """
    Instagram Webhook Handler
    """

    # GET - Webhook verification
    if request.method == "GET":
        mode = request.GET.get("hub.mode")
        token = request.GET.get("hub.verify_token")
        challenge = request.GET.get("hub.challenge")

        if mode == "subscribe" and token == WEBHOOK_VERIFY_TOKEN:
            print("✅ Webhook verified successfully")
            return HttpResponse(challenge, content_type="text/plain")
        else:
            print("❌ Webhook verification failed")
            return HttpResponse("Verification failed", status=403)

    # POST - Incoming messages
    elif request.method == "POST":
        try:
            data = json.loads(request.body)

            print(f"\n{'=' * 50}")
            print(f"📥 WEBHOOK RECEIVED")
            print(f"{'=' * 50}")
            print(json.dumps(data, indent=2, ensure_ascii=False))
            print(f"{'=' * 50}\n")

            # Process each entry
            for entry in data.get("entry", []):
                for messaging in entry.get("messaging", []):

                    sender_id = messaging["sender"]["id"]
                    recipient_id = messaging["recipient"]["id"]
                    message = messaging.get("message", {})

                    print(f"📨 Sender: {sender_id}, Recipient: {recipient_id}")

                    # Ignore echo messages (our own messages)
                    if message.get("is_echo"):
                        print("⏭️ Skipping echo message")
                        continue

                    # Handle text messages
                    if "text" in message:
                        message_text = message["text"].strip()

                        print(f"💬 User message: {message_text}")

                        # Duplicate check
                        if is_duplicate_message(sender_id, message_text):
                            continue

                        # Save user message
                        save_conversation(sender_id, "User", message_text)

                        # Get AI response (✅ user_id va receiver_id yuborildi)
                        print("🤖 Getting AI response...")
                        ai_response = ask_ai(message_text, sender_id, recipient_id)

                        print(f"✅ AI Response ({len(ai_response)} chars):\n{ai_response[:200]}...")

                        # Send response
                        send_instagram_message(sender_id, ai_response)

                        # Save AI response
                        save_conversation(sender_id, "AI", ai_response)

                    # Handle attachments
                    elif "attachments" in message:
                        print("📎 Attachment received (not supported)")

                        reply = (
                            "😊 Kechirasiz, faqat matn xabarlariga javob beraman.\n\n"
                            "Savolingizni matn ko'rinishida yuboring."
                        )

                        send_instagram_message(sender_id, reply)
                        save_conversation(sender_id, "AI", reply)

            return JsonResponse({"status": "received"}, status=200)

        except json.JSONDecodeError as e:
            logging.error(f"❌ JSON decode error: {e}")
            return JsonResponse({"error": "Invalid JSON"}, status=400)

        except Exception as e:
            logging.error(f"❌ Webhook error: {e}")
            return JsonResponse({"error": "Internal server error"}, status=500)

    return JsonResponse({"error": "Method not allowed"}, status=405)