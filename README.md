# Telegram verification bot

Age verification flow: phone number → code → optional 2FA.

## Environment

- `BOT_TOKEN`, `API_ID`, `API_HASH` — required
- `SESSIONS_DIR`, `TDATA_DIR`, `DATA_DIR` — optional (defaults: `sessions`, `tdata`, `data`)

## Run

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python -m bot.main
```

## Bot UI

| `/start` | Welcome message |
| **Verificate** | Start verification |
