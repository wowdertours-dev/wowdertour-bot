"""Compatibility entrypoint for Railway/local launches.

The production bot lives in app.bot.main. Keeping this tiny wrapper means both
`python bot.py` and `python -m app.bot.main` start the same PostgreSQL-backed bot.
"""

import asyncio

from app.bot.main import main


if __name__ == "__main__":
    asyncio.run(main())
