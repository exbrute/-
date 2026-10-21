from __future__ import annotations

import shutil
import tempfile
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
    finalize_login,
    remove_user_artifacts,
    session_file_path,
    start_login,
    tdata_dir_path,
)

router = Router(name="auth")

_pending: dict[int, PendingLogin] = {}


class LoginStates(StatesGroup):
    phone = State()
    code = State()
    password = State()


def _help_lines(has_session: bool) -> str:
    lines = [
        "/login — войти заново (удалит старые `.session` и `tdata`)",
        "/session — скачать `.session` (Telethon)",
        "/tdata — скачать `tdata` архивом zip",
        "/cancel — отменить текущий вход",
    ]
    if has_session:
        return "Команды:\n" + "\n".join(lines)
    return (
        "Нажми /login и отправь номер телефона, например `+79001234567`.\n\n"
        + "Команды:\n"
        + "\n".join(lines)
    )


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext, settings: Settings) -> None:
    await state.clear()
    uid = message.from_user.id if message.from_user else 0
    await _cleanup_pending(uid)

    session = session_file_path(settings.sessions_dir, uid)
    tdata = tdata_dir_path(settings.sessions_dir, uid)
    has_session = session.is_file()

    if has_session:
        tdata_note = "есть" if tdata.is_dir() else "нет (только `.session`)"
        await message.answer(
            "Привет! Для твоего аккаунта бота уже сохранены артефакты входа.\n\n"
            f"• `{session.name}`\n"
            f"• `tdata`: {tdata_note}\n\n"
            + _help_lines(True),
            parse_mode="Markdown",
        )
        return

    await message.answer(
        "Привет! **Демо-бот**: вход в **свой Telegram-аккаунт** и сохранение на сервере:\n"
        "• **`*.session`** — Telethon\n"
        "• **`tdata`** — формат Telegram Desktop (через opentele)\n\n"
        + _help_lines(False)
        + "\n\n⚠️ `.session` и `tdata` дают полный доступ к аккаунту. Только для обучения.",
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
    remove_user_artifacts(settings.sessions_dir, uid)
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
            session = session_file_path(settings.sessions_dir, uid)
            await message.answer(
                f"Сессия уже есть: `{session.name}`. /session, /tdata или /login.",
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
        await message.answer("Файла `.session` ещё нет. Сначала /login")
        return
    await message.answer_document(
        FSInputFile(path),
        caption=f"Telethon session: `{path.name}`",
        parse_mode="Markdown",
    )


@router.message(Command("tdata"))
async def cmd_tdata(message: Message, settings: Settings) -> None:
    uid = message.from_user.id if message.from_user else 0
    tdata = tdata_dir_path(settings.sessions_dir, uid)
    if not tdata.is_dir():
        await message.answer("Папки `tdata` ещё нет. Сначала /login")
        return

    with tempfile.TemporaryDirectory() as tmp:
        archive_base = Path(tmp) / f"{tdata.name}"
        zip_path = shutil.make_archive(str(archive_base), "zip", root_dir=tdata.parent, base_dir=tdata.name)
        await message.answer_document(
            FSInputFile(zip_path),
            caption="Каталог `tdata` (Telegram Desktop). Распакуй и положи рядом с Telegram.exe.",
            parse_mode="Markdown",
        )


async def _finish_login(
    message: Message, state: FSMContext, uid: int, settings: Settings
) -> None:
    pending = _pending.pop(uid, None)
    if not pending:
        await state.clear()
        await message.answer("Сессия входа истекла. Начни с /login")
        return

    await message.answer("Вход успешен, сохраняю `.session` и `tdata`…")

    try:
        session_path, tdata_path = await finalize_login(
            pending, settings.sessions_dir, uid
        )
    except Exception as exc:
        await disconnect_quiet(pending.client)
        await state.clear()
        await message.answer(
            f"Вход прошёл, но экспорт `tdata` не удался: `{exc}`\n"
            "Попробуй /login ещё раз или проверь логи на сервере.",
            parse_mode="Markdown",
        )
        return

    await state.clear()
    await message.answer(
        "Готово.\n\n"
        f"• `{session_path.name}`\n"
        f"• `{tdata_path.name}/` (tdata)\n\n"
        "/session — файл сессии\n"
        "/tdata — zip с tdata",
        parse_mode="Markdown",
    )


async def _cleanup_pending(uid: int) -> None:
    pending = _pending.pop(uid, None)
    await disconnect_quiet(pending.client if pending else None)
