import json

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from .ai_service import ask_ai

class ChatAPIView(APIView):
    def post(self, request):
        user_message = request.data.get("message")
        if not user_message:
            return Response({"error": "message is required"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            ai_response = ask_ai(user_message)

            if isinstance(ai_response, str):
                try:
                    # Agar AI stringni "..." shaklida yuborgan bo‘lsa
                    ai_response = json.loads(ai_response)
                except Exception:
                    ai_response = ai_response.replace('\\"', '"').replace("\\n", "\n")

            return Response({
                "user_message": user_message,
                "ai_response": ai_response
            }, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
