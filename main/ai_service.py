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
            {
                "role": "system",
                "content": (sytem_prompt)
            },
            {"role": "user", "content": message}],
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
        function_call="auto",  # model o'zi hal qiladi
    )

    msg = response["choices"][0]["message"]

    # Agar AI function chaqirsa
    if msg.get("function_call"):
        func_name = msg["function_call"]["name"]
        if func_name == "get_answer_from_file":
            args = json.loads(msg["function_call"]["arguments"])
            return get_answer_from_file(args["question"])


    result = msg.get("content", "Hech qanday javob topilmadi.")
    try:
        result = json.loads(result)
    except Exception:
        pass

    return result

