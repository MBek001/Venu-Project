

# utils.py
def get_answer_from_file(question: str, filepath="main/qa.txt") -> str:
    with open(filepath, "r", encoding="utf-8") as f:
        lines = f.readlines()
        print("gieeee",filepath)

    q, a = None, []
    for line in lines:
        line = line.strip()
        if not line:
            continue

        if "?" in line:  # Savol boshlangan joy
            q = line
            continue

        if q:
            a.append(line)
            # Agar foydalanuvchi savoli shu joyga to‘g‘ri kelsa — qaytaramiz
            if question.lower() in q.lower():
                return " ".join(a).strip()

    return "Kechirasiz, bu savol bo‘yicha javob topilmadi."
