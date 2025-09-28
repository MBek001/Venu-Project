# ai_service.py
import json
import openai
from .utils import get_answer_from_file
from .config import OPENAI_KEY, sytem_prompt

openai.api_key = OPENAI_KEY


def ask_ai(message: str) -> str:
    response = openai.ChatCompletion.create(
        model="gpt-4-0613",
        messages=[
            {"role": "system", "content": sytem_prompt},
            {"role": "user", "content": message}
        ],
        functions=[
            {
                "name": "get_answer_from_file",
                "description": "Savolga txt fayldan javob topib beradi",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "question": {"type": "string"}
                    },
                    "required": ["question"]
                },
            }
        ],
        function_call="auto",
    )

    msg = response["choices"][0]["message"]

    # 1️⃣ Function call ishlasa
    if msg.get("function_call"):
        func_name = msg["function_call"]["name"]
        if func_name == "get_answer_from_file":
            args = json.loads(msg["function_call"]["arguments"])
            file_answer = get_answer_from_file(args["question"])

            # Agar txt faylda topilgan bo‘lsa → shu qaytadi
            if file_answer and "javob topilmadi" not in file_answer.lower():
                return file_answer

            # Agar topilmasa → fallback qilib AI dan javob olish
            response2 = openai.ChatCompletion.create(
                model="gpt-4-0613",
                messages=[
                    {"role": "system", "content": sytem_prompt},
                    {"role": "user", "content": message}
                ]
            )
            return response2["choices"][0]["message"].get("content", "Hech qanday javob topilmadi.")

    # 2️⃣ Agar umuman function_call bo‘lmasa
    return msg.get("content", "Hech qanday javob topilmadi.")
