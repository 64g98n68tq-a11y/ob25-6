import os
import json
from datetime import datetime, timedelta
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes, ConversationHandler

DATA_FILE = "data.json"

# ===== Инициализация данных =====
if os.path.exists(DATA_FILE):
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
else:
    data = {}

if "admins" not in data:
    data["admins"] = [1091754600, 1267500760]
if "schedule_photo" not in data:
    data["schedule_photo"] = None
if "homeworks" not in data:
    data["homeworks"] = {}
if "notes" not in data:
    data["notes"] = []

def save_data():
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

def is_admin(user_id):
    return int(user_id) in data["admins"]

# ===== Состояния для ConversationHandler =====
SUBJECT, TASK, DEADLINE = range(3)
pending_schedule = {}
pending_notes = {}
homework_temp = {}

# ===== Команды =====
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    commands_text = """
Привет! Я бот для расписания, домашки и конспектов.

Для всех пользователей:
📌 /schedule - показать расписание
📌 /homework - показать всю домашку
📌 /check_deadlines - показать дедлайны на завтра
📌 /notes - показать конспекты

Для администраторов:
🛠 /set_schedule - загрузить новое расписание (отправь фото после команды)
🛠 /add_homework - добавить домашку пошагово
🛠 /del_homework <номер> - удалить домашку по номеру
🛠 /add_note - добавить конспект (отправь PDF или фото после команды)
🛠 /add_admin <айди> - добавить админа
🛠 /del_admin <айди> - удалить админа
"""
    await update.message.reply_text(commands_text)

# ===== Пошаговое добавление домашки =====
async def add_homework_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_admin(user_id):
        await update.message.reply_text("⛔ Только администратор может добавлять домашку.")
        return ConversationHandler.END
    await update.message.reply_text("Введите название предмета:")
    return SUBJECT

async def add_homework_subject(update: Update, context: ContextTypes.DEFAULT_TYPE):
    homework_temp[update.effective_user.id] = {"subject": update.message.text.strip()}
    await update.message.reply_text("Введите текст задания:")
    return TASK

async def add_homework_task(update: Update, context: ContextTypes.DEFAULT_TYPE):
    homework_temp[update.effective_user.id]["task"] = update.message.text.strip()
    await update.message.reply_text("Введите дедлайн в формате ДД.MM:")
    return DEADLINE

async def add_homework_deadline(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text.strip()
    try:
        # Добавляем текущий год для корректного парсинга
        datetime.strptime(text + f".{datetime.now().year}", "%d.%m.%Y")
    except:
        return await update.message.reply_text("❌ Неверный формат. Введите дату как ДД.MM")

    temp = homework_temp.pop(user_id)
    subject = temp["subject"]
    task = temp["task"]
    deadline = text

    if subject not in data["homeworks"]:
        data["homeworks"][subject] = []

    data["homeworks"][subject].append({"task": task, "deadline": deadline})
    save_data()
    await update.message.reply_text(f"✅ Домашка добавлена: {subject} - {task} (дедлайн: {deadline})")
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id in homework_temp:
        homework_temp.pop(user_id)
    await update.message.reply_text("Добавление домашки отменено.")
    return ConversationHandler.END

# ===== Удаление домашки по номеру =====
async def del_homework(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_admin(user_id):
        return await update.message.reply_text("⛔ Только администратор может удалять домашку.")

    try:
        number = int(context.args[0])
    except:
        return await update.message.reply_text("❌ Используй: /del_homework <номер>")

    # Создаем карту номеров
    hw_map = {}
    number_counter = 1
    for subject, tasks in data["homeworks"].items():
        for idx, hw in enumerate(tasks):
            hw_map[number_counter] = (subject, idx)
            number_counter += 1

    if number not in hw_map:
        return await update.message.reply_text("❌ Домашка с таким номером не найдена.")

    subject, idx = hw_map[number]
    removed = data["homeworks"][subject].pop(idx)
    if not data["homeworks"][subject]:
        del data["homeworks"][subject]
    save_data()
    await update.message.reply_text(f"✅ Удалена домашка: {removed['task']} по {subject}")

# ===== Просмотр домашки =====
async def show_homework(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not data["homeworks"]:
        return await update.message.reply_text("📚 Домашка пока отсутствует.")

    msg = "📚 Домашнее задание:\n\n"
    number = 1
    for subject, tasks in data["homeworks"].items():
        if tasks:
            msg += f"📝 {subject}:\n"
            for hw in tasks:
                msg += f"  {number}. {hw['task']} (дедлайн: {hw['deadline']})\n"
                number += 1
            msg += "\n"
    await update.message.reply_text(msg)

# ===== Остальные команды =====
async def set_schedule(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_admin(user_id):
        return await update.message.reply_text("⛔ Только администратор может изменить расписание.")
    pending_schedule[user_id] = True
    await update.message.reply_text("📷 Отправь фото расписания после этой команды.")

async def add_note(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_admin(user_id):
        return await update.message.reply_text("⛔ Только администратор может добавлять конспекты.")
    pending_notes[user_id] = True
    await update.message.reply_text("📎 Отправь PDF или изображение конспекта после этой команды.")

async def handle_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    # ===== Расписание =====
    if pending_schedule.get(user_id) and update.message.photo:
        file = await update.message.photo[-1].get_file()
        file_path = "schedule.jpg"
        try:
            await file.download_to_drive(file_path)
        except Exception as e:
            await update.message.reply_text(f"❌ Ошибка при сохранении фото: {e}")
            return
        data["schedule_photo"] = file_path
        save_data()
        pending_schedule[user_id] = False
        await update.message.reply_text("✅ Расписание обновлено!")
        return

    # ===== Конспекты =====
    if pending_notes.get(user_id) and (update.message.photo or update.message.document):
        os.makedirs("notes", exist_ok=True)
        if update.message.photo:
            file = await update.message.photo[-1].get_file()
            file_path = f"notes/note_{int(datetime.now().timestamp())}.jpg"
        else:
            file = await update.message.document.get_file()
            file_path = f"notes/{update.message.document.file_name}"

        try:
            await file.download_to_drive(file_path)
        except Exception as e:
            await update.message.reply_text(f"❌ Ошибка при сохранении файла: {e}")
            pending_notes[user_id] = False
            return

        data["notes"].append(file_path)
        save_data()
        pending_notes[user_id] = False
        await update.message.reply_text(f"✅ Конспект {os.path.basename(file_path)} добавлен!")
        return

async def show_schedule(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if data.get("schedule_photo") and os.path.exists(data["schedule_photo"]):
        try:
            with open(data["schedule_photo"], "rb") as f:
                await update.message.reply_photo(f, caption="📅 Расписание на ближайшую неделю")
        except Exception as e:
            await update.message.reply_text(f"❌ Ошибка при отправке фото: {e}")
    else:
        await update.message.reply_text("📅 Расписание пока не загружено.")

async def show_notes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not data["notes"]:
        return await update.message.reply_text("📎 Конспекты пока отсутствуют.")
    for file_path in data["notes"]:
        if os.path.exists(file_path):
            ext = os.path.splitext(file_path)[1].lower()
            try:
                with open(file_path, "rb") as f:
                    if ext in [".jpg", ".jpeg", ".png"]:
                        await update.message.reply_photo(f)
                    elif ext == ".pdf":
                        await update.message.reply_document(f)
            except Exception as e:
                await update.message.reply_text(f"❌ Не удалось отправить {os.path.basename(file_path)}: {e}")

async def check_deadlines(update: Update, context: ContextTypes.DEFAULT_TYPE):
    today = datetime.now().date()
    msg = ""
    for subject, tasks in data["homeworks"].items():
        for hw in tasks:
            try:
                deadline = datetime.strptime(hw["deadline"] + f".{today.year}", "%d.%m.%Y").date()
                if deadline - today == timedelta(days=1):
                    msg += f"⚠ Завтра дедлайн по {subject}: {hw['task']} ({hw['deadline']})\n"
            except:
                continue
    if msg:
        await update.message.reply_text(msg)
    else:
        await update.message.reply_text("✅ Нет дедлайнов на завтра.")

# ===== Управление админами =====
async def add_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_admin(user_id):
        return await update.message.reply_text("⛔ Только администратор может управлять админами.")
    try:
        new_admin_id = int(context.args[0])
    except:
        return await update.message.reply_text("❌ Используй: /add_admin <айди пользователя>")
    if new_admin_id in data["admins"]:
        return await update.message.reply_text("❌ Этот пользователь уже админ.")
    data["admins"].append(new_admin_id)
    save_data()
    await update.message.reply_text(f"✅ Пользователь {new_admin_id} добавлен в админы.")

async def del_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_admin(user_id):
        return await update.message.reply_text("⛔ Только администратор может управлять админами.")
    try:
        remove_admin_id = int(context.args[0])
    except:
        return await update.message.reply_text("❌ Используй: /del_admin <айди пользователя>")
    if remove_admin_id not in data["admins"]:
        return await update.message.reply_text("❌ Этот пользователь не является админом.")
    if remove_admin_id == user_id:
        return await update.message.reply_text("❌ Нельзя удалить себя из админов.")
    data["admins"].remove(remove_admin_id)
    save_data()
    await update.message.reply_text(f"✅ Пользователь {remove_admin_id} удален из админов.")

# ===== Запуск бота =====
TOKEN = "8539758241:AAH6Zp-2e_wwd7OJSrWCeOc-VtTNasBSDtk"
app = ApplicationBuilder().token(TOKEN).build()

# ConversationHandler для домашки
conv_handler = ConversationHandler(
    entry_points=[CommandHandler("add_homework", add_homework_start)],
    states={
        SUBJECT: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_homework_subject)],
        TASK: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_homework_task)],
        DEADLINE: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_homework_deadline)],
    },
    fallbacks=[CommandHandler("cancel", cancel)]
)

# ===== Регистрация команд =====
app.add_handler(conv_handler)
app.add_handler(CommandHandler("del_homework", del_homework))
app.add_handler(CommandHandler("homework", show_homework))
app.add_handler(CommandHandler("set_schedule", set_schedule))
app.add_handler(CommandHandler("schedule", show_schedule))
app.add_handler(CommandHandler("check_deadlines", check_deadlines))
app.add_handler(CommandHandler("add_note", add_note))
app.add_handler(CommandHandler("notes", show_notes))
app.add_handler(CommandHandler("add_admin", add_admin))
app.add_handler(CommandHandler("del_admin", del_admin))
app.add_handler(CommandHandler("start", start))

# Обработка фото и PDF
app.add_handler(MessageHandler(filters.PHOTO | filters.Document.PDF, handle_file))

print("Бот запущен...")
app.run_polling()
