# main/urls.py
from django.urls import path
from .views import (
    ChatAPIView,
    FastAPISyncView,
    HealthCheckView,
    ConversationView,
    ConversationListView
)
from .webhook import webhook

app_name = 'chatbot'

urlpatterns = [
    # ============================================
    # WEBHOOK
    # ============================================
    path('webhook/', webhook, name='webhook'),

    # ============================================
    # CONVERSATIONS (YANGI!)
    # ============================================
    # Bitta suhbatni ko'rish
    # HTML: /chats?user_id=123&receiver_id=456
    # JSON: /chats?user_id=123&receiver_id=456&format=json
    path('chats/', ConversationView.as_view(), name='conversation_detail'),

    # Barcha suhbatlar ro'yxati
    # HTML: /conversations/
    # JSON: /conversations/?format=json
    path('conversations/', ConversationListView.as_view(), name='conversation_list'),

    # ============================================
    # API ENDPOINTS
    # ============================================
    # Chatbot API
    path('message/', ChatAPIView.as_view(), name='chat_api'),

    # FastAPI bilan sinxronizatsiya
    path('sync-fastapi/', FastAPISyncView.as_view(), name='sync_fastapi'),

    # Health check
    path('health/', HealthCheckView.as_view(), name='health_check'),
]