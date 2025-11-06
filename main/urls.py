# chatbot/urls.py
from django.urls import path
from .views import ChatAPIView, FastAPISyncView, HealthCheckView
from .webhook import webhook

app_name = 'chatbot'

urlpatterns = [
    # Chatbot API
    path('webhook/', webhook, name='webhook'),
    path('message/', ChatAPIView.as_view(), name='chat_api'),

    # FastAPI bilan sinxronizatsiya
    path('sync-fastapi/', FastAPISyncView.as_view(), name='sync_fastapi'),

    # Health check
    path('health/', HealthCheckView.as_view(), name='health_check'),
]