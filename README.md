# Telegram demo: `.session` + `tdata`

Демо-бот: пользователь входит в **свой Telegram-аккаунт** (номер → код → при необходимости 2FA). На сервере сохраняются:

| Артефакт | Формат | Назначение |
|----------|--------|------------|
| `demo_<id>.session` | Telethon | userbot / скрипты |
| `demo_<id>_tdata/` | Telegram Desktop (`tdata`) | папка для Desktop-клиента |

Экспорт `tdata` делается через [opentele](https://github.com/thedemons/opentele) после успешного входа.

## Что нужно

1. **BOT_TOKEN** — [@BotFather](https://t.me/BotFather)
2. **API_ID** / **API_HASH** — [my.telegram.org/apps](https://my.telegram.org/apps)

## Запуск

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# заполни .env
python -m bot.main
```

На Linux для `opentele` может понадобиться `python3-dev` (сборка `tgcrypto`).

## Команды бота

| Команда | Описание |
|--------|----------|
| `/login` | Вход; старые `.session` и `tdata` для этого пользователя бота удаляются |
| `/session` | Отправить `.session` в чат |
| `/tdata` | Отправить zip с папкой `tdata` |
| `/cancel` | Отменить текущий вход |

## Как использовать `tdata`

1. Скачай архив через `/tdata`.
2. Распакуй.
3. Для **Telegram Desktop** положи содержимое в каталог `tdata` профиля клиента (или замени существующий `tdata` — только на тестовом аккаунте).

Структура на сервере:

```text
sessions/
  demo_123456789.session
  demo_123456789_tdata/
    key_datas/
    ...
```

## Безопасность

`.session` и `tdata` = **полный доступ к аккаунту**. Только для демонстрации; не запускай на чужом хостинге и не передавай файлы третьим лицам.
