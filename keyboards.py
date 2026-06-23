from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from database import get_setting, get_channels, get_active_tasks


# ── Main menu ──────────────────────────────────────────

def main_menu_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(get_setting("btn_post", "📝 Выложить задание"), callback_data="post_task")],
        [InlineKeyboardButton(get_setting("btn_stats", "📊 Статистика"), callback_data="stats")],
        [InlineKeyboardButton(get_setting("btn_delete", "🗑 Удалить задание"), callback_data="delete_task_menu")],
    ])


# ── Platform selection ─────────────────────────────────

def platform_kb():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(get_setting("btn_yandex", "🗺 Яндекс Карты"), callback_data="platform_Яндекс Карты"),
            InlineKeyboardButton(get_setting("btn_2gis", "🗺 2ГИС"), callback_data="platform_2ГИС"),
        ],
        [
            InlineKeyboardButton(get_setting("btn_google", "🗺 Гугл Карты"), callback_data="platform_Гугл Карты"),
            InlineKeyboardButton(get_setting("btn_avito", "🛍 Авито"), callback_data="platform_Авито"),
        ],
        [InlineKeyboardButton(get_setting("btn_other", "✏️ Другое"), callback_data="platform_other")],
        [InlineKeyboardButton("❌ Отмена", callback_data="cancel")],
    ])


# ── Confirm post ───────────────────────────────────────

def confirm_post_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Выложить задание", callback_data="confirm_post")],
        [InlineKeyboardButton("❌ Отменить", callback_data="cancel")],
    ])


# ── Auto-delete interval ───────────────────────────────

def auto_delete_kb():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("30 мин", callback_data="autodel_30"),
            InlineKeyboardButton("1 час", callback_data="autodel_60"),
            InlineKeyboardButton("2 часа", callback_data="autodel_120"),
        ],
        [
            InlineKeyboardButton("6 часов", callback_data="autodel_360"),
            InlineKeyboardButton("12 часов", callback_data="autodel_720"),
            InlineKeyboardButton("24 часа", callback_data="autodel_1440"),
        ],
        [InlineKeyboardButton("🙋 Удалю сам", callback_data="autodel_manual")],
    ])


# ── Delete task list ───────────────────────────────────

def delete_tasks_kb(user_id):
    tasks = get_active_tasks(user_id)
    if not tasks:
        return None
    buttons = []
    for t in tasks:
        label = f"#{t['id']} | {t['platform']} | {t['price']}"
        buttons.append([InlineKeyboardButton(label, callback_data=f"do_delete_{t['id']}")])
    buttons.append([InlineKeyboardButton("🔙 Назад", callback_data="back_main")])
    return InlineKeyboardMarkup(buttons)


# ── Channel selection ──────────────────────────────────

def channel_select_kb():
    channels = get_channels()
    if not channels:
        return None
    buttons = []
    for ch in channels:
        buttons.append([InlineKeyboardButton(ch["channel_name"], callback_data=f"channel_{ch['channel_id']}")])
    buttons.append([InlineKeyboardButton("❌ Отмена", callback_data="cancel")])
    return InlineKeyboardMarkup(buttons)


# ── Back button ────────────────────────────────────────

def back_kb():
    return InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Назад", callback_data="back_main")]])


# ── Admin menu ─────────────────────────────────────────

def admin_menu_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("👥 Пользователи", callback_data="adm_users")],
        [InlineKeyboardButton("➕ Новый пользователь", callback_data="adm_add_user")],
        [InlineKeyboardButton("🗑 Удалить задание", callback_data="adm_del_task")],
        [InlineKeyboardButton("📢 Добавить канал", callback_data="adm_add_channel")],
        [InlineKeyboardButton("🔤 Изменить кнопки", callback_data="adm_edit_buttons")],
        [InlineKeyboardButton("📝 Изменить шаблон поста", callback_data="adm_edit_template")],
        [InlineKeyboardButton("🎨 Изменить дизайн", callback_data="adm_design")],
    ])


# ── Admin: users list ──────────────────────────────────

def admin_users_kb(users):
    buttons = []
    for u in users:
        status = "✅" if u["allowed"] else "🚫"
        name = u["username"] or u["first_name"] or str(u["user_id"])
        buttons.append([
            InlineKeyboardButton(
                f"{status} @{name}",
                callback_data=f"adm_toggle_{u['user_id']}",
            )
        ])
    buttons.append([InlineKeyboardButton("🔙 Назад", callback_data="adm_back")])
    return InlineKeyboardMarkup(buttons)


# ── Admin: tasks list ──────────────────────────────────

def admin_tasks_kb(tasks):
    buttons = []
    for t in tasks:
        label = f"#{t['id']} @{t.get('username','?')} | {t['platform']}"
        buttons.append([InlineKeyboardButton(label, callback_data=f"adm_close_{t['id']}")])
    buttons.append([InlineKeyboardButton("🔙 Назад", callback_data="adm_back")])
    return InlineKeyboardMarkup(buttons)


# ── Admin: edit buttons list ───────────────────────────

def admin_buttons_kb():
    btn_keys = [
        ("btn_post", "Главная: Выложить задание"),
        ("btn_stats", "Главная: Статистика"),
        ("btn_delete", "Главная: Удалить задание"),
        ("btn_yandex", "Платформа: Яндекс Карты"),
        ("btn_2gis", "Платформа: 2ГИС"),
        ("btn_google", "Платформа: Гугл Карты"),
        ("btn_avito", "Платформа: Авито"),
        ("btn_other", "Платформа: Другое"),
    ]
    buttons = [[InlineKeyboardButton(label, callback_data=f"adm_btn_{key}")] for key, label in btn_keys]
    buttons.append([InlineKeyboardButton("🔙 Назад", callback_data="adm_back")])
    return InlineKeyboardMarkup(buttons)


# ── Admin: design menu ─────────────────────────────────

def admin_design_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✏️ Изменить эмодзи кнопок", callback_data="adm_design_emoji")],
        [InlineKeyboardButton("📋 Изменить шаблон задания", callback_data="adm_edit_template")],
        [InlineKeyboardButton("🔚 Изменить шаблон закрытия", callback_data="adm_edit_closed_tpl")],
        [InlineKeyboardButton("🔙 Назад", callback_data="adm_back")],
    ])


# ── Admin: channels list ───────────────────────────────

def admin_channels_kb():
    channels = get_channels()
    buttons = []
    for ch in channels:
        buttons.append([
            InlineKeyboardButton(f"🗑 {ch['channel_name']}", callback_data=f"adm_delch_{ch['channel_id']}")
        ])
    buttons.append([InlineKeyboardButton("🔙 Назад", callback_data="adm_back")])
    return InlineKeyboardMarkup(buttons)
