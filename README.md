# Telegram: `.session` + `tdata` по номеру телефона

Бот для входа в Telegram-аккаунт (номер → код → при необходимости 2FA).  
Имена файлов и папок — **цифры номера** (без `+`), например для `+79001234567`:

| Путь | Описание |
|------|----------|
| `sessions/79001234567.session` | Telethon |
| `tdata/79001234567/` | tdata (Telegram Desktop) |

Связь «пользователь бота → последний номер» хранится в `data/bot_users/<telegram_user_id>.json` (для команд `/session` и `/tdata`).

## Переменные окружения

- `BOT_TOKEN`, `API_ID`, `API_HASH` — обязательны
- `SESSIONS_DIR` (по умолчанию `sessions`)
- `TDATA_DIR` (по умолчанию `tdata`)
- `DATA_DIR` (по умолчанию `data`)

## Запуск

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python -m bot.main
```

## Команды бота

| Команда | Описание |
|--------|----------|
| **Verificate** (кнопка) / `/login` | Верификация: вход по номеру телефона |
| `/session` | Скачать `.session` |
| `/tdata` | Скачать zip с `tdata/<номер>/` |
| `/cancel` | Отменить текущий вход |
