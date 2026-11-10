# 🎬 Qashqirlar Makoni — Kino Bot

Telegram kino bot: ombor (storage) guruh/kanal, 10 talik seriyalar, admin paneli va reklama yuborish.

## ✨ Funksiyalar

### 👤 Foydalanuvchi tomoni
- `/start` bosganda **doimo birinchi seriya** chiqadi — **10 ta video**
- Pastida **Keyingi ➡️ / ⬅️ Orqaga** tugmalari (keyingi 10 talik / oldingi qism)
- **🎬 Kino ber** — boshidan boshlab yuboradi
- **ℹ️ Malumot** — bot haqida ma'lumot
- Har bir videoda yuboruvchi va asl izoh **yashirin** (file_id orqali yuboriladi),
  kapshnda albatta: `📢 @Tamosha_Vaqti obuna bo'ling`
- Videolar **omborga yuborilgan tartibda** chiqadi — eng avval yuborilgani eng tepada

### 👑 Admin tomoni (1 admin — `ADMIN_ID`)
- **📦 Ombor** bo'limi:
  - 🔗 **Ombor ulashish** — guruh/kanaldan botga forward qiling yoki Chat ID yozing
  - 🤖 Bot guruh/kanalda **admin qilinsa — avtomatik xabar** keladi va ombor avtomatik ulanadi
  - ➕ Video qo'shish — ombor guruhiga yoki botga video yuboring (avtomatik saqlanadi)
  - 📋 Videolar ro'yxati — ko'rish, **✏️ sarlavha o'zgartirish**, **🗑 o'chirish**
  - 🗑 Raqam bo'yicha o'chirish
  - 🔄 Yangilash (ombor holati), ❌ Omborni uzish
- **📢 Reklama yuborish** — xabarni yozing → tasdiqlang → hammaga boradi.
  Yakunda hisobot: **qanchasiga bordi / qanchasiga yetib bormadi** + pastda **`.txt` fayl**
  (har bir foydalanuvchining username, ID, ismi va holati yozilgan)
- **👥 Foydalanuvchilar** — ro'yxat + `.txt` eksport
- **📊 Statistika** — foydalanuvchi / video / ombor hisoboti

## 🚀 Railway ga joylash (5 daqiqa)

1. GitHub ga push qilingan repo ni Railway da **New Project → Deploy from GitHub repo** qiling
2. **Variables** bo'limiga qo'shing:

| Variable | Qiymati |
|---|---|
| `BOT_TOKEN` | @BotFather dan olingan token |
| `ADMIN_ID` | Sizning Telegram ID ingiz (masalan `@userinfobot` dan oling) |
| `CHANNEL_USERNAME` | `Tamosha_Vaqti` (ixtiyoriy) |
| `PAGE_SIZE` | `10` (ixtiyoriy) |

3. Deploy avtomatik boshlanadi (`python bot.py`). Logda `Bot ishga tushdi` yozilsa — tayyor! ✅

> Token va Admin ID ni **hech qachon GitHub ga yozmang** — faqat Railway Variables ga!

## 📦 Omborni ulash (birinchi marta)

1. Guruh yoki kanal yarating (masalan: «Kino Ombori»)
2. Botni shu yerga **admin** qiling (BotFather tokenli botni qo'shing)
3. Bot avtomatik xabar yuboradi: *«Men admin qilindim, endi bu guruh ombor!»* ✅
4. Shu guruhga video yuboring — bot omborga saqlaydi
5. Foydalanuvchi «🎬 Kino ber» desa — videolar shu yerdan chiqadi

## 🖥 Lokal ishga tushirish

```bash
pip install -r requirements.txt
cp .env.example .env   # token va admin ID ni yozing
python bot.py
```

## 📁 Fayllar

```
bot.py          — asosiy bot (barcha handlerlar)
database.py     — SQLite baza (foydalanuvchi, video, ombor sozlamasi)
requirements.txt
Procfile / railway.toml / Dockerfile — Railway uchun tayyor
.env.example    — Variables namunasi
```

## ⚠️ Eslatma
- Bot omborda **admin** bo'lishi shart (videolarni o'qish va xabar yuborish uchun)
- Videolar `file_id` orqali yuboriladi — shuning uchun asl yuboruvchi va izoh foydalanuvchiga **ko'rinmaydi**
- Ma'lumotlar `bot.db` (SQLite) da saqlanadi; Railway da disk vaqtinchalik — doimiy saqlash uchun keyin Postgres ga o'tkazish mumkin
