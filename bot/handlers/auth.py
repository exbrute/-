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
from bot.keyboards import VERIFY_BUTTON_TEXT, main_keyboard
from bot.session_auth import (
    PendingLogin,
    complete_code,
    complete_password,
    disconnect_quiet,
    finalize_login,
    normalize_phone,
    phone_slug,
    remove_phone_artifacts,
    session_file_path,
    start_login,
    tdata_account_dir,
)
from bot.user_store import clear_linked_phone, get_linked_phone, set_linked_phone

router = Router(name="auth")

_pending: dict[int, PendingLogin] = {}


class LoginStates(StatesGroup):
    phone = State()
    code = State()
    password = State()


def _help_lines(has_session: bool) -> str:
    lines = [
        f"кнопка **{VERIFY_BUTTON_TEXT}** или /login — вход по номеру",
        "/session — скачать `.session` (Telethon)",
        "/tdata — скачать `tdata` архивом zip",
        "/cancel — отменить текущий вход",
    ]
    if has_session:
        return "Команды:\n" + "\n".join(lines)
    return (
        f"Нажми **{VERIFY_BUTTON_TEXT}** на клавиатуре и отправь номер, "
        "например `+79001234567`.\n\n"
        + "Команды:\n"
        + "\n".join(lines)
    )


def _resolve_phone(settings: Settings, uid: int, pending: PendingLogin | None) -> str | None:
    if pending:
        return pending.phone
    return get_linked_phone(settings.data_dir, uid)


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext, settings: Settings) -> None:
    await state.clear()
    uid = message.from_user.id if message.from_user else 0
    await _cleanup_pending(uid)

    phone = get_linked_phone(settings.data_dir, uid)
    if phone:
        session = session_file_path(settings.sessions_dir, phone)
        tdata = tdata_account_dir(settings.tdata_dir, phone)
        tdata_note = "есть" if tdata.is_dir() else "нет"
        await message.answer(
            "Привет! Для твоего последнего входа сохранены артефакты.\n\n"
            f"• Номер: `{phone}`\n"
            f"• `{session.name}`\n"
            f"• `tdata/{phone_slug(phone)}/`: {tdata_note}\n\n"
            + _help_lines(True),
            parse_mode="Markdown",
            reply_markup=main_keyboard(),
        )
        return

    await message.answer(
        "Привет! Вход в Telegram-аккаунт по номеру телефона.\n"
        "Файлы сохраняются по **номеру**:\n"
        "• `sessions/<номер>.session`\n"
        "• `tdata/<номер>/`\n\n"
        + _help_lines(False),
        parse_mode="Markdown",
        reply_markup=main_keyboard(),
    )


async def _begin_verification(
    message: Message, state: FSMContext, settings: Settings
) -> None:
    uid = message.from_user.id if message.from_user else 0
    await state.clear()
    await _cleanup_pending(uid)

    old_phone = get_linked_phone(settings.data_dir, uid)
    if old_phone:
        remove_phone_artifacts(settings.sessions_dir, settings.tdata_dir, old_phone)
    clear_linked_phone(settings.data_dir, uid)

    await state.set_state(LoginStates.phone)
    await message.answer(
        "Верификация: отправь **номер телефона** аккаунта Telegram "
        "(с `+` и кодом страны), например `+79001234567`.",
        parse_mode="Markdown",
        reply_markup=main_keyboard(),
    )


@router.message(Command("cancel"))
async def cmd_cancel(message: Message, state: FSMContext) -> None:
    uid = message.from_user.id if message.from_user else 0
    await state.clear()
    await _cleanup_pending(uid)
    await message.answer("Вход отменён.", reply_markup=main_keyboard())


@router.message(F.text == VERIFY_BUTTON_TEXT)
async def btn_verificate(message: Message, state: FSMContext, settings: Settings) -> None:
    await _begin_verification(message, state, settings)


@router.message(Command("login"))
async def cmd_login(message: Message, state: FSMContext, settings: Settings) -> None:
    await _begin_verification(message, state, settings)


@router.message(LoginStates.phone, F.text)
async def on_phone(message: Message, state: FSMContext, settings: Settings) -> None:
    uid = message.from_user.id if message.from_user else 0

    try:
        pending = await start_login(
            settings.api_id,
            settings.api_hash,
            settings.sessions_dir,
            settings.tdata_dir,
            message.text or "",
        )
    except ValueError as e:
        await message.answer(f"Неверный номер: {e}")
        return
    except RuntimeError as e:
        if str(e) == "already_authorized":
            phone = normalize_phone(message.text or "")
            session = session_file_path(settings.sessions_dir, phone)
            set_linked_phone(settings.data_dir, uid, phone)
            await message.answer(
                f"Сессия для `{phone}` уже есть: `{session.name}`.\n"
                "/session, /tdata или /login.",
                parse_mode="Markdown",
            )
            await state.clear()
            return
        raise

    _pending[uid] = pending
    await state.set_state(LoginStates.code)
    await message.answer(
        f"Код отправлен на `{pending.phone}`.\n"
        "Пришли код одним сообщением (можно с пробелами).",
        parse_mode="Markdown",
        reply_markup=main_keyboard(),
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
    phone = _resolve_phone(settings, uid, _pending.get(uid))
    if not phone:
        await message.answer("Сначала /login — номер телефона ещё не привязан.")
        return

    path = session_file_path(settings.sessions_dir, phone)
    if not path.is_file():
        await message.answer("Файла `.session` для этого номера ещё нет. Сначала /login")
        return
    await message.answer_document(
        FSInputFile(path),
        caption=f"Telethon session `{path.name}` — {phone}",
        parse_mode="Markdown",
    )


@router.message(Command("tdata"))
async def cmd_tdata(message: Message, settings: Settings) -> None:
    uid = message.from_user.id if message.from_user else 0
    phone = _resolve_phone(settings, uid, _pending.get(uid))
    if not phone:
        await message.answer("Сначала /login — номер телефона ещё не привязан.")
        return

    tdata = tdata_account_dir(settings.tdata_dir, phone)
    if not tdata.is_dir():
        await message.answer("Папки `tdata` для этого номера ещё нет. Сначала /login")
        return

    slug = phone_slug(phone)
    with tempfile.TemporaryDirectory() as tmp:
        archive_base = Path(tmp) / f"{slug}_tdata"
        zip_path = shutil.make_archive(
            str(archive_base), "zip", root_dir=tdata.parent, base_dir=tdata.name
        )
        await message.answer_document(
            FSInputFile(zip_path),
            caption=f"`tdata` для {phone} — распакуй в профиль Telegram Desktop.",
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

    await message.answer(
        f"Вход на `{pending.phone}` успешен, сохраняю `.session` и `tdata`…",
        parse_mode="Markdown",
    )

    try:
        session_path, tdata_path = await finalize_login(
            pending, settings.sessions_dir, settings.tdata_dir
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

    set_linked_phone(settings.data_dir, uid, pending.phone)
    await state.clear()
    await message.answer(
        "Готово.\n\n"
        f"• Номер: `{pending.phone}`\n"
        f"• `sessions/{session_path.name}`\n"
        f"• `tdata/{tdata_path.name}/`\n\n"
        "/session — файл сессии\n"
        "/tdata — zip с tdata",
        parse_mode="Markdown",
        reply_markup=main_keyboard(),
    )


async def _cleanup_pending(uid: int) -> None:
    pending = _pending.pop(uid, None)
    await disconnect_quiet(pending.client if pending else None)
