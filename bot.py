import html
import logging
import asyncio
from datetime import datetime
from pathlib import Path
from typing import List, Tuple

import feedparser
import aiohttp
import aiosqlite
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ParseMode
from telegram.error import Forbidden, RetryAfter, TelegramError
from telegram.ext import (
    Application,
    ApplicationBuilder,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

# ==========================
# 基础配置 (启动前请务必修改这里)
# ==========================
BOT_TOKEN = "YOUR_BOT_TOKEN_HERE"      # 替换为你的 Telegram Bot Token
ADMIN_ID = 123456789                   # 替换为你的 Telegram 用户数字 ID
RSS_URL = "https://rss.nodeseek.com/"
DB_PATH = Path("nodeseek_bot.db")
DEFAULT_CHECK_INTERVAL = 30            # 默认 RSS 轮询间隔(秒)
REQUEST_TIMEOUT = 15

logging.basicConfig(
    format="[%(asctime)s] [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    level=logging.INFO,
)
logger = logging.getLogger("NodeSeekBot")


# ==========================
# 异步数据库管理器
# ==========================
class AsyncDBManager:
    def __init__(self, db_path: Path):
        self.db_path = db_path

    async def init_db(self):
        """初始化表结构"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            await db.execute("""
                CREATE TABLE IF NOT EXISTS system_config (
                    key TEXT PRIMARY KEY, value TEXT
                )
            """)
            await db.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    user_id INTEGER PRIMARY KEY,
                    is_active INTEGER DEFAULT 1,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            await db.execute("""
                CREATE TABLE IF NOT EXISTS user_blocked_keywords (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER, keyword TEXT,
                    UNIQUE(user_id, keyword)
                )
            """)
            await db.execute("""
                CREATE TABLE IF NOT EXISTS user_blocked_authors (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER, author TEXT,
                    UNIQUE(user_id, author)
                )
            """)
            await db.execute("INSERT OR IGNORE INTO system_config (key, value) VALUES ('max_id', '0')")
            await db.execute("INSERT OR IGNORE INTO system_config (key, value) VALUES ('is_public', '0')")
            await db.execute(f"INSERT OR IGNORE INTO system_config (key, value) VALUES ('check_interval', '{DEFAULT_CHECK_INTERVAL}')")
            await db.commit()

    async def get_config(self, key: str, default: str) -> str:
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute("SELECT value FROM system_config WHERE key = ?", (key,)) as cursor:
                row = await cursor.fetchone()
                return row[0] if row else default

    async def set_config(self, key: str, value: str):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("UPDATE system_config SET value = ? WHERE key = ?", (value, key))
            await db.commit()

    async def is_public_mode(self) -> bool:
        return await self.get_config('is_public', '0') == '1'

    async def get_max_id(self) -> int:
        return int(await self.get_config('max_id', '0'))

    async def get_check_interval(self) -> int:
        return int(await self.get_config('check_interval', str(DEFAULT_CHECK_INTERVAL)))

    async def set_check_interval(self, interval: int):
        await self.set_config('check_interval', str(interval))

    async def get_active_users(self) -> List[int]:
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute("SELECT user_id FROM users WHERE is_active = 1") as cursor:
                return [row[0] for row in await cursor.fetchall()]

    async def add_user(self, user_id: int):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("INSERT OR IGNORE INTO users (user_id, is_active) VALUES (?, 1)", (user_id,))
            await db.commit()

    async def is_user_active(self, user_id: int) -> bool:
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute("SELECT is_active FROM users WHERE user_id = ?", (user_id,)) as cursor:
                row = await cursor.fetchone()
                return bool(row[0]) if row else False

    async def toggle_user_active(self, user_id: int) -> bool:
        current = await self.is_user_active(user_id)
        new_state = 0 if current else 1
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("UPDATE users SET is_active = ? WHERE user_id = ?", (new_state, user_id))
            await db.commit()
        return bool(new_state)

    async def get_user_list_data(self, user_id: int, table: str, field: str) -> List[str]:
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute(f"SELECT {field} FROM {table} WHERE user_id = ?", (user_id,)) as cursor:
                return [row[0] for row in await cursor.fetchall()]

    async def add_user_items(self, user_id: int, table: str, field: str, items: List[str]):
        async with aiosqlite.connect(self.db_path) as db:
            for item in items:
                await db.execute(f"INSERT OR IGNORE INTO {table} (user_id, {field}) VALUES (?, ?)", (user_id, item.strip()))
            await db.commit()

    async def remove_user_item(self, user_id: int, table: str, field: str, item: str):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(f"DELETE FROM {table} WHERE user_id = ? AND {field} = ?", (user_id, item.strip()))
            await db.commit()

    async def clear_user_items(self, user_id: int, table: str):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(f"DELETE FROM {table} WHERE user_id = ?", (user_id,))
            await db.commit()

    async def get_stats(self) -> Tuple[int, int]:
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute("SELECT COUNT(*) FROM users") as c1:
                total = (await c1.fetchone())[0]
            async with db.execute("SELECT COUNT(*) FROM users WHERE is_active = 1") as c2:
                active = (await c2.fetchone())[0]
            return total, active


db = AsyncDBManager(DB_PATH)


# ==========================
# 异步 RSS 抓取与并发分发
# ==========================
async def fetch_rss_entries_async():
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(RSS_URL, timeout=REQUEST_TIMEOUT, headers={"User-Agent": "Mozilla/5.0 AsyncNodeSeekBot/3.0"}) as resp:
                resp.raise_for_status()
                content = await resp.read()
                feed = feedparser.parse(content)
                return feed.entries
    except Exception as e:
        logger.error(f"获取 RSS 失败: {e}")
        return None

async def should_user_block(user_id: int, author: str, title: str, summary: str) -> bool:
    blocked_authors = await db.get_user_list_data(user_id, "user_blocked_authors", "author")
    if author in blocked_authors:
        return True

    blocked_keywords = await db.get_user_list_data(user_id, "user_blocked_keywords", "keyword")
    for kw in blocked_keywords:
        if kw in title or kw in summary:
            return True

    return False

async def rss_poller_job(context: ContextTypes.DEFAULT_TYPE):
    max_id = await db.get_max_id()
    entries = await fetch_rss_entries_async()

    if not entries:
        return

    new_posts = []
    for entry in entries:
        try:
            post_id = int(entry.get("id", 0))
        except (ValueError, TypeError):
            continue

        if post_id <= max_id:
            continue

        new_posts.append({
            "id": post_id,
            "author": entry.get("author", ""),
            "title": entry.get("title", "").strip(),
            "link": entry.get("link", ""),
            "summary": entry.get("summary", ""),
        })

    if not new_posts:
        return

    new_posts.sort(key=lambda x: x["id"])
    logger.info(f"发现 {len(new_posts)} 篇新帖子")

    is_pub = await db.is_public_mode()
    all_active_users = await db.get_active_users()

    target_users = [u for u in all_active_users if is_pub or u == ADMIN_ID]
    if ADMIN_ID not in target_users and await db.is_user_active(ADMIN_ID):
        target_users.append(ADMIN_ID)

    latest_processed_id = max_id

    for post in new_posts:
        p_id, title, link, author, summary = post["id"], post["title"], post["link"], post["author"], post["summary"]

        if not title or not link:
            latest_processed_id = p_id
            continue

        safe_title = html.escape(title)
        safe_link = html.escape(link, quote=True)
        safe_author = html.escape(author)
        text = f'<b><a href="{safe_link}">{safe_title}</a></b>\n👤 作者: <code>{safe_author}</code>'

        for uid in target_users:
            if await should_user_block(uid, author, title, summary):
                continue

            try:
                await context.bot.send_message(chat_id=uid, text=text, parse_mode=ParseMode.HTML)
                await asyncio.sleep(0.05)
            except Forbidden:
                logger.warning(f"用户 {uid} 已封禁 Bot，停用该用户推送")
                await db.toggle_user_active(uid)
            except RetryAfter as e:
                logger.warning(f"触发 TG 限频，等待 {e.retry_after} 秒")
                await asyncio.sleep(e.retry_after)
                await context.bot.send_message(chat_id=uid, text=text, parse_mode=ParseMode.HTML)
            except TelegramError as e:
                logger.error(f"推送给用户 {uid} 失败: {e}")

        latest_processed_id = p_id

    if latest_processed_id > max_id:
        await db.set_config("max_id", str(latest_processed_id))
        logger.info(f"全局进度更新: {max_id} -> {latest_processed_id}")


# ==========================
# 机器人主逻辑类
# ==========================
class NodeSeekBot:
    
    @staticmethod
    def update_poller_job(context: ContextTypes.DEFAULT_TYPE, new_interval: int):
        """动态更新轮询任务的间隔"""
        jobs = context.job_queue.get_jobs_by_name("rss_poller")
        for job in jobs:
            job.schedule_removal()
        context.job_queue.run_repeating(rss_poller_job, interval=new_interval, first=1, name="rss_poller")

    @staticmethod
    async def check_permission(user_id: int) -> bool:
        if user_id == ADMIN_ID:
            return True
        return await db.is_public_mode()

    @staticmethod
    async def build_main_menu(user_id: int) -> InlineKeyboardMarkup:
        is_active = await db.is_user_active(user_id)
        active_text = "🟢 接收推送：已开启" if is_active else "🔴 接收推送：已关闭"
        
        keyboard = [
            [InlineKeyboardButton(active_text, callback_data="toggle_active")],
            [
                InlineKeyboardButton("📝 屏蔽词设置", callback_data="menu_keywords"),
                InlineKeyboardButton("👤 屏蔽用户设置", callback_data="menu_authors"),
            ],
            [InlineKeyboardButton("📊 查看我的配置", callback_data="view_my_config")],
        ]

        if user_id == ADMIN_ID:
            keyboard.append([InlineKeyboardButton("⚙️ 管理员面板", callback_data="admin_panel")])

        return InlineKeyboardMarkup(keyboard)

    @classmethod
    async def start_cmd(cls, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id

        if not await cls.check_permission(user_id):
            await update.message.reply_text("⛔ 当前机器人处于<b>私有模式</b>，仅管理员可用。", parse_mode=ParseMode.HTML)
            return

        await db.add_user(user_id)
        context.user_data.clear()

        text = (
            "👋 <b>欢迎使用 NodeSeek RSS 监控助手</b>\n\n"
            "你可以通过下方按钮自定义属于你的屏蔽规则（关键词、用户名）。\n"
            "所有用户的规则完全独立，互不影响。"
        )
        await update.message.reply_text(
            text, 
            reply_markup=await cls.build_main_menu(user_id), 
            parse_mode=ParseMode.HTML
        )

    @classmethod
    async def set_interval_cmd(cls, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        if user_id != ADMIN_ID:
            return
        try:
            new_interval = int(context.args[0])
            if new_interval < 10:
                await update.message.reply_text("❌ 间隔不能小于 10 秒。")
                return
            await db.set_check_interval(new_interval)
            cls.update_poller_job(context, new_interval)
            await update.message.reply_text(f"✅ 轮询间隔已成功更新为 {new_interval} 秒！")
        except (IndexError, ValueError):
            await update.message.reply_text("用法: /set_interval <秒数>")

    @classmethod
    async def callback_router(cls, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        user_id = update.effective_user.id
        data = query.data

        if not await cls.check_permission(user_id):
            await query.answer("⛔ 权限不足", show_alert=True)
            return

        if data not in ("kw_add", "au_add", "admin_change_interval"):
            context.user_data.pop("action", None)

        try:
            if data == "main_menu":
                await query.answer()
                await query.edit_message_text(
                    "👋 <b>NodeSeek RSS 监控助手 - 主菜单</b>",
                    reply_markup=await cls.build_main_menu(user_id),
                    parse_mode=ParseMode.HTML
                )

            elif data == "toggle_active":
                new_state = await db.toggle_user_active(user_id)
                await query.answer("✅ 已开启推送" if new_state else "❌ 已暂停推送")
                await query.edit_message_reply_markup(reply_markup=await cls.build_main_menu(user_id))

            elif data == "menu_keywords":
                await query.answer()
                keyboard = [
                    [InlineKeyboardButton("➕ 添加屏蔽词", callback_data="kw_add"),
                     InlineKeyboardButton("🗑️ 删除屏蔽词", callback_data="kw_delete_list")],
                    [InlineKeyboardButton("🧹 清空屏蔽词", callback_data="kw_clear")],
                    [InlineKeyboardButton("⬅️ 返回主菜单", callback_data="main_menu")],
                ]
                await query.edit_message_text(
                    "📝 <b>屏蔽关键词管理</b>\n\n命中标题或正文即不推送给您。",
                    reply_markup=InlineKeyboardMarkup(keyboard),
                    parse_mode=ParseMode.HTML
                )

            elif data == "menu_authors":
                await query.answer()
                keyboard = [
                    [InlineKeyboardButton("➕ 添加屏蔽用户", callback_data="au_add"),
                     InlineKeyboardButton("🗑️ 删除屏蔽用户", callback_data="au_delete_list")],
                    [InlineKeyboardButton("🧹 清空屏蔽用户", callback_data="au_clear")],
                    [InlineKeyboardButton("⬅️ 返回主菜单", callback_data="main_menu")],
                ]
                await query.edit_message_text(
                    "👤 <b>屏蔽作者管理</b>\n\n该用户发布的帖子将不会推送给您。",
                    reply_markup=InlineKeyboardMarkup(keyboard),
                    parse_mode=ParseMode.HTML
                )

            elif data == "view_my_config":
                await query.answer()
                kws = await db.get_user_list_data(user_id, "user_blocked_keywords", "keyword")
                aus = await db.get_user_list_data(user_id, "user_blocked_authors", "author")
                is_active = await db.is_user_active(user_id)

                text = (
                    f"📊 <b>我的配置概览</b>\n\n"
                    f"• <b>推送状态</b>: {'🟢 开启中' if is_active else '🔴 已暂停'}\n"
                    f"• <b>屏蔽词 ({len(kws)}个)</b>: <code>{html.escape('、'.join(kws)) if kws else '无'}</code>\n"
                    f"• <b>屏蔽用户 ({len(aus)}个)</b>: <code>{html.escape('、'.join(aus)) if aus else '无'}</code>\n"
                )
                await query.edit_message_text(
                    text, 
                    reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ 返回", callback_data="main_menu")]]), 
                    parse_mode=ParseMode.HTML
                )

            elif data in ("kw_add", "au_add"):
                await query.answer()
                context.user_data["action"] = data
                label = "屏蔽词" if data == "kw_add" else "屏蔽的用户名"
                back_cb = "menu_keywords" if data == "kw_add" else "menu_authors"
                
                keyboard = [[InlineKeyboardButton("❌ 取消输入", callback_data=back_cb)]]
                await query.edit_message_text(
                    f"✍️ <b>请输入要添加的{label}：</b>\n<i>(支持一次发送多个，用空格或换行分隔)</i>",
                    reply_markup=InlineKeyboardMarkup(keyboard),
                    parse_mode=ParseMode.HTML
                )

            elif data in ("kw_delete_list", "au_delete_list"):
                await query.answer()
                is_kw = (data == "kw_delete_list")
                table, field = ("user_blocked_keywords", "keyword") if is_kw else ("user_blocked_authors", "author")
                back_cb = "menu_keywords" if is_kw else "menu_authors"
                
                items = await db.get_user_list_data(user_id, table, field)
                if not items:
                    await query.edit_message_text(
                        "ℹ️ 当前列表为空。", 
                        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ 返回", callback_data=back_cb)]])
                    )
                    return

                cb_prefix = "del_kw:" if is_kw else "del_au:"
                buttons = [[InlineKeyboardButton(f"❌ {item}", callback_data=f"{cb_prefix}{item}")] for item in items]
                buttons.append([InlineKeyboardButton("⬅️ 返回", callback_data=back_cb)])

                await query.edit_message_text(
                    "🗑️ <b>点击下方按钮即可删除对应规则：</b>", 
                    reply_markup=InlineKeyboardMarkup(buttons), 
                    parse_mode=ParseMode.HTML
                )

            elif data.startswith("del_kw:") or data.startswith("del_au:"):
                is_kw = data.startswith("del_kw:")
                item_to_del = data.split(":", 1)[1]
                table, field = ("user_blocked_keywords", "keyword") if is_kw else ("user_blocked_authors", "author")
                
                await db.remove_user_item(user_id, table, field, item_to_del)
                await query.answer(f"✅ 已删除: {item_to_del}")
                
                items = await db.get_user_list_data(user_id, table, field)
                back_cb = "menu_keywords" if is_kw else "menu_authors"
                cb_prefix = "del_kw:" if is_kw else "del_au:"
                
                buttons = [[InlineKeyboardButton(f"❌ {item}", callback_data=f"{cb_prefix}{item}")] for item in items]
                buttons.append([InlineKeyboardButton("⬅️ 返回", callback_data=back_cb)])
                await query.edit_message_text(
                    "🗑️ <b>点击下方按钮即可删除对应规则：</b>", 
                    reply_markup=InlineKeyboardMarkup(buttons), 
                    parse_mode=ParseMode.HTML
                )

            elif data in ("kw_clear", "au_clear"):
                is_kw = (data == "kw_clear")
                table = "user_blocked_keywords" if is_kw else "user_blocked_authors"
                back_cb = "menu_keywords" if is_kw else "menu_authors"
                
                await db.clear_user_items(user_id, table)
                await query.answer("✅ 已全部清空", show_alert=True)
                await query.edit_message_text(
                    "🧹 您的配置已清空！", 
                    reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ 返回", callback_data=back_cb)]])
                )

            elif data == "admin_panel":
                if user_id != ADMIN_ID:
                    return
                await query.answer()
                is_pub = await db.is_public_mode()
                total, active = await db.get_stats()
                max_id = await db.get_max_id()
                interval = await db.get_check_interval()

                status_text = "🌐 公开模式" if is_pub else "🔒 私有模式"
                toggle_text = "切换为私有模式 🔒" if is_pub else "切换为公开模式 🌐"

                text = (
                    f"⚙️ <b>管理员控制台</b>\n\n"
                    f"• 运行模式: {status_text}\n"
                    f"• 总注册人数: {total}\n"
                    f"• 活跃接收人数: {active}\n"
                    f"• 当前 Max ID: <code>{max_id}</code>\n"
                    f"• RSS 轮询间隔: <b>{interval} 秒</b>\n"
                )
                keyboard = [
                    [InlineKeyboardButton(toggle_text, callback_data="admin_toggle"),
                     InlineKeyboardButton("⏱ 修改轮询间隔", callback_data="admin_change_interval")],
                    [InlineKeyboardButton("⬅️ 返回主菜单", callback_data="main_menu")],
                ]
                await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=ParseMode.HTML)

            elif data == "admin_toggle":
                if user_id != ADMIN_ID:
                    return
                is_pub = await db.is_public_mode()
                await db.set_config("is_public", "0" if is_pub else "1")
                await query.answer("✅ 模式已切换", show_alert=True)
                query.data = "admin_panel"
                await cls.callback_router(update, context)

            elif data == "admin_change_interval":
                if user_id != ADMIN_ID:
                    return
                await query.answer()
                context.user_data["action"] = "waiting_interval_input"
                keyboard = [[InlineKeyboardButton("❌ 取消输入", callback_data="admin_panel")]]
                await query.edit_message_text(
                    "⏱ <b>请输入新的 RSS 轮询间隔（秒）：</b>\n<i>建议不要低于 10 秒。你也可以直接发送指令 /set_interval <秒数></i>",
                    reply_markup=InlineKeyboardMarkup(keyboard),
                    parse_mode=ParseMode.HTML
                )

        except TelegramError as e:
            if "Message is not modified" not in str(e):
                logger.error(f"Callback 路由异常: {e}")

    @classmethod
    async def handle_user_text(cls, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        action = context.user_data.get("action")

        if not action or not update.message.text:
            return

        items = [item.strip() for item in update.message.text.replace("\n", " ").split() if item.strip()]
        if not items:
            return
            
        if action == "waiting_interval_input":
            try:
                new_interval = int(items[0])
                if new_interval < 10:
                    await update.message.reply_text("❌ 间隔不能小于 10 秒，请重新输入或点击取消。")
                    return
                await db.set_check_interval(new_interval)
                cls.update_poller_job(context, new_interval)
                context.user_data.pop("action", None)
                keyboard = [[InlineKeyboardButton("⬅️ 返回控制台", callback_data="admin_panel")]]
                await update.message.reply_text(f"✅ 轮询间隔已成功更新为 {new_interval} 秒！", reply_markup=InlineKeyboardMarkup(keyboard))
            except ValueError:
                await update.message.reply_text("❌ 请输入有效的纯数字（秒数）。")
            return

        if action == "kw_add":
            await db.add_user_items(user_id, "user_blocked_keywords", "keyword", items)
            back_cb = "menu_keywords"
            label = "屏蔽词"
        elif action == "au_add":
            await db.add_user_items(user_id, "user_blocked_authors", "author", items)
            back_cb = "menu_authors"
            label = "屏蔽用户"
        else:
            return

        context.user_data.pop("action", None)
        keyboard = [
            [InlineKeyboardButton("➕ 继续添加", callback_data=action),
             InlineKeyboardButton("⬅️ 返回列表", callback_data=back_cb)],
            [InlineKeyboardButton("🏠 返回主菜单", callback_data="main_menu")],
        ]
        
        await update.message.reply_text(
            f"✅ 成功添加 {len(items)} 个{label}：\n<code>{html.escape('、'.join(items))}</code>",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode=ParseMode.HTML
        )


# ==========================
# 启动入口
# ==========================
async def main():
    logger.info("初始化数据库...")
    await db.init_db()

    logger.info("构建 Telegram Application...")
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", NodeSeekBot.start_cmd))
    app.add_handler(CommandHandler("set_interval", NodeSeekBot.set_interval_cmd))
    app.add_handler(CallbackQueryHandler(NodeSeekBot.callback_router))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, NodeSeekBot.handle_user_text))

    if app.job_queue:
        interval = await db.get_check_interval()
        app.job_queue.run_repeating(rss_poller_job, interval=interval, first=5, name="rss_poller")
    else:
        logger.error("JobQueue 初始化失败")
        return

    logger.info("Bot 已上线启动...")
    await app.initialize()
    await app.start()
    await app.updater.start_polling(drop_pending_updates=True)
    
    stop_event = asyncio.Event()
    await stop_event.wait()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("程序正常退出。")
