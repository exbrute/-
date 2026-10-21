from __future__ import annotations

from pathlib import Path

from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import FSInputFile, Message

from bot.config import Settings
from bot.session_auth import (
    PendingLogin,
    complete_code,
    complete_password,
    disconnect_quiet,
    session_file_path,
    start_login,
)

router = Router(name="auth")

_pending: dict[int, PendingLogin] = {}


class LoginStates(StatesGroup):
    phone = State()
    code = State()
    password = State()


def _remove_session_files(settings: Settings, telegram_user_id: int) -> None:
    path = session_file_path(settings.sessions_dir, telegram_user_id)
    for candidate in (path, Path(f"{path}-journal")):
        if candidate.is_file():
            candidate.unlink()


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext, settings: Settings) -> None:
    await state.clear()
    uid = message.from_user.id if message.from_user else 0
    await _cleanup_pending(uid)

    path = session_file_path(settings.sessions_dir, uid)

    if path.is_file():
        await message.answer(
            "Привет! У тебя уже есть файл сессии для этого Telegram-аккаунта бота.\n\n"
            f"Файл: `{path.name}`\n\n"
            "Команды:\n"
            "/login — войти заново (перезапишет сессию)\n"
            "/session — получить `.session` файл\n"
            "/cancel — отменить текущий вход",
            parse_mode="Markdown",
        )
        return

    await message.answer(
        "Привет! Это **демо-бот**: через него можно войти в **свой Telegram-аккаунт** "
        "и на сервере создаётся файл **`*.session`** (Pyrogram), как в userbot-скриптах.\n\n"
        "Нажми /login и отправь номер телефона в международном формате, "
        "например `+79001234567`.\n\n"
        "⚠️ Демо только для обучения. Файл сессии = полный доступ к аккаунту. "
        "Не используй на чужих серверах и не передавай файл третьим лицам.",
        parse_mode="Markdown",
    )


@router.message(Command("cancel"))
async def cmd_cancel(message: Message, state: FSMContext) -> None:
    uid = message.from_user.id if message.from_user else 0
    await state.clear()
    await _cleanup_pending(uid)
    await message.answer("Вход отменён.")


@router.message(Command("login"))
async def cmd_login(message: Message, state: FSMContext, settings: Settings) -> None:
    uid = message.from_user.id if message.from_user else 0
    await state.clear()
    await _cleanup_pending(uid)
    _remove_session_files(settings, uid)
    await state.set_state(LoginStates.phone)
    await message.answer(
        "Отправь номер телефона аккаунта Telegram (с `+` и кодом страны)."
    )


@router.message(LoginStates.phone, F.text)
async def on_phone(message: Message, state: FSMContext, settings: Settings) -> None:
    uid = message.from_user.id if message.from_user else 0

    try:
        pending = await start_login(
            settings.api_id,
            settings.api_hash,
            settings.sessions_dir,
            uid,
            message.text or "",
        )
    except ValueError as e:
        await message.answer(f"Неверный номер: {e}")
        return
    except RuntimeError as e:
        if str(e) == "already_authorized":
            path = session_file_path(settings.sessions_dir, uid)
            await message.answer(
                f"Сессия уже есть: `{path.name}`. Используй /session или /login.",
                parse_mode="Markdown",
            )
            await state.clear()
            return
        raise

    _pending[uid] = pending
    await state.set_state(LoginStates.code)
    await message.answer(
        "Код отправлен в Telegram (приложение или SMS).\n"
        "Пришли код одним сообщением (можно с пробелами)."
    )


@router.message(LoginStates.code, F.text)
async def on_code(message: Message, state: FSMContext, settings: Settings) -> None:
    uid = message.from_user.id if message.from_user else 0
    pending = _pending.get(uid)
    if not pending:
        await state.clear()
        await message.answer("Сессия входа истекла. Начни с /login")
        return

    try:
        need_password = await complete_code(pending, message.text or "")
    except ValueError as e:
        if str(e) == "invalid_code":
            await message.answer("Неверный код. Попробуй ещё раз или /cancel")
            return
        if str(e) == "expired_code":
            await _cleanup_pending(uid)
            await state.clear()
            await message.answer("Код истёк. Начни с /login")
            return
        raise

    if need_password == "password":
        await state.set_state(LoginStates.password)
        await message.answer(
            "На аккаунте включена двухфакторная защита. Пришли пароль облачного пароля."
        )
        return

    await _finish_login(message, state, uid, settings)


@router.message(LoginStates.password, F.text)
async def on_password(
    message: Message, state: FSMContext, settings: Settings
) -> None:
    uid = message.from_user.id if message.from_user else 0
    pending = _pending.get(uid)
    if not pending:
        await state.clear()
        await message.answer("Сессия входа истекла. Начни с /login")
        return

    try:
        await complete_password(pending, message.text or "")
    except ValueError:
        await message.answer("Неверный пароль. Попробуй ещё раз или /cancel")
        return

    await _finish_login(message, state, uid, settings)


@router.message(Command("session"))
async def cmd_session(message: Message, settings: Settings) -> None:
    uid = message.from_user.id if message.from_user else 0
    path = session_file_path(settings.sessions_dir, uid)
    if not path.is_file():
        await message.answer("Файла сессии ещё нет. Сначала /login")
        return
    await message.answer_document(
        FSInputFile(path),
        caption=f"Файл сессии Pyrogram: `{path.name}`",
        parse_mode="Markdown",
    )


async def _finish_login(
    message: Message, state: FSMContext, uid: int, settings: Settings
) -> None:
    pending = _pending.pop(uid, None)
    if pending:
        await disconnect_quiet(pending.client)

    path = session_file_path(settings.sessions_dir, uid)
    await state.clear()
    await message.answer(
        "Вход выполнен. Файл сессии создан на сервере:\n"
        f"`{path}`\n\n"
        "Команда /session отправит файл в этот чат.",
        parse_mode="Markdown",
    )


async def _cleanup_pending(uid: int) -> None:
    pending = _pending.pop(uid, None)
    await disconnect_quiet(pending.client if pending else None)
