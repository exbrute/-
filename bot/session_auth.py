from __future__ import annotations

import re
import shutil
from dataclasses import dataclass
from pathlib import Path

from opentele.api import UseCurrentSession
from opentele.tl import TelegramClient
from telethon.errors import (
    PasswordHashInvalidError,
    PhoneCodeExpiredError,
    PhoneCodeInvalidError,
    SessionPasswordNeededError,
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


def phone_slug(phone: str) -> str:
    """Имя файлов/папок: только цифры номера (без `+`)."""
    return re.sub(r"\D", "", normalize_phone(phone))


def session_file_path(sessions_dir: str, phone: str) -> Path:
    return Path(sessions_dir) / f"{phone_slug(phone)}.session"


def session_stem_path(sessions_dir: str, phone: str) -> Path:
    return Path(sessions_dir) / phone_slug(phone)


def tdata_account_dir(tdata_dir: str, phone: str) -> Path:
    """Каталог аккаунта внутри корня `tdata/`."""
    return Path(tdata_dir) / phone_slug(phone)


def remove_phone_artifacts(sessions_dir: str, tdata_dir: str, phone: str) -> None:
    session = session_file_path(sessions_dir, phone)
    for candidate in (session, Path(f"{session}-journal")):
        if candidate.is_file():
            candidate.unlink()

    account_tdata = tdata_account_dir(tdata_dir, phone)
    if account_tdata.is_dir():
        shutil.rmtree(account_tdata)


@dataclass
class PendingLogin:
    phone: str
    client: TelegramClient


async def create_connected_client(
    api_id: int, api_hash: str, sessions_dir: str, phone: str
) -> TelegramClient:
    Path(sessions_dir).mkdir(parents=True, exist_ok=True)
    client = TelegramClient(
        str(session_stem_path(sessions_dir, phone)),
        api_id,
        api_hash,
    )
    await client.connect()
    return client


async def start_login(
    api_id: int,
    api_hash: str,
    sessions_dir: str,
    tdata_dir: str,
    phone_raw: str,
) -> PendingLogin:
    phone = normalize_phone(phone_raw)
    remove_phone_artifacts(sessions_dir, tdata_dir, phone)

    client = await create_connected_client(api_id, api_hash, sessions_dir, phone)
    if await client.is_user_authorized():
        await client.disconnect()
        raise RuntimeError("already_authorized")

    await client.send_code_request(phone)
    return PendingLogin(phone=phone, client=client)


async def complete_code(pending: PendingLogin, code_raw: str) -> str | None:
    code = re.sub(r"\s", "", code_raw.strip())
    try:
        await pending.client.sign_in(pending.phone, code)
    except SessionPasswordNeededError:
        return "password"
    except PhoneCodeInvalidError:
        raise ValueError("invalid_code")
    except PhoneCodeExpiredError:
        raise ValueError("expired_code")
    return None


async def complete_password(pending: PendingLogin, password: str) -> None:
    try:
        await pending.client.sign_in(password=password.strip())
    except PasswordHashInvalidError:
        raise ValueError("invalid_password")


async def export_tdata(client: TelegramClient, dest: Path) -> None:
    if dest.exists():
        shutil.rmtree(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    tdesk = await client.ToTDesktop(flag=UseCurrentSession)
    tdesk.SaveTData(str(dest))


async def finalize_login(
    pending: PendingLogin, sessions_dir: str, tdata_dir: str
) -> tuple[Path, Path]:
    tdata = tdata_account_dir(tdata_dir, pending.phone)
    await export_tdata(pending.client, tdata)
    await disconnect_quiet(pending.client)
    return session_file_path(sessions_dir, pending.phone), tdata


async def disconnect_quiet(client: TelegramClient | None) -> None:
    if client is None:
        return
    try:
        if client.is_connected():
            await client.disconnect()
    except Exception:
        pass
