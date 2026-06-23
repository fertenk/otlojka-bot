import os
import logging
from datetime import datetime, timedelta

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
    ContextTypes,
    JobQueue,
)

import database as db
from keyboards import (
    main_menu_kb, platform_kb, confirm_post_kb, auto_delete_kb,
    delete_tasks_kb, channel_select_kb, back_kb,
    admin_menu_kb, admin_users_kb, admin_tasks_kb,
    admin_buttons_kb, admin_design_kb, admin_channels_kb,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

BOT_TOKEN = os.environ["BOT_TOKEN"]
ADMIN_ID = int(os.environ["ADMIN_ID"])
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "67FERTENK_BS67")

# ── FSM states stored in user_data ────────────────────
# Keys: "state", "platform", "price", "description", "selected_channel"
# States: "wait_platform_text", "wait_price", "wait_description",
#         "wait_channel", "wait_admin_pass", "wait_add_user",
#         "wait_add_channel_id", "wait_add_channel_name",
#         "wait_edit_btn_key", "wait_edit_btn_value",
#         "wait_edit_template", "wait_edit_closed_tpl"


def is_admin(user_id):
    return user_id == ADMIN_ID


# ════════════════════════════════════════════════════════
#  HELPERS
# ════════════════════════════════════════════════════════

def build_task_text(platform, price, description):
    template = db.get_setting("task_template")
    return template.format(platform=platform, price=price, description=description)


def build_closed_text():
    return db.get_setting("closed_template")


def contact_button_kb(username: str):
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📩 Написать", url=f"https://t.me/{username}")]
    ])


async def close_task_in_channel(context: ContextTypes.DEFAULT_TYPE, task: dict):
    try:
        await context.bot.edit_message_text(
            chat_id=task["channel_id"],
            message_id=task["message_id"],
            text=build_closed_text(),
            reply_markup=None,
        )
    except Exception as e:
        logger.warning(f"Could not edit message: {e}")
    db.close_task(task["id"])


# ════════════════════════════════════════════════════════
#  COMMANDS
# ════════════════════════════════════════════════════════

async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    db.upsert_user(user.id, user.username, user.first_name)

    if not db.is_allowed(user.id) and not is_admin(user.id):
        await update.message.reply_text(
            "🚫 У вас нет доступа к боту.\n"
            "Свяжитесь с администратором для получения доступа."
        )
        return

    ctx.user_data.clear()
    await update.message.reply_text(
        f"👋 Привет, {user.first_name}!\n\nВыберите действие:",
        reply_markup=main_menu_kb(),
    )


async def admin_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    db.upsert_user(user.id, user.username, user.first_name)

    if is_admin(user.id):
        ctx.user_data["state"] = "wait_admin_pass"
        await update.message.reply_text("🔐 Введите пароль администратора:")
    else:
        await update.message.reply_text("❌ Неизвестная команда.")


# ════════════════════════════════════════════════════════
#  CALLBACK QUERY HANDLER
# ════════════════════════════════════════════════════════

async def callback(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    data = q.data
    user_id = q.from_user.id

    # ── Main menu actions ──────────────────────────────

    if data == "back_main":
        ctx.user_data.clear()
        await q.edit_message_text("Выберите действие:", reply_markup=main_menu_kb())
        return

    if data == "cancel":
        ctx.user_data.clear()
        await q.edit_message_text("❌ Отменено. Выберите действие:", reply_markup=main_menu_kb())
        return

    # ── Post task flow ─────────────────────────────────

    if data == "post_task":
        if not db.is_allowed(user_id) and not is_admin(user_id):
            await q.edit_message_text("🚫 Нет доступа.")
            return
        channels = db.get_channels()
        if not channels:
            await q.edit_message_text(
                "⚠️ Каналы не настроены. Обратитесь к администратору.",
                reply_markup=back_kb(),
            )
            return
        ctx.user_data["state"] = "wait_platform"
        await q.edit_message_text(
            "📌 Выберите платформу для задания:",
            reply_markup=platform_kb(),
        )
        return

    if data.startswith("platform_"):
        platform_val = data[len("platform_"):]
        if platform_val == "other":
            ctx.user_data["state"] = "wait_platform_text"
            await q.edit_message_text(
                "✏️ Введите название платформы:",
                reply_markup=InlineKeyboardMarkupCancel(),
            )
        else:
            ctx.user_data["platform"] = platform_val
            ctx.user_data["state"] = "wait_price"
            await q.edit_message_text(
                f"💰 Платформа: *{platform_val}*\n\nВведите цену за выполнение задания:",
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkupCancel(),
            )
        return

    # ── Stats ──────────────────────────────────────────

    if data == "stats":
        tasks = db.get_active_tasks(user_id)
        total = len(db.get_active_tasks(user_id))
        all_tasks_count = len(tasks)
        text = (
            f"📊 *Ваша статистика*\n\n"
            f"• Активных заданий: {all_tasks_count}\n"
        )
        await q.edit_message_text(text, parse_mode="Markdown", reply_markup=back_kb())
        return

    # ── Delete task menu ───────────────────────────────

    if data == "delete_task_menu":
        kb = delete_tasks_kb(user_id)
        if not kb:
            await q.edit_message_text(
                "📭 У вас нет активных заданий.",
                reply_markup=back_kb(),
            )
            return
        await q.edit_message_text(
            "🗑 Выберите задание для удаления:",
            reply_markup=kb,
        )
        return

    if data.startswith("do_delete_"):
        task_id = int(data[len("do_delete_"):])
        task = db.get_task(task_id)
        if task and task["user_id"] == user_id and task["status"] == "active":
            await close_task_in_channel(ctx, task)
            await q.edit_message_text(
                "✅ Задание закрыто. Сообщение в канале обновлено.",
                reply_markup=back_kb(),
            )
        else:
            await q.edit_message_text("⚠️ Задание не найдено или уже закрыто.", reply_markup=back_kb())
        return

    # ── Channel selection ──────────────────────────────

    if data.startswith("channel_"):
        channel_id = data[len("channel_"):]
        ctx.user_data["selected_channel"] = channel_id
        ctx.user_data["state"] = "wait_confirm"

        platform = ctx.user_data.get("platform", "—")
        price = ctx.user_data.get("price", "—")
        description = ctx.user_data.get("description", "—")
        preview = build_task_text(platform, price, description)

        await q.edit_message_text(
            f"👁 *Предпросмотр поста:*\n\n{preview}",
            parse_mode="Markdown",
            reply_markup=confirm_post_kb(),
        )
        return

    if data == "confirm_post":
        platform = ctx.user_data.get("platform", "—")
        price = ctx.user_data.get("price", "—")
        description = ctx.user_data.get("description", "—")
        channel_id = ctx.user_data.get("selected_channel")
        username = q.from_user.username

        if not username:
            await q.edit_message_text(
                "⚠️ У вас не установлен username в Telegram.\n\n"
                "Для публикации задания необходимо установить username:\n"
                "Настройки → Изменить профиль → Имя пользователя",
                reply_markup=back_kb(),
            )
            return

        text = build_task_text(platform, price, description)

        try:
            msg = await ctx.bot.send_message(
                chat_id=channel_id,
                text=text,
                reply_markup=contact_button_kb(username),
            )
        except Exception as e:
            await q.edit_message_text(
                f"❌ Ошибка публикации: {e}\n\nПроверьте, что бот является администратором канала.",
                reply_markup=back_kb(),
            )
            return

        db.create_task(user_id, platform, price, description, channel_id, msg.message_id)
        task_id = db.get_active_tasks(user_id)[0]["id"]
        ctx.user_data["last_task_id"] = task_id
        ctx.user_data["state"] = "wait_autodel"

        await q.edit_message_text(
            "✅ Задание опубликовано!\n\n⏱ Через какое время автоматически закрыть задание?",
            reply_markup=auto_delete_kb(),
        )
        return

    if data.startswith("autodel_"):
        val = data[len("autodel_"):]
        task_id = ctx.user_data.get("last_task_id")
        if task_id and val != "manual":
            minutes = int(val)
            auto_at = (datetime.utcnow() + timedelta(minutes=minutes)).strftime("%Y-%m-%d %H:%M:%S")
            conn = db.get_conn()
            conn.execute("UPDATE tasks SET auto_delete_at=? WHERE id=?", (auto_at, task_id))
            conn.commit()
            conn.close()
            await q.edit_message_text(
                f"⏰ Задание будет закрыто автоматически через {_format_minutes(minutes)}.",
                reply_markup=back_kb(),
            )
        else:
            await q.edit_message_text(
                "👌 Окей, закроете задание вручную через «Удалить задание».",
                reply_markup=back_kb(),
            )
        ctx.user_data.clear()
        return

    # ════════════════════════════════════════════════════
    #  ADMIN PANEL
    # ════════════════════════════════════════════════════

    if data == "adm_back":
        if not is_admin(user_id):
            return
        await q.edit_message_text("🛠 Панель администратора:", reply_markup=admin_menu_kb())
        return

    if data == "adm_users":
        if not is_admin(user_id):
            return
        users = db.get_all_users()
        if not users:
            await q.edit_message_text("👥 Пользователей нет.", reply_markup=InlineKeyboardMarkupBack())
            return
        await q.edit_message_text(
            "👥 Пользователи (нажмите для смены доступа):",
            reply_markup=admin_users_kb(users),
        )
        return

    if data.startswith("adm_toggle_"):
        if not is_admin(user_id):
            return
        target_id = int(data[len("adm_toggle_"):])
        users_before = db.get_all_users()
        target = next((u for u in users_before if u["user_id"] == target_id), None)
        if target:
            new_status = not target["allowed"]
            db.set_allowed(target_id, new_status)
        users = db.get_all_users()
        await q.edit_message_text(
            "👥 Пользователи (нажмите для смены доступа):",
            reply_markup=admin_users_kb(users),
        )
        return

    if data == "adm_add_user":
        if not is_admin(user_id):
            return
        ctx.user_data["state"] = "wait_add_user"
        await q.edit_message_text(
            "👤 Введите @username нового пользователя:",
            reply_markup=InlineKeyboardMarkupBack("adm_back"),
        )
        return

    if data == "adm_del_task":
        if not is_admin(user_id):
            return
        tasks = db.get_all_tasks_admin()
        active = [t for t in tasks if t["status"] == "active"]
        if not active:
            await q.edit_message_text("📭 Нет активных заданий.", reply_markup=InlineKeyboardMarkupBack("adm_back"))
            return
        await q.edit_message_text(
            "🗑 Выберите задание для закрытия:",
            reply_markup=admin_tasks_kb(active),
        )
        return

    if data.startswith("adm_close_"):
        if not is_admin(user_id):
            return
        task_id = int(data[len("adm_close_"):])
        task = db.get_task(task_id)
        if task and task["status"] == "active":
            await close_task_in_channel(ctx, task)
            await q.edit_message_text("✅ Задание закрыто.", reply_markup=InlineKeyboardMarkupBack("adm_back"))
        else:
            await q.edit_message_text("⚠️ Не найдено.", reply_markup=InlineKeyboardMarkupBack("adm_back"))
        return

    if data == "adm_add_channel":
        if not is_admin(user_id):
            return
        channels = db.get_channels()
        text = "📢 *Каналы:*\n"
        if channels:
            for ch in channels:
                text += f"• {ch['channel_name']} (`{ch['channel_id']}`)\n"
        else:
            text += "_Каналы не добавлены_\n"
        text += "\nВведите ID канала (например: `-1001234567890`):"
        ctx.user_data["state"] = "wait_add_channel_id"
        await q.edit_message_text(text, parse_mode="Markdown", reply_markup=admin_channels_kb())
        return

    if data.startswith("adm_delch_"):
        if not is_admin(user_id):
            return
        ch_id = data[len("adm_delch_"):]
        db.delete_channel(ch_id)
        await q.edit_message_text("✅ Канал удалён.", reply_markup=InlineKeyboardMarkupBack("adm_back"))
        return

    if data == "adm_edit_buttons":
        if not is_admin(user_id):
            return
        await q.edit_message_text(
            "🔤 Выберите кнопку для изменения:",
            reply_markup=admin_buttons_kb(),
        )
        return

    if data.startswith("adm_btn_"):
        if not is_admin(user_id):
            return
        btn_key = data[len("adm_btn_"):]
        current = db.get_setting(btn_key, "")
        ctx.user_data["state"] = "wait_edit_btn_value"
        ctx.user_data["edit_btn_key"] = btn_key
        await q.edit_message_text(
            f"✏️ Текущее значение: *{current}*\n\nВведите новый текст кнопки (можно с эмодзи):",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkupBack("adm_back"),
        )
        return

    if data == "adm_edit_template":
        if not is_admin(user_id):
            return
        current = db.get_setting("task_template", "")
        ctx.user_data["state"] = "wait_edit_template"
        await q.edit_message_text(
            f"📝 Текущий шаблон:\n\n`{current}`\n\n"
            "Введите новый шаблон. Используйте:\n"
            "`{platform}` — платформа\n`{price}` — цена\n`{description}` — описание",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkupBack("adm_back"),
        )
        return

    if data == "adm_edit_closed_tpl":
        if not is_admin(user_id):
            return
        current = db.get_setting("closed_template", "")
        ctx.user_data["state"] = "wait_edit_closed_tpl"
        await q.edit_message_text(
            f"🔚 Текущий шаблон закрытия:\n\n`{current}`\n\nВведите новый текст:",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkupBack("adm_back"),
        )
        return

    if data == "adm_design":
        if not is_admin(user_id):
            return
        await q.edit_message_text("🎨 Раздел дизайна:", reply_markup=admin_design_kb())
        return

    if data == "adm_design_emoji":
        if not is_admin(user_id):
            return
        await q.edit_message_text(
            "✏️ Изменение эмодзи кнопок — выберите кнопку:",
            reply_markup=admin_buttons_kb(),
        )
        return


# ════════════════════════════════════════════════════════
#  MESSAGE HANDLER (FSM)
# ════════════════════════════════════════════════════════

async def message_handler(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    text = update.message.text or ""
    state = ctx.user_data.get("state")

    # ── Admin password ─────────────────────────────────
    if state == "wait_admin_pass":
        if text == ADMIN_PASSWORD:
            ctx.user_data.clear()
            await update.message.reply_text("✅ Добро пожаловать в панель администратора!", reply_markup=admin_menu_kb())
        else:
            ctx.user_data.clear()
            await update.message.reply_text("❌ Неверный пароль.")
        return

    # ── Access check for regular users ────────────────
    if not db.is_allowed(user.id) and not is_admin(user.id):
        await update.message.reply_text("🚫 У вас нет доступа к боту.")
        return

    # ── Platform text (custom) ─────────────────────────
    if state == "wait_platform_text":
        ctx.user_data["platform"] = text
        ctx.user_data["state"] = "wait_price"
        await update.message.reply_text(
            f"✅ Платформа: *{text}*\n\n💰 Введите цену за выполнение задания:",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkupCancel(),
        )
        return

    # ── Price ──────────────────────────────────────────
    if state == "wait_price":
        ctx.user_data["price"] = text
        ctx.user_data["state"] = "wait_description"
        await update.message.reply_text(
            f"✅ Цена: *{text}*\n\n📝 Введите описание задания:",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkupCancel(),
        )
        return

    # ── Description ────────────────────────────────────
    if state == "wait_description":
        ctx.user_data["description"] = text
        ctx.user_data["state"] = "wait_channel"
        channels = db.get_channels()
        if len(channels) == 1:
            ctx.user_data["selected_channel"] = channels[0]["channel_id"]
            ctx.user_data["state"] = "wait_confirm"
            platform = ctx.user_data.get("platform", "—")
            price = ctx.user_data.get("price", "—")
            preview = build_task_text(platform, price, text)
            await update.message.reply_text(
                f"👁 *Предпросмотр поста:*\n\n{preview}",
                parse_mode="Markdown",
                reply_markup=confirm_post_kb(),
            )
        else:
            kb = channel_select_kb()
            await update.message.reply_text(
                "📢 Выберите канал для публикации:",
                reply_markup=kb,
            )
        return

    # ── Admin: add user ────────────────────────────────
    if state == "wait_add_user":
        if not is_admin(user.id):
            return
        username = text.lstrip("@")
        db.add_user_by_username(username)
        ctx.user_data.clear()
        await update.message.reply_text(
            f"✅ Пользователь @{username} добавлен и получил доступ.",
            reply_markup=admin_menu_kb(),
        )
        return

    # ── Admin: add channel id ──────────────────────────
    if state == "wait_add_channel_id":
        if not is_admin(user.id):
            return
        ctx.user_data["new_channel_id"] = text.strip()
        ctx.user_data["state"] = "wait_add_channel_name"
        await update.message.reply_text("✏️ Введите название канала (для отображения в боте):")
        return

    if state == "wait_add_channel_name":
        if not is_admin(user.id):
            return
        ch_id = ctx.user_data.get("new_channel_id")
        db.add_channel(ch_id, text.strip())
        ctx.user_data.clear()
        await update.message.reply_text(
            f"✅ Канал «{text.strip()}» (`{ch_id}`) добавлен.",
            parse_mode="Markdown",
            reply_markup=admin_menu_kb(),
        )
        return

    # ── Admin: edit button value ───────────────────────
    if state == "wait_edit_btn_value":
        if not is_admin(user.id):
            return
        key = ctx.user_data.get("edit_btn_key")
        db.set_setting(key, text)
        ctx.user_data.clear()
        await update.message.reply_text(
            f"✅ Кнопка обновлена: *{text}*",
            parse_mode="Markdown",
            reply_markup=admin_menu_kb(),
        )
        return

    # ── Admin: edit task template ──────────────────────
    if state == "wait_edit_template":
        if not is_admin(user.id):
            return
        db.set_setting("task_template", text)
        ctx.user_data.clear()
        await update.message.reply_text("✅ Шаблон задания обновлён.", reply_markup=admin_menu_kb())
        return

    # ── Admin: edit closed template ────────────────────
    if state == "wait_edit_closed_tpl":
        if not is_admin(user.id):
            return
        db.set_setting("closed_template", text)
        ctx.user_data.clear()
        await update.message.reply_text("✅ Шаблон закрытия обновлён.", reply_markup=admin_menu_kb())
        return

    # ── Fallback ───────────────────────────────────────
    await update.message.reply_text("Воспользуйтесь кнопками меню.", reply_markup=main_menu_kb())


# ════════════════════════════════════════════════════════
#  AUTO-DELETE JOB
# ════════════════════════════════════════════════════════

async def auto_delete_job(context: ContextTypes.DEFAULT_TYPE):
    tasks = db.get_tasks_to_auto_delete()
    for task in tasks:
        logger.info(f"Auto-closing task #{task['id']}")
        await close_task_in_channel(context, task)


# ════════════════════════════════════════════════════════
#  INLINE KEYBOARD HELPERS (local)
# ════════════════════════════════════════════════════════

from telegram import InlineKeyboardButton, InlineKeyboardMarkup


def InlineKeyboardMarkupCancel():
    return InlineKeyboardMarkup([[InlineKeyboardButton("❌ Отмена", callback_data="cancel")]])


def InlineKeyboardMarkupBack(cb="back_main"):
    return InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Назад", callback_data=cb)]])


# ════════════════════════════════════════════════════════
#  UTILS
# ════════════════════════════════════════════════════════

def _format_minutes(m):
    if m < 60:
        return f"{m} мин"
    h = m // 60
    return f"{h} ч" if m % 60 == 0 else f"{h} ч {m % 60} мин"


# ════════════════════════════════════════════════════════
#  MAIN
# ════════════════════════════════════════════════════════

def main():
    db.init_db()

    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("admin", admin_cmd))
    app.add_handler(CallbackQueryHandler(callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))

    # Auto-delete job every minute
    app.job_queue.run_repeating(auto_delete_job, interval=60, first=10)

    logger.info("Bot started")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
