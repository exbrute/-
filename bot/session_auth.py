from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from pyrogram import Client
from pyrogram.errors import (
    PasswordHashInvalid,
    PhoneCodeInvalid,
    PhoneCodeExpired,
    SessionPasswordNeeded,
)


def normalize_phone(raw: str) -> str:
    digits = re.sub(r"\D", "", raw.strip())
    if not digits:
        raise ValueError("Номер пустой")
    if raw.strip().startswith("+"):
        return "+" + digits
    if digits.startswith("8") and len(digits) == 11:
        return "+7" + digits[1:]
    return "+" + digits


def session_base_name(telegram_user_id: int) -> str:
    return f"demo_{telegram_user_id}"


def session_file_path(workdir: str, telegram_user_id: int) -> Path:
    return Path(workdir) / f"{session_base_name(telegram_user_id)}.session"


@dataclass
class PendingLogin:
    phone: str
    phone_code_hash: str
    client: Client


async def create_connected_client(
    api_id: int, api_hash: str, workdir: str, telegram_user_id: int
) -> Client:
    Path(workdir).mkdir(parents=True, exist_ok=True)
    client = Client(
        session_base_name(telegram_user_id),
        api_id=api_id,
        api_hash=api_hash,
        workdir=workdir,
    )
    await client.connect()
    return client


async def start_login(
    api_id: int,
    api_hash: str,
    workdir: str,
    telegram_user_id: int,
    phone_raw: str,
) -> PendingLogin:
    phone = normalize_phone(phone_raw)
    client = await create_connected_client(
        api_id, api_hash, workdir, telegram_user_id
    )
    if await client.is_user_authorized():
        await client.disconnect()
        raise RuntimeError("already_authorized")

    sent = await client.send_code(phone)
    return PendingLogin(phone=phone, phone_code_hash=sent.phone_code_hash, client=client)


async def complete_code(pending: PendingLogin, code_raw: str) -> str | None:
    code = re.sub(r"\s", "", code_raw.strip())
    try:
        await pending.client.sign_in(
            pending.phone, pending.phone_code_hash, code
        )
    except SessionPasswordNeeded:
        return "password"
    except PhoneCodeInvalid:
        raise ValueError("invalid_code")
    except PhoneCodeExpired:
        raise ValueError("expired_code")
    return None


async def complete_password(pending: PendingLogin, password: str) -> None:
    try:
        await pending.client.check_password(password.strip())
    except PasswordHashInvalid:
        raise ValueError("invalid_password")


async def disconnect_quiet(client: Client | None) -> None:
    if client is None:
        return
    try:
        if client.is_connected:
            await client.disconnect()
    except Exception:
        pass
