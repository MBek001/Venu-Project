import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
QA_FILE = os.path.join(BASE_DIR, "qa.txt")

def get_answer_from_file(question: str, filepath=QA_FILE) -> str:
    qa_dict = {}
    current_q = None
    current_a = []

    with open(filepath, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue

            if line.endswith("?"):  # savol
                if current_q and current_a:
                    qa_dict[current_q.lower()] = " ".join(current_a).strip()
                current_q = line
                current_a = []
            else:  # javob
                current_a.append(line)

        # oxirgi blokni ham qo‘shamiz
        if current_q and current_a:
            qa_dict[current_q.lower()] = " ".join(current_a).strip()

    # endi qidiramiz
    for q_text, a_text in qa_dict.items():
        if question.lower() in q_text:  # savolni qisman moslashtirish
            return a_text

    return "Kechirasiz, bu savol bo‘yicha javob topilmadi."
