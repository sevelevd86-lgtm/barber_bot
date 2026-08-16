import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes, MessageHandler, filters, ConversationHandler
from datetime import datetime, timedelta
import json
import os

# ---------- НАСТРОЙКИ ----------
TOKEN = "8944409425:AAGC659vkO9fJPzBAoHOTBVP-ClS4t0UclY"

# ---------- СОСТОЯНИЯ ----------
CONTACT = 1

# ---------- ДАННЫЕ ----------
users = {}
bookings = {}
prebook_settings = {}
admins = {}

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
    else:
        users = {}
        bookings = {}
        prebook_settings = {}
        admins = {}

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
        [InlineKeyboardButton("📅 Активные записи", callback_data="admin_bookings")],
        [InlineKeyboardButton("⚙️ Настройка предзаписи", callback_data="admin_prebook_setup")],
        [InlineKeyboardButton("🔊 Вкл/Выкл звук", callback_data="admin_toggle_sound")],
        [InlineKeyboardButton("🔙 Выход из админки", callback_data="admin_exit")],
    ]
    return InlineKeyboardMarkup(keyboard)

def has_contacts(user_id):
    return user_id in users and users[user_id].get("contacts_given", False)

# ---------- ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ----------
def get_booked_slots():
    """Возвращает все забронированные слоты {месяц: {день: [{time, slot_key, booked_by}]}}"""
    result = {}
    for slot_key, info in prebook_settings.items():
        if info.get("booked_by"):
            # Формат slot_key: "15_Сентябрь_20:00"
            parts = slot_key.split("_")
            if len(parts) >= 3:
                day = parts[0]
                month = parts[1]
                time = parts[2]  # уже с :00
                if month not in result:
                    result[month] = {}
                if day not in result[month]:
                    result[month][day] = []
                result[month][day].append({
                    "time": time,
                    "slot_key": slot_key,
                    "booked_by": info["booked_by"]
                })
    return result

def has_active_slots_in_month(month):
    for slot_key, info in prebook_settings.items():
        if info.get("available", False) or info.get("booked_by"):
            parts = slot_key.split("_")
            if len(parts) >= 2:
                month_from_slot = parts[1]
                if month_from_slot == month:
                    return True
    return False

def has_active_slots_in_day(day, month):
    date_key = f"{day}_{month}"
    for slot_key, info in prebook_settings.items():
        if slot_key.startswith(date_key):
            if info.get("available", False) or info.get("booked_by"):
                return True
    return False

def get_available_slots_for_user():
    available = {}
    for slot_key, info in prebook_settings.items():
        if info.get("available", False) and not info.get("booked_by"):
            parts = slot_key.split("_")
            if len(parts) >= 3:
                day = parts[0]
                month = parts[1]
                time = parts[2]
                date_key = f"{day}_{month}"
                if date_key not in available:
                    available[date_key] = []
                available[date_key].append({
                    "time": time,
                    "slot_key": slot_key
                })
    return available

def format_month_buttons(months, callback_prefix):
    keyboard = []
    row = []
    for month in months:
        row.append(InlineKeyboardButton(month, callback_data=f"{callback_prefix}_{month}"))
        if len(row) == 2:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)
    return keyboard

def format_day_buttons(days, month, callback_prefix):
    keyboard = []
    row = []
    for day in days:
        row.append(InlineKeyboardButton(day, callback_data=f"{callback_prefix}_{month}_{day}"))
        if len(row) == 5:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)
    return keyboard

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
            bookings_text = ""
            for i, b in enumerate(user_bookings, 1):
                bookings_text += f"{i}. {b['date']} в {b['time']} — {b['service']}\n"
            keyboard = []
            for i, b in enumerate(user_bookings):
                keyboard.append([InlineKeyboardButton(
                    f"❌ Отменить запись #{i+1} ({b['date']} {b['time']})",
                    callback_data=f"cancel_booking_{i}"
                )])
            keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data="back")])
            text = (
                f"👤 **Твой профиль**\n\n"
                f"Имя: {name}\n"
                f"📱 Телефон: {phone}\n\n"
                f"📋 **Твои записи:**\n{bookings_text}"
            )
            await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
        else:
            text = (
                f"👤 **Твой профиль**\n\n"
                f"Имя: {name}\n"
                f"📱 Телефон: {phone}\n\n"
                f"📋 **Твои записи:**\nНет активных записей"
            )
            await query.edit_message_text(text, reply_markup=main_menu(), parse_mode="Markdown")

    elif data.startswith("cancel_booking_"):
        try:
            index = int(data.replace("cancel_booking_", ""))
            user_bookings = bookings.get(user_id, [])
            if index < len(user_bookings):
                booking_to_cancel = user_bookings[index]
                slot_key = booking_to_cancel.get("slot_key")
                
                del bookings[user_id][index]
                if not bookings[user_id]:
                    del bookings[user_id]
                
                if slot_key and slot_key in prebook_settings:
                    prebook_settings[slot_key]["booked_by"] = None
                    prebook_settings[slot_key]["available"] = False
                
                save_data()
                
                for admin_id, admin_info in admins.items():
                    if admin_info.get("sound_on", True):
                        try:
                            await context.bot.send_message(
                                chat_id=admin_id,
                                text=f"🗑️ **Пользователь отменил запись!**\n\n"
                                     f"👤 {users[user_id]['name']}\n"
                                     f"📅 {booking_to_cancel.get('date', '')}\n"
                                     f"🕐 {booking_to_cancel.get('time', '')}",
                                parse_mode="Markdown"
                            )
                        except:
                            pass
                
                await query.edit_message_text(
                    "✅ Запись успешно отменена!",
                    reply_markup=main_menu()
                )
            else:
                await query.edit_message_text("❌ Запись не найдена.", reply_markup=main_menu())
        except Exception as e:
            await query.edit_message_text(f"❌ Ошибка при отмене: {e}", reply_markup=main_menu())

    elif data == "prebook":
        available = get_available_slots_for_user()
        
        months_with_slots = set()
        for date_key in available:
            parts = date_key.split("_")
            if len(parts) >= 2:
                months_with_slots.add(parts[1])

        if not months_with_slots:
            text = "📅 **Предварительная запись**\n\n"
            text += "На данный момент нет доступных слотов для записи.\n"
            text += "Загляни позже!"
            await query.edit_message_text(text, reply_markup=main_menu(), parse_mode="Markdown")
            return

        keyboard = format_month_buttons(sorted(months_with_slots), "user_month")
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

        available = get_available_slots_for_user()
        days_with_slots = set()
        for date_key in available:
            parts = date_key.split("_")
            if len(parts) >= 2 and parts[1] == month:
                days_with_slots.add(parts[0])

        if not days_with_slots:
            await query.edit_message_text("❌ В этом месяце нет свободных слотов.", reply_markup=main_menu())
            return

        keyboard = format_day_buttons(sorted(days_with_slots, key=int), month, "user_day")
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

        available = get_available_slots_for_user()
        available_hours = []
        if date_key in available:
            for slot in available[date_key]:
                available_hours.append(slot["time"])

        if not available_hours:
            await query.edit_message_text("❌ В этот день нет свободных слотов.", reply_markup=main_menu())
            return

        keyboard = []
        row = []
        for hour in sorted(available_hours):
            row.append(InlineKeyboardButton(hour, callback_data=f"user_book_{date_key}_{hour}"))
            if len(row) == 3:
                keyboard.append(row)
                row = []
        if row:
            keyboard.append(row)
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
        time_slot = parts[2]
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
        return

    # ---------- РАЗДЕЛ: АКТИВНЫЕ ЗАПИСИ ----------
    if data == "admin_bookings":
        booked_slots = get_booked_slots()
        if not booked_slots:
            await query.edit_message_text("📅 Активных записей пока нет.", reply_markup=admin_menu())
            return

        keyboard = []
        for month in sorted(booked_slots.keys()):
            keyboard.append([InlineKeyboardButton(f"📅 {month}", callback_data=f"admin_booking_month_{month}")])
        keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data="admin_back")])
        await query.edit_message_text(
            "📅 **Выбери месяц с активными записями:**",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return

    if data.startswith("admin_booking_month_"):
        month = data.replace("admin_booking_month_", "")
        booked_slots = get_booked_slots()
        if month not in booked_slots:
            await query.edit_message_text("❌ В этом месяце нет записей.", reply_markup=admin_menu())
            return

        keyboard = []
        for day in sorted(booked_slots[month].keys(), key=int):
            keyboard.append([InlineKeyboardButton(f"{day}", callback_data=f"admin_booking_day_{month}_{day}")])
        keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data="admin_bookings")])
        await query.edit_message_text(
            f"📅 **Выбери день в {month}:**",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return

    if data.startswith("admin_booking_day_"):
        parts = data.replace("admin_booking_day_", "").split("_")
        month = parts[0]
        day = parts[1]
        booked_slots = get_booked_slots()
        
        if month not in booked_slots or day not in booked_slots[month]:
            await query.edit_message_text("❌ В этот день нет записей.", reply_markup=admin_menu())
            return

        keyboard = []
        for slot in booked_slots[month][day]:
            user_info = users.get(slot['booked_by'], {})
            name = user_info.get("name", "Неизвестный")
            keyboard.append([InlineKeyboardButton(
                f"🕐 {slot['time']} — {name}",
                callback_data=f"admin_booking_slot_{slot['slot_key']}"
            )])
        keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data=f"admin_booking_month_{month}")])
        await query.edit_message_text(
            f"📅 **{day} {month}**\n\n"
            "Выбери время, чтобы увидеть контакты клиента:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return

    if data.startswith("admin_booking_slot_"):
        slot_key = data.replace("admin_booking_slot_", "")
        if slot_key in prebook_settings and prebook_settings[slot_key].get("booked_by"):
            uid = prebook_settings[slot_key]["booked_by"]
            user_info = users.get(uid, {})
            parts = slot_key.split("_")
            date = parts[0] + "_" + parts[1]
            time = parts[2]
            date_display = date.replace("_", " ")
            
            contact_text = (
                f"📋 **Данные клиента**\n\n"
                f"📅 {date_display}\n"
                f"🕐 {time}\n\n"
                f"👤 {user_info.get('name', 'Неизвестный')}\n"
                f"📱 Телефон: {user_info.get('phone', 'Не указан')}\n"
                f"✂️ Telegram: @{user_info.get('username', 'Не указан')}\n\n"
                f"Выбери действие:"
            )
            
            keyboard = [
                [InlineKeyboardButton("🗑️ Снять бронь", callback_data=f"admin_cancel_prebook_{slot_key}")],
                [InlineKeyboardButton("🔙 Назад", callback_data=f"admin_booking_day_{date_display.replace(' ', '_')}")]
            ]
            
            await query.edit_message_text(
                contact_text,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode="Markdown"
            )
        else:
            await query.edit_message_text("❌ Информация не найдена.", reply_markup=admin_menu())
        return

    # ---------- ОСТАЛЬНЫЕ АДМИН-ФУНКЦИИ ----------
    if data.startswith("admin_cancel_prebook_"):
        slot_key = data.replace("admin_cancel_prebook_", "")
        if slot_key in prebook_settings and prebook_settings[slot_key].get("booked_by"):
            uid = prebook_settings[slot_key]["booked_by"]
            if uid in bookings:
                bookings[uid] = [b for b in bookings[uid] if b.get("slot_key") != slot_key]
                if not bookings[uid]:
                    del bookings[uid]
            prebook_settings[slot_key]["booked_by"] = None
            prebook_settings[slot_key]["available"] = False
            save_data()
            await query.edit_message_text(f"✅ Запись снята!", reply_markup=admin_menu())
        else:
            await query.edit_message_text("❌ Запись не найдена.", reply_markup=admin_menu())
        return

    if data == "admin_prebook_setup":
        keyboard = []
        months = ["Январь", "Февраль", "Март", "Апрель", "Май", "Июнь", 
                  "Июль", "Август", "Сентябрь", "Октябрь", "Ноябрь", "Декабрь"]
        row = []
        for month in months:
            if has_active_slots_in_month(month):
                row.append(InlineKeyboardButton(f"📌 {month}", callback_data=f"admin_month_{month}"))
            else:
                row.append(InlineKeyboardButton(month, callback_data=f"admin_month_{month}"))
            if len(row) == 2:
                keyboard.append(row)
                row = []
        if row:
            keyboard.append(row)
        keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data="admin_back")])
        await query.edit_message_text(
            "📅 **Выбери месяц для настройки:**\n\n"
            "📌 — в этом месяце есть активные слоты",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )
        return

    if data.startswith("admin_month_"):
        month = data.replace("admin_month_", "")
        context.user_data["admin_month"] = month
        days = 31
        if month in ["Апрель", "Июнь", "Сентябрь", "Ноябрь"]:
            days = 30
        elif month == "Февраль":
            days = 28

        keyboard = []
        row = []
        for day in range(1, days + 1):
            if has_active_slots_in_day(str(day), month):
                row.append(InlineKeyboardButton(f"📌 {day}", callback_data=f"admin_day_{month}_{day}"))
            else:
                row.append(InlineKeyboardButton(str(day), callback_data=f"admin_day_{month}_{day}"))
            if len(row) == 5:
                keyboard.append(row)
                row = []
        if row:
            keyboard.append(row)
        keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data="admin_prebook_setup")])
        await query.edit_message_text(
            f"📅 **Выбери день в {month}:**\n\n"
            "📌 — в этот день есть активные слоты\n"
            "Ты можешь выбрать несколько часов для этого дня.",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )
        return

    if data.startswith("admin_day_"):
        parts = data.split("_")
        month = parts[2]
        day = parts[3]
        date_key = f"{day}_{month}"
        context.user_data["admin_date"] = date_key

        keyboard = []
        for hour in range(10, 22):
            time_slot = f"{hour:02d}:00"
            slot_key = f"{date_key}_{time_slot}"
            
            if slot_key in prebook_settings:
                if prebook_settings[slot_key].get("booked_by"):
                    uid = prebook_settings[slot_key]["booked_by"]
                    user_info = users.get(uid, {})
                    name = user_info.get("name", "Неизвестный")
                    keyboard.append([InlineKeyboardButton(
                        f"{time_slot} ✍️ {name}", 
                        callback_data=f"admin_show_user_{slot_key}"
                    )])
                elif prebook_settings[slot_key].get("available", False):
                    keyboard.append([InlineKeyboardButton(
                        f"{time_slot} ✅", 
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
        
        keyboard.append([InlineKeyboardButton("🔙 Назад к дням", callback_data=f"admin_month_{month}")])
        await query.edit_message_text(
            f"📅 **{day} {month}**\n\n"
            "➕ — создать слот (сразу станет доступен)\n"
            "⬜ — скрыт\n"
            "✅ — доступен для пользователей\n"
            "✍️ — занят (нажми для данных клиента)\n\n"
            "Нажимай на время, чтобы менять статус:",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )
        return

    if data.startswith("admin_create_"):
        slot_key = data.replace("admin_create_", "")
        prebook_settings[slot_key] = {"available": True, "booked_by": None}
        save_data()
        parts = slot_key.split("_")
        date_part = parts[0] + "_" + parts[1]
        day, month = date_part.split("_")
        await show_admin_day(update, context, day, month)
        return

    if data.startswith("admin_toggle_on_"):
        slot_key = data.replace("admin_toggle_on_", "")
        if slot_key in prebook_settings:
            prebook_settings[slot_key]["available"] = True
            save_data()
            parts = slot_key.split("_")
            date_part = parts[0] + "_" + parts[1]
            day, month = date_part.split("_")
            await show_admin_day(update, context, day, month)
        else:
            await query.edit_message_text("❌ Слот не найден.", reply_markup=admin_menu())
        return

    if data.startswith("admin_toggle_off_"):
        slot_key = data.replace("admin_toggle_off_", "")
        if slot_key in prebook_settings:
            prebook_settings[slot_key]["available"] = False
            save_data()
            parts = slot_key.split("_")
            date_part = parts[0] + "_" + parts[1]
            day, month = date_part.split("_")
            await show_admin_day(update, context, day, month)
        else:
            await query.edit_message_text("❌ Слот не найден.", reply_markup=admin_menu())
        return

    if data.startswith("admin_show_user_"):
        slot_key = data.replace("admin_show_user_", "")
        if slot_key in prebook_settings and prebook_settings[slot_key].get("booked_by"):
            uid = prebook_settings[slot_key]["booked_by"]
            user_info = users.get(uid, {})
            parts = slot_key.split("_")
            date = parts[0] + "_" + parts[1]
            time = parts[2]
            date_display = date.replace("_", " ")
            
            contact_text = (
                f"📋 **Данные клиента**\n\n"
                f"📅 {date_display}\n"
                f"🕐 {time}\n\n"
                f"👤 {user_info.get('name', 'Неизвестный')}\n"
                f"📱 Телефон: {user_info.get('phone', 'Не указан')}\n"
                f"✂️ Telegram: @{user_info.get('username', 'Не указан')}\n\n"
                f"Выбери действие:"
            )
            
            keyboard = [
                [InlineKeyboardButton("🗑️ Снять бронь", callback_data=f"admin_cancel_prebook_{slot_key}")],
                [InlineKeyboardButton("🔙 Оставить", callback_data=f"admin_day_{date_display.replace(' ', '_')}")]
            ]
            
            await query.edit_message_text(
                contact_text,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode="Markdown"
            )
        else:
            await query.edit_message_text("❌ Информация не найдена.", reply_markup=admin_menu())
        return

    if data == "admin_back":
        await query.edit_message_text("Админ-панель:", reply_markup=admin_menu())
        return

    if data == "admin_exit":
        await query.edit_message_text("Вы вышли из админ-панели.", reply_markup=main_menu())
        context.user_data.clear()
        return

async def show_admin_day(update: Update, context: ContextTypes.DEFAULT_TYPE, day: str, month: str):
    """Показывает настройку дня без выброса в начало"""
    query = update.callback_query
    date_key = f"{day}_{month}"
    context.user_data["admin_date"] = date_key

    keyboard = []
    for hour in range(10, 22):
        time_slot = f"{hour:02d}:00"
        slot_key = f"{date_key}_{time_slot}"
        
        if slot_key in prebook_settings:
            if prebook_settings[slot_key].get("booked_by"):
                uid = prebook_settings[slot_key]["booked_by"]
                user_info = users.get(uid, {})
                name = user_info.get("name", "Неизвестный")
                keyboard.append([InlineKeyboardButton(
                    f"{time_slot} ✍️ {name}", 
                    callback_data=f"admin_show_user_{slot_key}"
                )])
            elif prebook_settings[slot_key].get("available", False):
                keyboard.append([InlineKeyboardButton(
                    f"{time_slot} ✅", 
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
    
    keyboard.append([InlineKeyboardButton("🔙 Назад к дням", callback_data=f"admin_month_{month}")])
    await query.edit_message_text(
        f"📅 **{day} {month}**\n\n"
        "➕ — создать слот (сразу станет доступен)\n"
        "⬜ — скрыт\n"
        "✅ — доступен для пользователей\n"
        "✍️ — занят (нажми для данных клиента)\n\n"
        "Нажимай на время, чтобы менять статус:",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )

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