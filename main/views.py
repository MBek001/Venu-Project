# views.py
import json
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from .ai_service import ask_ai
from .models import Category, Product
from .utils import fetch_and_save_categories, fetch_and_save_products


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