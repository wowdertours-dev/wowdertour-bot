from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
MODELS = ROOT / "app/database/models.py"
TOURS = ROOT / "app/crm/tours.py"
ROUTES = ROOT / "app/crm/routes.py"
FINANCE = ROOT / "app/crm/finance.py"
TOUR_TPL = ROOT / "app/crm/templates/tour_direction.html"


def read(path):
    if not path.exists():
        raise SystemExit(f"Не найден файл: {path}")
    return path.read_text()


def write(path, text):
    path.write_text(text)


def patch_models():
    text = read(MODELS)
    if "season: Mapped[str]" not in text:
        anchor = "    end_date: Mapped[date] = mapped_column(Date)\n"
        if anchor not in text:
            raise SystemExit("models.py: не найден TourDeparture.end_date")
        text = text.replace(
            anchor,
            anchor + "\n    season: Mapped[str] = mapped_column(\n        String(20),\n        index=True,\n    )\n",
            1,
        )
        write(MODELS, text)
        print("models.py: добавлено поле season")
    else:
        print("models.py: season уже есть")


def ensure_import(text):
    new_import = (
        "from app.crm.seasons import "
        "available_seasons, current_season_label, departure_season, normalize_season\n"
    )

    if "from app.crm.seasons import" in text:
        return re.sub(
            r"from app\.crm\.seasons import [^\n]+\n",
            new_import,
            text,
            count=1,
        )

    # Поддерживаем как однострочный, так и многострочный импорт SessionLocal.
    patterns = [
        r"from app\.database\.session import SessionLocal\n",
        r"from app\.database\.session import \(\n(?:[^\n]*\n)*?\)\n",
    ]

    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            insert_at = match.end()
            return text[:insert_at] + new_import + text[insert_at:]

    # Если импорт SessionLocal оформлен иначе, добавляем импорт сезонов
    # перед первым локальным импортом app.*, не ломая существующий код.
    match = re.search(r"^from app\.", text, flags=re.MULTILINE)
    if match:
        return text[:match.start()] + new_import + text[match.start():]

    # Последний безопасный вариант — после стандартных/сторонних импортов.
    return new_import + text


def patch_tours():
    text = ensure_import(read(TOURS))

    add_start = text.find("async def add_departure(")
    upd_start = text.find("async def update_departure(")
    if add_start == -1 or upd_start == -1:
        raise SystemExit("tours.py: не найдены add/update departure")

    add_block = text[add_start:upd_start]
    if 'season: str = Form("")' not in add_block:
        old = '    prepayment_amount: str = Form("0"),\n    notes: str = Form(""),\n'
        if old not in add_block:
            raise SystemExit("tours.py: не найдены параметры add_departure")
        abs_pos = add_start + add_block.find(old)
        repl = '    prepayment_amount: str = Form("0"),\n    season: str = Form(""),\n    notes: str = Form(""),\n'
        text = text[:abs_pos] + repl + text[abs_pos + len(old):]

    upd_start = text.find("async def update_departure(")
    upd_block = text[upd_start:]
    if 'season: str = Form("")' not in upd_block.split("):", 1)[0]:
        old = '    prepayment_amount: str = Form("0"),\n    notes: str = Form(""),\n'
        rel = upd_block.find(old)
        if rel == -1:
            raise SystemExit("tours.py: не найдены параметры update_departure")
        abs_pos = upd_start + rel
        repl = '    prepayment_amount: str = Form("0"),\n    season: str = Form(""),\n    notes: str = Form(""),\n'
        text = text[:abs_pos] + repl + text[abs_pos + len(old):]

    add_start = text.find("async def add_departure(")
    upd_start = text.find("async def update_departure(")
    add_block = text[add_start:upd_start]
    if "# WOWDER_STORED_SEASON_ADD" not in add_block:
        rel = add_block.find("    if capacity < 1:\n")
        if rel == -1:
            raise SystemExit("tours.py: не найден capacity check add")
        abs_pos = add_start + rel
        block = '''    # WOWDER_STORED_SEASON_ADD\n    try:\n        departure_season_value = normalize_season(\n            season,\n            fallback_date=start,\n        )\n    except ValueError as error:\n        return HTMLResponse(str(error), status_code=400)\n\n'''
        text = text[:abs_pos] + block + text[abs_pos:]

    add_start = text.find("async def add_departure(")
    upd_start = text.find("async def update_departure(")
    add_block = text[add_start:upd_start]
    if "season=departure_season_value" not in add_block:
        rel = add_block.find("            end_date=end,\n")
        if rel == -1:
            raise SystemExit("tours.py: не найдено создание TourDeparture")
        abs_pos = add_start + rel + len("            end_date=end,\n")
        text = text[:abs_pos] + "            season=departure_season_value,\n" + text[abs_pos:]

    upd_start = text.find("async def update_departure(")
    upd_block = text[upd_start:]
    if "# WOWDER_STORED_SEASON_UPDATE" not in upd_block:
        rel = upd_block.find("    if capacity < 1:\n")
        if rel == -1:
            raise SystemExit("tours.py: не найден capacity check update")
        abs_pos = upd_start + rel
        block = '''    # WOWDER_STORED_SEASON_UPDATE\n    try:\n        departure_season_value = normalize_season(\n            season,\n            fallback_date=start,\n        )\n    except ValueError as error:\n        return HTMLResponse(str(error), status_code=400)\n\n'''
        text = text[:abs_pos] + block + text[abs_pos:]

    upd_start = text.find("async def update_departure(")
    upd_block = text[upd_start:]
    if "departure.season = departure_season_value" not in upd_block:
        rel = upd_block.find("        departure.end_date = end\n")
        if rel == -1:
            raise SystemExit("tours.py: не найден departure.end_date")
        abs_pos = upd_start + rel + len("        departure.end_date = end\n")
        text = text[:abs_pos] + "        departure.season = departure_season_value\n" + text[abs_pos:]

    write(TOURS, text)
    print("tours.py: сезон подключён")


def patch_filter_file(path):
    text = ensure_import(read(path))
    text = text.replace("season_label(booking.departure.start_date)", "departure_season(booking.departure)")
    text = text.replace("season_label(departure.start_date)", "departure_season(departure)")
    text = text.replace(", season_label", "")
    write(path, text)
    print(f"{path.name}: фильтры используют сохранённый season")


def field_html(value=""):
    value_attr = f' value="{value}"' if value else ""
    return f'''                        <div class="form-field season-field">\n                            <label>Сезон</label>\n                            <input type="text" name="season" placeholder="Например: 2026/27" pattern="\\d{{4}}[/\\-]\\d{{2,4}}" title="Например: 2026/27" autocomplete="off"{value_attr}>\n                            <small>Пустое поле = определить автоматически по дате начала.</small>\n                        </div>\n\n'''


def patch_template():
    text = read(TOUR_TPL)

    if "WOWDER_SEASON_ADD_FIELD" not in text:
        pos = text.find('action="/tours/{{ tour.id }}/departures/add"')
        if pos == -1:
            raise SystemExit("tour_direction.html: не найдена add form")
        end = text.find("</form>", pos)
        block = text[pos:end]
        rel = block.find('name="notes"')
        if rel == -1:
            rel = block.find('type="submit"')
        if rel == -1:
            raise SystemExit("tour_direction.html: не найдено место для season add")
        div = block.rfind("<div", 0, rel)
        abs_pos = pos + (div if div != -1 else rel)
        text = text[:abs_pos] + "                        <!-- WOWDER_SEASON_ADD_FIELD -->\n" + field_html() + text[abs_pos:]

    if "WOWDER_SEASON_EDIT_FIELD" not in text:
        pos = text.find('action="/departures/{{ departure.id }}/settings"')
        if pos == -1:
            raise SystemExit("tour_direction.html: не найдена settings form")
        end = text.find("</form>", pos)
        block = text[pos:end]
        rel = block.find('name="notes"')
        if rel == -1:
            rel = block.find('type="submit"')
        if rel == -1:
            raise SystemExit("tour_direction.html: не найдено место для season edit")
        div = block.rfind("<div", 0, rel)
        abs_pos = pos + (div if div != -1 else rel)
        text = text[:abs_pos] + "                        <!-- WOWDER_SEASON_EDIT_FIELD -->\n" + field_html("{{ departure.season or '' }}") + text[abs_pos:]

    write(TOUR_TPL, text)
    print("tour_direction.html: поле сезона добавлено")


def main():
    patch_models()
    patch_tours()
    patch_filter_file(FINANCE)
    patch_filter_file(ROUTES)
    patch_template()
    print("\nГотово. Теперь: python -m compileall -q app scripts && alembic upgrade head")


if __name__ == "__main__":
    main()
