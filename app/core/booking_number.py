import hashlib


BOOKING_CODE_ALPHABET = (
    "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
)


def booking_public_number(
    booking_id: int,
) -> str:
    """
    Возвращает стабильный внешний номер заявки.

    Внутренний Booking.id остаётся числовым и
    продолжает использоваться в БД и URL.
    Пользователю показывается код вида WT-ABC234.
    """
    digest = hashlib.sha256(
        (
            "wowdertour-booking-v1:"
            f"{int(booking_id)}"
        ).encode("utf-8")
    ).digest()

    value = int.from_bytes(
        digest[:8],
        "big",
    )

    chars = []

    for _ in range(6):
        value, index = divmod(
            value,
            len(BOOKING_CODE_ALPHABET),
        )
        chars.append(
            BOOKING_CODE_ALPHABET[index]
        )

    return (
        "WT-"
        + "".join(chars)
    )
