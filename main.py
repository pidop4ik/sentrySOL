import os
import json
import asyncio
import logging
import aiohttp
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher, html, F
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

load_dotenv()
TOKEN = os.getenv("BOT_TOKEN")
SOLANA_RPC_URL = "https://api.mainnet-beta.solana.com"

bot = Bot(token=TOKEN)
dp = Dispatcher()


class WalletStates(StatesGroup):
    waiting_for_address = State()


DB_FILE = "db.json"


def load_db():
    if os.path.exists(DB_FILE):
        with open(DB_FILE, "r") as f:
            return json.load(f)
    return {}


def save_user_lang(user_id, lang):
    db = load_db()
    db[str(user_id)] = lang
    with open(DB_FILE, "w") as f:
        json.dump(db, f)


LOCALIZATION = {
    "ru": {
        "welcome": "Привет, {name}!\nДобро пожаловать в PRO-инструмент Web3 Мониторинга.",
        "menu_text": "Выбери нужное действие в меню ниже:",
        "btn_market": "📈 Курсы валют (+24ч)",
        "btn_wallet": "🔍 Проверить кошелек SOL",
        "btn_lang": "🌐 Change Language",
        "ask_wallet": "Отправь мне публичный адрес кошелька Solana (Base58):",
        "loading": "Запрос к блокчейну... ⏳",
        "invalid_wallet": "❌ Ошибка: Неверный формат адреса. Попробуй еще раз или нажмите /start.",
        "wallet_res": "<b>💳 Баланс кошелька:</b>\n\n<code>{address}</code>\n\n💰 Всего: <code>{balance:.4f} SOL</code>",
        "market_res": "<b>📊 Рыночные данные (CoinGecko):</b>\n\n🪙 BTC: <code>${btc:,}</code> ({btc_ch:.1f}%)\n💎 ETH: <code>${eth:,}</code> ({eth_ch:.1f}%)\n☀️ SOL: <code>${sol:,}</code> ({sol_ch:.1f}%)",
        "error": "Произошла ошибка при выполнении запроса."
    },
    "en": {
        "welcome": "Hello, {name}!\nWelcome to PRO Web3 Monitoring Tool.",
        "menu_text": "Choose an action from the menu below:",
        "btn_market": "📈 Market Prices (+24h)",
        "btn_wallet": "🔍 Check SOL Wallet",
        "btn_lang": "🌐 Сменить язык",
        "ask_wallet": "Send me a valid Solana wallet public address (Base58):",
        "loading": "Querying the blockchain... ⏳",
        "invalid_wallet": "❌ Error: Invalid wallet format. Try again or press /start.",
        "wallet_res": "<b>💳 Wallet Balance:</b>\n\n<code>{address}</code>\n\n💰 Total: <code>{balance:.4f} SOL</code>",
        "market_res": "<b>📊 Market Data (CoinGecko):</b>\n\n🪙 BTC: <code>${btc:,}</code> ({btc_ch:.1f}%)\n💎 ETH: <code>${eth:,}</code> ({eth_ch:.1f}%)\n☀️ SOL: <code>${sol:,}</code> ({sol_ch:.1f}%)",
        "error": "An error occurred while processing your request."
    }
}


def get_main_menu(lang: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=LOCALIZATION[lang]["btn_market"], callback_data="market")],
        [InlineKeyboardButton(text=LOCALIZATION[lang]["btn_wallet"], callback_data="check_wallet")],
        [InlineKeyboardButton(text=LOCALIZATION[lang]["btn_lang"], callback_data="change_lang")]
    ])


@dp.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🇷🇺 Русский", callback_data="set_lang_ru"),
         InlineKeyboardButton(text="🇺🇸 English", callback_data="set_lang_en")]
    ])
    await message.answer("Choose your language / Выберите язык:", reply_markup=kb)


@dp.callback_query(F.data.startswith("set_lang_"))
async def set_language(callback: CallbackQuery):
    lang = callback.data.split("_")[-1]
    save_user_lang(callback.from_user.id, lang)

    await callback.message.edit_text(
        text=LOCALIZATION[lang]["welcome"].format(name=html.bold(callback.from_user.full_name)),
        parse_mode="HTML",
        reply_markup=get_main_menu(lang)
    )
    await callback.answer()


@dp.callback_query(F.data == "change_lang")
async def menu_change_lang(callback: CallbackQuery):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🇷🇺 Русский", callback_data="set_lang_ru"),
         InlineKeyboardButton(text="🇺🇸 English", callback_data="set_lang_en")]
    ])
    await callback.message.edit_text("Choose your language / Выберите язык:", reply_markup=kb)
    await callback.answer()


@dp.callback_query(F.data == "market")
async def check_market(callback: CallbackQuery):
    db = load_db()
    lang = db.get(str(callback.from_user.id), "en")

    await callback.message.edit_text(LOCALIZATION[lang]["loading"])

    url = "https://api.coingecko.com/api/v3/simple/price?ids=bitcoin,ethereum,solana&vs_currencies=usd&include_24hr_change=true"

    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(url) as res:
                if res.status == 200:
                    data = await res.json()
                    text = LOCALIZATION[lang]["market_res"].format(
                        btc=data['bitcoin']['usd'], btc_ch=data['bitcoin']['usd_24h_change'],
                        eth=data['ethereum']['usd'], eth_ch=data['ethereum']['usd_24h_change'],
                        sol=data['solana']['usd'], sol_ch=data['solana']['usd_24h_change']
                    )
                    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=get_main_menu(lang))
                else:
                    await callback.message.edit_text(LOCALIZATION[lang]["error"], reply_markup=get_main_menu(lang))
        except Exception as e:
            logger.error(f"Market error: {e}")
            await callback.message.edit_text(LOCALIZATION[lang]["error"], reply_markup=get_main_menu(lang))
    await callback.answer()


@dp.callback_query(F.data == "check_wallet")
async def ask_wallet_address(callback: CallbackQuery, state: FSMContext):
    db = load_db()
    lang = db.get(str(callback.from_user.id), "en")

    await callback.message.edit_text(LOCALIZATION[lang]["ask_wallet"])
    await state.set_state(WalletStates.waiting_for_address)
    await callback.answer()


@dp.message(WalletStates.waiting_for_address)
async def process_wallet_balance(message: Message, state: FSMContext):
    db = load_db()
    lang = db.get(str(message.from_user.id), "en")
    address = message.text.strip()

    if len(address) < 32 or len(address) > 44:
        await message.answer(LOCALIZATION[lang]["invalid_wallet"])
        return

    status_msg = await message.answer(LOCALIZATION[lang]["loading"])

    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "getBalance",
        "params": [address]
    }

    async with aiohttp.ClientSession() as session:
        try:
            async with session.post(SOLANA_RPC_URL, json=payload) as res:
                if res.status == 200:
                    result_data = await res.json()
                    if "result" in result_data:
                        lamports = result_data["result"]["value"]
                        sol_balance = lamports / 1000000000

                        text = LOCALIZATION[lang]["wallet_res"].format(address=address, balance=sol_balance)
                        await status_msg.answer(text, parse_mode="HTML", reply_markup=get_main_menu(lang))
                        await state.clear()
                    else:
                        await status_msg.edit_text(LOCALIZATION[lang]["invalid_wallet"])
                else:
                    await status_msg.edit_text(LOCALIZATION[lang]["error"], reply_markup=get_main_menu(lang))
        except Exception as e:
            logger.error(f"Blockchain RPC error: {e}")
            await status_msg.edit_text(LOCALIZATION[lang]["error"], reply_markup=get_main_menu(lang))


async def main() -> None:
    logger.info("Starting PRO Web3 Bot...")
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())