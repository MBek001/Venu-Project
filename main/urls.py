# chatbot/urls.py
from django.urls import path
from .views import ChatAPIView

urlpatterns = [
    path("message/", ChatAPIView.as_view(), name="chat_api"),
]
