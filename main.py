import sqlite3
import asyncio
import yagmail
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    CallbackContext,
    CallbackQueryHandler
)

BOT_TOKEN = ''
ADMIN_ID = 5201926556
command = "d"
user_states = {}


def add_early_completed_column(conn):
    cursor = conn.cursor()
    cursor.execute("PRAGMA table_info(user_stats)")
    columns = [column[1] for column in cursor.fetchall()]

    if 'early_completed' not in columns:
        cursor.execute('ALTER TABLE user_stats ADD COLUMN early_completed INTEGER DEFAULT 0')
        conn.commit()


def init_db():
    conn = sqlite3.connect('deadlines.db', check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS deadlines (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        subject TEXT,
        deadline TEXT,
        task TEXT,
        reminder_sent INTEGER DEFAULT 0,
        completed INTEGER DEFAULT 0)''')
    cursor.execute("PRAGMA table_info(user_ids)")
    columns = [column[1] for column in cursor.fetchall()]
    if 'user_ids' not in [table[0] for table in
                          cursor.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]:
        cursor.execute('''CREATE TABLE user_ids (
            id INTEGER PRIMARY KEY, 
            user_email TEXT,
            user_name TEXT)''')

    elif 'user_name' not in columns:
        cursor.execute('ALTER TABLE user_ids ADD COLUMN user_name TEXT')
    cursor.execute('''CREATE TABLE IF NOT EXISTS user_stats (
        user_id INTEGER PRIMARY KEY,
        tasks_completed INTEGER DEFAULT 0,
        last_completed TEXT,
        streak_days INTEGER DEFAULT 0,
        early_completed INTEGER DEFAULT 0)''')

    add_early_completed_column(conn)

    conn.commit()
    return conn


conn = init_db()


async def show_stats(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    cursor = conn.cursor()
    cursor.execute('''SELECT tasks_completed, streak_days, early_completed 
                      FROM user_stats WHERE user_id = ?''', (user_id,))
    stats = cursor.fetchone()
    if not stats:
        await update.message.reply_text("📊 У вас пока нет статистики. Добавьте и выполните задачи!")
        return
    tasks_completed, streak_days, early_completed = stats
    cursor.execute('''SELECT COUNT(*) FROM deadlines 
                      WHERE user_id = ? AND completed = 1 
                      AND deadline >= date('now', '-7 days')''', (user_id,))
    weekly_completed = cursor.fetchone()[0]
    response = (
        "📊 <b>Ваша статистика:</b>\n\n"
        f"✅ <b>Выполнено задач:</b> {tasks_completed}\n"
        f"🔥 <b>Текущая серия:</b> {streak_days} дней\n"
        f"⏱ <b>Досрочно выполнено:</b> {early_completed}\n"
        f"📅 <b>За последнюю неделю:</b> {weekly_completed}\n\n"
        "Продолжайте в том же духе! 💪"
    )
    await update.message.reply_text(response, parse_mode='HTML')


async def start(update, context):
    cursor = conn.cursor()
    user_id = update.message.from_user.id
    cursor.execute("SELECT user_name FROM user_ids WHERE id = ?", (user_id,))
    user_data = cursor.fetchone()
    if user_data is None:
        await update.message.reply_text(
            'Привет! Я бот для отслеживания дедлайнов.\n'
            'Как тебя зовут?')
        user_states[user_id] = 'awaiting_name'
    else:
        user_name = user_data[0] or "пользователь"
        await update.message.reply_text(
            f'Привет-привет, {user_name}! 👋\n\n'
            'Я тут, чтобы помочь тебе не забывать о важном:\n\n'
            '📌 /add_deadline — добавить новый дедлайн (давай запланируем!)\n'
            '📋 /my_deadlines — список текущих задач (что на горизонте?)\n'
            '📧 /set_mail — привязать почту (для важных напоминаний)\n'
            '📊 /stats — твоя статистика продуктивности (ты жжешь!)\n'
            '🆘 /help — если что-то непонятно (я помогу!)\n\n'
            'P.S. Ты уже молодец, что заботишься о своих задачах! 💪\n'
            'Главное — начать, а там и остальное получится 😊')


async def help(update, context):
    cursor = conn.cursor()
    user_id = update.message.from_user.id
    cursor.execute("SELECT user_name FROM user_ids WHERE id = ?", (user_id,))
    user_data = cursor.fetchone()
    if user_data is None:
        await start(update, context)
        return
    user_name = user_data[0]
    await update.message.reply_text(
        'Ой, что-то непонятно? Давай разберёмся вместе! 🤗\n\n'
        'Вот что я могу для тебя сделать:\n\n'
        '• /add_deadline - добавим новую задачку\n'
        '• /my_deadlines - посмотрим, что в работе\n'
        '• /set_mail - сохраним твою почту\n'
        '• /stats - полюбуемся на твои успехи\n\n'
        'Не стесняйся спрашивать, если что! Мы с тобой одна команда! ✌️')


async def handle_name(update, context):
    user_id = update.message.from_user.id
    user_name = update.message.text.strip()
    if len(user_name) < 2 or len(user_name) > 50:
        await update.message.reply_text('Пожалуйста, введите корректное имя (от 2 до 50 символов)')
        return
    cursor = conn.cursor()
    try:
        cursor.execute('INSERT OR REPLACE INTO user_ids (id, user_name) VALUES (?, ?)', (user_id, user_name))
        conn.commit()
        if user_id in user_states:
            del user_states[user_id]
        await update.message.reply_text(
            f'Привет-привет, {user_name}! 👋\n\n'
            'Я тут, чтобы помочь тебе не забывать о важном:\n\n'
            '📌 /add_deadline — добавить новый дедлайн (давай запланируем!)\n'
            '📋 /my_deadlines — список текущих задач (что на горизонте?)\n'
            '📧 /set_mail — привязать почту (для важных напоминаний)\n'
            '📊 /stats — твоя статистика продуктивности (ты жжешь!)\n'
            '🆘 /help — если что-то непонятно (я помогу!)\n\n'
            'P.S. Ты уже молодец, что заботишься о своих задачах! 💪\n'
            'Главное — начать, а там и остальное получится 😊')

    except Exception as e:
        print(f"Ошибка при сохранении имени: {e}")
        await update.message.reply_text('Произошла ошибка. Пожалуйста, попробуйте еще раз.')


async def add_deadline(update, context):
    global command
    command = "d"
    await update.message.reply_text(
        '📝 Давай добавим новый дедлайн! Это проще, чем кажется 😊\n\n'
        'Отправь мне данные в таком формате:\n'
        '<b>Предмет, Задание, ДД.ММ.ГГГГ</b>\n\n'
        'Например:\n'
        '<code>Математика, ДЗ 5, 25.12.2025</code>\n\n'
        '✨ <i>Совет:</i> Можно копировать шаблон выше и просто менять данные!\n\n'
        'Ты отлично справляешься! Остался всего один шаг 💪',
        parse_mode='HTML')


async def getting_s_text(update, context):
    user_id = update.message.from_user.id
    if user_id in user_states and user_states[user_id] == 'awaiting_name':
        await handle_name(update, context)
        return
    try:
        if command == "d":
            data = [x.strip() for x in update.message.text.split(',')]
            if len(data) != 3:
                raise ValueError
            subject, task, deadline = data
            deadline_date = datetime.strptime(deadline, '%d.%m.%Y').date()
            if deadline_date < datetime.now().date():
                raise ZeroDivisionError
            cursor = conn.cursor()
            cursor.execute(
                'INSERT INTO deadlines (user_id, subject, task, deadline) '
                'VALUES (?, ?, ?, ?)',
                (user_id, subject, task, deadline_date.strftime('%Y-%m-%d')))
            conn.commit()
            await update.message.reply_text(
                f'Дедлайн добавлен!\n'
                f'Предмет: {subject}\n'
                f'Задание: {task}\n'
                f'Срок: {deadline}')
            await my_deadlines(update, context)
        elif command == "m":
            ml = update.message.text
            cursor = conn.cursor()
            cursor.execute(
                'UPDATE user_ids SET user_email = ? '
                'WHERE id = ?', (ml, user_id))
            conn.commit()
            await update.message.reply_text(f'Почта успешно добавлена!')
    except ValueError:
        await update.message.reply_text(
            'Неверный формат! Используй:\n'
            'Предмет, Задание, ДД.ММ.ГГГГ')
    except ZeroDivisionError:
        await update.message.reply_text(
            f'Кажется время вышло, сегодня уже {datetime.now().date().strftime("%d.%m.%Y")}')


async def my_deadlines(update, context):
    user_id = update.message.from_user.id
    today = datetime.now().date()
    print(today)
    cursor = conn.cursor()
    cursor.execute("""SELECT subject, task, deadline, id FROM deadlines WHERE user_id = ?""", (user_id,))
    deadlines = cursor.fetchall()
    print(deadlines)
    s = ""
    if deadlines:
        tomorrow = today + timedelta(days=1)
        cursor.execute(
            "SELECT subject, task, deadline FROM deadlines "
            "WHERE deadline = ? and user_id = ?",
            (str(today), user_id,))
        crazy_fast = cursor.fetchall()
        s = ""
        for el in crazy_fast:
            s += (f"🔴 Предмет: {el[0]}\n     Задание: {el[1]}\n     "
                  f"Выполнить до {'.'.join(reversed(el[2].split('-')))}\n\n")
        crazy_fast = []
        cursor.execute(
            "SELECT subject, task, deadline FROM deadlines "
            "WHERE deadline = ? and user_id = ?",
            (str(tomorrow), user_id,))
        crazy_fast = cursor.fetchall()
        for el in crazy_fast:
            s += (f"🟡 Предмет: {el[0]}\n     Задание: {el[1]}\n     "
                  f"Выполнить до {'.'.join(reversed(el[2].split('-')))}\n\n")
        crazy_fast = []
        cursor.execute(
            "SELECT subject, task, deadline FROM deadlines WHERE (deadline != ? and deadline != ?) and user_id = ?",
            (str(today), str(tomorrow), user_id,))
        crazy_fast = cursor.fetchall()
        for el in crazy_fast:
            s += (f"🟢 Предмет: {el[0]}\n     Задание: {el[1]}\n     "
                  f"Выполнить до {'.'.join(reversed(el[2].split('-')))}\n\n")
    if s:
        buttons = []
        for el in deadlines:
            subject, task, deadline, deadline_id = el
            button = InlineKeyboardButton(f"{subject}: {task}", callback_data=f"complete_{deadline_id}")
            buttons.append([button])
        keyboard = InlineKeyboardMarkup(buttons)
        await context.bot.send_message(
            chat_id=user_id,
            text=s +
                 "Выберите задание, если вы его выполнили:",
            reply_markup=keyboard
        )
    else:
        await context.bot.send_message(chat_id=user_id, text="У вас нет заданий! Добавьте новый: /add_deadline")


async def mark_task_completed(update, context):
    user_id = update.callback_query.from_user.id
    callback_data = update.callback_query.data
    task_id = callback_data.split('_')[1]

    cursor = conn.cursor()
    cursor.execute('SELECT deadline FROM deadlines WHERE id = ?', (task_id,))
    task = cursor.fetchone()
    if task:
        deadline_date = datetime.strptime(task[0], '%Y-%m-%d').date()
        today = datetime.now().date()

        early_completed = 0
        if deadline_date > today:
            early_completed = 2
        else:
            early_completed = 1

        cursor.execute('UPDATE deadlines SET completed = 1 WHERE id = ?', (task_id,))
        cursor.execute(
            'SELECT tasks_completed, last_completed, streak_days, early_completed FROM user_stats WHERE user_id = ?',
            (user_id,))
        stats = cursor.fetchone()
        if stats:
            tasks_completed, last_completed, streak_days, early = stats
            tasks_completed += 1
            early_completed += early
            if last_completed == (today - timedelta(days=1)).isoformat():
                streak_days += 1
            elif last_completed != today.isoformat():
                streak_days = 1

            cursor.execute('''
                UPDATE user_stats
                SET tasks_completed = ?, last_completed = ?, streak_days = ?, early_completed = ?
                WHERE user_id = ?
            ''', (tasks_completed, today.isoformat(), streak_days, early_completed, user_id))
        else:
            cursor.execute('''
                INSERT INTO user_stats (user_id, tasks_completed, last_completed, streak_days, early_completed)
                VALUES (?, ?, ?, ?, ?)
            ''', (user_id, 1, today.isoformat(), 1, early_completed))
        cursor.execute('DELETE FROM deadlines WHERE id = ? AND user_id = ?', (task_id, user_id))
        conn.commit()
        await update.callback_query.answer("Задание выполнено! ✅")
        await update.callback_query.edit_message_text("✅ Задание помечено как выполненное.")


async def broadcast_message(context, message):
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM user_ids")
    users = cursor.fetchall()
    for user in users:
        try:
            await context.bot.send_message(chat_id=user[0], text=message)
            await mail(context, message, user[0])
            await asyncio.sleep(0.1)
        except Exception as e:
            print(f"Ошибка отправки: {e}")


async def scheduled_broadcast(context):
    message = (
        "📢 Ежедневное напоминание!\n"
        "Проверьте свои дедлайны: /my_deadlines\n"
        "Добавить новый дедлайн: /add_deadline"
    )
    await broadcast_message(context, message)


async def admin_broadcast(update, context):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("❌ У вас нет прав на эту команду!")
        return
    if not context.args:
        await update.message.reply_text("Пример использования: /admin_broadcast Ваше сообщение")
        return
    message = " ".join(context.args)
    await broadcast_message(context, f"📢 Сообщение от администратора:\n\n{message}")
    await update.message.reply_text("✅ Рассылка выполнена!")


async def add_mail(update, context):
    global command
    command = "m"
    await update.message.reply_text("Введите свою почту")


async def mail(update, context, usid):
    try:
        user_id = usid
        cursor = conn.cursor()
        cursor.execute("""SELECT user_email FROM user_ids WHERE id = ?""", (user_id,))
        mail_us = cursor.fetchall()
        print(mail_us)
        mail_us = mail_us[0][0]
        if mail_us:
            try:
                yag = yagmail.SMTP(
                    user="workhazieva@yandex.ru",
                    password="siljyenedxygkvyz",
                    host="smtp.yandex.ru",
                    port=465,
                    smtp_ssl=True
                )
                today = datetime.now().date()
                tomorrow = today + timedelta(days=1)
                cursor.execute(
                    "SELECT subject, task, deadline FROM deadlines "
                    "WHERE (deadline = ?) and user_id = ?",
                    (str(today), user_id,))
                crazy_fast = cursor.fetchall()
                s = ""
                for el in crazy_fast:
                    s += (f"🔴 Предмет: {el[0]}\n     Задание: {el[1]}\n    "
                          f"выполнить до {'.'.join(reversed(el[2].split('-')))}\n\n")
                cursor.execute(
                    "SELECT subject, task, deadline FROM deadlines "
                    "WHERE (deadline = ?) and user_id = ?",
                    (str(tomorrow), user_id,))
                crazy_fast = cursor.fetchall()
                for el in crazy_fast:
                    s += (f"🟡 Предмет: {el[0]}\n     Задание: {el[1]}\n    "
                          f"выполнить до {'.'.join(reversed(el[2].split('-')))}\n\n")
                cursor.execute(
                    "SELECT subject, task, deadline FROM deadlines "
                    "WHERE (deadline != ? and deadline != ?) and user_id = ?",
                    (today, tomorrow, user_id,))
                crazy_fast = cursor.fetchall()
                for el in crazy_fast:
                    s += (f"🟢 Предмет: {el[0]}\n     Задание: {el[1]}\n    "
                          f"выполнить до {'.'.join(reversed(el[2].split('-')))}\n\n")
                if not s:
                    s = ("Заданий нет, отдыхай :)\n\n\n\n"
                         "С уважением команда SmartHomeworkBot\n"
                         "https://t.me/SmartHomeworkBot")
                yag.send(
                    to=mail_us,
                    subject="Напоминалка",
                    contents=s + "\n\n\n\n"
                                 "С уважением команда SmartHomeworkBot\n"
                                 "https://t.me/SmartHomeworkBot")
                print("✅ Отправлено!")
            except Exception as e:
                print(f"❌ Ошибка: {e}")
            finally:
                yag.close()
    except Exception as e:
        print(e)


def main():
    application = Application.builder().token(BOT_TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help))
    application.add_handler(CommandHandler("add_deadline", add_deadline))
    application.add_handler(CallbackQueryHandler(mark_task_completed, pattern="^complete_"))
    application.add_handler(CommandHandler("my_deadlines", my_deadlines))
    application.add_handler(CommandHandler("stats", show_stats))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, getting_s_text))
    application.add_handler(CommandHandler("admin_broadcast", admin_broadcast))
    application.add_handler(CommandHandler("set_mail", add_mail))

    application.job_queue.run_repeating(scheduled_broadcast, interval=86400, first=10)

    application.run_polling()


if __name__ == "__main__":
    main()
