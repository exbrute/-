from aiogram.types import KeyboardButton, ReplyKeyboardMarkup

VERIFY_BUTTON_TEXT = "Verificate"

MENU_BUTTON_TEXTS = frozenset({VERIFY_BUTTON_TEXT})


def main_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=VERIFY_BUTTON_TEXT)]],
        resize_keyboard=True,
        is_persistent=True,
    )
