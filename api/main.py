import os
import asyncio
import json
from http.server import BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, Bot
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

# ─── API: التحقق من القناة ──────────────────────────────

async def api_verify_channel(uid):
    """
    يتحقق من اشتراك المستخدم في القناة فعلاً عن طريق تلغرام
    ولو مشترك يحدث Supabase ويحسب الإحالة
    """
    bot = Bot(token=BOT_TOKEN)
    try:
        is_member = await check_member(bot, int(uid))
        if not is_member:
            return {"ok": False, "msg": "not_member"}

        user = await get_user(int(uid))
        if not user:
            return {"ok": False, "msg": "user_not_found"}

        if user.get('channel_bonus'):
            return {"ok": True, "msg": "already_done", "coins": user.get('coins', 0)}

        # ✅ مشترك وأول مرة — احسب النقاط
        new_coins = (user.get('coins') or 0) + 50
        await db_update('users', 'telegram_id', int(uid), {
            'is_member': True,
            'channel_bonus': True,
            'coins': new_coins
        })

        # ✅ لو عنده محيل، احسب الإحالة
        stored_ref = user.get('referred_by')
        if stored_ref and str(stored_ref) != str(uid):
            await give_ref_bonus(stored_ref, uid)

        return {"ok": True, "msg": "success", "coins": new_coins}
    except Exception as e:
        print(f"[api_verify] Error: {e}")
        return {"ok": False, "msg": str(e)}
    finally:
        await bot.close()

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

    text, markup = await get_menu(uid)
    await update.message.reply_text(text, reply_markup=markup)

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    uid = query.from_user.id

    if query.data == 'tasks':
        user = await get_user(uid)
        channel_bonus = user.get('channel_bonus', False) if user else False
        if channel_bonus:
            keyboard = [
                [InlineKeyboardButton("✅ تم الاشتراك", callback_data='tasks')],
                [InlineKeyboardButton("🔙 رجوع", callback_data='back')]
            ]
            await query.edit_message_text(
                "📋 المهام:\n\n📢 الاشتراك في قناة TaskEarn\n🎁 50 نقطة\nالحالة: ✅ مكتملة",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        else:
            keyboard = [
                [InlineKeyboardButton("📢 اشترك في القناة (+50 نقطة)", url=f"https://t.me/{CHANNEL_ID.replace('@', '')}")],
                [InlineKeyboardButton("✅ تحقق من اشتراكي", callback_data='verify_task')],
                [InlineKeyboardButton("🔙 رجوع", callback_data='back')]
            ]
            await query.edit_message_text(
                "📋 المهام:\n\n📢 الاشتراك في قناة TaskEarn\n🎁 50 نقطة\nالحالة: ⭕ لم تكتمل\n\nاشترك ثم اضغط تحقق 👇",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )

    elif query.data == 'verify_task':
        result = await api_verify_channel(uid)
        if result['ok']:
            if result['msg'] == 'already_done':
                await query.answer("✅ أنت مشترك بالفعل!", show_alert=True)
            else:
                await query.answer("🎉 تم! ربحت 50 نقطة", show_alert=True)
            text, markup = await get_menu(uid)
            await query.edit_message_text(text, reply_markup=markup)
        else:
            await query.answer("❌ لسه مشتركتش في القناة!", show_alert=True)
            keyboard = [
                [InlineKeyboardButton("📢 اشترك في القناة (+50 نقطة)", url=f"https://t.me/{CHANNEL_ID.replace('@', '')}")],
                [InlineKeyboardButton("✅ تحقق من اشتراكي", callback_data='verify_task')],
                [InlineKeyboardButton("🔙 رجوع", callback_data='back')]
            ]
            await query.edit_message_text(
                "📋 المهام:\n\n📢 الاشتراك في قناة TaskEarn\n🎁 50 نقطة\nالحالة: ⭕ لم تكتمل\n\n❌ لسه مشتركتش!\nاشترك الأول ثم اضغط تحقق 👇",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )

    elif query.data == 'referral':
        ref_link = f"https://t.me/earntaskpro_bot?start={uid}"
        await query.edit_message_text(
            f"👥 رابط الإحالة:\n\n`{ref_link}`\n\n🎁 100 نقطة لكل صديق ينضم!",
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data='back')]])
        )

    elif query.data == 'balance':
        user = await get_user(uid)
        coins = user.get('coins', 0) if user else 0
        usdt = coins * 0.0001
        await query.edit_message_text(
            f"🪙 رصيدك: {coins} نقطة\n💵 ≈ {usdt:.4f} USDT\n\n📌 1000 نقطة = 0.1 USDT",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data='back')]])
        )

    elif query.data == 'stats':
        user = await get_user(uid)
        refs = user.get('refs', 0) if user else 0
        ads = user.get('ads_watched', 0) if user else 0
        coins = user.get('coins', 0) if user else 0
        await query.edit_message_text(
            f"📊 إحصائياتك:\n\n👥 إحالات: {refs}\n📺 إعلانات: {ads}\n🪙 نقاط: {coins}\n💰 من الإحالات: {refs*100}",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data='back')]])
        )

    elif query.data == 'back':
        text, markup = await get_menu(uid)
        await query.edit_message_text(text, reply_markup=markup)

# ─── API: تصحيح الإحالات القديمة ────────────────────────

async def fix_old_refs():
    """يصلح الإحالات القديمة اللي ما اتحسبتش"""
    async with httpx.AsyncClient() as client:
        r = await client.get(
            f"{SUPABASE_URL}/rest/v1/users?referred_by=not.is.null&select=*",
            headers=HEADERS()
        )
        users = r.json()

    fixed = 0
    for user in users:
        ref_id = user.get('referred_by')
        uid = user.get('telegram_id')
        if not ref_id or str(ref_id) == str(uid):
            continue
        ref_data = await get_user(int(ref_id))
        if ref_data:
            # تحقق إن الإحالة دي ما اتحسبتش
            current_refs = ref_data.get('refs', 0)
            # عد الناس اللي referred_by بتاعهم = ref_id
            async with httpx.AsyncClient() as client:
                r2 = await client.get(
                    f"{SUPABASE_URL}/rest/v1/users?referred_by=eq.{ref_id}&select=telegram_id",
                    headers=HEADERS()
                )
                actual_refs = len(r2.json())
            if actual_refs != current_refs:
                await db_update('users', 'telegram_id', int(ref_id), {
                    'refs': actual_refs,
                    'coins': (ref_data.get('coins') or 0) + ((actual_refs - current_refs) * 100)
                })
                fixed += 1
    return fixed

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
        parsed = urlparse(self.path)
        params = parse_qs(parsed.query)

        # ─── API: تحقق من القناة ───────────────────────
        if parsed.path == '/api/verify':
            uid = params.get('uid', [None])[0]
            if not uid:
                self.send_response(400)
                self.end_headers()
                self.wfile.write(b'{"ok":false,"msg":"missing uid"}')
                return
            result = asyncio.run(api_verify_channel(uid))
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(json.dumps(result).encode())
            return

        # ─── API: صلح الإحالات القديمة ────────────────
        if parsed.path == '/api/fix-refs':
            fixed = asyncio.run(fix_old_refs())
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({"ok": True, "fixed": fixed}).encode())
            return

        self.send_response(200)
        self.end_headers()
        self.wfile.write(b'TaskEarn Bot is Running!')
