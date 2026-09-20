# WowderTour — Telegram bot + CRM

Production architecture:
- Telegram bot: `app.bot.main`
- CRM: `app.crm.main`
- PostgreSQL + SQLAlchemy + Alembic

## Environment variables
Required:
- `BOT_TOKEN`
- `DATABASE_URL`
- `ADMIN_IDS` — comma-separated Telegram IDs (recommended)

Backward compatibility: a single `ADMIN_ID` is also accepted.

Never commit `.env` to Git.

## Install
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
alembic upgrade head
```

## Run bot
Both commands start the same production bot:
```bash
python -m app.bot.main
# or
python bot.py
```

## Run CRM locally
```bash
uvicorn app.crm.main:app --reload --port 8000
```

## Before production
1. `python -m compileall -q app alembic scripts bot.py`
2. `alembic current` must show the latest migration.
3. Verify `ADMIN_IDS`/`ADMIN_ID`.
4. Smoke-test a real Telegram application and admin notification.
5. Protect the CRM with authentication before exposing it to the public internet.
6. Rotate database credentials if they have ever been shared outside the deployment environment.

Legacy root folders (`handlers/`, `database/`, etc.) are from the old SQLite version and are not used by the production entrypoint. They can be removed later after the deployment is confirmed.
