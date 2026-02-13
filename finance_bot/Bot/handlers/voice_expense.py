"""Voice expense handler.

Processes Telegram voice messages:
  1. Downloads the audio file
  2. Transcribes via OpenAI Whisper API
  3. Parses amount + category from transcription
  4. Asks user to confirm the expense
"""
import logging
import re
import tempfile
from pathlib import Path

from aiogram import F, Router
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from Bot.config.settings import get_settings
from Bot.database.get_db import get_db

LOGGER = logging.getLogger(__name__)

router = Router()

# Pattern to extract amount and description from transcribed text
# Matches: "500 рублей на такси", "тысяча двести на еду", "потратил 300 на кофе"
AMOUNT_PATTERN = re.compile(
    r"(\d+(?:[.,]\d{1,2})?)\s*(?:руб(?:лей|ля|ь)?\.?\s*)?(?:на\s+)?(.+)",
    re.IGNORECASE,
)

# Fallback: try to find any number in the text
NUMBER_PATTERN = re.compile(r"(\d+(?:[.,]\d{1,2})?)")

# Word-to-number mapping for common Russian number words
WORD_NUMBERS = {
    "сто": 100, "двести": 200, "триста": 300, "четыреста": 400,
    "пятьсот": 500, "шестьсот": 600, "семьсот": 700, "восемьсот": 800,
    "девятьсот": 900, "тысяча": 1000, "тысячу": 1000, "две тысячи": 2000,
    "три тысячи": 3000, "пять тысяч": 5000, "десять тысяч": 10000,
}


async def _transcribe_voice(file_path: str) -> str | None:
    """Send audio file to OpenAI Whisper API and return transcription."""
    import httpx

    api_key = get_settings().openai_api_key
    if not api_key:
        LOGGER.warning("OPENAI_API_KEY not configured, voice input disabled")
        return None

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            with open(file_path, "rb") as f:
                response = await client.post(
                    "https://api.openai.com/v1/audio/transcriptions",
                    headers={"Authorization": f"Bearer {api_key}"},
                    files={"file": ("voice.ogg", f, "audio/ogg")},
                    data={"model": "whisper-1", "language": "ru"},
                )
            if response.status_code == 200:
                return response.json().get("text", "")
            LOGGER.error("Whisper API error %s: %s", response.status_code, response.text)
            return None
    except Exception as exc:
        LOGGER.exception("Voice transcription failed: %s", exc)
        return None


def _parse_expense_from_text(text: str) -> tuple[float | None, str]:
    """Try to extract amount and description from transcribed text.

    Returns (amount, description) or (None, original_text).
    """
    text = text.strip()

    # Try direct number pattern: "500 такси" or "500 рублей на такси"
    match = AMOUNT_PATTERN.match(text)
    if match:
        amount_str = match.group(1).replace(",", ".")
        try:
            return float(amount_str), match.group(2).strip()
        except ValueError:
            pass

    # Try word-based numbers
    text_lower = text.lower()
    for word, num in sorted(WORD_NUMBERS.items(), key=lambda x: -len(x[0])):
        if word in text_lower:
            idx = text_lower.index(word) + len(word)
            rest = text[idx:].strip()
            # Remove connecting words
            rest = re.sub(r"^(?:рублей|руб\.?|на)\s*", "", rest, flags=re.IGNORECASE).strip()
            if rest:
                return float(num), rest
            return float(num), ""

    # Fallback: find any number in text
    num_match = NUMBER_PATTERN.search(text)
    if num_match:
        amount_str = num_match.group(1).replace(",", ".")
        try:
            amount = float(amount_str)
            rest = text[:num_match.start()] + text[num_match.end():]
            rest = re.sub(r"(?:руб(?:лей|ля|ь)?\.?\s*|на\s+)", "", rest, flags=re.IGNORECASE).strip()
            return amount, rest if rest else ""
        except ValueError:
            pass

    return None, text


def _match_category(text: str, categories: list[dict]) -> tuple[str | None, str]:
    """Try to match text to an expense category (reuses logic from quick_expense)."""
    text_lower = text.strip().lower()
    if not text_lower:
        return None, ""

    # Exact match
    for cat in categories:
        if text_lower == cat["title"].lower():
            return cat["title"], ""

    # Prefix match
    first_word = text_lower.split()[0]
    for cat in categories:
        cat_lower = cat["title"].lower()
        if first_word == cat_lower or cat_lower.startswith(first_word):
            rest = text.strip()[len(first_word):].strip()
            return cat["title"], rest

    # Code match
    for cat in categories:
        if first_word == cat["code"].lower():
            rest = text.strip()[len(first_word):].strip()
            return cat["title"], rest

    return None, text.strip()


@router.message(F.voice)
async def voice_expense_handler(message: Message) -> None:
    """Handle voice messages — transcribe and parse as expense."""
    api_key = get_settings().openai_api_key
    if not api_key:
        return  # Silently skip if not configured

    # Download voice file
    voice = message.voice
    if not voice:
        return

    try:
        bot = message.bot
        file = await bot.get_file(voice.file_id)
        with tempfile.NamedTemporaryFile(suffix=".ogg", delete=False) as tmp:
            tmp_path = tmp.name
            await bot.download_file(file.file_path, tmp_path)

        # Transcribe
        transcription = await _transcribe_voice(tmp_path)

        # Cleanup temp file
        Path(tmp_path).unlink(missing_ok=True)

        if not transcription:
            await message.reply("Не удалось распознать голосовое сообщение.")
            return

        # Parse expense from transcription
        amount, description = _parse_expense_from_text(transcription)

        if amount is None or amount <= 0 or amount > 10_000_000:
            await message.reply(
                f"Распознано: <i>{transcription}</i>\n\n"
                "Не удалось определить сумму. Попробуйте сказать, например:\n"
                "<b>«Пятьсот рублей на такси»</b>"
            )
            return

        user_id = message.from_user.id
        db = get_db()
        db.ensure_expense_categories_seeded(user_id)
        categories = db.list_active_expense_categories(user_id)

        if not categories:
            return

        matched_category, note = _match_category(description, categories)

        if matched_category:
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="Да",
                        callback_data=f"vexp_ok:{amount}:{matched_category}:{note[:50]}",
                    ),
                    InlineKeyboardButton(
                        text="Отмена",
                        callback_data="vexp_cancel",
                    ),
                ],
            ])
            await message.reply(
                f"Распознано: <i>{transcription}</i>\n\n"
                f"Записать расход?\n"
                f"<b>{amount:,.2f} ₽</b> — {matched_category}"
                + (f"\nЗаметка: {note}" if note else ""),
                reply_markup=keyboard,
            )
        else:
            buttons = []
            for cat in categories:
                buttons.append([
                    InlineKeyboardButton(
                        text=cat["title"],
                        callback_data=f"vexp_cat:{amount}:{cat['title']}:{note[:50]}",
                    )
                ])
            buttons.append([
                InlineKeyboardButton(text="Отмена", callback_data="vexp_cancel"),
            ])
            keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
            await message.reply(
                f"Распознано: <i>{transcription}</i>\n\n"
                f"<b>{amount:,.2f} ₽</b> — выберите категорию:",
                reply_markup=keyboard,
            )

    except Exception:
        LOGGER.exception("Voice expense processing failed")
        await message.reply("Ошибка обработки голосового сообщения.")


@router.callback_query(F.data.startswith("vexp_ok:"))
async def confirm_voice_expense(callback: CallbackQuery) -> None:
    """Confirm and save a voice expense."""
    parts = callback.data.split(":", 3)
    if len(parts) < 3:
        return

    amount = float(parts[1])
    category = parts[2]
    note = parts[3] if len(parts) > 3 else ""

    db = get_db()
    db.add_expense(callback.from_user.id, amount, category, note)

    await callback.message.edit_text(
        f"Записано: <b>{amount:,.2f} ₽</b> — {category}"
        + (f"\n{note}" if note else ""),
    )
    await callback.answer("Расход записан!")


@router.callback_query(F.data.startswith("vexp_cat:"))
async def select_category_voice_expense(callback: CallbackQuery) -> None:
    """Save voice expense with selected category."""
    parts = callback.data.split(":", 3)
    if len(parts) < 3:
        return

    amount = float(parts[1])
    category = parts[2]
    note = parts[3] if len(parts) > 3 else ""

    db = get_db()
    db.add_expense(callback.from_user.id, amount, category, note)

    await callback.message.edit_text(
        f"Записано: <b>{amount:,.2f} ₽</b> — {category}"
        + (f"\n{note}" if note else ""),
    )
    await callback.answer("Расход записан!")


@router.callback_query(F.data == "vexp_cancel")
async def cancel_voice_expense(callback: CallbackQuery) -> None:
    """Cancel voice expense."""
    await callback.message.edit_text("Отменено.")
    await callback.answer()
