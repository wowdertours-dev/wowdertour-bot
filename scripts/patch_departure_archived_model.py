from pathlib import Path

path = Path("app/database/models.py")

if not path.exists():
    raise SystemExit(
        "Не найден app/database/models.py. Запусти скрипт из корня проекта."
    )

text = path.read_text(encoding="utf-8")

if "archived: Mapped[bool]" in text:
    print("Поле archived уже есть в models.py — ничего менять не нужно.")
    raise SystemExit(0)

needle = '''    active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
    )

    notes: Mapped[str | None] = mapped_column(
'''

replacement = '''    active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
    )

    archived: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        server_default="false",
        index=True,
    )

    notes: Mapped[str | None] = mapped_column(
'''

if needle not in text:
    raise SystemExit(
        "Не удалось найти блок TourDeparture.active. models.py не изменён."
    )

text = text.replace(needle, replacement, 1)
path.write_text(text, encoding="utf-8")

print("Готово: archived добавлен в TourDeparture.")
