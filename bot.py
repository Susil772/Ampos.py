#!/usr/bin/env python3
import os
import sqlite3
import random
import string
import requests
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes
from telegram.error import BadRequest

BOT_TOKEN = os.getenv("BOT_TOKEN", "8867955581:AAH1zCrwf3YMYAu5WB7lcD3sk0e7n7SjI1w")
ADMIN_USER_ID = int(os.getenv("ADMIN_ID", "7979274156"))
WEBHOOK_URL = os.getenv("WEBHOOK_URL", "")
PORT = int(os.getenv("PORT", "8080"))
DB_FILE = "bot_database.db"

# ============================================================
# DATABASE
# ============================================================
def get_db():
    conn = sqlite3.connect(DB_FILE, timeout=10)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    c = conn.cursor()
    c.execute("""CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY, username TEXT, first_name TEXT,
        is_verified INTEGER DEFAULT 0, is_vip INTEGER DEFAULT 0,
        credits INTEGER DEFAULT 0, last_daily_bonus TEXT,
        referral_code TEXT UNIQUE, referred_by INTEGER,
        join_date TEXT DEFAULT CURRENT_TIMESTAMP
    )""")
    c.execute("""CREATE TABLE IF NOT EXISTS redeem_codes (
        code TEXT PRIMARY KEY, points INTEGER, max_uses INTEGER,
        used_count INTEGER DEFAULT 0, created_by INTEGER,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    )""")
    c.execute("""CREATE TABLE IF NOT EXISTS redeemed (
        user_id INTEGER, code TEXT,
        redeemed_at TEXT DEFAULT CURRENT_TIMESTAMP,
        PRIMARY KEY (user_id, code)
    )""")
    c.execute("""CREATE TABLE IF NOT EXISTS settings (
        key TEXT PRIMARY KEY, value TEXT
    )""")
    c.execute("""CREATE TABLE IF NOT EXISTS subscriptions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        plan_name TEXT, price REAL, credits INTEGER,
        duration_days INTEGER, description TEXT
    )""")
    c.execute("""CREATE TABLE IF NOT EXISTS pending_approvals (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER, plan_id INTEGER, plan_name TEXT,
        status TEXT DEFAULT 'pending', created_at TEXT DEFAULT CURRENT_TIMESTAMP
    )""")

    defaults = [
        ("sms_limit", "1"),
        ("sms_cost", "1"),
        ("daily_bonus_credits", "5"),
        ("referral_reward_credits", "10"),
        ("channel_1_username", os.getenv("CHANNEL_1", "@channel1")),
        ("channel_2_username", os.getenv("CHANNEL_2", "@channel2")),
        ("channel_1_link", os.getenv("CHANNEL_1_LINK", "https://t.me/channel1")),
        ("channel_2_link", os.getenv("CHANNEL_2_LINK", "https://t.me/channel2")),
        ("support_dev", os.getenv("SUPPORT_DEV", "@developer")),
        ("support_owner", os.getenv("SUPPORT_OWNER", "@owner")),
        ("sms_api_url", "https://sms-sender-rww0.onrender.com"),
        ("sms_api_key", "SuSHiLx2024SMS"),
        ("sms_api_params", "phone={phone}&count={amount}&apikey={api_key}"),
    ]
    for k, v in defaults:
        c.execute("INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)", (k, v))

    c.execute("SELECT COUNT(*) FROM subscriptions")
    if c.fetchone()[0] == 0:
        plans = [
            ("Basic Monthly", 5.00, 100, 30, "100 credits + VIP 30 days"),
            ("Premium Monthly", 10.00, 250, 30, "250 credits + VIP 30 days"),
            ("Ultimate Monthly", 20.00, 600, 30, "600 credits + VIP 30 days"),
        ]
        c.executemany(
            "INSERT INTO subscriptions (plan_name, price, credits, duration_days, description) VALUES (?, ?, ?, ?, ?)",
            plans,
        )
    conn.commit()
    conn.close()

def get_setting(key):
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT value FROM settings WHERE key = ?", (key,))
    row = c.fetchone()
    conn.close()
    return row["value"] if row else None

def set_setting(key, value):
    conn = get_db()
    c = conn.cursor()
    c.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, value))
    conn.commit()
    conn.close()

def get_user(user_id):
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
    row = c.fetchone()
    conn.close()
    return row

def create_user(user_id, username, first_name, referred_by=None):
    conn = get_db()
    c = conn.cursor()
    ref_code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
    try:
        c.execute(
            "INSERT INTO users (user_id, username, first_name, referral_code, referred_by) VALUES (?, ?, ?, ?, ?)",
            (user_id, username, first_name, ref_code, referred_by),
        )
        conn.commit()
    except sqlite3.IntegrityError:
        pass
    conn.close()

def verify_user(user_id):
    conn = get_db()
    c = conn.cursor()
    c.execute("UPDATE users SET is_verified = 1 WHERE user_id = ?", (user_id,))
    if c.rowcount > 0:
        user = c.fetchone() if False else None
        conn2 = get_db()
        u = conn2.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)).fetchone()
        if u and u["referred_by"]:
            reward = int(get_setting("referral_reward_credits") or 10)
            conn2.execute("UPDATE users SET credits = credits + ? WHERE user_id = ? AND is_verified = 1",
                          (reward, u["referred_by"]))
            conn2.commit()
        conn2.close()
    conn.commit()
    conn.close()

def add_credits(user_id, amount):
    conn = get_db()
    conn.execute("UPDATE users SET credits = credits + ? WHERE user_id = ?", (amount, user_id))
    conn.commit()
    conn.close()

def deduct_credits(user_id, amount):
    conn = get_db()
    c = conn.cursor()
    c.execute("UPDATE users SET credits = credits - ? WHERE user_id = ? AND credits >= ?",
              (amount, user_id, amount))
    success = c.rowcount > 0
    conn.commit()
    conn.close()
    return success

def set_vip(user_id, is_vip):
    conn = get_db()
    conn.execute("UPDATE users SET is_vip = ? WHERE user_id = ?", (is_vip, user_id))
    conn.commit()
    conn.close()

def create_redeem_code(code, points, max_uses, admin_id):
    conn = get_db()
    try:
        conn.execute(
            "INSERT INTO redeem_codes (code, points, max_uses, created_by) VALUES (?, ?, ?, ?)",
            (code, points, max_uses, admin_id),
        )
        conn.commit()
        success = True
    except sqlite3.IntegrityError:
        success = False
    conn.close()
    return success

def redeem_code(user_id, code):
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT * FROM redeem_codes WHERE code = ?", (code,))
    rc = c.fetchone()
    if not rc: conn.close(); return False, "Invalid code."
    if rc["used_count"] >= rc["max_uses"]:
        conn.close(); return False, "Code has reached max uses."
    c.execute("SELECT * FROM redeemed WHERE user_id = ? AND code = ?", (user_id, code))
    if c.fetchone(): conn.close(); return False, "You already used this code."
    c.execute("UPDATE redeem_codes SET used_count = used_count + 1 WHERE code = ?", (code,))
    c.execute("INSERT INTO redeemed (user_id, code) VALUES (?, ?)", (user_id, code))
    c.execute("UPDATE users SET credits = credits + ? WHERE user_id = ?", (rc["points"], user_id))
    conn.commit(); conn.close()
    return True, rc["points"]

def claim_daily_bonus(user_id):
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT last_daily_bonus, credits, is_vip FROM users WHERE user_id = ?", (user_id,))
    user = c.fetchone()
    if not user: conn.close(); return False, "User not found."
    today = datetime.now().strftime("%Y-%m-%d")
    if user["last_daily_bonus"] == today:
        conn.close(); return False, "Already claimed today."
    bonus = int(get_setting("daily_bonus_credits") or 5)
    if user["is_vip"]: bonus *= 2
    c.execute("UPDATE users SET credits = credits + ?, last_daily_bonus = ? WHERE user_id = ?",
              (bonus, today, user_id))
    conn.commit(); conn.close()
    return True, bonus

def get_all_subscriptions():
    conn = get_db()
    rows = conn.execute("SELECT * FROM subscriptions").fetchall()
    conn.close()
    return rows

def get_subscription(plan_id):
    conn = get_db()
    row = conn.execute("SELECT * FROM subscriptions WHERE id = ?", (plan_id,)).fetchone()
    conn.close()
    return row

def add_subscription(name, price, credits, duration, desc):
    conn = get_db()
    conn.execute(
        "INSERT INTO subscriptions (plan_name, price, credits, duration_days, description) VALUES (?, ?, ?, ?, ?)",
        (name, price, credits, duration, desc),
    )
    conn.commit()
    conn.close()

def update_subscription(plan_id, field, value):
    conn = get_db()
    allowed = ["plan_name", "price", "credits", "duration_days", "description"]
    if field not in allowed: conn.close(); return
    conn.execute(f"UPDATE subscriptions SET {field} = ? WHERE id = ?", (value, plan_id))
    conn.commit(); conn.close()

def delete_subscription(plan_id):
    conn = get_db()
    conn.execute("DELETE FROM subscriptions WHERE id = ?", (plan_id,))
    conn.commit(); conn.close()

def create_pending_approval(user_id, plan_id, plan_name):
    conn = get_db()
    conn.execute(
        "INSERT INTO pending_approvals (user_id, plan_id, plan_name) VALUES (?, ?, ?)",
        (user_id, plan_id, plan_name),
    )
    conn.commit(); conn.close()

def get_pending_approvals():
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM pending_approvals WHERE status = 'pending' ORDER BY created_at ASC"
    ).fetchall()
    conn.close()
    return rows

def approve_payment(approval_id):
    conn = get_db()
    c = conn.cursor()
    c.execute("UPDATE pending_approvals SET status = 'approved' WHERE id = ?", (approval_id,))
    approval = c.execute("SELECT * FROM pending_approvals WHERE id = ?", (approval_id,)).fetchone()
    if approval:
        plan = get_subscription(approval["plan_id"])
        if plan:
            add_credits(approval["user_id"], plan["credits"])
        set_vip(approval["user_id"], 1)
    conn.commit(); conn.close()
    return approval

def decline_payment(approval_id):
    conn = get_db()
    conn.execute("UPDATE pending_approvals SET status = 'declined' WHERE id = ?", (approval_id,))
    approval = conn.execute("SELECT * FROM pending_approvals WHERE id = ?", (approval_id,)).fetchone()
    conn.commit(); conn.close()
    return approval

def get_all_users():
    conn = get_db()
    rows = conn.execute("SELECT * FROM users").fetchall()
    conn.close()
    return rows

def get_stats():
    conn = get_db()
    total = conn.execute("SELECT COUNT(*) as c FROM users").fetchone()["c"]
    verified = conn.execute("SELECT COUNT(*) as c FROM users WHERE is_verified = 1").fetchone()["c"]
    vip = conn.execute("SELECT COUNT(*) as c FROM users WHERE is_vip = 1").fetchone()["c"]
    pending = conn.execute("SELECT COUNT(*) as c FROM pending_approvals WHERE status = 'pending'").fetchone()["c"]
    conn.close()
    return total, verified, vip, pending

def get_all_codes():
    conn = get_db()
    rows = conn.execute("SELECT * FROM redeem_codes ORDER BY created_at DESC").fetchall()
    conn.close()
    return rows

# ============================================================
# KEYBOARDS
# ============================================================
def main_menu_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📤 Send Message", callback_data="send_start")],
        [InlineKeyboardButton("👑 VIP Mode", callback_data="menu_vip")],
        [InlineKeyboardButton("💰 Buy Subscription", callback_data="sub_menu")],
        [InlineKeyboardButton("👤 Profile", callback_data="menu_profile")],
        [InlineKeyboardButton("🎁 Daily Bonus", callback_data="menu_daily")],
        [InlineKeyboardButton("🎫 Redeem Code", callback_data="redeem_start")],
        [InlineKeyboardButton("🔗 Refer & Earn", callback_data="menu_refer")],
        [InlineKeyboardButton("📞 Support", callback_data="menu_support")],
    ])

def back_main_btn():
    return InlineKeyboardButton("🔙 Back", callback_data="menu_main")

def admin_main_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📨 SMS Settings", callback_data="admin_sms_menu")],
        [InlineKeyboardButton("💳 Subscription Plans", callback_data="admin_subs_menu")],
        [InlineKeyboardButton("👑 VIP / Approvals", callback_data="admin_vip_menu")],
        [InlineKeyboardButton("🎁 Rewards Config", callback_data="admin_rewards_menu")],
        [InlineKeyboardButton("🔗 Bot Settings", callback_data="admin_settings_menu")],
        [InlineKeyboardButton("🎫 Redeem Codes", callback_data="admin_codes_menu")],
        [InlineKeyboardButton("📊 Statistics", callback_data="admin_stats")],
        [InlineKeyboardButton("📢 Broadcast", callback_data="admin_broadcast")],
    ])

# ============================================================
# HELPERS
# ============================================================
async def check_channel_membership(user_id, context):
    ch1 = get_setting("channel_1_username") or "@channel1"
    ch2 = get_setting("channel_2_username") or "@channel2"
    try:
        m1 = await context.bot.get_chat_member(ch1, user_id)
        m2 = await context.bot.get_chat_member(ch2, user_id)
        return m1.status in ("member", "administrator", "creator") and \
               m2.status in ("member", "administrator", "creator")
    except BadRequest:
        return False

def clear_states(context):
    for k in ("send_state", "phone_number", "redeem_state", "admin_state", "admin_sub_state",
              "gen_code", "gen_code_points", "sub_buy_plan_id", "sms_limit_amount"):
        context.user_data.pop(k, None)

# ============================================================
# COMMANDS
# ============================================================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    args = context.args
    ref_code = args[0] if args else None
    db_user = get_user(user.id)

    if not db_user:
        referred_by = None
        if ref_code:
            conn = get_db()
            r = conn.execute("SELECT user_id FROM users WHERE referral_code = ?", (ref_code,)).fetchone()
            conn.close()
            if r: referred_by = r["user_id"]
        create_user(user.id, user.username, user.first_name, referred_by)
        db_user = get_user(user.id)

    if db_user and db_user["is_verified"]:
        await update.message.reply_text("🌟 Welcome back! Choose an option:", reply_markup=main_menu_kb())
        return

    ch1_link = get_setting("channel_1_link") or "https://t.me/channel1"
    ch2_link = get_setting("channel_2_link") or "https://t.me/channel2"
    text = (
        "👋 *Welcome!*\n\nTo use this bot, join both channels:\n"
        f"📢 {ch1_link}\n📢 {ch2_link}\n\n"
        "Then click *Verify* below."
    )
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("📢 Channel 1", url=ch1_link)],
        [InlineKeyboardButton("📢 Channel 2", url=ch2_link)],
        [InlineKeyboardButton("✅ Verify", callback_data="verify")],
    ])
    await update.message.reply_text(text, reply_markup=kb, parse_mode="Markdown")

async def admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_USER_ID:
        await update.message.reply_text("❌ Unauthorized.")
        return
    clear_states(context)
    await update.message.reply_text("🔧 *Admin Panel*", reply_markup=admin_main_kb(), parse_mode="Markdown")

# ============================================================
# CALLBACK HANDLER
# ============================================================
async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user = update.effective_user
    data = query.data
    db_user = get_user(user.id)
    if not db_user:
        await query.edit_message_text("Use /start first.")
        return

    # ========== VERIFY ==========
    if data == "verify":
        if db_user["is_verified"]:
            await query.edit_message_text("✅ Already verified!", reply_markup=main_menu_kb())
            return
        is_member = await check_channel_membership(user.id, context)
        if not is_member:
            ch1_l = get_setting("channel_1_link") or "https://t.me/channel1"
            ch2_l = get_setting("channel_2_link") or "https://t.me/channel2"
            kb = InlineKeyboardMarkup([
                [InlineKeyboardButton("📢 Channel 1", url=ch1_l)],
                [InlineKeyboardButton("📢 Channel 2", url=ch2_l)],
                [InlineKeyboardButton("✅ Verify", callback_data="verify")],
            ])
            await query.edit_message_text(
                "❌ Join *both* channels first!", reply_markup=kb, parse_mode="Markdown"
            )
            return
        verify_user(user.id)
        await query.edit_message_text("✅ Verified! Welcome!", reply_markup=main_menu_kb())

    # ========== MAIN MENU ==========
    elif data == "menu_main":
        clear_states(context)
        await query.edit_message_text("Main Menu:", reply_markup=main_menu_kb())

    elif data == "menu_profile":
        u = get_user(user.id)
        status = "👑 VIP" if u["is_vip"] else "🔹 Normal"
        ref_link = f"https://t.me/{context.bot.username}?start={u['referral_code']}"
        text = (
            f"👤 *Profile*\n\n"
            f"🆔: `{u['user_id']}`\n"
            f"⭐: {status}\n"
            f"💎: {u['credits']} credits\n"
            f"🔗: `{u['referral_code']}`\n\n"
            f"Invite: `{ref_link}`"
        )
        kb = InlineKeyboardMarkup([[back_main_btn()]])
        await query.edit_message_text(text, reply_markup=kb, parse_mode="Markdown")

    elif data == "menu_daily":
        ok, result = claim_daily_bonus(user.id)
        text = f"🎁 +{result} credits!" if ok else f"❌ {result}"
        kb = InlineKeyboardMarkup([[back_main_btn()]])
        await query.edit_message_text(text, reply_markup=kb, parse_mode="Markdown")

    elif data == "menu_refer":
        u = get_user(user.id)
        ref_link = f"https://t.me/{context.bot.username}?start={u['referral_code']}"
        reward = get_setting("referral_reward_credits") or "10"
        text = f"🔗 *Refer & Earn*\n\nLink: `{ref_link}`\nReward: *{reward}* credits per verified referral."
        kb = InlineKeyboardMarkup([[back_main_btn()]])
        await query.edit_message_text(text, reply_markup=kb, parse_mode="Markdown")

    elif data == "menu_support":
        dev = get_setting("support_dev") or "@dev"
        owner = get_setting("support_owner") or "@owner"
        text = f"📞 *Support*\n\n👨‍💻 Dev: {dev}\n👑 Owner: {owner}"
        kb = InlineKeyboardMarkup([[back_main_btn()]])
        await query.edit_message_text(text, reply_markup=kb, parse_mode="Markdown")

    elif data == "menu_vip":
        u = get_user(user.id)
        if u["is_vip"]:
            text = "👑 *You are VIP!*\n\nBenefits:\n• 2x Daily Bonus\n• Unlimited SMS\n• Priority support"
        else:
            text = "👑 *VIP Mode*\n\nYou are not VIP.\nBuy a subscription to unlock:\n• 2x Daily Bonus\n• Unlimited SMS"
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("💰 Buy Subscription", callback_data="sub_menu")],
                                   [back_main_btn()]])
        await query.edit_message_text(text, reply_markup=kb, parse_mode="Markdown")

    # ========== SEND MESSAGE ==========
    elif data == "send_start":
        u = get_user(user.id)
        if not u["is_vip"]:
            cost = int(get_setting("sms_cost") or 1)
            if u["credits"] < cost:
                await query.edit_message_text(
                    f"❌ Need {cost} credit(s). You have {u['credits']}.\nEarn: Daily Bonus / Referrals / Redeem Codes.",
                    reply_markup=InlineKeyboardMarkup([[back_main_btn()]]))
                return
        clear_states(context)
        context.user_data["send_state"] = "awaiting_phone"
        await query.edit_message_text(
            "📤 *Send Message*\n\nEnter target phone number:\n(Format: +1234567890)",
            parse_mode="Markdown")

    # ========== REDEEM CODE ==========
    elif data == "redeem_start":
        clear_states(context)
        context.user_data["redeem_state"] = "awaiting_code"
        await query.edit_message_text("🎫 *Redeem Code*\n\nEnter your redeem code:", parse_mode="Markdown")

    # ========== SUBSCRIPTIONS ==========
    elif data == "sub_menu":
        plans = get_all_subscriptions()
        if not plans:
            await query.edit_message_text("No plans available.", reply_markup=InlineKeyboardMarkup([[back_main_btn()]]))
            return
        text = "💰 *Subscription Plans*\n\n"
        kb = []
        for p in plans:
            text += f"*{p['plan_name']}* — ${p['price']:.2f}\n  💎 {p['credits']} credits | {p['duration_days']} days\n\n"
            kb.append([InlineKeyboardButton(f"🛒 Buy: {p['plan_name']}", callback_data=f"sub_buy_{p['id']}")])
        text += "After purchase, admin will approve your VIP."
        kb.append([back_main_btn()])
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown")

    elif data.startswith("sub_buy_"):
        plan_id = int(data.split("sub_buy_")[1])
        plan = get_subscription(plan_id)
        if not plan:
            await query.edit_message_text("Plan not found.", reply_markup=InlineKeyboardMarkup([[back_main_btn()]]))
            return
        owner = get_setting("support_owner") or "@owner"
        text = (
            f"💳 *Purchase: {plan['plan_name']}*\n\n"
            f"💰 Price: *${plan['price']:.2f}*\n"
            f"💎 Credits: *{plan['credits']}*\n"
            f"📅 Duration: *{plan['duration_days']} days*\n\n"
            f"Pay to: {owner}\n"
            f"After payment, click below."
        )
        context.user_data["sub_buy_plan_id"] = plan_id
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("✅ I've Paid — Submit for Approval", callback_data=f"sub_confirm_{plan_id}")],
            [back_main_btn()],
        ])
        await query.edit_message_text(text, reply_markup=kb, parse_mode="Markdown")

    elif data.startswith("sub_confirm_"):
        plan_id = int(data.split("sub_confirm_")[1])
        plan = get_subscription(plan_id)
        if not plan or context.user_data.get("sub_buy_plan_id") != plan_id:
            await query.edit_message_text("Error. Try again.", reply_markup=InlineKeyboardMarkup([[back_main_btn()]]))
            return
        create_pending_approval(user.id, plan_id, plan["plan_name"])
        context.user_data.pop("sub_buy_plan_id", None)
        await query.edit_message_text(
            "✅ *Submitted!* Admin will review your payment.\nYou'll be notified once approved.",
            reply_markup=main_menu_kb(), parse_mode="Markdown")
        try:
            await context.bot.send_message(
                ADMIN_USER_ID,
                f"🔔 *New Purchase Request*\nUser: {user.id} (@{user.username or 'N/A'})\nPlan: {plan['plan_name']}\nGo to Admin Panel → VIP/Approvals.",
                parse_mode="Markdown")
        except Exception:
            pass

    # ====================================================================
    # ADMIN PANEL
    # ====================================================================
    elif data == "admin":
        if user.id != ADMIN_USER_ID: return
        clear_states(context)
        await query.edit_message_text("🔧 *Admin Panel*", reply_markup=admin_main_kb(), parse_mode="Markdown")

    # --- SMS Settings ---
    elif data == "admin_sms_menu":
        if user.id != ADMIN_USER_ID: return
        sms_limit = get_setting("sms_limit") or "1"
        sms_cost = get_setting("sms_cost") or "1"
        text = f"📨 *SMS Settings*\n\nLimit per request: *{sms_limit}*\nCost per SMS: *{sms_cost}* credits"
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("✏️ Change SMS Limit", callback_data="admin_sms_limit")],
            [InlineKeyboardButton("✏️ Change SMS Cost", callback_data="admin_sms_cost")],
            [InlineKeyboardButton("🔙 Admin Panel", callback_data="admin")],
        ])
        await query.edit_message_text(text, reply_markup=kb, parse_mode="Markdown")

    elif data == "admin_sms_limit":
        if user.id != ADMIN_USER_ID: return
        context.user_data["admin_state"] = "awaiting_sms_limit"
        await query.edit_message_text(
            f"Current limit: *{get_setting('sms_limit') or '1'}*\nSend the new *max SMS per request*:",
            parse_mode="Markdown")

    elif data == "admin_sms_cost":
        if user.id != ADMIN_USER_ID: return
        context.user_data["admin_state"] = "awaiting_sms_cost"
        await query.edit_message_text(
            f"Current cost: *{get_setting('sms_cost') or '1'}* credits\nSend the new *cost per SMS*:",
            parse_mode="Markdown")

    # --- Subscription Management ---
    elif data == "admin_subs_menu":
        if user.id != ADMIN_USER_ID: return
        plans = get_all_subscriptions()
        text = "💳 *Subscription Plans*\n\n"
        kb = []
        for p in plans:
            text += f"• {p['plan_name']} — ${p['price']:.2f} ({p['credits']} cr)\n"
            kb.append([InlineKeyboardButton(f"✏️ Edit: {p['plan_name']}", callback_data=f"admin_subs_edit_{p['id']}")])
            kb.append([InlineKeyboardButton(f"🗑 Delete: {p['plan_name']}", callback_data=f"admin_subs_del_{p['id']}")])
        kb.append([InlineKeyboardButton("➕ Add New Plan", callback_data="admin_subs_add")])
        kb.append([InlineKeyboardButton("🔙 Admin Panel", callback_data="admin")])
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown")

    elif data.startswith("admin_subs_edit_"):
        if user.id != ADMIN_USER_ID: return
        plan_id = int(data.split("admin_subs_edit_")[1])
        plan = get_subscription(plan_id)
        if not plan: return
        text = (
            f"✏️ *Edit: {plan['plan_name']}*\n\n"
            f"Name: {plan['plan_name']}\nPrice: ${plan['price']:.2f}\nCredits: {plan['credits']}\nDuration: {plan['duration_days']} days\nDesc: {plan['description']}"
        )
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("✏️ Name", callback_data=f"admin_subs_field_{plan_id}_plan_name")],
            [InlineKeyboardButton("✏️ Price", callback_data=f"admin_subs_field_{plan_id}_price")],
            [InlineKeyboardButton("✏️ Credits", callback_data=f"admin_subs_field_{plan_id}_credits")],
            [InlineKeyboardButton("✏️ Duration", callback_data=f"admin_subs_field_{plan_id}_duration_days")],
            [InlineKeyboardButton("✏️ Description", callback_data=f"admin_subs_field_{plan_id}_description")],
            [InlineKeyboardButton("🔙 Plans", callback_data="admin_subs_menu")],
        ])
        await query.edit_message_text(text, reply_markup=kb, parse_mode="Markdown")

    elif data.startswith("admin_subs_field_"):
        if user.id != ADMIN_USER_ID: return
        parts = data.split("_")
        field = parts[3]
        plan_id = int(parts[4]) if len(parts) > 4 else int(parts[3])
        context.user_data["admin_sub_state"] = f"edit_{plan_id}_{field}"
        await query.edit_message_text(
            f"Send new value for *{field}*:", parse_mode="Markdown")

    elif data.startswith("admin_subs_del_"):
        if user.id != ADMIN_USER_ID: return
        plan_id = int(data.split("admin_subs_del_")[1])
        delete_subscription(plan_id)
        await query.edit_message_text("✅ Plan deleted.", reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 Plans", callback_data="admin_subs_menu")]
        ]))

    elif data == "admin_subs_add":
        if user.id != ADMIN_USER_ID: return
        context.user_data["admin_sub_state"] = "add_name"
        await query.edit_message_text("➕ *Add Plan*\n\nSend plan *name*:", parse_mode="Markdown")

    # --- VIP / Approvals ---
    elif data == "admin_vip_menu":
        if user.id != ADMIN_USER_ID: return
        pending = len(get_pending_approvals())
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton(f"📋 Pending Approvals ({pending})", callback_data="admin_vip_pending")],
            [InlineKeyboardButton("👤 Manually Set VIP", callback_data="admin_vip_manual_set")],
            [InlineKeyboardButton("👤 Remove VIP", callback_data="admin_vip_manual_remove")],
            [InlineKeyboardButton("📋 List VIP Users", callback_data="admin_vip_list")],
            [InlineKeyboardButton("🔙 Admin Panel", callback_data="admin")],
        ])
        await query.edit_message_text("👑 *VIP Management*", reply_markup=kb, parse_mode="Markdown")

    elif data == "admin_vip_pending":
        if user.id != ADMIN_USER_ID: return
        approvals = get_pending_approvals()
        if not approvals:
            await query.edit_message_text("No pending approvals.", reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 VIP Menu", callback_data="admin_vip_menu")]
            ]))
            return
        text = "📋 *Pending Approvals*\n\n"
        kb = []
        for a in approvals:
            uu = get_user(a["user_id"])
            uname = f"@{uu['username']}" if uu and uu["username"] else str(a["user_id"])
            text += f"🆔 {a['user_id']} ({uname}) → {a['plan_name']}\n"
            kb.append([
                InlineKeyboardButton(f"✅ Approve #{a['id']}", callback_data=f"admin_vip_approve_{a['id']}"),
                InlineKeyboardButton(f"❌ Decline #{a['id']}", callback_data=f"admin_vip_decline_{a['id']}"),
            ])
        kb.append([InlineKeyboardButton("🔙 VIP Menu", callback_data="admin_vip_menu")])
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown")

    elif data.startswith("admin_vip_approve_"):
        if user.id != ADMIN_USER_ID: return
        aid = int(data.split("admin_vip_approve_")[1])
        approval = approve_payment(aid)
        if approval:
            uu = get_user(approval["user_id"])
            plan = get_subscription(approval["plan_id"])
            pname = plan["plan_name"] if plan else approval["plan_name"]
            try:
                await context.bot.send_message(
                    approval["user_id"],
                    f"🎉 *VIP Approved!*\nPlan: {pname}\nYou now have VIP — unlimited SMS!\n/start",
                    parse_mode="Markdown")
            except Exception:
                pass
            await query.edit_message_text(
                f"✅ Approved! User {approval['user_id']} is now VIP.\nPlan: {pname}",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔙 Pending", callback_data="admin_vip_pending")]
                ]))

    elif data.startswith("admin_vip_decline_"):
        if user.id != ADMIN_USER_ID: return
        aid = int(data.split("admin_vip_decline_")[1])
        approval = decline_payment(aid)
        if approval:
            try:
                await context.bot.send_message(
                    approval["user_id"],
                    "❌ Your payment was *declined*. Contact support.\n/start",
                    parse_mode="Markdown")
            except Exception:
                pass
            await query.edit_message_text(
                f"❌ Declined. User {approval['user_id']} notified.",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔙 Pending", callback_data="admin_vip_pending")]
                ]))

    elif data == "admin_vip_manual_set":
        if user.id != ADMIN_USER_ID: return
        context.user_data["admin_state"] = "awaiting_vip_set"
        await query.edit_message_text("Send *User ID* to set as VIP:", parse_mode="Markdown")

    elif data == "admin_vip_manual_remove":
        if user.id != ADMIN_USER_ID: return
        context.user_data["admin_state"] = "awaiting_vip_remove"
        await query.edit_message_text("Send *User ID* to remove VIP:", parse_mode="Markdown")

    elif data == "admin_vip_list":
        if user.id != ADMIN_USER_ID: return
        users = get_all_users()
        vips = [u for u in users if u["is_vip"]]
        if not vips:
            text = "No VIP users."
        else:
            text = "👑 *VIP Users:*\n" + "\n".join(
                f"• `{u['user_id']}` - {u['first_name'] or 'N/A'} (@{u['username'] or 'N/A'})" for u in vips)
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 VIP Menu", callback_data="admin_vip_menu")]])
        await query.edit_message_text(text, reply_markup=kb, parse_mode="Markdown")

    # --- Rewards Config ---
    elif data == "admin_rewards_menu":
        if user.id != ADMIN_USER_ID: return
        db = get_setting("daily_bonus_credits") or "5"
        ref = get_setting("referral_reward_credits") or "10"
        text = f"🎁 *Rewards*\n\nDaily Bonus: *{db}* credits\nReferral: *{ref}* credits"
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("✏️ Set Daily Bonus", callback_data="admin_rewards_daily")],
            [InlineKeyboardButton("✏️ Set Referral Reward", callback_data="admin_rewards_referral")],
            [InlineKeyboardButton("🔙 Admin Panel", callback_data="admin")],
        ])
        await query.edit_message_text(text, reply_markup=kb, parse_mode="Markdown")

    elif data == "admin_rewards_daily":
        if user.id != ADMIN_USER_ID: return
        context.user_data["admin_state"] = "awaiting_rewards_daily"
        await query.edit_message_text(
            f"Current daily bonus: *{get_setting('daily_bonus_credits') or '5'}*\nSend new value:",
            parse_mode="Markdown")

    elif data == "admin_rewards_referral":
        if user.id != ADMIN_USER_ID: return
        context.user_data["admin_state"] = "awaiting_rewards_referral"
        await query.edit_message_text(
            f"Current referral reward: *{get_setting('referral_reward_credits') or '10'}*\nSend new value:",
            parse_mode="Markdown")

    # --- Bot Settings (channels, support) ---
    elif data == "admin_settings_menu":
        if user.id != ADMIN_USER_ID: return
        ch1_u = get_setting("channel_1_username") or "@channel1"
        ch2_u = get_setting("channel_2_username") or "@channel2"
        ch1_l = get_setting("channel_1_link") or ""
        ch2_l = get_setting("channel_2_link") or ""
        s_dev = get_setting("support_dev") or "@dev"
        s_own = get_setting("support_owner") or "@owner"
        api_u = get_setting("sms_api_url") or ""
        api_k = get_setting("sms_api_key") or ""
        api_p = get_setting("sms_api_params") or ""
        text = (
            "🔗 *Bot Settings*\n\n"
            f"Channel 1: {ch1_u}\n"
            f"Channel 1 Link: {ch1_l}\n"
            f"Channel 2: {ch2_u}\n"
            f"Channel 2 Link: {ch2_l}\n"
            f"Support Dev: {s_dev}\n"
            f"Support Owner: {s_own}\n"
            f"──────────────\n"
            f"API URL: `{api_u}`\n"
            f"API Key: `{api_k}`\n"
            f"API Params: `{api_p}`"
        )
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("✏️ Channel 1 Username", callback_data="admin_set_ch1_username")],
            [InlineKeyboardButton("✏️ Channel 1 Link", callback_data="admin_set_ch1_link")],
            [InlineKeyboardButton("✏️ Channel 2 Username", callback_data="admin_set_ch2_username")],
            [InlineKeyboardButton("✏️ Channel 2 Link", callback_data="admin_set_ch2_link")],
            [InlineKeyboardButton("✏️ Support Dev", callback_data="admin_set_support_dev")],
            [InlineKeyboardButton("✏️ Support Owner", callback_data="admin_set_support_owner")],
            [InlineKeyboardButton("✏️ API URL", callback_data="admin_set_api_url")],
            [InlineKeyboardButton("✏️ API Key", callback_data="admin_set_api_key")],
            [InlineKeyboardButton("✏️ API Params", callback_data="admin_set_api_params")],
            [InlineKeyboardButton("🔙 Admin Panel", callback_data="admin")],
        ])
        await query.edit_message_text(text, reply_markup=kb, parse_mode="Markdown")

    elif data.startswith("admin_set_"):
        if user.id != ADMIN_USER_ID: return
        key_map = {
            "admin_set_ch1_username": ("channel_1_username", "Channel 1 Username"),
            "admin_set_ch1_link": ("channel_1_link", "Channel 1 Link"),
            "admin_set_ch2_username": ("channel_2_username", "Channel 2 Username"),
            "admin_set_ch2_link": ("channel_2_link", "Channel 2 Link"),
            "admin_set_support_dev": ("support_dev", "Support Dev"),
            "admin_set_support_owner": ("support_owner", "Support Owner"),
            "admin_set_api_url": ("sms_api_url", "API URL"),
            "admin_set_api_key": ("sms_api_key", "API Key"),
            "admin_set_api_params": ("sms_api_params", "API Params"),
        }
        if data in key_map:
            context.user_data["admin_state"] = f"awaiting_setting_{key_map[data][0]}"
            cur = get_setting(key_map[data][0]) or "(empty)"
            await query.edit_message_text(
                f"Current *{key_map[data][1]}*: `{cur}`\nSend new value:",
                parse_mode="Markdown")

    # --- Redeem Codes Admin ---
    elif data == "admin_codes_menu":
        if user.id != ADMIN_USER_ID: return
        codes = get_all_codes()
        text = "🎫 *Redeem Codes*\n\n"
        if codes:
            for c in codes:
                text += f"`{c['code']}` — {c['points']}pts ({c['used_count']}/{c['max_uses']} used)\n"
        else:
            text += "No codes yet."
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("➕ Generate New Code", callback_data="admin_codes_gen")],
            [InlineKeyboardButton("🔙 Admin Panel", callback_data="admin")],
        ])
        await query.edit_message_text(text, reply_markup=kb, parse_mode="Markdown")

    elif data == "admin_codes_gen":
        if user.id != ADMIN_USER_ID: return
        code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=10))
        context.user_data["gen_code"] = code
        context.user_data["admin_state"] = "awaiting_gen_code_points"
        await query.edit_message_text(
            f"🎫 Code: `{code}`\nSend the *points* this code gives:",
            parse_mode="Markdown")

    # --- Stats ---
    elif data == "admin_stats":
        if user.id != ADMIN_USER_ID: return
        total, verified, vip, pending = get_stats()
        text = (
            f"📊 *Stats*\n\n"
            f"👥 Users: {total}\n"
            f"✅ Verified: {verified}\n"
            f"👑 VIP: {vip}\n"
            f"📋 Pending Approvals: {pending}"
        )
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Admin Panel", callback_data="admin")]])
        await query.edit_message_text(text, reply_markup=kb, parse_mode="Markdown")

    # --- Broadcast ---
    elif data == "admin_broadcast":
        if user.id != ADMIN_USER_ID: return
        context.user_data["admin_state"] = "awaiting_broadcast"
        await query.edit_message_text("📢 Send the message to broadcast:", parse_mode="Markdown")

# ============================================================
# MESSAGE HANDLER
# ============================================================
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    text = update.message.text.strip()
    db_user = get_user(user.id)

    if text.lower() == "/admin" and user.id == ADMIN_USER_ID:
        await update.message.reply_text("🔧 *Admin Panel*", reply_markup=admin_main_kb(), parse_mode="Markdown")
        return

    if not db_user or not db_user["is_verified"]:
        await update.message.reply_text("Use /start and verify first.")
        return

    # --- Send Message flow ---
    state = context.user_data.get("send_state")
    if state == "awaiting_phone":
        phone = text.strip()
        if not phone:
            await update.message.reply_text("Enter a valid phone number.")
            return
        context.user_data["phone_number"] = phone
        context.user_data["send_state"] = "awaiting_amount"
        sms_limit = get_setting("sms_limit") or "1"
        await update.message.reply_text(f"How many messages? (Max: *{sms_limit}*)", parse_mode="Markdown")
        return

    if state == "awaiting_amount":
        try:
            amount = int(text.strip())
        except ValueError:
            await update.message.reply_text("Enter a valid number.")
            return
        sms_limit = int(get_setting("sms_limit") or 1)
        u = get_user(user.id)

        if not u["is_vip"] and amount > sms_limit:
            warning = (
                f"⚠️ *Warning:* Max is *{sms_limit}* per request. "
                "This system is heavily monitored to prevent spam. "
                "Any attempt to abuse this system or bypass limits "
                "will result in an immediate permanent ban and strict legal action."
            )
            await update.message.reply_text(warning, parse_mode="Markdown")
            clear_states(context)
            return
        if amount < 1:
            await update.message.reply_text("Minimum is 1.", reply_markup=main_menu_kb())
            clear_states(context)
            return

        if not u["is_vip"]:
            sms_cost = int(get_setting("sms_cost") or 1)
            total_cost = sms_cost * amount
            if u["credits"] < total_cost:
                await update.message.reply_text(
                    f"❌ Need {total_cost} credits. You have {u['credits']}.",
                    reply_markup=main_menu_kb())
                clear_states(context)
                return
            if not deduct_credits(user.id, total_cost):
                await update.message.reply_text("❌ Error. Try again.", reply_markup=main_menu_kb())
                clear_states(context)
                return
            cost_msg = f"\n💎 Cost: {total_cost} credit(s)"
        else:
            cost_msg = "\n👑 VIP: *No credits deducted*"

        phone = context.user_data.get("phone_number", "")
        await update.message.reply_text(
            f"📤 *Processing*\n\n📱: `{phone}`\n📨: {amount}{cost_msg}\n\n⏳ Sending...",
            parse_mode="Markdown")

        api_url = get_setting("sms_api_url") or "https://sms-sender-rww0.onrender.com"
        api_key = get_setting("sms_api_key") or "SuSHiLx2024SMS"
        api_params = get_setting("sms_api_params") or "phone={phone}&count={amount}&apikey={api_key}"
        api_params = api_params.replace("{phone}", phone).replace("{amount}", str(amount)).replace("{api_key}", api_key)
        full_url = f"{api_url.rstrip('/')}?{api_params}"

        try:
            resp = requests.get(full_url, timeout=15)
            if resp.status_code == 200:
                await update.message.reply_text("✅ *Sent successfully!* /start for menu.", parse_mode="Markdown")
            else:
                await update.message.reply_text(
                    f"⚠️ API returned status {resp.status_code}. /start for menu.", parse_mode="Markdown")
        except Exception as e:
            await update.message.reply_text(
                f"❌ Failed to connect to API.\n`{e}`\n\nContact support. /start", parse_mode="Markdown")

        clear_states(context)
        return

    # --- Redeem Code flow ---
    if context.user_data.get("redeem_state") == "awaiting_code":
        code = text.strip().upper()
        ok, result = redeem_code(user.id, code)
        msg = f"🎫 +{result} credits!" if ok else f"❌ {result}"
        await update.message.reply_text(msg, reply_markup=main_menu_kb(), parse_mode="Markdown")
        context.user_data.pop("redeem_state", None)
        return

    # --- Admin states ---
    admin_state = context.user_data.get("admin_state")
    admin_sub_state = context.user_data.get("admin_sub_state")

    if user.id == ADMIN_USER_ID and admin_state:
        if admin_state == "awaiting_sms_limit":
            try:
                val = int(text)
                if val < 1: raise ValueError
            except ValueError:
                await update.message.reply_text("Enter a positive number.")
                return
            set_setting("sms_limit", str(val))
            await update.message.reply_text(
                f"✅ SMS limit set to *{val}*.", reply_markup=admin_main_kb(), parse_mode="Markdown")
            context.user_data.pop("admin_state", None)

        elif admin_state == "awaiting_sms_cost":
            try:
                val = int(text)
                if val < 0: raise ValueError
            except ValueError:
                await update.message.reply_text("Enter a valid number.")
                return
            set_setting("sms_cost", str(val))
            await update.message.reply_text(
                f"✅ SMS cost set to *{val}* credits.", reply_markup=admin_main_kb(), parse_mode="Markdown")
            context.user_data.pop("admin_state", None)

        elif admin_state == "awaiting_rewards_daily":
            try:
                val = int(text)
                if val < 1: raise ValueError
            except ValueError:
                await update.message.reply_text("Enter a positive number.")
                return
            set_setting("daily_bonus_credits", str(val))
            await update.message.reply_text(
                f"✅ Daily bonus set to *{val}*.", reply_markup=admin_main_kb(), parse_mode="Markdown")
            context.user_data.pop("admin_state", None)

        elif admin_state == "awaiting_rewards_referral":
            try:
                val = int(text)
                if val < 1: raise ValueError
            except ValueError:
                await update.message.reply_text("Enter a positive number.")
                return
            set_setting("referral_reward_credits", str(val))
            await update.message.reply_text(
                f"✅ Referral reward set to *{val}*.", reply_markup=admin_main_kb(), parse_mode="Markdown")
            context.user_data.pop("admin_state", None)

        elif admin_state.startswith("awaiting_setting_"):
            key = admin_state.replace("awaiting_setting_", "")
            set_setting(key, text)
            label_map = {
                "channel_1_username": "Channel 1 Username",
                "channel_1_link": "Channel 1 Link",
                "channel_2_username": "Channel 2 Username",
                "channel_2_link": "Channel 2 Link",
                "support_dev": "Support Dev",
                "support_owner": "Support Owner",
            }
            label = label_map.get(key, key)
            await update.message.reply_text(
                f"✅ *{label}* updated.", reply_markup=admin_main_kb(), parse_mode="Markdown")
            context.user_data.pop("admin_state", None)

        elif admin_state == "awaiting_gen_code_points":
            try:
                points = int(text)
                if points < 1: raise ValueError
            except ValueError:
                await update.message.reply_text("Enter a positive number.")
                return
            context.user_data["gen_code_points"] = points
            context.user_data["admin_state"] = "awaiting_gen_code_uses"
            await update.message.reply_text("Send *max uses* for this code:", parse_mode="Markdown")

        elif admin_state == "awaiting_gen_code_uses":
            try:
                uses = int(text)
                if uses < 1: raise ValueError
            except ValueError:
                await update.message.reply_text("Enter a positive number.")
                return
            code = context.user_data.get("gen_code", "")
            points = context.user_data.get("gen_code_points", 0)
            ok = create_redeem_code(code, points, uses, user.id)
            if ok:
                await update.message.reply_text(
                    f"✅ Code `{code}` — {points}pts, {uses} uses", reply_markup=admin_main_kb(),
                    parse_mode="Markdown")
            else:
                await update.message.reply_text("❌ Code exists.", reply_markup=admin_main_kb())
            context.user_data.pop("admin_state", None)
            context.user_data.pop("gen_code", None)
            context.user_data.pop("gen_code_points", None)

        elif admin_state == "awaiting_vip_set":
            try:
                tid = int(text)
            except ValueError:
                await update.message.reply_text("Send valid User ID.")
                return
            t = get_user(tid)
            if not t:
                await update.message.reply_text("User not found.", reply_markup=admin_main_kb())
                context.user_data.pop("admin_state", None)
                return
            set_vip(tid, 1)
            await update.message.reply_text(
                f"✅ User `{tid}` is now *VIP*.", reply_markup=admin_main_kb(), parse_mode="Markdown")
            context.user_data.pop("admin_state", None)

        elif admin_state == "awaiting_vip_remove":
            try:
                tid = int(text)
            except ValueError:
                await update.message.reply_text("Send valid User ID.")
                return
            t = get_user(tid)
            if not t:
                await update.message.reply_text("User not found.", reply_markup=admin_main_kb())
                context.user_data.pop("admin_state", None)
                return
            set_vip(tid, 0)
            await update.message.reply_text(
                f"✅ VIP removed from `{tid}`.", reply_markup=admin_main_kb(), parse_mode="Markdown")
            context.user_data.pop("admin_state", None)

        elif admin_state == "awaiting_broadcast":
            users = get_all_users()
            sent, failed = 0, 0
            for u in users:
                try:
                    await context.bot.send_message(u["user_id"], f"📢 *Broadcast*\n\n{text}", parse_mode="Markdown")
                    sent += 1
                except Exception:
                    failed += 1
            await update.message.reply_text(
                f"📢 Sent: {sent} ✅ | Failed: {failed} ❌", reply_markup=admin_main_kb())
            context.user_data.pop("admin_state", None)
        return

    # --- Admin sub state (subscription editing) ---
    if user.id == ADMIN_USER_ID and admin_sub_state:
        if admin_sub_state == "add_name":
            context.user_data["admin_sub_state"] = "add_price"
            context.user_data["admin_sub_data"] = {"name": text}
            await update.message.reply_text("Send plan *price* (e.g. 9.99):", parse_mode="Markdown")
        elif admin_sub_state == "add_price":
            try:
                price = float(text)
            except ValueError:
                await update.message.reply_text("Enter a valid price.")
                return
            context.user_data["admin_sub_data"]["price"] = price
            context.user_data["admin_sub_state"] = "add_credits"
            await update.message.reply_text("Send plan *credits*:", parse_mode="Markdown")
        elif admin_sub_state == "add_credits":
            try:
                credits = int(text)
            except ValueError:
                await update.message.reply_text("Enter a valid number.")
                return
            context.user_data["admin_sub_data"]["credits"] = credits
            context.user_data["admin_sub_state"] = "add_duration"
            await update.message.reply_text("Send plan *duration* (days):", parse_mode="Markdown")
        elif admin_sub_state == "add_duration":
            try:
                dur = int(text)
            except ValueError:
                await update.message.reply_text("Enter a valid number.")
                return
            context.user_data["admin_sub_data"]["duration"] = dur
            context.user_data["admin_sub_state"] = "add_description"
            await update.message.reply_text("Send plan *description*:", parse_mode="Markdown")
        elif admin_sub_state == "add_description":
            d = context.user_data["admin_sub_data"]
            add_subscription(d["name"], d["price"], d["credits"], d["duration"], text)
            await update.message.reply_text("✅ Plan added!", reply_markup=admin_main_kb())
            context.user_data.pop("admin_sub_state", None)
            context.user_data.pop("admin_sub_data", None)

        elif admin_sub_state.startswith("edit_"):
            parts = admin_sub_state.split("_")
            if len(parts) >= 3:
                plan_id = int(parts[1])
                field = parts[2]
                if field == "price":
                    try:
                        val = float(text)
                    except ValueError:
                        await update.message.reply_text("Invalid number.")
                        return
                elif field in ("credits", "duration_days"):
                    try:
                        val = int(text)
                    except ValueError:
                        await update.message.reply_text("Invalid number.")
                        return
                else:
                    val = text
                update_subscription(plan_id, field, val)
                await update.message.reply_text(
                    f"✅ Updated.", reply_markup=InlineKeyboardMarkup([
                        [InlineKeyboardButton("🔙 Plans", callback_data="admin_subs_menu")]
                    ]))
                context.user_data.pop("admin_sub_state", None)
        return

    # --- Fallback ---
    await update.message.reply_text("Use /start for the menu.", reply_markup=main_menu_kb())

# ============================================================
# MAIN
# ============================================================
def main():
    init_db()
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("admin", admin_command))
    app.add_handler(CallbackQueryHandler(callback_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    if WEBHOOK_URL or os.getenv("RENDER_EXTERNAL_URL"):
        render_url = WEBHOOK_URL or os.getenv("RENDER_EXTERNAL_URL", "")
        app.run_webhook(listen="0.0.0.0", port=PORT, url_path=BOT_TOKEN,
                        webhook_url=f"{render_url.rstrip('/')}/{BOT_TOKEN}")
    else:
        print("Bot running (polling)...")
        app.run_polling()

if __name__ == "__main__":
    main()
