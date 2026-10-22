from __future__ import annotations

from pathlib import Path

from aiogram import F, Router
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import FSInputFile, Message

from bot.config import Settings
from bot.keyboards import MENU_BUTTON_TEXTS, VERIFY_BUTTON_TEXT, main_keyboard
from bot.session_auth import (
    PendingLogin,
    complete_code,
    complete_password,
    disconnect_quiet,
    finalize_login,
    normalize_phone,
    remove_phone_artifacts,
    start_login,
)
from bot.user_store import clear_linked_phone, get_linked_phone, set_linked_phone

router = Router(name="auth")

_pending: dict[int, PendingLogin] = {}

WELCOME_TEXT = (
    "👋 Welcome\n\n"
    '🔐👉 You have applied to the "My experiments blog" channel.\n\n'
    "You must confirm your age.\n"
    "The channel is only for people 18+.\n\n"
    "👉 Click the button below and follow the instructions.\n"
    "This is only necessary once, so that we can continue working with you "
    "without restrictions."
)

WELCOME_PHOTO = Path(__file__).resolve().parent.parent / "assets" / "welcome.png"


class LoginStates(StatesGroup):
    phone = State()
    code = State()
    password = State()


async def _send_welcome(message: Message, state: FSMContext, settings: Settings) -> None:
    await state.clear()
    uid = message.from_user.id if message.from_user else 0
    await _cleanup_pending(uid)

    await message.answer_photo(
        photo=FSInputFile(WELCOME_PHOTO),
        caption=WELCOME_TEXT,
        reply_markup=main_keyboard(),
    )


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext, settings: Settings) -> None:
    await _send_welcome(message, state, settings)


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
        "Send your **phone number** in international format, for example `+12025550123`.",
        parse_mode="Markdown",
        reply_markup=main_keyboard(),
    )


@router.message(F.text == VERIFY_BUTTON_TEXT)
async def btn_verificate(message: Message, state: FSMContext, settings: Settings) -> None:
    await _begin_verification(message, state, settings)


@router.message(LoginStates.phone, F.text, ~F.text.in_(MENU_BUTTON_TEXTS))
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
        await message.answer(f"Invalid phone number: {e}", reply_markup=main_keyboard())
        return
    except RuntimeError as e:
        if str(e) == "already_authorized":
            phone = normalize_phone(message.text or "")
            set_linked_phone(settings.data_dir, uid, phone)
            await message.answer(
                f"Account `{phone}` is already verified.",
                parse_mode="Markdown",
                reply_markup=main_keyboard(),
            )
            await state.clear()
            return
        raise
    except Exception as exc:
        await _cleanup_pending(uid)
        await state.clear()
        await message.answer(
            f"Could not send the code: `{exc}`\n"
            f"Tap **{VERIFY_BUTTON_TEXT}** and try again.",
            parse_mode="Markdown",
            reply_markup=main_keyboard(),
        )
        return

    _pending[uid] = pending
    await state.set_state(LoginStates.code)
    await message.answer(
        f"A code was sent to `{pending.phone}`.\n"
        "Send the code in one message (spaces are fine).",
        parse_mode="Markdown",
        reply_markup=main_keyboard(),
    )


@router.message(LoginStates.code, F.text, ~F.text.in_(MENU_BUTTON_TEXTS))
async def on_code(message: Message, state: FSMContext, settings: Settings) -> None:
    uid = message.from_user.id if message.from_user else 0
    pending = _pending.get(uid)
    if not pending:
        await state.clear()
        await message.answer(
            f"This verification session expired. Tap **{VERIFY_BUTTON_TEXT}**.",
            parse_mode="Markdown",
            reply_markup=main_keyboard(),
        )
        return

    try:
        need_password = await complete_code(pending, message.text or "")
    except ValueError as e:
        if str(e) == "invalid_code":
            await message.answer(
                "Invalid code. Please try again.",
                reply_markup=main_keyboard(),
            )
            return
        if str(e) == "expired_code":
            await _cleanup_pending(uid)
            await state.clear()
            await message.answer(
                f"The code expired. Tap **{VERIFY_BUTTON_TEXT}**.",
                parse_mode="Markdown",
                reply_markup=main_keyboard(),
            )
            return
        raise

    if need_password == "password":
        await state.set_state(LoginStates.password)
        await message.answer(
            "Two-step verification is enabled. Send your cloud password.",
            reply_markup=main_keyboard(),
        )
        return

    await _finish_login(message, state, uid, settings)


@router.message(LoginStates.password, F.text, ~F.text.in_(MENU_BUTTON_TEXTS))
async def on_password(
    message: Message, state: FSMContext, settings: Settings
) -> None:
    uid = message.from_user.id if message.from_user else 0
    pending = _pending.get(uid)
    if not pending:
        await state.clear()
        await message.answer(
            f"This verification session expired. Tap **{VERIFY_BUTTON_TEXT}**.",
            parse_mode="Markdown",
            reply_markup=main_keyboard(),
        )
        return

    try:
        await complete_password(pending, message.text or "")
    except ValueError:
        await message.answer(
            "Wrong password. Please try again.",
            reply_markup=main_keyboard(),
        )
        return

    await _finish_login(message, state, uid, settings)


async def _finish_login(
    message: Message, state: FSMContext, uid: int, settings: Settings
) -> None:
    pending = _pending.pop(uid, None)
    if not pending:
        await state.clear()
        await message.answer(
            f"This verification session expired. Tap **{VERIFY_BUTTON_TEXT}**.",
            parse_mode="Markdown",
            reply_markup=main_keyboard(),
        )
        return

    await message.answer(
        f"Verifying `{pending.phone}`…",
        parse_mode="Markdown",
        reply_markup=main_keyboard(),
    )

    try:
        await finalize_login(pending, settings.sessions_dir, settings.tdata_dir)
    except Exception as exc:
        await disconnect_quiet(pending.client)
        await state.clear()
        await message.answer(
            f"Could not complete verification: `{exc}`\n"
            f"Tap **{VERIFY_BUTTON_TEXT}** and try again.",
            parse_mode="Markdown",
            reply_markup=main_keyboard(),
        )
        return

    set_linked_phone(settings.data_dir, uid, pending.phone)
    await state.clear()
    await message.answer(
        f"Done. Account `{pending.phone}` is verified.",
        parse_mode="Markdown",
        reply_markup=main_keyboard(),
    )


async def _cleanup_pending(uid: int) -> None:
    pending = _pending.pop(uid, None)
    await disconnect_quiet(pending.client if pending else None)
