# Telegram demo: вход в аккаунт и `.session`

Небольшой бот для **демонстрации**: пользователь проходит стандартный вход Telegram (номер → код → при необходимости облачный пароль), на сервере создаётся файл **`demo_<telegram_user_id>.session`** в формате [Pyrogram](https://docs.pyrogram.org/).

## Что нужно

1. **Bot token** — [@BotFather](https://t.me/BotFather)
2. **API_ID** и **API_HASH** — [my.telegram.org](https://my.telegram.org/apps) (те же, что для userbot-клиентов)

## Запуск

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# отредактируй .env
python -m bot.main
```

## Команды бота

| Команда | Описание |
|--------|----------|
| `/start` | Справка |
| `/login` | Начать вход (старый `.session` для этого пользователя бота удаляется) |
| `/session` | Отправить готовый `.session` файл в чат |
| `/cancel` | Отменить текущий вход |

## Как это устроено

- **aiogram** — интерфейс бота (диалог с пользователем).
- **Pyrogram** — MTProto-авторизация и запись `.session` в каталог `sessions/` (см. `SESSIONS_DIR` в `.env`).

Имя сессии: `demo_<id пользователя в Telegram, который пишет боту>`. Один пользователь бота — один файл сессии на сервере.

## Безопасность

Файл `.session` даёт **полный доступ к аккаунту Telegram**, как у обычного клиента. Это учебный пример: не запускай на недоверенном хостинге и не отдавай файл посторонним.
