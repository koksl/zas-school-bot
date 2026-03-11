"""
Демо-бот для онлайн-школы/курсов — показывает клиентам Kwork/Авито
что такое "бот с ИИ под ключ".

Функции:
- Каталог курсов с ценами и расписанием
- Запись на курс / бесплатный урок (FSM)
- Тест "Какой курс подойдёт тебе?" (квиз)
- ИИ-ответы на вопросы об обучении (Claude API)
- Уведомление владельца о каждой заявке
"""

import asyncio
import logging
import os
from dotenv import load_dotenv

load_dotenv()

from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
    ReplyKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardRemove,
)
import anthropic

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
OWNER_ID = int(os.getenv("OWNER_TELEGRAM_ID", "0"))
ANTHROPIC_KEY = os.getenv("ANTHROPIC_API_KEY", "")
SCHOOL_NAME = os.getenv("SCHOOL_NAME", "Онлайн-школа SkillUp")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())
claude = anthropic.Anthropic(api_key=ANTHROPIC_KEY) if ANTHROPIC_KEY else None

# ─── КАТАЛОГ КУРСОВ ──────────────────────────────────────────────────────────

COURSES = {
    "python": {
        "name": "🐍 Python с нуля до Junior",
        "price": "18 900 ₽",
        "old_price": "25 000 ₽",
        "duration": "3 месяца",
        "format": "Видео + живые вебинары",
        "schedule": "Вт, Чт 19:00 МСК",
        "level": "Новичок",
        "desc": "Научишься программировать на Python, создашь 5 реальных проектов и получишь поддержку ментора.",
        "start": "1 апреля 2026",
    },
    "smm": {
        "name": "📱 SMM и продвижение в соцсетях",
        "price": "12 900 ₽",
        "old_price": "18 000 ₽",
        "duration": "6 недель",
        "format": "Видео + домашние задания",
        "schedule": "Пн, Ср, Пт — в своё время",
        "level": "Любой",
        "desc": "Научишься вести соцсети и привлекать клиентов через Instagram, ВКонтакте и Telegram.",
        "start": "15 марта 2026",
    },
    "ai": {
        "name": "🤖 ИИ-инструменты для бизнеса",
        "price": "9 900 ₽",
        "old_price": "14 000 ₽",
        "duration": "4 недели",
        "format": "Видео + практика",
        "schedule": "В своё время",
        "level": "Любой",
        "desc": "ChatGPT, Claude, Midjourney, автоматизация рутины — научишься экономить 15+ часов в неделю.",
        "start": "10 марта 2026",
    },
    "design": {
        "name": "🎨 Графический дизайн в Figma",
        "price": "14 900 ₽",
        "old_price": "20 000 ₽",
        "duration": "2 месяца",
        "format": "Видео + проекты в портфолио",
        "schedule": "Ср, Сб 18:00 МСК",
        "level": "Новичок",
        "desc": "От нуля до готового портфолио. Научишься создавать сайты, логотипы, баннеры в Figma.",
        "start": "1 апреля 2026",
    },
}

SYSTEM_PROMPT = f"""Ты — дружелюбный консультант онлайн-школы «{SCHOOL_NAME}».
Помогаешь студентам выбрать подходящий курс и отвечаешь на вопросы об обучении.

ИНФОРМАЦИЯ О ШКОЛЕ:
Режим: все курсы онлайн, доступ к материалам 24/7
Поддержка: куратор отвечает в течение 24 часов
Сертификат: выдаётся по окончании курса
Рассрочка: доступна на все курсы (0% на 3 мес)
Гарантия: возврат денег в течение 7 дней если не понравится

КУРСЫ:
- Python с нуля: 18 900 ₽, 3 мес, для новичков
- SMM и соцсети: 12 900 ₽, 6 нед, для любого уровня
- ИИ-инструменты: 9 900 ₽, 4 нед, для любого уровня
- Дизайн в Figma: 14 900 ₽, 2 мес, для новичков

ПРАВИЛА:
- Отвечай тепло, кратко, мотивирующе
- Если не уверен — предложи записаться на бесплатный урок
- Не придумывай курсы вне списка
- Если спрашивают "что выбрать" — задай 1-2 уточняющих вопроса
"""

# ─── FSM ─────────────────────────────────────────────────────────────────────

class EnrollState(StatesGroup):
    entering_name = State()
    entering_phone = State()
    confirming = State()

class LeadState(StatesGroup):
    waiting_description = State()

class QuizState(StatesGroup):
    q1_goal = State()
    q2_time = State()
    q3_experience = State()

# ─── КЛАВИАТУРЫ ──────────────────────────────────────────────────────────────

def main_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🐍 Python с нуля", callback_data="course:python"),
         InlineKeyboardButton(text="🤖 ИИ-инструменты", callback_data="course:ai")],
        [InlineKeyboardButton(text="📱 SMM и соцсети", callback_data="course:smm"),
         InlineKeyboardButton(text="🎨 Дизайн в Figma", callback_data="course:design")],
        [InlineKeyboardButton(text="🎯 Какой курс подойдёт мне?", callback_data="quiz:start")],
        [InlineKeyboardButton(text="📝 Записаться на бесплатный урок", callback_data="enroll:free")],
        [InlineKeyboardButton(text="❓ Задать вопрос", callback_data="ask")],
        [InlineKeyboardButton(text="💼 Хочу такой бот для своего бизнеса", callback_data="lead")],
    ])


def course_keyboard(course_key: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Записаться на этот курс", callback_data=f"enroll:{course_key}")],
        [InlineKeyboardButton(text="🎁 Бесплатный вводный урок", callback_data="enroll:free")],
        [InlineKeyboardButton(text="← Все курсы", callback_data="menu")],
    ])


def back_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="← Все курсы", callback_data="menu")],
        [InlineKeyboardButton(text="📝 Записаться", callback_data="enroll:free")],
    ])


def phone_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="📱 Отправить номер", request_contact=True)]],
        resize_keyboard=True,
        one_time_keyboard=True,
    )

# ─── ХЭНДЛЕРЫ ────────────────────────────────────────────────────────────────

@dp.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()
    await message.answer(
        f"Привет! Добро пожаловать в *{SCHOOL_NAME}* 🎓\n\n"
        "Здесь ты найдёшь курсы, которые реально меняют жизнь.\n\n"
        "Я помогу тебе:\n"
        "• Выбрать подходящий курс\n"
        "• Записаться на бесплатный вводный урок\n"
        "• Ответить на любые вопросы\n\n"
        "С чего начнём?\n\n"
        "_Хотите такого бота для своего бизнеса? → «💼 Хочу такой бот»_",
        parse_mode="Markdown",
        reply_markup=main_menu(),
    )


@dp.callback_query(F.data == "menu")
async def cb_menu(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text(
        f"*{SCHOOL_NAME}* — выбери курс или пройди тест 🎓",
        parse_mode="Markdown",
        reply_markup=main_menu(),
    )
    await callback.answer()


# ── Карточка курса ────────────────────────────────────────────────────────────

@dp.callback_query(F.data.startswith("course:"))
async def cb_course(callback: CallbackQuery):
    key = callback.data.split(":")[1]
    c = COURSES.get(key)
    if not c:
        await callback.answer("Курс не найден")
        return

    text = (
        f"*{c['name']}*\n\n"
        f"📖 {c['desc']}\n\n"
        f"⏱ Длительность: {c['duration']}\n"
        f"📅 Старт: {c['start']}\n"
        f"🕐 Формат: {c['format']}\n"
        f"📡 Расписание: {c['schedule']}\n"
        f"🎯 Уровень: {c['level']}\n\n"
        f"💰 Цена: *{c['price']}* ~~{c['old_price']}~~\n"
        f"💳 Рассрочка: 0% на 3 месяца"
    )
    await callback.message.edit_text(text, parse_mode="Markdown", reply_markup=course_keyboard(key))
    await callback.answer()


# ── Квиз "Какой курс подойдёт?" ───────────────────────────────────────────────

@dp.callback_query(F.data == "quiz:start")
async def cb_quiz_start(callback: CallbackQuery, state: FSMContext):
    await state.set_state(QuizState.q1_goal)
    await callback.message.edit_text(
        "🎯 *Тест: какой курс тебе подойдёт?*\n\n"
        "Вопрос 1 из 3:\n*Какова твоя главная цель?*",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="💼 Сменить профессию", callback_data="q1:career")],
            [InlineKeyboardButton(text="💰 Дополнительный доход", callback_data="q1:income")],
            [InlineKeyboardButton(text="🚀 Развить свой бизнес", callback_data="q1:business")],
            [InlineKeyboardButton(text="📚 Получить новый навык", callback_data="q1:skill")],
        ]),
    )
    await callback.answer()


@dp.callback_query(QuizState.q1_goal, F.data.startswith("q1:"))
async def quiz_q1(callback: CallbackQuery, state: FSMContext):
    await state.update_data(goal=callback.data.split(":")[1])
    await state.set_state(QuizState.q2_time)
    await callback.message.edit_text(
        "Вопрос 2 из 3:\n*Сколько времени готов уделять учёбе?*",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⚡ 30–60 мин в день", callback_data="q2:low")],
            [InlineKeyboardButton(text="🔥 1–2 часа в день", callback_data="q2:mid")],
            [InlineKeyboardButton(text="💪 3+ часа в день", callback_data="q2:high")],
        ]),
    )
    await callback.answer()


@dp.callback_query(QuizState.q2_time, F.data.startswith("q2:"))
async def quiz_q2(callback: CallbackQuery, state: FSMContext):
    await state.update_data(time=callback.data.split(":")[1])
    await state.set_state(QuizState.q3_experience)
    await callback.message.edit_text(
        "Вопрос 3 из 3:\n*Есть ли опыт в IT или дизайне?*",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🐣 Нет, полный новичок", callback_data="q3:none")],
            [InlineKeyboardButton(text="🌱 Немного, базовые знания", callback_data="q3:basic")],
            [InlineKeyboardButton(text="🌳 Есть опыт", callback_data="q3:exp")],
        ]),
    )
    await callback.answer()


@dp.callback_query(QuizState.q3_experience, F.data.startswith("q3:"))
async def quiz_result(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    await state.clear()

    goal = data.get("goal", "")
    time_pref = data.get("time", "")

    # Простая логика рекомендации
    if goal == "business" or goal == "income":
        if time_pref == "low":
            rec_key = "ai"
        else:
            rec_key = "smm"
    elif goal == "career":
        rec_key = "python"
    else:
        rec_key = "design"

    c = COURSES[rec_key]
    await callback.message.edit_text(
        f"✨ *Твой идеальный курс:*\n\n"
        f"*{c['name']}*\n\n"
        f"{c['desc']}\n\n"
        f"⏱ {c['duration']} | 💰 {c['price']}\n"
        f"📅 Старт: {c['start']}\n\n"
        "Записаться можно прямо сейчас — или начни с бесплатного урока!",
        parse_mode="Markdown",
        reply_markup=course_keyboard(rec_key),
    )
    await callback.answer()


# ── Запись на курс / бесплатный урок ──────────────────────────────────────────

@dp.callback_query(F.data.startswith("enroll:"))
async def cb_enroll_start(callback: CallbackQuery, state: FSMContext):
    course_key = callback.data.split(":")[1]
    course_name = COURSES[course_key]["name"] if course_key in COURSES else "Бесплатный вводный урок"
    await state.update_data(course=course_name)
    await state.set_state(EnrollState.entering_name)
    await callback.message.edit_text(
        f"📝 *Запись:* {course_name}\n\n"
        "Шаг 1/2 — Как тебя зовут?",
        parse_mode="Markdown",
    )
    await callback.answer()


@dp.message(EnrollState.entering_name)
async def enroll_name(message: Message, state: FSMContext):
    name = message.text.strip()
    if len(name) < 2:
        await message.answer("Введи своё имя:")
        return
    await state.update_data(name=name)
    await state.set_state(EnrollState.entering_phone)
    await message.answer(
        f"Отлично, *{name}*! 🎉\n\n"
        "Шаг 2/2 — Укажи номер телефона\n(куратор свяжется для старта):",
        parse_mode="Markdown",
        reply_markup=phone_keyboard(),
    )


@dp.message(EnrollState.entering_phone, F.contact)
async def enroll_phone_contact(message: Message, state: FSMContext):
    await _finish_enroll(message, state, message.contact.phone_number)


@dp.message(EnrollState.entering_phone, F.text)
async def enroll_phone_text(message: Message, state: FSMContext):
    phone = message.text.strip()
    digits = ''.join(c for c in phone if c.isdigit())
    if len(digits) < 10:
        await message.answer("Введи корректный номер телефона:")
        return
    await _finish_enroll(message, state, phone)


async def _finish_enroll(message: Message, state: FSMContext, phone: str):
    data = await state.get_data()
    await state.clear()

    owner_text = (
        f"🎓 Новая заявка на курс!\n\n"
        f"👤 {data['name']}\n"
        f"📱 {phone}\n"
        f"📚 Курс: {data.get('course', '?')}\n"
        f"TG: @{message.from_user.username or '—'} (id: {message.from_user.id})"
    )
    try:
        await bot.send_message(OWNER_ID, owner_text)
    except Exception as e:
        log.error(f"Owner notification failed: {e}")

    await message.answer(
        f"✅ *Заявка принята!*\n\n"
        f"Курс: *{data.get('course', '')}*\n\n"
        "Наш куратор свяжется с тобой в течение нескольких часов "
        "и расскажет как начать.\n\n"
        "Будущий студент — это уже смелый шаг! 🚀",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="← Все курсы", callback_data="menu")]
        ]),
    )


# ── ИИ-ответы ─────────────────────────────────────────────────────────────────

@dp.callback_query(F.data == "ask")
async def cb_ask(callback: CallbackQuery):
    await callback.message.edit_text(
        "❓ Задай любой вопрос об обучении — отвечу сразу:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="← Меню", callback_data="menu")]
        ]),
    )
    await callback.answer()


@dp.message(F.text & ~F.text.startswith("/"))
async def handle_free_text(message: Message, state: FSMContext):
    current_state = await state.get_state()
    if current_state:
        return

    await bot.send_chat_action(message.chat.id, "typing")

    if claude:
        try:
            response = claude.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=350,
                system=SYSTEM_PROMPT,
                messages=[{"role": "user", "content": message.text}],
            )
            answer = response.content[0].text
        except Exception as e:
            log.error(f"Claude error: {e}")
            answer = _fallback(message.text)
    else:
        answer = _fallback(message.text)

    await message.answer(
        answer,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📚 Все курсы", callback_data="menu"),
             InlineKeyboardButton(text="🎯 Подобрать курс", callback_data="quiz:start")],
        ]),
    )


def _fallback(text: str) -> str:
    t = text.lower()
    if any(w in t for w in ["цен", "стоит", "сколько"]):
        return "Цены на курсы:\n🐍 Python — 18 900 ₽\n🤖 ИИ-инструменты — 9 900 ₽\n📱 SMM — 12 900 ₽\n🎨 Дизайн — 14 900 ₽\n\nВсе с рассрочкой 0% на 3 мес 💳"
    if any(w in t for w in ["рассрочк", "в кредит", "оплат"]):
        return "Да, есть рассрочка 0% на 3 месяца на все курсы — без банков и переплат 👍"
    if any(w in t for w in ["сертификат", "документ"]):
        return "После окончания курса выдаём сертификат 🎓 Его можно добавить в резюме и LinkedIn."
    if any(w in t for w in ["гарантия", "верн", "возврат"]):
        return "Если в течение 7 дней курс не понравится — вернём деньги полностью, без вопросов ✅"
    return "Хороший вопрос! 😊 Пройди наш короткий тест — подберём курс именно под тебя."


# ─── ЗАХВАТ ЛИДОВ ────────────────────────────────────────────────────────────

@dp.callback_query(F.data == "lead")
async def cb_lead_start(callback: CallbackQuery, state: FSMContext):
    await state.set_state(LeadState.waiting_description)
    await callback.message.edit_text(
        "💼 *Хотите такого бота для своего бизнеса?*\n\n"
        "Этот бот сделан за 5 дней на Python + ИИ.\n\n"
        "Расскажите кратко:\n"
        "• Чем занимается ваш бизнес?\n"
        "• Что должен делать бот?\n\n"
        "Я передам запрос разработчику — он пришлёт расчёт:",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="← Отмена", callback_data="menu")]
        ]),
    )
    await callback.answer()


@dp.message(LeadState.waiting_description)
async def lead_description(message: Message, state: FSMContext):
    await state.clear()
    user = message.from_user
    username = f"@{user.username}" if user.username else f"id{user.id}"
    full_name = f"{user.first_name or ''} {user.last_name or ''}".strip() or "Без имени"

    owner_text = (
        f"🔥 Новый лид — @ZasSchoolBot (школа)!\n\n"
        f"👤 {full_name} ({username})\n"
        f"🔗 Написать: tg://user?id={user.id}\n\n"
        f"📝 Задача:\n{message.text}"
    )
    try:
        await bot.send_message(OWNER_ID, owner_text)
    except Exception as e:
        log.error(f"Lead notification failed: {e}")

    await message.answer(
        "✅ *Отлично! Запрос передан разработчику.*\n\n"
        "Он свяжется с вами в ближайший час — обсудит детали и пришлёт точный расчёт стоимости.\n\n"
        "_Разработка ботов от 25 000 ₽, срок 5-7 дней._",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="← Вернуться в меню", callback_data="menu")]
        ]),
    )


# ─── ЗАПУСК ───────────────────────────────────────────────────────────────────

async def main():
    log.info(f"Demo school bot '{SCHOOL_NAME}' starting...")
    await dp.start_polling(bot, skip_updates=True)


if __name__ == "__main__":
    asyncio.run(main())
