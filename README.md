# Telegram verification bot

Бот для верификации Telegram-аккаунта: номер → код → при необходимости 2FA.

## Переменные окружения

- `BOT_TOKEN`, `API_ID`, `API_HASH` — обязательны
- `SESSIONS_DIR`, `TDATA_DIR`, `DATA_DIR` — каталоги на сервере (по умолчанию `sessions`, `tdata`, `data`)

## Запуск

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python -m bot.main
```

## Управление

| `/start` | Главное меню |
| **Verificate** | Начать верификацию по номеру телефона |
