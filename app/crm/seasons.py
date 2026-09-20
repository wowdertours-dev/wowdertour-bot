from datetime import date
from typing import Iterable


def season_from_date(value: date) -> str:
    start_year = value.year if value.month >= 9 else value.year - 1
    return f"{start_year}/{str(start_year + 1)[-2:]}"


def normalize_season(value: str | None, *, fallback_date: date | None = None) -> str:
    raw = (value or "").strip().replace(" ", "").replace("-", "/")
    if not raw:
        if fallback_date is None:
            return ""
        return season_from_date(fallback_date)

    parts = raw.split("/")
    if len(parts) != 2 or not parts[0].isdigit() or not parts[1].isdigit():
        raise ValueError("Сезон должен быть в формате 2026/27")

    start = int(parts[0])
    if len(parts[0]) != 4:
        raise ValueError("Сезон должен быть в формате 2026/27")

    if len(parts[1]) == 4:
        end = int(parts[1])
    elif len(parts[1]) == 2:
        end = (start // 100) * 100 + int(parts[1])
        if end < start:
            end += 100
    else:
        raise ValueError("Сезон должен быть в формате 2026/27")

    if end != start + 1:
        raise ValueError("Сезон должен состоять из двух последовательных лет")

    return f"{start}/{str(end)[-2:]}"


def departure_season(departure) -> str:
    stored = (getattr(departure, "season", None) or "").strip()
    if stored:
        return stored
    return season_from_date(departure.start_date)


def current_season_label(today: date | None = None) -> str:
    return season_from_date(today or date.today())


def available_seasons(departures: Iterable) -> list[str]:
    labels = {
        departure_season(departure)
        for departure in departures
        if getattr(departure, "start_date", None) is not None
    }
    return sorted(labels, reverse=True)
