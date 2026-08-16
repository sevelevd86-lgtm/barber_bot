import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes, MessageHandler, filters, ConversationHandler
from datetime import datetime, timedelta
import json
import os

# ---------- НАСТРОЙКИ ----------
TOKEN = "ТВОЙ_ТОКЕН_ОТ_BOTFATHER"

# ---------- СОСТОЯНИЯ ----------
CONTACT = 1

# ---------- ДАННЫЕ ----------
users = {}
bookings = {}
prebook_settings = {}  # {"дата_время": {"booked_by": user_id или None, "available": True/False}}
admins = {}  # {user_id: {"sound_on": True/False}}

DATA_FILE = "barber_data.json"

def load_data():
    global users, bookings, prebook_settings, admins
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            users = {int(k): v for k, v in data.get("users", {}).items()}
            bookings = {int(k): v for k, v in data.get("bookings", {}).items()}
            prebook_settings = data.get("prebook_settings", {})
            admins = {int(k): v for k, v in data.get("admins", {}).items()}

def save_data():
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump({
            "users": users,
            "bookings": bookings,
            "prebook_settings": prebook_settings,
            "admins": admins
        }, f, ensure_ascii=False, indent=2)

load_data()

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# ---------- КЛАВИАТУРЫ ----------
def main_menu():
    keyboard = [
        [InlineKeyboardButton("📞 Контакты", callback_data="contacts")],
        [InlineKeyboardButton("👤 Профиль", callback_data="profile")],
        [InlineKeyboardButton("📅 Предварительная запись", callback_data="prebook")],
        [InlineKeyboardButton("✏️ Изменить контакты", callback_data="edit_contacts")],
    ]
    return InlineKeyboardMarkup(keyboard)

def contact_keyboard():
    button = KeyboardButton("📱 Отправить номер телефона", request_contact=True)
    return ReplyKeyboardMarkup([[button]], resize_keyboard=True, one_time_keyboard=True)

def admin_menu():
    keyboard = [
        [InlineKeyboardButton("👥 Все пользователи", callback_data="admin_users")],
        [InlineKeyboardButton("📅 Управление записями", callback_data="admin_bookings")],
        [InlineKeyboardButton("⚙️ Настройка предзаписи", callback_data="admin_prebook_setup")],
        [InlineKeyboardButton("🔊 Вкл/Выкл звук", callback_data="admin_toggle_sound")],
        [InlineKeyboardButton("🔙 Выход из админки", callback_data="admin_exit")],
    ]
    return InlineKeyboardMarkup(keyboard)

def has_contacts(user_id):
    return user_id in users and users[user_id].get("phone") and users[user_id].get("contacts_given", False)

# ---------- ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ----------
def has_active_slots_in_month(month):
    """Проверяет, есть ли в месяце активные слоты (доступные или забронированные)"""
    for slot_key, info in prebook_settings.items():
        if info.get("available", False) or info.get("booked_by"):
            date_part = slot_key.split("_")[0]
            if "_" in date_part:
                month_from_slot = date_part.split("_")[1]
                if month_from_slot == month:
                    return True
    return False

def has_active_slots_in_day(day, month):
    """Проверяет, есть ли в конкретном дне активные слоты"""
    date_key = f"{day}_{month}"
    for slot_key, info in prebook_settings.items():
        if slot_key.startswith(date_key):
            if info.get("available", False) or info.get("booked_by"):
                return True
    return False

# ---------- ОБРАБОТЧИКИ ПОЛЬЗОВАТЕЛЯ ----------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    first_name = update.effective_user.first_name

    if user_id not in users:
        users[user_id] = {
            "name": first_name,
            "phone": None,
            "contacts_given": False,
            "first_seen": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "username": update.effective_user.username or "Не указан"
        }
        save_data()

    if has_contacts(user_id):
        await update.message.reply_text(
            f"✂️ С возвращением, {users[user_id]['name']}!",
            reply_markup=main_menu()
        )
        return

    await update.message.reply_text(
        f"👋 Привет, {first_name}!\n\n"
        "Чтобы пользоваться ботом, нажми на кнопку ниже и отправь свой номер телефона.",
        reply_markup=contact_keyboard()
    )
    return CONTACT

async def handle_contact(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    contact = update.message.contact

    if not contact:
        await update.message.reply_text(
            "Пожалуйста, используй кнопку 'Отправить номер телефона'.",
            reply_markup=contact_keyboard()
        )
        return CONTACT

    users[user_id]["phone"] = contact.phone_number
    users[user_id]["contacts_given"] = True
    if not users[user_id].get("name"):
        users[user_id]["name"] = contact.first_name or "Гость"
    save_data()

    await update.message.reply_text(
        f"✅ Отлично, {users[user_id]['name']}! Твой номер сохранён.\n\n"
        "Теперь ты можешь пользоваться ботом:",
        reply_markup=main_menu()
    )
    return ConversationHandler.END

# ---------- ОБРАБОТЧИК ТЕКСТА ----------
async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    user_id = update.effective_user.id
    
    if text == "Стасбар":
        if user_id not in admins:
            admins[user_id] = {"sound_on": True}
            save_data()
        sound_status = "🟢 Вкл" if admins[user_id]["sound_on"] else "🔴 Выкл"
        await update.message.reply_text(
            f"🔐 Админ-панель\n\n"
            f"🔊 Звук: {sound_status}\n"
            f"(уведомления о новых записях {'приходят' if admins[user_id]['sound_on'] else 'НЕ приходят'})",
            reply_markup=admin_menu()
        )

# ---------- ОБРАБОТЧИК КНОПОК ----------
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    user_id = update.effective_user.id

    if data.startswith("admin_"):
        await admin_handler(update, context)
        return

    if data != "edit_contacts" and not has_contacts(user_id):
        await query.edit_message_text(
            "Сначала укажи свои контакты, нажав кнопку ниже.",
            reply_markup=contact_keyboard()
        )
        return

    if data == "contacts":
        text = (
            "📞 **Связь с нами:**\n\n"
            "📍 Ленинградский просп. 38А, корп. 1\n"
            "✂️ Chop X Chop\n"
            "✂️ Telegram: @DMITROVSTAS\n"
            "🕐 Работаем: ежедневно с 10:00 до 22:00"
        )
        await query.edit_message_text(text, reply_markup=main_menu(), parse_mode="Markdown")

    elif data == "profile":
        user_info = users.get(user_id, {})
        phone = user_info.get("phone", "Не указан")
        name = user_info.get("name", "Гость")

        user_bookings = bookings.get(user_id, [])
        if user_bookings:
            bookings_text = "\n".join([f"• {b['date']} в {b['time']} — {b['service']}" for b in user_bookings])
        else:
            bookings_text = "Нет активных записей"

        text = (
            f"👤 **Твой профиль**\n\n"
            f"Имя: {name}\n"
            f"📱 Телефон: {phone}\n\n"
            f"📋 **Твои записи:**\n{bookings_text}"
        )
        await query.edit_message_text(text, reply_markup=main_menu(), parse_mode="Markdown")

    elif data == "prebook":
        months_with_slots = set()
        for slot_key, info in prebook_settings.items():
            if info.get("available", False) and not info.get("booked_by"):
                date_part = slot_key.split("_")[0]
                if "_" in date_part:
                    month = date_part.split("_")[1]
                    months_with_slots.add(month)

        if not months_with_slots:
            text = "📅 **Предварительная запись**\n\n"
            text += "На данный момент нет доступных слотов для записи.\n"
            text += "Загляни позже!"
            await query.edit_message_text(text, reply_markup=main_menu(), parse_mode="Markdown")
            return

        keyboard = []
        for month in sorted(months_with_slots):
            keyboard.append([InlineKeyboardButton(month, callback_data=f"user_month_{month}")])
        keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data="back")])
        await query.edit_message_text(
            "📅 **Выбери месяц:**\n\n"
            "Доступны следующие месяцы для предзаписи:",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )

    elif data.startswith("user_month_"):
        month = data.replace("user_month_", "")
        context.user_data["user_month"] = month

        days_with_slots = set()
        for slot_key, info in prebook_settings.items():
            if info.get("available", False) and not info.get("booked_by"):
                date_part = slot_key.split("_")[0]
                if "_" in date_part:
                    day, month_from_slot = date_part.split("_")
                    if month_from_slot == month:
                        days_with_slots.add(day)

        if not days_with_slots:
            await query.edit_message_text("❌ В этом месяце нет свободных слотов.", reply_markup=main_menu())
            return

        keyboard = []
        for day in sorted(days_with_slots, key=int):
            keyboard.append([InlineKeyboardButton(f"{day} {month}", callback_data=f"user_day_{month}_{day}")])
        keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data="prebook")])
        await query.edit_message_text(
            f"📅 **Выбери день в {month}:**",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )

    elif data.startswith("user_day_"):
        parts = data.replace("user_day_", "").split("_")
        month = parts[0]
        day = parts[1]
        date_key = f"{day}_{month}"

        available_hours = []
        for slot_key, info in prebook_settings.items():
            if info.get("available", False) and not info.get("booked_by"):
                if slot_key.startswith(date_key):
                    time_part = slot_key.split("_")[2]
                    available_hours.append(time_part)

        if not available_hours:
            await query.edit_message_text("❌ В этот день нет свободных слотов.", reply_markup=main_menu())
            return

        keyboard = []
        for hour in sorted(available_hours):
            keyboard.append([InlineKeyboardButton(hour, callback_data=f"user_book_{date_key}_{hour}")])
        keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data=f"user_month_{month}")])
        await query.edit_message_text(
            f"📅 {day} {month}\n\n"
            "Выбери удобное время:",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )

    elif data.startswith("user_book_"):
        parts = data.replace("user_book_", "").split("_")
        date_key = parts[0] + "_" + parts[1]
        time_slot = parts[2] + ":" + parts[3]
        slot_key = f"{date_key}_{time_slot}"

        if slot_key not in prebook_settings or not prebook_settings[slot_key].get("available", False) or prebook_settings[slot_key].get("booked_by"):
            await query.edit_message_text("❌ Этот слот уже занят. Выбери другой.", reply_markup=main_menu())
            return

        prebook_settings[slot_key]["booked_by"] = user_id
        save_data()

        if user_id not in bookings:
            bookings[user_id] = []
        bookings[user_id].append({
            "service": "Предзапись",
            "time": time_slot,
            "date": f"{date_key.replace('_', ' ')}",
            "slot_key": slot_key
        })
        save_data()

        user_info = users.get(user_id, {})
        for admin_id, admin_info in admins.items():
            if admin_info.get("sound_on", True):
                try:
                    await context.bot.send_message(
                        chat_id=admin_id,
                        text=f"📢 **НОВАЯ ПРЕДЗАПИСЬ!**\n\n"
                             f"👤 {user_info.get('name', 'Неизвестный')}\n"
                             f"📱 Телефон: {user_info.get('phone', 'Не указан')}\n"
                             f"✂️ Telegram: @{user_info.get('username', 'Не указан')}\n"
                             f"📅 {date_key.replace('_', ' ')}\n"
                             f"🕐 {time_slot}\n\n"
                             f"✅ Предзапись активирована!",
                        parse_mode="Markdown"
                    )
                except:
                    pass

        await query.edit_message_text(
            "✅ **Вы записаны на предзапись!**\n\n"
            "Вам напишут в Telegram!\n"
            "Если есть вопросы, напишите сами!\n"
            "Все данные для связи есть по кнопке «Контакты».",
            reply_markup=main_menu(),
            parse_mode="Markdown"
        )

    elif data == "edit_contacts":
        if user_id in users:
            users[user_id]["contacts_given"] = False
            users[user_id]["phone"] = None
            save_data()
        await query.edit_message_text(
            "✏️ Обновим твои контакты. Нажми кнопку ниже:",
            reply_markup=contact_keyboard()
        )
        return CONTACT

    elif data == "back":
        await query.edit_message_text("Главное меню:", reply_markup=main_menu())

# ---------- АДМИН-ХЕНДЛЕР ----------
async def admin_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data
    user_id = update.effective_user.id

    if data == "admin_toggle_sound":
        if user_id in admins:
            admins[user_id]["sound_on"] = not admins[user_id]["sound_on"]
            save_data()
            sound_status = "🟢 Вкл" if admins[user_id]["sound_on"] else "🔴 Выкл"
            await query.edit_message_text(
                f"🔊 Звук: {sound_status}\n"
                f"(уведомления о новых записях {'приходят' if admins[user_id]['sound_on'] else 'НЕ приходят'})",
                reply_markup=admin_menu()
            )
        else:
            admins[user_id] = {"sound_on": True}
            save_data()
            await query.edit_message_text(
                "🔊 Звук: 🟢 Вкл\n(уведомления о новых записях приходят)",
                reply_markup=admin_menu()
            )
        return

    if data == "admin_users":
        text = "👥 **Список пользователей:**\n\n"
        with_contacts = []
        without_contacts = []

        for uid, info in users.items():
            name = info.get("name", "Без имени")
            phone = info.get("phone", "Не указан")
            if info.get("contacts_given", False):
                with_contacts.append(f"• {name} — {phone}")
            else:
                without_contacts.append(f"• {name} (ID: {uid})")

        text += "**✅ С контактами:**\n" + ("\n".join(with_contacts) if with_contacts else "Нет") + "\n\n"
        text += "**❌ Без контактов:**\n" + ("\n".join(without_contacts) if without_contacts else "Нет")

        await query.edit_message_text(text, reply_markup=admin_menu(), parse_mode="Markdown")

    elif data == "admin_bookings":
        # Показываем все активные записи (и предзаписи, и доступные слоты)
        bookings_list = []
        for slot_key, info in prebook_settings.items():
            if info.get("booked_by"):
                # Предзапись
                uid = info["booked_by"]
                user_info = users.get(uid, {})
                name = user_info.get("name", "Неизвестный")
                date, time = slot_key.split("_")
                date_display = date.replace("_", " ")
                bookings_list.append({
                    "type": "✍️",
                    "display": f"✍️ {date_display} {time} — {name}",
                    "slot_key": slot_key,
                    "callback": f"admin_userinfo_{slot_key}"
                })
            elif info.get("available", False):
                # Доступный слот
                date, time = slot_key.split("_")
                date_display = date.replace("_", " ")
                bookings_list.append({
                    "type": "❌",
                    "display": f"❌ {date_display} {time} — доступен",
                    "slot_key": slot_key,
                    "callback": f"admin_toggle_off_{slot_key}"
                })

        if not bookings_list:
            await query.edit_message_text("📅 Активных записей пока нет.", reply_markup=admin_menu())
            return

        text = "📅 **Активные записи и слоты:**\n\n"
        keyboard = []
        for item in bookings_list:
            text += f"• {item['display']}\n"
            keyboard.append([InlineKeyboardButton(
                item['display'],
                callback_data=item['callback']
            )])

        keyboard.append([InlineKeyboardButton("🔙 Назад в админку", callback_data="admin_back")])
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

    elif data.startswith("admin_userinfo_"):
        slot_key = data.replace("admin_userinfo_", "")
        if slot_key in prebook_settings and prebook_settings[slot_key].get("booked_by"):
            uid = prebook_settings[slot_key]["booked_by"]
            user_info = users.get(uid, {})
            date, time = slot_key.split("_")
            date_display = date.replace("_", " ")
            text = (
                f"📋 **Информация о предзаписи:**\n\n"
                f"📅 {date_display}\n"
                f"🕐 {time}\n\n"
                f"👤 {user_info.get('name', 'Неизвестный')}\n"
                f"📱 Телефон: {user_info.get('phone', 'Не указан')}\n"
                f"✂️ Telegram: @{user_info.get('username', 'Не указан')}"
            )
            keyboard = [
                [InlineKeyboardButton("🔙 Назад", callback_data="admin_bookings")],
                [InlineKeyboardButton("🗑️ Отменить предзапись", callback_data=f"admin_cancel_prebook_{slot_key}")]
            ]
            await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
        else:
            await query.edit_message_text("❌ Информация не найдена.", reply_markup=admin_menu())

    elif data.startswith("admin_cancel_prebook_"):
        slot_key = data.replace("admin_cancel_prebook_", "")
        if slot_key in prebook_settings and prebook_settings[slot_key].get("booked_by"):
            uid = prebook_settings[slot_key]["booked_by"]
            if uid in bookings:
                bookings[uid] = [b for b in bookings[uid] if b.get("slot_key") != slot_key]
            prebook_settings[slot_key]["booked_by"] = None
            prebook_settings[slot_key]["available"] = False
            save_data()
            await query.edit_message_text(f"✅ Предзапись {slot_key} отменена!", reply_markup=admin_menu())
        else:
            await query.edit_message_text("❌ Предзапись не найдена.", reply_markup=admin_menu())

    elif data == "admin_prebook_setup":
        keyboard = []
        months = ["Январь", "Февраль", "Март", "Апрель", "Май", "Июнь", 
                  "Июль", "Август", "Сентябрь", "Октябрь", "Ноябрь", "Декабрь"]
        for month in months:
            if has_active_slots_in_month(month):
                keyboard.append([InlineKeyboardButton(f"📌 {month}", callback_data=f"admin_month_{month}")])
            else:
                keyboard.append([InlineKeyboardButton(month, callback_data=f"admin_month_{month}")])
        keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data="admin_back")])
        await query.edit_message_text(
            "📅 **Выбери месяц для настройки:**\n\n"
            "📌 — в этом месяце есть активные слоты",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )

    elif data.startswith("admin_month_"):
        month = data.replace("admin_month_", "")
        context.user_data["admin_month"] = month
        days = 31
        if month in ["Апрель", "Июнь", "Сентябрь", "Ноябрь"]:
            days = 30
        elif month == "Февраль":
            days = 28

        keyboard = []
        for day in range(1, days + 1):
            if has_active_slots_in_day(str(day), month):
                keyboard.append([InlineKeyboardButton(f"📌 {day}", callback_data=f"admin_day_{month}_{day}")])
            else:
                keyboard.append([InlineKeyboardButton(f"{day}", callback_data=f"admin_day_{month}_{day}")])
        keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data="admin_prebook_setup")])
        await query.edit_message_text(
            f"📅 **Выбери день в {month}:**\n\n"
            "📌 — в этот день есть активные слоты\n"
            "Ты можешь выбрать несколько часов для этого дня.",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )

    elif data.startswith("admin_day_"):
        parts = data.split("_")
        month = parts[2]
        day = parts[3]
        date_key = f"{day}_{month}"
        context.user_data["admin_date"] = date_key

        keyboard = []
        for hour in range(10, 23):
            time_slot = f"{hour:02d}:00"
            slot_key = f"{date_key}_{time_slot}"
            
            if slot_key in prebook_settings:
                if prebook_settings[slot_key].get("booked_by"):
                    uid = prebook_settings[slot_key]["booked_by"]
                    user_info = users.get(uid, {})
                    name = user_info.get("name", "Неизвестный")
                    keyboard.append([InlineKeyboardButton(
                        f"{time_slot} ✍️ {name}", 
                        callback_data=f"admin_userinfo_{slot_key}"
                    )])
                elif prebook_settings[slot_key].get("available", False):
                    keyboard.append([InlineKeyboardButton(
                        f"{time_slot} ❌", 
                        callback_data=f"admin_toggle_off_{slot_key}"
                    )])
                else:
                    keyboard.append([InlineKeyboardButton(
                        f"{time_slot} ⬜", 
                        callback_data=f"admin_toggle_on_{slot_key}"
                    )])
            else:
                keyboard.append([InlineKeyboardButton(
                    f"{time_slot} ➕", 
                    callback_data=f"admin_create_{slot_key}"
                )])
        
        # Кнопка "Назад" — возвращаемся к дням этого же месяца
        keyboard.append([InlineKeyboardButton("🔙 Назад к дням", callback_data=f"admin_month_{month}")])
        await query.edit_message_text(
            f"📅 **{day} {month}**\n\n"
            "🔘 ➕ — создать слот\n"
            "🔘 ⬜ — скрыт (не виден пользователям)\n"
            "🔘 ❌ — доступен для пользователей\n"
            "🔘 ✍️ — занят пользователем (нажми для инфо)\n\n"
            "Нажимай на время, чтобы менять статус:",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )

    elif data.startswith("admin_create_"):
        slot_key = data.replace("admin_create_", "")
        prebook_settings[slot_key] = {"available": True, "booked_by": None}
        save_data()
        # Остаёмся на этом же дне, просто обновляем клавиатуру
        # Парсим дату из slot_key
        date_part = slot_key.split("_")[0]
        day, month = date_part.split("_")
        # Пересоздаём экран с этим же днём
        context.user_data["admin_month"] = month
        await update.callback_query.edit_message_text(
            f"✅ Слот {slot_key} создан и доступен для пользователей!",
            reply_markup=admin_menu()
        )
        # Отправляем обратно на настройку дня
        keyboard = []
        for hour in range(10, 23):
            time_slot = f"{hour:02d}:00"
            new_slot_key = f"{date_part}_{time_slot}"
            if new_slot_key in prebook_settings:
                if prebook_settings[new_slot_key].get("booked_by"):
                    uid = prebook_settings[new_slot_key]["booked_by"]
                    user_info = users.get(uid, {})
                    name = user_info.get("name", "Неизвестный")
                    keyboard.append([InlineKeyboardButton(
                        f"{time_slot} ✍️ {name}", 
                        callback_data=f"admin_userinfo_{new_slot_key}"
                    )])
                elif prebook_settings[new_slot_key].get("available", False):
                    keyboard.append([InlineKeyboardButton(
                        f"{time_slot} ❌", 
                        callback_data=f"admin_toggle_off_{new_slot_key}"
                    )])
                else:
                    keyboard.append([InlineKeyboardButton(
                        f"{time_slot} ⬜", 
                        callback_data=f"admin_toggle_on_{new_slot_key}"
                    )])
            else:
                keyboard.append([InlineKeyboardButton(
                    f"{time_slot} ➕", 
                    callback_data=f"admin_create_{new_slot_key}"
                )])
        keyboard.append([InlineKeyboardButton("🔙 Назад к дням", callback_data=f"admin_month_{month}")])
        await context.bot.edit_message_text(
            chat_id=update.effective_chat.id,
            message_id=update.callback_query.message.message_id,
            text=f"📅 **{day} {month}**\n\n"
                 "🔘 ➕ — создать слот\n"
                 "🔘 ⬜ — скрыт (не виден пользователям)\n"
                 "🔘 ❌ — доступен для пользователей\n"
                 "🔘 ✍️ — занят пользователем (нажми для инфо)\n\n"
                 "Нажимай на время, чтобы менять статус:",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )

    elif data.startswith("admin_toggle_on_"):
        slot_key = data.replace("admin_toggle_on_", "")
        if slot_key in prebook_settings:
            prebook_settings[slot_key]["available"] = True
            save_data()
            # Обновляем текущий экран без выхода
            date_part = slot_key.split("_")[0]
            day, month = date_part.split("_")
            keyboard = []
            for hour in range(10, 23):
                time_slot = f"{hour:02d}:00"
                new_slot_key = f"{date_part}_{time_slot}"
                if new_slot_key in prebook_settings:
                    if prebook_settings[new_slot_key].get("booked_by"):
                        uid = prebook_settings[new_slot_key]["booked_by"]
                        user_info = users.get(uid, {})
                        name = user_info.get("name", "Неизвестный")
                        keyboard.append([InlineKeyboardButton(
                            f"{time_slot} ✍️ {name}", 
                            callback_data=f"admin_userinfo_{new_slot_key}"
                        )])
                    elif prebook_settings[new_slot_key].get("available", False):
                        keyboard.append([InlineKeyboardButton(
                            f"{time_slot} ❌", 
                            callback_data=f"admin_toggle_off_{new_slot_key}"
                        )])
                    else:
                        keyboard.append([InlineKeyboardButton(
                            f"{time_slot} ⬜", 
                            callback_data=f"admin_toggle_on_{new_slot_key}"
                        )])
                else:
                    keyboard.append([InlineKeyboardButton(
                        f"{time_slot} ➕", 
                        callback_data=f"admin_create_{new_slot_key}"
                    )])
            keyboard.append([InlineKeyboardButton("🔙 Назад к дням", callback_data=f"admin_month_{month}")])
            await context.bot.edit_message_text(
                chat_id=update.effective_chat.id,
                message_id=update.callback_query.message.message_id,
                text=f"📅 **{day} {month}**\n\n"
                     "🔘 ➕ — создать слот\n"
                     "🔘 ⬜ — скрыт (не виден пользователям)\n"
                     "🔘 ❌ — доступен для пользователей\n"
                     "🔘 ✍️ — занят пользователем (нажми для инфо)\n\n"
                     "Нажимай на время, чтобы менять статус:",
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode="Markdown"
            )
        else:
            await query.edit_message_text("❌ Слот не найден.", reply_markup=admin_menu())

    elif data.startswith("admin_toggle_off_"):
        slot_key = data.replace("admin_toggle_off_", "")
        if slot_key in prebook_settings:
            prebook_settings[slot_key]["available"] = False
            save_data()
            # Обновляем текущий экран без выхода
            date_part = slot_key.split("_")[0]
            day, month = date_part.split("_")
            keyboard = []
            for hour in range(10, 23):
                time_slot = f"{hour:02d}:00"
                new_slot_key = f"{date_part}_{time_slot}"
                if new_slot_key in prebook_settings:
                    if prebook_settings[new_slot_key].get("booked_by"):
                        uid = prebook_settings[new_slot_key]["booked_by"]
                        user_info = users.get(uid, {})
                        name = user_info.get("name", "Неизвестный")
                        keyboard.append([InlineKeyboardButton(
                            f"{time_slot} ✍️ {name}", 
                            callback_data=f"admin_userinfo_{new_slot_key}"
                        )])
                    elif prebook_settings[new_slot_key].get("available", False):
                        keyboard.append([InlineKeyboardButton(
                            f"{time_slot} ❌", 
                            callback_data=f"admin_toggle_off_{new_slot_key}"
                        )])
                    else:
                        keyboard.append([InlineKeyboardButton(
                            f"{time_slot} ⬜", 
                            callback_data=f"admin_toggle_on_{new_slot_key}"
                        )])
                else:
                    keyboard.append([InlineKeyboardButton(
                        f"{time_slot} ➕", 
                        callback_data=f"admin_create_{new_slot_key}"
                    )])
            keyboard.append([InlineKeyboardButton("🔙 Назад к дням", callback_data=f"admin_month_{month}")])
            await context.bot.edit_message_text(
                chat_id=update.effective_chat.id,
                message_id=update.callback_query.message.message_id,
                text=f"📅 **{day} {month}**\n\n"
                     "🔘 ➕ — создать слот\n"
                     "🔘 ⬜ — скрыт (не виден пользователям)\n"
                     "🔘 ❌ — доступен для пользователей\n"
                     "🔘 ✍️ — занят пользователем (нажми для инфо)\n\n"
                     "Нажимай на время, чтобы менять статус:",
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode="Markdown"
            )
        else:
            await query.edit_message_text("❌ Слот не найден.", reply_markup=admin_menu())

    elif data == "admin_back":
        await query.edit_message_text("Админ-панель:", reply_markup=admin_menu())

    elif data == "admin_exit":
        await query.edit_message_text("Вы вышли из админ-панели.", reply_markup=main_menu())

# ---------- ЗАПУСК ----------
def main():
    app = Application.builder().token(TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            CONTACT: [MessageHandler(filters.CONTACT, handle_contact)],
        },
        fallbacks=[],
    )

    app.add_handler(conv_handler)
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    logger.info("Бот запущен...")
    app.run_polling()

if __name__ == "__main__":
    main()