"""
🎬 Qashqirlar Makoni — Kino Bot
- Ombor (storage) guruh/kanal ulashish + admin qilinsa avtomatik xabar
- Admin ombor bo'limi: qo'shish / yangilash / o'chirish / sarlavha o'zgartirish
- Foydalanuvchi: /start da 10 talik seriya, pastida Keyingi / Orqaga
- Har bir videoda: 📢 @Tamosha_Vaqti obuna bo'ling (yuboruvchi/izoh yashirin)
- Admin reklama: hammaga yuborish + hisobot + .txt fayl
- Foydalanuvchida: ℹ️ Malumot
"""
import asyncio
import logging
import os
from datetime import datetime

from aiogram import Bot, Dispatcher, F, Router
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode, ChatType
from aiogram.exceptions import TelegramAPIError, TelegramForbiddenError
from aiogram.filters import Command, CommandStart, ChatMemberUpdatedFilter, KICKED, MEMBER, ADMINISTRATOR, CREATOR
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import (
    Message, CallbackQuery, FSInputFile, InlineKeyboardButton,
    InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton,
)
from dotenv import load_dotenv

import database as db

load_dotenv()
logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
log = logging.getLogger(__name__)

# ---------- Konfiguratsiya (Railway Variables) ----------
BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
ADMIN_ID_RAW = os.getenv("ADMIN_ID", "").strip()
CHANNEL_USERNAME = os.getenv("CHANNEL_USERNAME", "Tamosha_Vaqti").strip().lstrip("@")
PAGE_SIZE = int(os.getenv("PAGE_SIZE", "10"))

if not BOT_TOKEN:
    raise SystemExit("❌ BOT_TOKEN topilmadi! Railway -> Variables ga BOT_TOKEN qo'shing.")
if not ADMIN_ID_RAW:
    raise SystemExit("❌ ADMIN_ID topilmadi! Railway -> Variables ga ADMIN_ID qo'shing.")

ADMIN_IDS = {int(x.strip()) for x in ADMIN_ID_RAW.replace(";", ",").split(",") if x.strip().isdigit()}

SUBSCRIBE_LINE = f"📢 @{CHANNEL_USERNAME} obuna bo'ling"


def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS


# ---------- Klaviaturalar ----------
def user_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🎬 Kino ber")],
            [KeyboardButton(text="ℹ️ Malumot")],
        ],
        resize_keyboard=True,
    )


def admin_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🎬 Kino ber"), KeyboardButton(text="ℹ️ Malumot")],
            [KeyboardButton(text="📦 Ombor")],
            [KeyboardButton(text="👥 Foydalanuvchilar"), KeyboardButton(text="📊 Statistika")],
            [KeyboardButton(text="📢 Reklama yuborish")],
        ],
        resize_keyboard=True,
    )


def page_keyboard(page: int, total_pages: int) -> InlineKeyboardMarkup:
    buttons = []
    row = []
    if page > 0:
        row.append(InlineKeyboardButton(text="⬅️ Orqaga", callback_data=f"page:{page - 1}"))
    if page < total_pages - 1:
        row.append(InlineKeyboardButton(text="Keyingi ➡️", callback_data=f"page:{page + 1}"))
    if row:
        buttons.append(row)
    buttons.append([InlineKeyboardButton(text="ℹ️ Malumot", callback_data="info")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def ombor_menu_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📋 Videolar ro'yxati", callback_data="ombor_list:0")],
        [InlineKeyboardButton(text="➕ Video qo'shish (yo'riqnoma)", callback_data="ombor_add")],
        [InlineKeyboardButton(text="🔗 Ombor ulashish / almashtirish", callback_data="ombor_share")],
        [InlineKeyboardButton(text="🔄 Yangilash (ombor holati)", callback_data="ombor_refresh")],
        [InlineKeyboardButton(text="🗑 Raqam bo'yicha o'chirish", callback_data="ombor_del_by_num")],
        [InlineKeyboardButton(text="❌ Omborni uzish", callback_data="ombor_unlink")],
    ])


def video_view_keyboard(video_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✏️ Sarlavhani o'zgartirish", callback_data=f"vid_edit:{video_id}")],
        [InlineKeyboardButton(text="🗑 O'chirish", callback_data=f"vid_del:{video_id}")],
        [InlineKeyboardButton(text="⬅️ Ro'yxatga qaytish", callback_data="ombor_list:0")],
    ])


# ---------- FSM ----------
class AdminStates(StatesGroup):
    waiting_broadcast = State()
    waiting_share = State()
    waiting_edit_caption = State()
    waiting_delete_number = State()


# ---------- Yordamchi ----------
def make_caption(original: str | None) -> str:
    base = (original or "").strip()
    if SUBSCRIBE_LINE in base:
        return base
    if base:
        return f"{base}\n\n{SUBSCRIBE_LINE}"
    return SUBSCRIBE_LINE


async def send_page(bot: Bot, chat_id: int, page: int):
    """10 talik seriyani yuborish (eng avval yuborilgani tepada)."""
    total = await db.get_video_count()
    if total == 0:
        await bot.send_message(
            chat_id,
            "📭 Hozircha omborda hech qanday video yo'q.\n"
            "Admin videolarni omborga qo'shgach shu yerda chiqadi.",
            reply_markup=page_keyboard(0, 1),
        )
        return
    total_pages = (total + PAGE_SIZE - 1) // PAGE_SIZE
    page = max(0, min(page, total_pages - 1))
    videos = await db.get_videos_page(page * PAGE_SIZE, PAGE_SIZE)

    start_num = page * PAGE_SIZE + 1
    for i, v in enumerate(videos, start=start_num):
        try:
            await bot.send_video(
                chat_id=chat_id,
                video=v["file_id"],
                caption=make_caption(v.get("caption")),
                duration=v.get("duration") or None,
            )
        except TelegramAPIError as e:
            log.warning("Video yuborishda xato (id=%s): %s", v["id"], e)
            continue

    await bot.send_message(
        chat_id,
        f"🎬 Seriya {page + 1}/{total_pages}  •  Videolar {start_num}–{start_num + len(videos) - 1} / {total}",
        reply_markup=page_keyboard(page, total_pages),
    )


async def ombor_status_text(bot: Bot) -> str:
    storage_id = await db.get_setting("storage_chat_id")
    storage_title = await db.get_setting("storage_title")
    total = await db.get_video_count()
    if storage_id:
        text = (
            "📦 <b>Ombor holati</b>\n\n"
            f"🔗 Ulangan ombor: <b>{storage_title or '—'}</b>\n"
            f"🆔 Chat ID: <code>{storage_id}</code>\n"
            f"🎞 Ombordagi videolar: <b>{total} ta</b>\n\n"
            "Videolar omborga yuborilgan tartibda saqlanadi — "
            "eng avval yuborilgani eng tepada chiqadi."
        )
    else:
        text = (
            "📦 <b>Ombor holati</b>\n\n"
            "⚠️ Ombor hali ulanmagan!\n"
            "Pastdagi «Ombor ulashish» tugmasini bosing va "
            "ombor guruh/kanaldan botga istalgan xabarni forward qiling."
        )
    return text


# ---------- Router ----------
router = Router()


# ===== START =====
@router.message(CommandStart())
async def cmd_start(message: Message):
    user = message.from_user
    await db.upsert_user(user.id, user.username, user.full_name)
    if is_admin(user.id):
        await message.answer(
            "👋 Salom, Admin!\n\n"
            "📦 <b>Ombor</b> — videolarni boshqarish\n"
            "📢 <b>Reklama yuborish</b> — hammaga xabar\n"
            "👥 <b>Foydalanuvchilar</b> — ro'yxat va statistika\n\n"
            "Pastdagi tugmalar orqali boshqaring. "
            "Foydalanuvchilar kabi kino ko'rish uchun «🎬 Kino ber» ni bosing.",
            reply_markup=admin_keyboard(),
        )
        return
    await message.answer(
        "👋 Salom! 🎬\n\n"
        "Sizga birinchi seriyani yuboryapman — 10 ta video.\n"
        "Pastdagi «Keyingi ➡️» bilan davom ettiring.",
        reply_markup=user_keyboard(),
    )
    await send_page(message.bot, message.chat.id, 0)


# ===== BOT GURUH/KANALGA ADMIN QILINSA — AVTO XABAR =====
@router.my_chat_member(
    ChatMemberUpdatedFilter(
        member_status_changed=(KICKED | MEMBER) >> (ADMINISTRATOR | CREATOR),
    )
)
async def bot_became_admin(event, bot: Bot):
    chat = event.chat
    if chat.type not in (ChatType.GROUP, ChatType.SUPERGROUP, ChatType.CHANNEL):
        return
    # Ombor sifatida avtomatik ulash
    await db.set_setting("storage_chat_id", str(chat.id))
    await db.set_setting("storage_title", chat.title or chat.full_name or str(chat.id))

    auto_text = (
        "✅ <b>Men admin qilindim!</b>\n\n"
        "Endi bu guruh/kanal <b>ombor</b> sifatida ishlatiladi. 📦\n\n"
        "📌 <b>Qanday video qo'shiladi?</b>\n"
        "• Bu yerga video yuboring — bot avtomatik omborga saqlaydi\n"
        "• Yoki videoni botning shaxsiy chatiga forward qiling\n\n"
        "🎬 Foydalanuvchilar «Kino ber» deganda videolar "
        "shu yerdan, yuborilgan tartibda chiqadi.\n"
        f"{SUBSCRIBE_LINE}"
    )
    try:
        await bot.send_message(chat.id, auto_text, parse_mode=ParseMode.HTML)
    except TelegramAPIError as e:
        log.warning("Avto xabar yuborib bo'lmadi: %s", e)

    # Admin(lar)ga shaxsiy xabar
    for admin_id in ADMIN_IDS:
        try:
            await bot.send_message(
                admin_id,
                f"🔔 <b>Bot yangi omborda admin qilindi!</b>\n\n"
                f"📦 Ombor: <b>{chat.title or chat.full_name or '—'}</b>\n"
                f"🆔 Chat ID: <code>{chat.id}</code>\n"
                f"🔗 Holat: avtomatik ulandi ✅\n\n"
                "Endi shu guruh/kanalga video yuborsangiz omborga qo'shiladi.",
                parse_mode=ParseMode.HTML,
            )
        except TelegramAPIError:
            pass


# ===== FOYDALANUVCHI: KINO BER / MALUMOT =====
@router.message(F.text == "🎬 Kino ber")
async def user_kino(message: Message):
    if message.from_user:
        await db.upsert_user(message.from_user.id, message.from_user.username, message.from_user.full_name)
    await send_page(message.bot, message.chat.id, 0)


@router.message(F.text == "ℹ️ Malumot")
async def user_info(message: Message):
    total = await db.get_video_count()
    users = await db.get_user_count()
    await message.answer(
        "ℹ️ <b>Malumot</b>\n\n"
        f"🎬 Ombordagi videolar: <b>{total} ta</b>\n"
        f"👥 Ro'yxatdan o'tgan foydalanuvchilar: <b>{users} ta</b>\n\n"
        "📺 <b>Qanday ishlaydi?</b>\n"
        "• «🎬 Kino ber» ni bosing — birinchi 10 talik seriya chiqadi\n"
        "• «Keyingi ➡️» — keyingi 10 talik, «⬅️ Orqaga» — oldingi qism\n"
        "• Videolar omborga yuborilgan tartibda, eng avvali tepada\n\n"
        f"{SUBSCRIBE_LINE}\n"
        f"📢 Kanal: @{CHANNEL_USERNAME}",
        parse_mode=ParseMode.HTML,
        reply_markup=admin_keyboard() if is_admin(message.from_user.id) else user_keyboard(),
    )


@router.callback_query(F.data.startswith("page:"))
async def on_page(callback: CallbackQuery):
    page = int(callback.data.split(":")[1])
    await callback.answer()
    try:
        await callback.message.delete()
    except TelegramAPIError:
        pass
    await send_page(callback.bot, callback.message.chat.id, page)


@router.callback_query(F.data == "info")
async def on_info(callback: CallbackQuery):
    await callback.answer()
    total = await db.get_video_count()
    await callback.message.answer(
        "ℹ️ <b>Malumot</b>\n\n"
        f"🎬 Ombordagi videolar: <b>{total} ta</b>\n\n"
        "📺 «Keyingi ➡️» — keyingi 10 talik video, «⬅️ Orqaga» — oldingi qism.\n\n"
        f"{SUBSCRIBE_LINE}",
        parse_mode=ParseMode.HTML,
    )


# ===== ADMIN: OMBOR BO'LIMI =====
@router.message(F.text == "📦 Ombor")
async def admin_ombor(message: Message):
    if not is_admin(message.from_user.id):
        await message.answer("⛔ Bu bo'lim faqat admin uchun.")
        return
    await message.answer(
        await ombor_status_text(message.bot),
        parse_mode=ParseMode.HTML,
        reply_markup=ombor_menu_keyboard(),
    )


@router.callback_query(F.data == "ombor_add")
async def ombor_add(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return await callback.answer("⛔", show_alert=True)
    await callback.answer()
    await callback.message.answer(
        "➕ <b>Video qo'shish</b>\n\n"
        "Usul 1: videoni <b>ombor guruh/kanaliga</b> yuboring — bot avtomatik saqlaydi.\n"
        "Usul 2: videoni <b>shu botga</b> (shaxsiy chatga) yuboring yoki forward qiling.\n\n"
        "Videolar yuborilgan tartibda saqlanadi — eng avval yuborilgani eng tepada chiqadi.",
        parse_mode=ParseMode.HTML,
    )


@router.callback_query(F.data == "ombor_share")
async def ombor_share(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        return await callback.answer("⛔", show_alert=True)
    await callback.answer()
    await state.set_state(AdminStates.waiting_share)
    await callback.message.answer(
        "🔗 <b>Ombor ulashish</b>\n\n"
        "Quyidagilardan birini qiling:\n"
        "1️⃣ Ombor guruh/kanalidan botga istalgan xabarni <b>forward</b> qiling, yoki\n"
        "2️⃣ Chat ID ni yozing (masalan: <code>-1001234567890</code>)\n\n"
        "⚠️ Bot o'sha guruh/kanalda <b>admin</b> bo'lishi shart!",
        parse_mode=ParseMode.HTML,
    )


@router.message(AdminStates.waiting_share)
async def ombor_share_received(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    if message.text and message.text.startswith("/"):
        return
    chat_id = None
    title = None
    if message.forward_from_chat:
        chat_id = message.forward_from_chat.id
        title = message.forward_from_chat.title or message.forward_from_chat.full_name
    elif message.text and message.text.strip().lstrip("-").isdigit():
        chat_id = int(message.text.strip())
    else:
        await message.answer("❌ Forward qilingan xabar yoki Chat ID yuboring. Bekor qilish uchun /cancel")
        return

    try:
        chat = await message.bot.get_chat(chat_id)
        title = chat.title or chat.full_name or str(chat_id)
    except TelegramAPIError as e:
        await message.answer(f"❌ Omborga ulanib bo'lmadi: {e}\nBot o'sha yerda adminmi, tekshiring.")
        return

    await db.set_setting("storage_chat_id", str(chat_id))
    await db.set_setting("storage_title", str(title))
    await state.clear()
    await message.answer(
        f"✅ Ombor ulandi!\n\n🔗 <b>{title}</b>\n🆔 <code>{chat_id}</code>\n\n"
        "Endi shu yerga video yuborsangiz omborga qo'shiladi.",
        parse_mode=ParseMode.HTML,
        reply_markup=admin_keyboard(),
    )


@router.callback_query(F.data == "ombor_refresh")
async def ombor_refresh(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return await callback.answer("⛔", show_alert=True)
    await callback.answer("Yangilanmoqda...")
    storage_id = await db.get_setting("storage_chat_id")
    total = await db.get_video_count()
    if not storage_id:
        await callback.message.answer("⚠️ Ombor ulanmagan. Avval «Ombor ulashish» ni qiling.")
        return
    try:
        chat = await callback.bot.get_chat(int(storage_id))
        title = chat.title or chat.full_name or str(storage_id)
        await db.set_setting("storage_title", str(title))
        await callback.message.answer(
            f"🔄 <b>Yangilandi!</b>\n\n"
            f"🔗 Ombor: <b>{title}</b>\n"
            f"🆔 <code>{storage_id}</code>\n"
            f"🎞 Ombordagi videolar: <b>{total} ta</b>\n"
            f"✅ Bot omborda admin sifatida mavjud",
            parse_mode=ParseMode.HTML,
            reply_markup=ombor_menu_keyboard(),
        )
    except TelegramAPIError as e:
        await callback.message.answer(
            f"❌ Omborga ulanib bo'lmadi: {e}\n"
            "Botni omborda admin qiling yoki omborni qayta ulang.",
            reply_markup=ombor_menu_keyboard(),
        )


@router.callback_query(F.data == "ombor_unlink")
async def ombor_unlink(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return await callback.answer("⛔", show_alert=True)
    await callback.answer()
    await db.delete_setting("storage_chat_id")
    await db.delete_setting("storage_title")
    await callback.message.answer(
        "❌ Ombor uzildi. Videolar bazada qolmoqda — yangi ombor ulasangiz davom etadi.",
        reply_markup=ombor_menu_keyboard(),
    )


@router.callback_query(F.data.startswith("ombor_list:"))
async def ombor_list(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return await callback.answer("⛔", show_alert=True)
    await callback.answer()
    page = int(callback.data.split(":")[1])
    videos = await db.get_all_videos()
    if not videos:
        await callback.message.answer("📭 Omborda hozircha video yo'q.")
        return
    per_page = 10
    total_pages = (len(videos) + per_page - 1) // per_page
    page = max(0, min(page, total_pages - 1))
    chunk = videos[page * per_page:(page + 1) * per_page]

    rows = []
    for v in chunk:
        cap = (v.get("caption") or "Sarlavhasiz video")[:40]
        rows.append([InlineKeyboardButton(text=f"#{v['id']}  {cap}", callback_data=f"vid:{v['id']}")])
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton(text="⬅️", callback_data=f"ombor_list:{page - 1}"))
    if page < total_pages - 1:
        nav.append(InlineKeyboardButton(text="➡️", callback_data=f"ombor_list:{page + 1}"))
    if nav:
        rows.append(nav)
    rows.append([InlineKeyboardButton(text="📦 Ombor menyusi", callback_data="ombor_back")])

    await callback.message.answer(
        f"📋 <b>Ombordagi videolar</b> (jami {len(videos)} ta, sahifa {page + 1}/{total_pages})\n"
        "Ko'rish / o'zgartirish / o'chirish uchun videoni bosing:",
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=rows),
    )


@router.callback_query(F.data == "ombor_back")
async def ombor_back(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return await callback.answer("⛔", show_alert=True)
    await callback.answer()
    await callback.message.answer(
        await ombor_status_text(callback.bot),
        parse_mode=ParseMode.HTML,
        reply_markup=ombor_menu_keyboard(),
    )


@router.callback_query(F.data.startswith("vid:"))
async def video_view(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return await callback.answer("⛔", show_alert=True)
    await callback.answer()
    vid_id = int(callback.data.split(":")[1])
    v = await db.get_video_by_id(vid_id)
    if not v:
        await callback.message.answer("❌ Video topilmadi (o'chirilgan bo'lishi mumkin).")
        return
    await callback.message.answer_video(
        video=v["file_id"],
        caption=f"#{v['id']} • {(v.get('caption') or 'Sarlavhasiz')[:500]}",
        reply_markup=video_view_keyboard(vid_id),
    )


@router.callback_query(F.data.startswith("vid_del:"))
async def video_delete(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return await callback.answer("⛔", show_alert=True)
    await callback.answer()
    vid_id = int(callback.data.split(":")[1])
    await db.delete_video(vid_id)
    await callback.message.answer(
        f"🗑 #{vid_id} videosi ombordan o'chirildi.",
        reply_markup=ombor_menu_keyboard(),
    )


@router.callback_query(F.data.startswith("vid_edit:"))
async def video_edit_start(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        return await callback.answer("⛔", show_alert=True)
    await callback.answer()
    vid_id = int(callback.data.split(":")[1])
    await state.set_state(AdminStates.waiting_edit_caption)
    await state.update_data(video_id=vid_id)
    await callback.message.answer(
        f"✏️ #{vid_id} uchun yangi sarlavhani yozing:\n"
        "(Foydalanuvchiga yuborilganda pastiga avtomatik "
        f"«{SUBSCRIBE_LINE}» qo'shiladi)",
    )


@router.message(AdminStates.waiting_edit_caption)
async def video_edit_save(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    data = await state.get_data()
    vid_id = data.get("video_id")
    if not vid_id:
        await state.clear()
        return
    await db.update_caption(vid_id, message.text or "")
    await state.clear()
    await message.answer(f"✅ #{vid_id} sarlavhasi yangilandi.", reply_markup=ombor_menu_keyboard())


@router.callback_query(F.data == "ombor_del_by_num")
async def del_by_num_start(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        return await callback.answer("⛔", show_alert=True)
    await callback.answer()
    await state.set_state(AdminStates.waiting_delete_number)
    await callback.message.answer("🗑 O'chiriladigan video raqamini yozing (masalan: 5)")


@router.message(AdminStates.waiting_delete_number)
async def del_by_num_save(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    if not message.text or not message.text.strip().isdigit():
        await message.answer("❌ Raqam yozing (masalan: 5). Bekor qilish: /cancel")
        return
    vid_id = int(message.text.strip())
    v = await db.get_video_by_id(vid_id)
    if not v:
        await message.answer("❌ Bunday raqamli video topilmadi.")
        return
    await db.delete_video(vid_id)
    await state.clear()
    await message.answer(f"🗑 #{vid_id} o'chirildi.", reply_markup=ombor_menu_keyboard())


# ===== ADMIN: FOYDALANUVCHILAR =====
@router.message(F.text == "👥 Foydalanuvchilar")
async def admin_users(message: Message):
    if not is_admin(message.from_user.id):
        await message.answer("⛔ Bu bo'lim faqat admin uchun.")
        return
    users = await db.get_all_users()
    total = len(users)
    blocked = sum(1 for u in users if u.get("is_blocked"))
    lines = ["👥 <b>Foydalanuvchilar</b>\n"]
    for i, u in enumerate(users[:20], 1):
        uname = f"@{u['username']}" if u.get("username") else "—"
        lines.append(f"{i}. {uname} • <code>{u['user_id']}</code> • {u.get('full_name') or ''}")
    if total > 20:
        lines.append(f"\n... va yana {total - 20} ta (to'liq ro'yxat uchun .txt eksport)")
    lines.append(f"\n📊 Jami: <b>{total} ta</b> • Bloklangan: <b>{blocked} ta</b>")
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📄 .txt eksport qilish", callback_data="users_export")],
    ])
    await message.answer("\n".join(lines), parse_mode=ParseMode.HTML, reply_markup=kb)


@router.callback_query(F.data == "users_export")
async def users_export(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return await callback.answer("⛔", show_alert=True)
    await callback.answer()
    users = await db.get_all_users()
    text_lines = [
        "FOYDALANUVCHILAR RO'YXATI",
        f"Sana: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        f"Jami: {len(users)} ta",
        "=" * 50,
    ]
    for i, u in enumerate(users, 1):
        uname = f"@{u['username']}" if u.get("username") else "(username yo'q)"
        text_lines.append(
            f"{i}. Username: {uname} | ID: {u['user_id']} | "
            f"Ism: {u.get('full_name') or '—'} | Holat: {'Bloklangan' if u.get('is_blocked') else 'Faol'}"
        )
    content = "\n".join(text_lines)
    path = "users_export.txt"
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    await callback.message.answer_document(
        FSInputFile(path, filename="foydalanuvchilar.txt"),
        caption=f"📄 Foydalanuvchilar ro'yxati ({len(users)} ta)",
    )


# ===== ADMIN: STATISTIKA =====
@router.message(F.text == "📊 Statistika")
async def admin_stats(message: Message):
    if not is_admin(message.from_user.id):
        await message.answer("⛔ Bu bo'lim faqat admin uchun.")
        return
    users = await db.get_all_users()
    videos = await db.get_video_count()
    storage_id = await db.get_setting("storage_chat_id")
    storage_title = await db.get_setting("storage_title")
    blocked = sum(1 for u in users if u.get("is_blocked"))
    await message.answer(
        "📊 <b>Statistika</b>\n\n"
        f"👥 Foydalanuvchilar: <b>{len(users)} ta</b> (bloklangan: {blocked})\n"
        f"🎞 Ombordagi videolar: <b>{videos} ta</b>\n"
        f"📦 Ombor: <b>{storage_title or 'ulanmagan'}</b> <code>{storage_id or ''}</code>\n"
        f"📢 Kanal: @{CHANNEL_USERNAME}",
        parse_mode=ParseMode.HTML,
        reply_markup=admin_keyboard(),
    )


# ===== ADMIN: REKLAMA YUBORISH =====
@router.message(F.text == "📢 Reklama yuborish")
async def broadcast_start(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        await message.answer("⛔ Bu bo'lim faqat admin uchun.")
        return
    await state.set_state(AdminStates.waiting_broadcast)
    await message.answer(
        "📢 <b>Reklama yuborish</b>\n\n"
        "Hammaga yubormoqchi bo'lgan xabaringizni yozing:\n"
        "• Matn, rasm, video, hujjat — istalganini yuboring\n"
        "• Keyin tasdiqlash so'raladi va yuborish boshlanadi\n\n"
        "Bekor qilish: /cancel",
        parse_mode=ParseMode.HTML,
    )


@router.message(AdminStates.waiting_broadcast)
async def broadcast_received(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    # Xabar turini saqlash
    payload = {
        "text": message.text,
        "caption": message.caption,
        "photo": message.photo[-1].file_id if message.photo else None,
        "video": message.video.file_id if message.video else None,
        "document": message.document.file_id if message.document else None,
        "animation": message.animation.file_id if message.animation else None,
        "voice": message.voice.file_id if message.voice else None,
        "audio": message.audio.file_id if message.audio else None,
    }
    if not any(payload.values()):
        await message.answer("❌ Xabar topilmadi. Matn yoki media yuboring.")
        return
    await state.update_data(broadcast=payload)
    await state.set_state(AdminStates.waiting_broadcast)  # tasdiqlash bosqichida qolamiz
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Yuborishni boshlash", callback_data="broadcast_send")],
        [InlineKeyboardButton(text="❌ Bekor qilish", callback_data="broadcast_cancel")],
    ])
    users_count = await db.get_user_count()
    await message.answer(
        f"📝 Xabaringiz tayyor! Hammaga ({users_count} ta foydalanuvchiga) yuboriladi.\n"
        "Tasdiqlaysizmi?",
        reply_markup=kb,
    )


@router.callback_query(F.data == "broadcast_cancel")
async def broadcast_cancel(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.clear()
    await callback.message.answer("❌ Reklama yuborish bekor qilindi.", reply_markup=admin_keyboard())


@router.callback_query(F.data == "broadcast_send")
async def broadcast_send(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        return await callback.answer("⛔", show_alert=True)
    await callback.answer()
    data = await state.get_data()
    payload = data.get("broadcast")
    if not payload:
        await callback.message.answer("❌ Xabar topilmadi. Qaytadan urinib ko'ring.")
        await state.clear()
        return
    await state.clear()

    users = await db.get_all_users()
    if not users:
        await callback.message.answer("⚠️ Hozircha hech qanday foydalanuvchi yo'q.")
        return

    await callback.message.answer(f"📤 Yuborish boshlandi... Jami: {len(users)} ta foydalanuvchi")
    bot = callback.bot
    success = 0
    failed = 0
    report_lines = [
        "REKLAMA YUBORISH HISOBOTI",
        f"Sana: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        f"Jami foydalanuvchi: {len(users)} ta",
        "=" * 60,
    ]

    for i, u in enumerate(users, 1):
        uid = u["user_id"]
        uname = f"@{u['username']}" if u.get("username") else "(username yo'q)"
        status = "Yuborildi"
        try:
            if payload.get("photo"):
                await bot.send_photo(uid, payload["photo"], caption=payload.get("caption"))
            elif payload.get("video"):
                await bot.send_video(uid, payload["video"], caption=payload.get("caption"))
            elif payload.get("document"):
                await bot.send_document(uid, payload["document"], caption=payload.get("caption"))
            elif payload.get("animation"):
                await bot.send_animation(uid, payload["animation"], caption=payload.get("caption"))
            elif payload.get("voice"):
                await bot.send_voice(uid, payload["voice"], caption=payload.get("caption"))
            elif payload.get("audio"):
                await bot.send_audio(uid, payload["audio"], caption=payload.get("caption"))
            else:
                await bot.send_message(uid, payload.get("text") or "")
            success += 1
        except (TelegramForbiddenError, TelegramAPIError):
            failed += 1
            status = "Yetib bormadi"
            await db.set_blocked(uid, True)
        report_lines.append(
            f"{i}. Username: {uname} | ID: {uid} | Ism: {u.get('full_name') or '—'} | Holat: {status}"
        )
        if i % 20 == 0:
            await asyncio.sleep(0.5)  # flood cheklovidan himoya

    report_lines.append("=" * 60)
    report_lines.append(f"✅ Yuborildi: {success} ta")
    report_lines.append(f"❌ Yetib bormadi: {failed} ta")
    report = "\n".join(report_lines)

    path = "broadcast_report.txt"
    with open(path, "w", encoding="utf-8") as f:
        f.write(report)

    await callback.message.answer(
        f"📊 <b>Reklama yuborish yakunlandi!</b>\n\n"
        f"✅ Yuborildi: <b>{success} ta</b>\n"
        f"❌ Yetib bormadi: <b>{failed} ta</b>\n"
        f"👥 Jami: <b>{len(users)} ta</b>\n\n"
        "Pastda .txt fayl — aynan qaysi foydalanuvchiga borgani/bormagani yozilgan.",
        parse_mode=ParseMode.HTML,
        reply_markup=admin_keyboard(),
    )
    await callback.message.answer_document(
        FSInputFile(path, filename="reklama_hisobot.txt"),
        caption="📄 Reklama hisobot (.txt)",
    )


# ===== OMBORGA VIDEO QO'SHISH (avtomatik) =====
@router.message(F.video)
async def on_video_received(message: Message):
    storage_id = await db.get_setting("storage_chat_id")
    from_storage = storage_id and str(message.chat.id) == str(storage_id)
    from_admin_private = is_admin(message.from_user.id) and message.chat.type == ChatType.PRIVATE

    if not (from_storage or from_admin_private):
        return

    video = message.video
    vid_id = await db.add_video(
        file_id=video.file_id,
        file_unique_id=video.file_unique_id,
        caption=message.caption,
        duration=video.duration,
        file_size=video.file_size,
    )
    if from_storage:
        await message.answer(f"✅ Video omborga qo'shildi! (#{vid_id})")
    else:
        await message.answer(
            f"✅ Video omborga qo'shildi! (#{vid_id})\n\n"
            "Foydalanuvchilar endi uni «🎬 Kino ber» da ko'radi.",
            reply_markup=admin_keyboard(),
        )



# ===== /cancel =====
@router.message(Command("cancel"))
async def cmd_cancel(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("❌ Bekor qilindi.", reply_markup=admin_keyboard() if is_admin(message.from_user.id) else user_keyboard())


# ---------- Asosiy ----------
async def main():
    await db.init_db()
    bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher(storage=MemoryStorage())
    dp.include_router(router)
    # Bot o'zini tanishtiradi
    me = await bot.get_me()
    log.info("Bot ishga tushdi: @%s (id=%s)", me.username, me.id)
    for admin_id in ADMIN_IDS:
        try:
            await bot.send_message(admin_id, f"✅ Bot ishga tushdi: @{me.username}\nOmbor va reklama tayyor.")
        except TelegramAPIError:
            pass
    await dp.start_polling(bot, allowed_updates=["message", "callback_query", "my_chat_member"])


if __name__ == "__main__":
    asyncio.run(main())
