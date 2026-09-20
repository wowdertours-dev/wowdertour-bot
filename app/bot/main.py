import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties

from app.bot.routers.booking import router as booking_router
from app.bot.routers.public import router as public_router
from app.core.config import settings


async def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )

    bot = Bot(
        token=settings.bot_token,
        default=DefaultBotProperties(
            parse_mode=ParseMode.HTML,
        ),
    )

    dp = Dispatcher()

    # booking должен стоять раньше public,
    # чтобы FSM заявки обрабатывался первым.
    dp.include_router(booking_router)
    dp.include_router(public_router)

    # Do not discard messages/applications that arrived during a deploy.
    await bot.delete_webhook(drop_pending_updates=False)

    if not settings.admins:
        logging.warning(
            "ADMIN_IDS/ADMIN_ID is empty: new booking notifications will not be sent"
        )

    logging.info("WowderTour bot started")

    try:
        await dp.start_polling(bot)
    finally:
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())