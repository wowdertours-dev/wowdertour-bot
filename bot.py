import asyncio

from aiogram import Bot, Dispatcher

from config import BOT_TOKEN

from handlers.start import router as start_router
from handlers.ski import router as ski_router
from handlers.kirovsk import router as kirovsk_router
from handlers.sheregesh import router as sheregesh_router
from handlers.wake import router as wake_router
from handlers.skate import router as skate_router
from handlers.company import router as company_router

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

dp.include_router(start_router)
dp.include_router(ski_router)
dp.include_router(kirovsk_router)
dp.include_router(sheregesh_router)
dp.include_router(wake_router)
dp.include_router(skate_router)
dp.include_router(company_router)


async def main():
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())