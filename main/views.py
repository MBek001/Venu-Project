# views.py
import os
from datetime import datetime
from django.shortcuts import render
from django.http import JsonResponse
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from .ai_service import ask_ai
from .models import Category, Product
from .utils import fetch_and_save_categories, fetch_and_save_products
from .config import CONVERSATIONS_DIR, VENU_PAGE_ID


# ============================================
# CONVERSATION VIEWS (YANGI!)
# ============================================


class ConversationView(APIView):
    """
    Conversation suhbatlarini ko'rsatish uchun view
    """

    def get(self, request):
        user_id = request.GET.get('user_id')
        receiver_id = request.GET.get('receiver_id', VENU_PAGE_ID)
        format_type = request.GET.get('format', 'html')

        print(f"\n{'=' * 60}")
        print(f"📥 CONVERSATION REQUEST")
        print(f"{'=' * 60}")
        print(f"User ID: {user_id}")
        print(f"Receiver ID: {receiver_id}")
        print(f"Format: {format_type}")
        print(f"{'=' * 60}\n")

        # Validatsiya
        if not user_id:
            if format_type == 'json':
                return Response({
                    "error": "user_id parameter kerak"
                }, status=status.HTTP_400_BAD_REQUEST)
            else:
                return render(request, 'conversation.html', {
                    'error': 'user_id parameter kerak',
                    'chat_lines': [],
                    'user_id': 'Unknown'
                })

        try:
            # Conversation faylini o'qish
            chat_lines = self._read_conversation(receiver_id, user_id)

            print(f"✅ {len(chat_lines)} ta xabar qaytarildi\n")

            # JSON formatda qaytarish
            if format_type == 'json':
                return Response({
                    "success": True,
                    "user_id": user_id,
                    "receiver_id": receiver_id,
                    "total_messages": len(chat_lines),
                    "messages": chat_lines
                }, status=status.HTTP_200_OK)

            # HTML formatda qaytarish
            return render(request, 'conversation.html', {
                'chat_lines': chat_lines,
                'user_id': user_id,
                'receiver_id': receiver_id,
                'total_messages': len(chat_lines)
            })

        except Exception as e:
            print(f"❌ ConversationView error: {e}")
            import traceback
            traceback.print_exc()

            if format_type == 'json':
                return Response({
                    "error": "Suhbatni yuklashda xatolik",
                    "details": str(e)
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            else:
                return render(request, 'conversation.html', {
                    'error': f'Xatolik: {str(e)}',
                    'chat_lines': [],
                    'user_id': user_id
                })

    def _read_conversation(self, receiver_id, user_id):
        """
        Conversation faylidan suhbatni o'qish
        """
        try:
            # File path yaratish
            file_path = os.path.join(CONVERSATIONS_DIR, f"{receiver_id}_{user_id}.txt")

            print(f"📂 Fayl yo'li: {file_path}")
            print(f"📂 CONVERSATIONS_DIR: {CONVERSATIONS_DIR}")

            # Katalog mavjudligini tekshirish
            if not os.path.exists(CONVERSATIONS_DIR):
                print(f"❌ Katalog mavjud emas: {CONVERSATIONS_DIR}")
                return []

            # Fayl mavjudligini tekshirish
            if not os.path.exists(file_path):
                print(f"❌ Fayl topilmadi: {file_path}")
                print(f"📋 Mavjud fayllar:")
                try:
                    files = os.listdir(CONVERSATIONS_DIR)
                    for f in files:
                        print(f"   - {f}")
                except Exception as list_error:
                    print(f"❌ Fayllarni ko'rsatishda xatolik: {list_error}")
                return []

            print(f"✅ Fayl topildi, o'qilmoqda...")

            chat_lines = []
            last_date = None
            line_count = 0

            with open(file_path, "r", encoding="utf-8") as f:
                for line in f:
                    line_count += 1
                    line = line.strip()

                    if not line:
                        continue

                    print(f"📝 Line {line_count}: {line[:100]}...")

                    # Parse qilish: "2025-11-07 15:30:45 User: Salom"
                    try:
                        # Timestamp va qolgan qismni ajratish
                        parts = line.split(' ', 2)  # Max 3 qismga bo'lish

                        if len(parts) < 3:
                            print(f"⚠️ Line {line_count}: Kam qism ({len(parts)} ta)")
                            continue

                        date_str = parts[0]  # 2025-11-07
                        time_str = parts[1]  # 15:30:45
                        rest = parts[2]  # User: Salom

                        print(f"   Date: {date_str}, Time: {time_str}, Rest: {rest[:50]}...")

                        # Role va message ni ajratish
                        role = None
                        message = None

                        if 'User:' in rest:
                            role = 'client'
                            message = rest.split('User:', 1)[1].strip()
                        elif 'Client:' in rest:
                            role = 'client'
                            message = rest.split('Client:', 1)[1].strip()
                        elif 'AI:' in rest:
                            role = 'ai'
                            message = rest.split('AI:', 1)[1].strip()
                        elif 'Operator:' in rest:
                            role = 'operator'
                            message = rest.split('Operator:', 1)[1].strip()
                        else:
                            print(f"⚠️ Line {line_count}: Role topilmadi")
                            continue

                        print(f"   Role: {role}, Message: {message[:50]}...")

                        # Timestamp formatlash
                        timestamp = f"{date_str} {time_str[:5]}"

                        # Sanani ko'rsatish kerakmi?
                        show_date = (last_date != date_str)
                        last_date = date_str

                        chat_lines.append({
                            "role": role,
                            "message": message,
                            "timestamp": timestamp,
                            "date": date_str,
                            "time": time_str[:5],
                            "show_date": show_date
                        })

                        print(f"   ✅ Qo'shildi (jami: {len(chat_lines)})")

                    except Exception as parse_error:
                        print(f"❌ Line {line_count} parse error: {parse_error}")
                        continue

            print(f"\n✅ Jami {len(chat_lines)} ta xabar o'qildi ({line_count} ta qatordan)\n")
            return chat_lines

        except Exception as e:
            print(f"❌ _read_conversation error: {e}")
            import traceback
            traceback.print_exc()
            return []

class ConversationListView(APIView):
    """
    Barcha conversations ro'yxatini ko'rsatish

    Usage:
    - HTML: /conversations/
    - JSON: /conversations/?format=json
    """

    def get(self, request):
        format_type = request.GET.get('format', 'html')

        try:
            conversations = self._get_all_conversations()

            if format_type == 'json':
                return Response({
                    "success": True,
                    "total_conversations": len(conversations),
                    "conversations": conversations
                }, status=status.HTTP_200_OK)
            else:
                return render(request, 'conversation_list.html', {
                    'conversations': conversations,
                    'total_conversations': len(conversations)
                })

        except Exception as e:
            print(f"❌ ConversationListView error: {e}")

            if format_type == 'json':
                return Response({
                    "error": "Conversations ro'yxatini yuklashda xatolik",
                    "details": str(e)
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            else:
                return render(request, 'conversation_list.html', {
                    'error': str(e),
                    'conversations': []
                })

    def _get_all_conversations(self):
        """
        Barcha conversation fayllarini o'qish

        Returns:
        [
            {
                "user_id": "123456",
                "receiver_id": "17841476420904341",
                "last_message": "Rahmat",
                "last_timestamp": "2025-11-07 15:30",
                "total_messages": 15,
                "file_path": "17841476420904341_123456.txt"
            }
        ]
        """
        try:
            if not os.path.exists(CONVERSATIONS_DIR):
                os.makedirs(CONVERSATIONS_DIR, exist_ok=True)
                return []

            conversations = []

            # Barcha .txt fayllarni o'qish
            for filename in os.listdir(CONVERSATIONS_DIR):
                if not filename.endswith('.txt'):
                    continue

                # Filename parse: "receiver_user.txt"
                try:
                    name_parts = filename.replace('.txt', '').split('_')
                    if len(name_parts) != 2:
                        continue

                    receiver_id = name_parts[0]
                    user_id = name_parts[1]

                    file_path = os.path.join(CONVERSATIONS_DIR, filename)

                    # Fayldan oxirgi xabarni o'qish
                    with open(file_path, 'r', encoding='utf-8') as f:
                        lines = f.readlines()

                    total_messages = len([l for l in lines if l.strip()])

                    # Oxirgi xabar
                    last_line = None
                    for line in reversed(lines):
                        if line.strip():
                            last_line = line.strip()
                            break

                    if last_line:
                        # Parse: "2025-11-07 15:30:45 User: Salom"
                        parts = last_line.split(' ', 2)
                        if len(parts) >= 3:
                            date_str = parts[0]
                            time_str = parts[1]
                            rest = parts[2]

                            # Message
                            if ':' in rest:
                                last_message = rest.split(':', 1)[1].strip()
                            else:
                                last_message = rest

                            last_timestamp = f"{date_str} {time_str[:5]}"
                        else:
                            last_message = "..."
                            last_timestamp = "Unknown"
                    else:
                        last_message = ""
                        last_timestamp = ""

                    # File modification time
                    file_mtime = os.path.getmtime(file_path)
                    file_date = datetime.fromtimestamp(file_mtime)

                    conversations.append({
                        "user_id": user_id,
                        "receiver_id": receiver_id,
                        "last_message": last_message[:100],  # Birinchi 100 ta belgi
                        "last_timestamp": last_timestamp,
                        "total_messages": total_messages,
                        "file_path": filename,
                        "file_date": file_date.strftime("%Y-%m-%d %H:%M")
                    })

                except Exception as file_error:
                    print(f"⚠️ File parse error: {file_error} | File: {filename}")
                    continue

            # Oxirgi xabarga qarab saralash (eng yangi birinchi)
            conversations.sort(key=lambda x: x.get('file_date', ''), reverse=True)

            return conversations

        except Exception as e:
            print(f"❌ _get_all_conversations error: {e}")
            import traceback
            traceback.print_exc()
            return []


# ============================================
# CHATBOT API (MAVJUD)
# ============================================

class ChatAPIView(APIView):
    """Chatbot API endpoint"""

    def post(self, request):
        user_message = request.data.get("message", "").strip()

        if not user_message:
            return Response(
                {"error": "message maydoni bo'sh"},
                status=status.HTTP_400_BAD_REQUEST
            )

        if len(user_message) > 1000:
            return Response(
                {"error": "Xabar juda uzun (max 1000 belgi)"},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            ai_response = ask_ai(user_message)

            return Response({
                "user_message": user_message,
                "ai_response": ai_response
            }, status=status.HTTP_200_OK)

        except Exception as e:
            print(f"❌ ChatAPIView error: {e}")
            return Response(
                {"error": "Ichki xatolik", "details": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


# ============================================
# SYNC & HEALTH CHECK (MAVJUD)
# ============================================

class FastAPISyncView(APIView):
    """FastAPI dan ma'lumotlarni yuklash"""

    def get(self, request):
        try:
            categories_count = fetch_and_save_categories()
            products_count = fetch_and_save_products()

            total_categories = Category.objects.count()
            total_products = Product.objects.count()

            return Response({
                "success": True,
                "message": "Sinxronizatsiya yakunlandi",
                "synced_categories": categories_count,
                "synced_products": products_count,
                "total_categories": total_categories,
                "total_products": total_products
            }, status=status.HTTP_200_OK)

        except Exception as e:
            print(f"❌ Sync error: {e}")
            return Response({
                "success": False,
                "error": "Sinxronizatsiyada xatolik",
                "details": str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class HealthCheckView(APIView):
    """Sistem holatini tekshirish"""

    def get(self, request):
        try:
            categories_count = Category.objects.count()
            products_count = Product.objects.count()
            db_status = "connected"
        except Exception as e:
            db_status = f"error: {str(e)}"
            categories_count = 0
            products_count = 0

        return Response({
            "status": "ok",
            "database": db_status,
            "categories_count": categories_count,
            "products_count": products_count,
            "api_version": "2.0"
        }, status=status.HTTP_200_OK)