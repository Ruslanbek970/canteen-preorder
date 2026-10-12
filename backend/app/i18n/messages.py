"""Notification texts in the user's language (SPEC 7.11). Unknown languages fall back to ru."""

from dataclasses import dataclass

LANGUAGES = ("ru", "kk", "en")


@dataclass(frozen=True)
class Message:
    title: str
    body: str


# kind -> language -> (title, body). Bodies use str.format placeholders.
TEMPLATES: dict[str, dict[str, tuple[str, str]]] = {
    "order_paid": {
        "ru": ("Заказ {number} оплачен", "Ждём вас в {slot}. Покажите QR-код на выдаче."),
        "kk": (
            "{number} тапсырысы төленді",
            "Беру уақыты: {slot}. Беру орнында QR-кодты көрсетіңіз.",
        ),
        "en": ("Order {number} is paid", "See you at {slot}. Show the QR code at pickup."),
    },
    "order_ready": {
        "ru": ("Заказ {number} готов", "Заберите на полке {shelf}."),
        "kk": ("{number} тапсырысы дайын", "{shelf} сөреден алыңыз."),
        "en": ("Order {number} is ready", "Pick it up from shelf {shelf}."),
    },
    "order_cancelled": {
        "ru": ("Заказ {number} отменён", "Если заказ был оплачен, деньги вернутся."),
        "kk": ("{number} тапсырысы жойылды", "Тапсырыс төленген болса, ақша қайтарылады."),
        "en": ("Order {number} is cancelled", "If you paid for it, the money will be returned."),
    },
    "slot_reminder": {
        "ru": (
            "Скоро выдача: {number}",
            "Ваш слот начинается в {slot}. Не забудьте забрать заказ.",
        ),
        "kk": ("Жақында беру: {number}", "Слоттың басталуы: {slot}. Тапсырысты алуды ұмытпаңыз."),
        "en": ("Pickup soon: {number}", "Your slot starts at {slot}. Don't forget your order."),
    },
    "leftover_discount": {
        "ru": (
            "Скидка {percent}% на {dish}",
            "Сегодня до {until} в «{canteen}». Успейте заказать.",
        ),
        "kk": (
            "{dish} үшін {percent}% жеңілдік",
            "Бүгін {until} дейін, «{canteen}». Тапсырыс беріп үлгеріңіз.",
        ),
        "en": ("{percent}% off {dish}", "Today until {until} at {canteen}. Order while it lasts."),
    },
}


def render(kind: str, language: str | None, **params: object) -> Message:
    texts = TEMPLATES[kind]
    title, body = texts.get(language or "ru", texts["ru"])
    return Message(title=title.format(**params), body=body.format(**params))


BOT_TEXTS: dict[str, dict[str, str]] = {
    "start_help": {
        "ru": "Здравствуйте! Чтобы получать уведомления о заказах, откройте профиль в приложении, "
        "нажмите «Привязать Telegram» и отправьте мне код: /start 123456",
        "kk": "Сәлеметсіз бе! Тапсырыс туралы хабарлама алу үшін қолданбада профильді ашып, "
        "«Telegram байланыстыру» батырмасын басыңыз да, кодты жіберіңіз: /start 123456",
        "en": "Hello! To get order notifications, open your profile in the app, tap "
        "“Link Telegram” and send me the code: /start 123456",
    },
    "linked": {
        "ru": "Готово, {name}! Теперь уведомления о заказах будут приходить сюда. "
        "/orders — активные заказы, /stop — отвязать.",
        "kk": "Дайын, {name}! Енді тапсырыс туралы хабарламалар осында келеді. "
        "/orders — белсенді тапсырыстар, /stop — ажырату.",
        "en": "Done, {name}! Order notifications will now come here. "
        "/orders — active orders, /stop — unlink.",
    },
    "linked_already": {
        "ru": "Этот чат уже привязан. /orders — активные заказы, /stop — отвязать.",
        "kk": "Бұл чат байланыстырылған. /orders — белсенді тапсырыстар, /stop — ажырату.",
        "en": "This chat is already linked. /orders — active orders, /stop — unlink.",
    },
    "bad_code": {
        "ru": "Код не подошёл или устарел. Получите новый в профиле приложения.",
        "kk": "Код жарамсыз немесе ескірген. Қолданба профилінен жаңасын алыңыз.",
        "en": "The code is wrong or expired. Get a new one in your profile in the app.",
    },
    "not_linked": {
        "ru": "Чат ещё не привязан к аккаунту. Получите код в профиле и отправьте /start <код>.",
        "kk": "Чат әлі аккаунтқа байланыстырылмаған. Профильден код алып, /start <код> жіберіңіз.",
        "en": "This chat is not linked yet. Get a code in your profile and send /start <code>.",
    },
    "no_orders": {
        "ru": "Активных заказов нет.",
        "kk": "Белсенді тапсырыстар жоқ.",
        "en": "No active orders.",
    },
    "orders_title": {
        "ru": "Ваши активные заказы:",
        "kk": "Белсенді тапсырыстарыңыз:",
        "en": "Your active orders:",
    },
    "shelf": {"ru": ", полка {shelf}", "kk": ", {shelf} сөре", "en": ", shelf {shelf}"},
    "stopped": {
        "ru": "Чат отвязан, уведомления сюда больше не придут.",
        "kk": "Чат ажыратылды, хабарламалар енді мұнда келмейді.",
        "en": "Chat unlinked, notifications will no longer come here.",
    },
    "help": {
        "ru": "Команды: /orders — активные заказы, /stop — отвязать чат.",
        "kk": "Командалар: /orders — белсенді тапсырыстар, /stop — чатты ажырату.",
        "en": "Commands: /orders — active orders, /stop — unlink this chat.",
    },
    "status_pending_payment": {
        "ru": "ждёт оплаты",
        "kk": "төлемді күтуде",
        "en": "awaiting payment",
    },
    "status_paid": {"ru": "оплачен", "kk": "төленді", "en": "paid"},
    "status_cooking": {"ru": "готовится", "kk": "дайындалуда", "en": "cooking"},
    "status_ready": {"ru": "готов", "kk": "дайын", "en": "ready"},
}


def bot_text(key: str, language: str | None, **params: object) -> str:
    texts = BOT_TEXTS[key]
    return texts.get(language or "ru", texts["ru"]).format(**params)
