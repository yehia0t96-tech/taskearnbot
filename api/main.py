import os
import asyncio
import json
from http.server import BaseHTTPRequestHandler
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes
import httpx

BOT_TOKEN = os.getenv('BOT_TOKEN')
SUPABASE_URL = os.getenv('SUPABASE_URL')
SUPABASE_KEY = os.getenv('SUPABASE_KEY')
CHANNEL_ID = os.getenv('CHANNEL_ID', '@gxhxd')
MINI_APP_URL = 'https://t.me/earntaskpro_bot/TaskEarn'

HEADERS = lambda: {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json"
}

# ─── Database ───────────────────────────────────────────

async def db_get(table, field, value):
    async with httpx.AsyncClient() as client:
        r = await client.get(
            f"{SUPABASE_URL}/rest/v1/{table}?{field}=eq.{value}&select=*",
            headers=HEADERS()
        )
        return r.json()

async def db_insert(table, data):
    async with httpx.AsyncClient() as client:
        await client.post(
            f"{SUPABASE_URL}/rest/v1/{table}",
            headers=HEADERS(),
            json=data
        )

async def db_update(table, field, value, data):
    async with httpx.AsyncClient() as client:
        await client.patch(
            f"{SUPABASE_URL}/rest/v1/{table}?{field}=eq.{value}",
            headers=HEADERS(),
            json=data
        )

# ─── Helpers ────────────────────────────────────────────

async def check_member(bot, uid):
    try:
        member = await bot.get_chat_member(CHANNEL_ID, uid)
        return member.status in ['member', 'administrator', 'creator', 'restricted']
    except:
        return False

async def get_user(uid):
    result = await db_get('users', 'telegram_id', uid)
    return result[0] if result and len(result) > 0 else None

async def give_ref_bonus(ref_id, uid):
    if not ref_id:
        return
    try:
        ref_id = int(ref_id)
        if ref_id == int(uid):
            return
        ref_data = await get_user(ref_id)
        if ref_data:
            await db_update('users', 'telegram_id', ref_id, {
                'coins': (ref_data.get('coins') or 0) + 100,
                'refs': (ref_data.get('refs') or 0) + 1
            })
    except Exception as e:
        print(f"[give_ref_bonus] Error: {e}")

async def get_menu(uid):
    user = await get_user(uid)
    coins = user.get('coins', 0) if user else 0
    refs = user.get('refs', 0) if user else 0
    ads = user.get('ads_watched', 0) if user else 0
    usdt = coins * 0.0001

    text = (
        f"👋 أهلاً في TaskEarn!\n\n"
        f"🪙 رصيدك: {coins} نقطة\n"
        f"💵 ≈ {usdt:.4f} USDT\n"
        f"👥 إحالاتك: {refs}\n"
        f"📺 إعلانات شاهدتها: {ads}\n\n"
        f"افتح التطبيق واكسب أكتر! 👇"
    )
    keyboard = [
        [InlineKeyboardButton("🚀 فتح التطبيق", url=MINI_APP_URL)],
        [InlineKeyboardButton(f"🪙 رصيدك: {coins} نقطة", callback_data='balance')],
        [InlineKeyboardButton("👥 رابط الإحالة", callback_data='referral'),
         InlineKeyboardButton("📊 إحصائياتك", callback_data='stats')],
        [InlineKeyboardButton("📋 المهام", callback_data='tasks')]
    ]
    return text, InlineKeyboardMarkup(keyboard)

# ─── Handlers ───────────────────────────────────────────

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    uid = user.id
    username = user.username or ''
    ref_id = context.args[0] if context.args else None
    existing = await get_user(uid)

    if not existing:
        await db_insert('users', {
            'telegram_id': uid,
            'username': username,
            'coins': 0,
            'ads_watched': 0,
            'tasks_done': 0,
            'refs': 0,
            'referred_by': str(ref_id) if ref_id else None,
            'is_member': False,
            'channel_bonus': False
        })
        # ✅ الإحالة تتحسب فوراً لما حد جديد يفتح البوت
        if ref_id and str(ref_id) != str(uid):
            await give_ref_bonus(ref_id, uid)

    text, markup = await get_menu(uid)
    await update.message.reply_text(text, reply_markup=markup)

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    uid = query.from_user.id

    # ─── صفحة المهام ───────────────────────────────────
    if query.data == 'tasks':
        user = await get_user(uid)
        channel_bonus = user.get('channel_bonus', False) if user else False

        if channel_bonus:
            keyboard = [
                [InlineKeyboardButton("✅ تم الاشتراك", callback_data='tasks')],
                [InlineKeyboardButton("🔙 رجوع", callback_data='back')]
            ]
            await query.edit_message_text(
                f"📋 المهام المتاحة:\n\n"
                f"📢 الاشتراك في قناة TaskEarn\n"
                f"🎁 المكافأة: 50 نقطة\n"
                f"الحالة: ✅ مكتملة\n\n"
                f"لا توجد مهام أخرى حالياً، ترقب المزيد! 🔔",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        else:
            keyboard = [
                [InlineKeyboardButton("📢 اشترك في القناة (+50 نقطة)", url=f"https://t.me/{CHANNEL_ID.replace('@', '')}")],
                [InlineKeyboardButton("✅ تحقق من اشتراكي", callback_data='verify_task')],
                [InlineKeyboardButton("🔙 رجوع", callback_data='back')]
            ]
            await query.edit_message_text(
                f"📋 المهام المتاحة:\n\n"
                f"📢 الاشتراك في قناة TaskEarn\n"
                f"🎁 المكافأة: 50 نقطة\n"
                f"الحالة: ⭕ لم تكتمل\n\n"
                f"اشترك في القناة ثم اضغط تحقق! 👇",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )

    # ─── التحقق من اشتراك القناة ───────────────────────
    elif query.data == 'verify_task':
        is_member = await check_member(context.bot, uid)

        if is_member:
            user = await get_user(uid)
            if user and not user.get('channel_bonus'):
                await db_update('users', 'telegram_id', uid, {
                    'is_member': True,
                    'channel_bonus': True,
                    'coins': (user.get('coins') or 0) + 50
                })
                await query.answer("🎉 تم التحقق! ربحت 50 نقطة", show_alert=True)
            else:
                await query.answer("✅ أنت مشترك بالفعل!", show_alert=True)

            text, markup = await get_menu(uid)
            await query.edit_message_text(text, reply_markup=markup)

        else:
            keyboard = [
                [InlineKeyboardButton("📢 اشترك في القناة (+50 نقطة)", url=f"https://t.me/{CHANNEL_ID.replace('@', '')}")],
                [InlineKeyboardButton("✅ تحقق من اشتراكي", callback_data='verify_task')],
                [InlineKeyboardButton("🔙 رجوع", callback_data='back')]
            ]
            await query.answer("❌ لم يتم الاشتراك بعد!", show_alert=True)
            await query.edit_message_text(
                f"📋 المهام المتاحة:\n\n"
                f"📢 الاشتراك في قناة TaskEarn\n"
                f"🎁 المكافأة: 50 نقطة\n"
                f"الحالة: ⭕ لم تكتمل\n\n"
                f"❌ لسه مشتركتش!\n"
                f"اشترك في القناة الأول ثم اضغط تحقق 👇",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )

    # ─── رابط الإحالة ──────────────────────────────────
    elif query.data == 'referral':
        ref_link = f"https://t.me/earntaskpro_bot?start={uid}"
        await query.edit_message_text(
            f"👥 رابط الإحالة بتاعك:\n\n`{ref_link}`\n\n"
            f"🎁 بتاخد 100 نقطة لكل صديق ينضم عن طريق رابطك!",
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data='back')]])
        )

    # ─── الرصيد ────────────────────────────────────────
    elif query.data == 'balance':
        user = await get_user(uid)
        coins = user.get('coins', 0) if user else 0
        usdt = coins * 0.0001
        await query.edit_message_text(
            f"🪙 رصيدك الحالي: {coins} نقطة\n"
            f"💵 ≈ {usdt:.4f} USDT\n\n"
            f"📌 1000 نقطة = 0.1 USDT",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data='back')]])
        )

    # ─── الإحصائيات ────────────────────────────────────
    elif query.data == 'stats':
        user = await get_user(uid)
        refs = user.get('refs', 0) if user else 0
        ads = user.get('ads_watched', 0) if user else 0
        coins = user.get('coins', 0) if user else 0
        await query.edit_message_text(
            f"📊 إحصائياتك:\n\n"
            f"👥 إحالات: {refs}\n"
            f"📺 إعلانات: {ads}\n"
            f"🪙 إجمالي النقاط: {coins}\n"
            f"💰 نقاط الإحالات: {refs * 100}",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data='back')]])
        )

    # ─── رجوع ──────────────────────────────────────────
    elif query.data == 'back':
        text, markup = await get_menu(uid)
        await query.edit_message_text(text, reply_markup=markup)

# ─── App Builder ────────────────────────────────────────

async def process_update(update_data):
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_handler))
    async with app:
        update = Update.de_json(update_data, app.bot)
        await app.process_update(update)

# ─── Vercel Handler ─────────────────────────────────────

class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        try:
            content_length = int(self.headers['Content-Length'])
            body = self.rfile.read(content_length)
            update_data = json.loads(body.decode())
            asyncio.run(process_update(update_data))
            self.send_response(200)
        except Exception as e:
            print(f"[Handler Error] {e}")
            self.send_response(500)
        finally:
            self.end_headers()

    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b'TaskEarn Bot is Running!')
