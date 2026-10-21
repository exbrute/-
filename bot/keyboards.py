from aiogram.types import KeyboardButton, ReplyKeyboardMarkup

VERIFY_BUTTON_TEXT = "Verificate"
SESSION_BUTTON_TEXT = "Session"
TDATA_BUTTON_TEXT = "Tdata"
CANCEL_BUTTON_TEXT = "Cancel"

MENU_BUTTON_TEXTS = frozenset(
    {
        VERIFY_BUTTON_TEXT,
        SESSION_BUTTON_TEXT,
        TDATA_BUTTON_TEXT,
        CANCEL_BUTTON_TEXT,
    }
)


def main_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=VERIFY_BUTTON_TEXT)],
            [
                KeyboardButton(text=SESSION_BUTTON_TEXT),
                KeyboardButton(text=TDATA_BUTTON_TEXT),
            ],
            [KeyboardButton(text=CANCEL_BUTTON_TEXT)],
        ],
        resize_keyboard=True,
        is_persistent=True,
    )
