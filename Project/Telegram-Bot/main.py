import asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, ConversationHandler, filters, ContextTypes
import os
import logging
import redis
import requests
from dotenv import load_dotenv
import uuid
from aiohttp import web
from flask import Flask, request

# Загружаем переменные из .env файла
load_dotenv()

# Настройки Redis
redis_client = redis.StrictRedis(host='localhost', port=6379, db=0)

# Пример URL для вашего API
SERVER_URL = "https://loving-beetle-sharing.ngrok-free.app/"  # URL сервера
ADMIN_JWT_TOKEN = os.getenv('JWT_TOKEN')  # Токен из файла .env

# Состояния для аутентификации
ASK_EMAIL, ASK_PASSWORD = range(2)

def generate_token():
    """Генерирует случайный токен"""
    return str(uuid.uuid4())

def login(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id  # Получаем chat_id пользователя

    # Проверяем, есть ли chat_id в Redis
    user_status = redis_client.get(chat_id)

    if user_status is None:
        # Если ключа нет, отправляем сообщение о том, что пользователь не авторизован
        update.message.reply_text(
            "Вы не заголинены! Пожалуйста, авторизуйтесь через:\n"
            "- GitHub\n"
            "- Яндекс ID\n"
            "- Введите код (например: /login type=<тип>)"
        )
    else:
        # Если пользователь уже авторизован, уведомляем его
        update.message.reply_text("Вы уже авторизованы.")

def login_with_type(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    token = generate_token()  # Функция, генерирующая токен

    # Сохраняем статус и токен в Redis
    redis_client.set(chat_id, f"Anonymous:{token}")

    # Теперь делаем запрос к модулю авторизации
    response = requests.post(
        "https://loving-beetle-sharing.ngrok-free.app/",
        json={"token": token}
    )

    if response.status_code == 200:
        # Обработка успешного ответа
        update.message.reply_text("Вы успешно авторизованы.")
    else:
        # Обработка ошибки
        update.message.reply_text("Ошибка авторизации. Пожалуйста, попробуйте снова.")

# Функция для аутентификации пользователя
async def authenticate_user(email: str, password: str) -> str:
    """Отправка данных на сервер и получение статуса пользователя"""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(SERVER_URL, json={'email': email, 'password': password}) as response:
                if response.status == 200:
                    data = await response.json()
                    return data.get('role', 'user')  # по умолчанию 'user', если роль не указана
                else:
                    return None  # Ошибка при аутентификации
    except aiohttp.ClientError as e:
        print(f"Ошибка запроса: {e}")
        return None

async def start_login_conversation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
   """Запускает процесс аутентификации"""
   await update.message.reply_text('Введите вашу почту:')
   return ASK_EMAIL


# Сохранение почты пользователя и запрос пароля
async def ask_email(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Запрос почты"""
    user_email = update.message.text.strip()
    if not user_email:
        await update.message.reply_text('Пожалуйста, введите корректный email.')
        return ASK_EMAIL
    context.user_data['email'] = user_email  # Сохраняем email
    await update.message.reply_text('Введите ваш пароль:')
    return ASK_PASSWORD

# Сохранение пароля и аутентификация
async def ask_password(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Запрос пароля и аутентификация"""
    user_password = update.message.text.strip()
    if not user_password:
        await update.message.reply_text('Пожалуйста, введите корректный пароль.')
        return ASK_PASSWORD

    email = context.user_data['email']  # Получаем сохраненную почту
    # Отправляем данные на сервер для аутентификации
    role = await authenticate_user(email, user_password)

    if role is None:
        await update.message.reply_text('Неверная почта или пароль. Попробуйте еще раз.')
        return ConversationHandler.END  # Завершаем, если ошибка аутентификации

    # Сохраняем роль пользователя
    context.user_data['role'] = role

    if role == 'admin':
        await update.message.reply_text(f'Здравствуйте, {update.message.from_user.first_name}! Вы администратор.')
    else:
        await update.message.reply_text(f'Здравствуйте, {update.message.from_user.first_name}! Вы обычный пользователь.')

    return ConversationHandler.END  # Завершаем разговор

# Функция, которая проверяет роль пользователя перед выполнением команды
async def restricted_access(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Команда, доступная только администраторам"""
    if 'role' not in context.user_data or context.user_data['role'] != 'admin':
        await update.message.reply_text('У вас нет доступа к этой команде, потому что вы не администратор.')
    else:
        await update.message.reply_text('Доступ к админ-команде получен.')

# Функция для проверки JWT-токена перед выполнением команды
async def check_jwt_token(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Проверка JWT-токена перед выполнением команды"""
    if 'role' not in context.user_data or context.user_data['role'] != 'admin':
        await update.message.reply_text('У вас нет доступа к этой команде, так как вы не администратор.')
    else:
        # Проверка токена из файла .env
        user_jwt_token = os.getenv('JWT_TOKEN')
        if user_jwt_token != ADMIN_JWT_TOKEN:
            await update.message.reply_text('Ваш токен недействителен. Вы не имеете доступа к администраторским функциям.')
        else:
            await update.message.reply_text('JWT-токен проверен. Доступ к админ-команде получен.')

# Создаем приложение Flask
app = Flask(__name__)

# Логирование для отладки
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                    level=logging.INFO)
logger = logging.getLogger(__name__)

# Ваш токен бота
TOKEN = os.getenv('TOKEN')

# Создаем приложение Telegram
application = Application.builder().token(TOKEN).build()

# Создаем вебхуки для Flask
async def webhook_handler(request):
    try:
        update = Update.de_json(await request.json(), application.bot)
        await application.process_update(update)
    except Exception as e:
        logger.error(f"Ошибка при обработке обновления: {e}")
    return web.Response(status=200)

# Настройка вебхука
async def set_webhook():
    url = f'https://535c-195-93-160-12.ngrok-free.app/{TOKEN}'  # URL от ngrok
    await application.bot.set_webhook(url)

# Переменные для хранения данных о тестах и баллах
tasts = {}
scores = {}

# Состояния для обработки создания теста
CREATE_TEST, SET_TIME_LIMIT, ADD_QUESTION_TEXT, ADD_ANSWERS, SELECT_CORRECT_ANSWER, FINISH_CREATION, TESTS_TEST, ASK_QUESTION, CHECK_ANSWER, DELETE_TEST, CONFIRM_DELETE, DEFAULT_TYPE = range(12)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text('Привет! Я бот для создания и прохождения тестов. Используйте:\n/create для создания собственного теста\n/tests для просмотра списка доступных тестов\n/view_results для просмотра своих результатов\n/list_rankings для ранжирования участников\n/delete для удаления своего теста.')

async def list_tests(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if tasts:
        test_list = '\n'.join([f'{discipline}: {", ".join(tasts[discipline].keys())}' for discipline in tasts])
        await update.message.reply_text(f'Доступные тесты:\n{test_list}')
    else:
        await update.message.reply_text('Нет доступных тестов.')

async def create(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text('Введите название теста:')
    return CREATE_TEST

async def create_test(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    test_name = update.message.text.strip()
    if not test_name:
        await update.message.reply_text('Название теста не может быть пустым. Пожалуйста, введите название теста:')
        return CREATE_TEST
    if test_name in tasts:
        await update.message.reply_text(f'Тест "{test_name}" уже существует. Пожалуйста, введите другое название теста:')
        return CREATE_TEST
    tasts[test_name] = {'questions': [], 'time_limit': None, 'creator': update.message.from_user.id}
    context.user_data['current_test'] = test_name
    await update.message.reply_text(f'Тест "{test_name}" создан. Установите время для прохождения теста (в минутах):')
    return SET_TIME_LIMIT

async def set_time_limit(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    time_limit = update.message.text.strip()
    if not time_limit.isdigit():
        await update.message.reply_text('Время должно быть числом. Пожалуйста, введите время для прохождения теста (в минутах):')
        return SET_TIME_LIMIT
    tasts[context.user_data['current_test']]['time_limit'] = int(time_limit)
    await update.message.reply_text(f'Время для прохождения теста установлено на {time_limit} минут. Добавьте вопросы с помощью /add_question.')
    return ADD_QUESTION_TEXT

async def add_question(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text('Введите вопрос:')
    return ADD_QUESTION_TEXT

async def add_question_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    question_text = update.message.text.strip()
    if not question_text:
        await update.message.reply_text('Текст вопроса не может быть пустым. Пожалуйста, введите вопрос:')
        return ADD_QUESTION_TEXT
    context.user_data['current_question'] = question_text
    await update.message.reply_text('Введите варианты ответов через запятую:')
    return ADD_ANSWERS

async def add_answers(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    answers = [answer.strip() for answer in update.message.text.split(',')]
    if len(answers) < 2:
        await update.message.reply_text('Должно быть как минимум два варианта ответа. Пожалуйста, введите варианты ответов через запятую:')
        return ADD_ANSWERS
    context.user_data['current_answers'] = answers
    keyboard = [[InlineKeyboardButton(answer, callback_data=f'correct_{i}')] for i, answer in enumerate(answers)]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text('Выберите правильный ответ:', reply_markup=reply_markup)
    return SELECT_CORRECT_ANSWER

async def select_correct_answer(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    correct_index = int(query.data.replace('correct_', ''))
    question = {
        'text': context.user_data['current_question'],
        'answers': context.user_data['current_answers'],
        'correct_answer': context.user_data['current_answers'][correct_index]
    }
    tasts[context.user_data['current_test']]['questions'].append(question)
    keyboard = [
        [InlineKeyboardButton("Добавить еще вопрос", callback_data='add_question')],
        [InlineKeyboardButton("Завершить создание теста", callback_data='finish_creation')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.message.reply_text('Что вы хотите сделать дальше?', reply_markup=reply_markup)
    return FINISH_CREATION

async def finish_creation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    if query.data == 'add_question':
        await query.message.reply_text('Введите вопрос:')
        return ADD_QUESTION_TEXT
    elif query.data == 'finish_creation':
        await query.message.reply_text('Тест создан! Вы можете использовать:\n/create для создания собственного теста\n/tests для просмотра списка доступных тестов\n/view_results для просмотра своих результатов\n/list_rankings для ранжирования участников\n/delete для удаления своего теста.')
        return ConversationHandler.END


import time

async def tests(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    keyboard = [[InlineKeyboardButton(test, callback_data=f'test_{test}')] for test in tasts.keys()]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text('Выберите тест для прохождения:', reply_markup=reply_markup)
    return TESTS_TEST

async def button(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    if query.data.startswith('test_'):
        test_name = query.data.replace('test_', '')
        context.user_data['current_test'] = test_name
        context.user_data['current_question_index'] = 0
        context.user_data['correct_answers'] = 0
        time_limit = tasts[test_name]['time_limit']
        if time_limit:
            context.user_data['time_limit'] = time_limit
            context.user_data['start_time'] = time.time()
            minutes, seconds = divmod(time_limit * 60, 60)
            await query.message.reply_text(f'У вас есть {minutes} минут и {seconds} секунд для прохождения теста.')
        await ask_question(update, context)
        return ASK_QUESTION
    elif query.data.startswith('answer_'):
        await check_answer(update, context)
        return CHECK_ANSWER

async def ask_question(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    test_name = context.user_data['current_test']
    question_index = context.user_data['current_question_index']
    question = tasts[test_name]['questions'][question_index]
    keyboard = [[InlineKeyboardButton(answer, callback_data=f'answer_{answer}')] for answer in question['answers']]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.message.reply_text(question['text'], reply_markup=reply_markup)
    return CHECK_ANSWER

async def view_results(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_name = update.message.from_user.first_name
    if user_name not in scores:
        await update.message.reply_text('У вас нет результатов.')
        return

    user_scores = scores[user_name]
    results = '\n'.join([f'Тест: {test_name}, Количество правильных ответов: {score}' for test_name, score in user_scores.items()])
    await update.message.reply_text(f'Пользователь: {user_name}\nРезультаты:\n{results}')
    await update.message.reply_text('Вы можете использовать:\n/create для создания собственного теста\n/tests для просмотра списка доступных тестов\n/view_results для просмотра своих результатов\n/list_rankings для ранжирования участников\n/delete для удаления своего теста.')

async def update_score(user_name: str, test_name: str, score: int) -> None:
    if user_name not in scores:
        scores[user_name] = {}
    scores[user_name][test_name] = score


async def check_answer(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    selected_answer = query.data.replace('answer_', '')
    test_name = context.user_data['current_test']
    question_index = context.user_data['current_question_index']
    correct_answer = tasts[test_name]['questions'][question_index]['correct_answer']
    if selected_answer == correct_answer:
        context.user_data['correct_answers'] += 1
    context.user_data['current_question_index'] += 1
    if context.user_data['current_question_index'] < len(tasts[test_name]['questions']):
        elapsed_time = time.time() - context.user_data['start_time']
        remaining_time = context.user_data['time_limit'] * 60 - elapsed_time
        minutes, seconds = divmod(remaining_time, 60)
        await query.message.reply_text(f'Осталось {int(minutes)} минут и {int(seconds)} секунд.')
        await ask_question(update, context)
        return ASK_QUESTION
    else:
        correct_answers = context.user_data['correct_answers']
        total_questions = len(tasts[test_name]['questions'])
        await query.message.reply_text(f'Вы завершили тест! Количество правильных ответов: {correct_answers}/{total_questions}')
        await query.message.reply_text('Вы можете использовать:\n/create для создания собственного теста\n/tests для просмотра списка доступных тестов\n/view_results для просмотра своих результатов\n/list_rankings для ранжирования участников\n/delete для удаления своего теста.')
        user_name = update.callback_query.from_user.first_name
        await update_score(user_name, test_name, correct_answers)
        
        return ConversationHandler.END

async def list_rankings(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if scores:
        user_scores = {user: sum(test_scores.values()) for user, test_scores in scores.items()}
        sorted_scores = sorted(user_scores.items(), key=lambda item: item[1], reverse=True)
        ranking_list = '\n'.join([f'{user_name}: {score} баллов' for user_name, score in sorted_scores])
        await update.message.reply_text(f'Рейтинг участников:\n{ranking_list}')
        await update.message.reply_text('Вы можете использовать:\n/create для создания собственного теста\n/tests для просмотра списка доступных тестов\n/view_results для просмотра своих результатов\n/list_rankings для ранжирования участников\n/delete для удаления своего теста.')
    else:
        await update.message.reply_text('Нет данных о рейтингах.')
        await update.message.reply_text('Вы можете использовать:\n/create для создания собственного теста\n/tests для просмотра списка доступных тестов\n/view_results для просмотра своих результатов\n/list_rankings для ранжирования участников\n/delete для удаления своего теста.')

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text('Привет! Я бот для создания и прохождения тестов. Используйте:\n/create для создания собственного теста\n/tests для просмотра списка доступных тестов\n/view_results для просмотра своих результатов\n/list_rankings для ранжирования участников\n/delete для удаления своего теста.')

async def delete_test(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.message.from_user.id
    user_tests = [test for test, details in tasts.items() if details['creator'] == user_id]
    
    if not user_tests:
        await update.message.reply_text('У вас нет тестов для удаления.')
        return
    
    tests_list = '\n'.join(user_tests)
    await update.message.reply_text(f'Ваши тесты:\n{tests_list}\nВведите название теста, который вы хотите удалить:')
    context.user_data['deleting_test'] = True

async def confirm_delete(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if context.user_data.get('deleting_test'):
        test_name = update.message.text.strip()
        if test_name in tasts and tasts[test_name]['creator'] == update.message.from_user.id:
            del tasts[test_name]
            await update.message.reply_text(f'Тест "{test_name}" был удален.')
            await update.message.reply_text('Доступные команды:\n/create для создания собственного теста\n/tests для просмотра списка доступных тестов\n/view_results для просмотра своих результатов\n/list_rankings для ранжирования участников\n/delete для удаления своего теста.')
        else:
            await update.message.reply_text('Тест не найден или вы не являетесь его создателем.')
        context.user_data['deleting_test'] = False

async def handle_updates(app, application):
    while True:
        try:
            update = await app['updates'].get()  # Получаем обновление из очереди
            if update:
                await application.process_update(update)
            else:
                await asyncio.sleep(0.1)  # Задержка, если очередь пуста
        except Exception as e:
            logging.error(f"Error handling updates: {e}")
            await asyncio.sleep(1)

async def run_flask():
    app = web.Application()
    app.router.add_post(f"/{TOKEN}", webhook_handler)
    app['updates'] = asyncio.Queue()  # Создаём очередь

    async def start_flask():
        runner = web.AppRunner(app)
        await runner.setup()
        # Remove the TCPSite and site.start lines
        # Instead we keep track of the queue.
        # site = web.TCPSite(runner, '0.0.0.0', int(os.environ.get("PORT", 8080)))
        # await site.start()
        update_task = asyncio.create_task(handle_updates(app, application))
        await update_task  # Ожидаем завершение задачи обработки обновлений

    await start_flask()

def start_bot(application):
    # Обработчик для команды /login без параметров
    application.add_handler(CommandHandler("login", login))

    # Обработчик для команды /login с параметром type
    application.add_handler(CommandHandler("login", login_with_type))
    """Основная функция для запуска бота"""
    # Обработчик команды /login
    login_conv_handler = ConversationHandler(
        entry_points=[CommandHandler('login', start_login_conversation)],
        states={
            ASK_EMAIL: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_email)],  # Запрос почты
            ASK_PASSWORD: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_password)],  # Запрос пароля
        },
        fallbacks=[CommandHandler('start', start)],
    )
    create_conv_handler = ConversationHandler(
        entry_points=[CommandHandler('create', create)],
        states={
            CREATE_TEST: [MessageHandler(filters.TEXT & ~filters.COMMAND, create_test)],
            SET_TIME_LIMIT: [MessageHandler(filters.TEXT & ~filters.COMMAND, set_time_limit)],
            ADD_QUESTION_TEXT: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_question_text)],
            ADD_ANSWERS: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_answers)],
            SELECT_CORRECT_ANSWER: [CallbackQueryHandler(select_correct_answer)],
            FINISH_CREATION: [CallbackQueryHandler(finish_creation)],
            TESTS_TEST: [CallbackQueryHandler(button)],
            ASK_QUESTION: [CallbackQueryHandler(button)],
            CHECK_ANSWER: [CallbackQueryHandler(check_answer)],
        },
        fallbacks=[CommandHandler('start', start)],
    )

    application.add_handler(login_conv_handler)
    application.add_handler(create_conv_handler)
    application.add_handler(CommandHandler('list', list_tests))
    application.add_handler(CommandHandler('tests', tests))
    application.add_handler(CommandHandler('start', start))
    application.add_handler(CommandHandler('view_results', view_results))
    application.add_handler(CallbackQueryHandler(button))
    application.add_handler(CommandHandler('list_rankings', list_rankings))
    application.add_handler(CommandHandler('delete', delete_test))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, confirm_delete))

async def run_bot(application):
    await set_webhook()
    try:
      await application.initialize()
      print("Application started")
      await application.start()
    except Exception as e:
      print(f"Error initialize bot: {e}")
    finally:
        try:
          await application.stop()
        finally:
          await application.shutdown()


async def main():
    application = Application.builder().token(TOKEN).build()
    start_bot(application)
    try:
        await asyncio.gather(run_flask(), run_bot(application))
    except Exception as e:
        print(f"An error occurred: {e}")

if __name__ == "__main__":
    asyncio.run(main())
