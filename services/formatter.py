from data.tours import KIROVSK

def kirovsk_price():

    includes = "\n".join(f"• {x}" for x in KIROVSK["includes"])
    not_included = "\n".join(f"• {x}" for x in KIROVSK["not_included"])

    return f"""
🏔 *Кировск*

💰 **Стоимость — {KIROVSK["price"]:,} ₽**

*Что входит:*

{includes}

————————————

*Не входит:*

{not_included}
"""

def kirovsk_dates():

    dates = "\n".join(f"• {d}" for d in KIROVSK["dates"])

    return f"""
🏔 *Кировск*

📅 **Ближайшие туры**

{dates}

⏳ {KIROVSK["duration"]}
"""