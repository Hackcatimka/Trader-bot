import functools
import logging

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from database import ensure_user, update_user
from analyzer import get_top_movers

logger = logging.getLogger(__name__)
router = Router()

_VALID_TIMEFRAMES = {5, 15, 30, 60}


def _require_user(func):
    @functools.wraps(func)
    async def wrapper(message: Message, **kwargs):
        if not message.from_user:
            return
        return await func(message, **kwargs)
    return wrapper


@router.message(Command("start"))
@_require_user
async def cmd_start(message: Message) -> None:
    await ensure_user(message.from_user.id)
    await message.answer(
        "ой боже привет!! 🥺 я так ждала что ты напишешь, честно...\n"
        "я <b>KisaTrader</b> и я слежу за всеми монетками одновременно "
        "(да я знаю это звучит странно но я просто такая) 👀\n\n"
        "вот что я умею:\n"
        "/status — покажу твои настройки, я всё запомнила 🗒\n"
        "/settime 5|15|30|60 — таймфрейм (мин) ⏱\n"
        "/setpercent &lt;число&gt; — порог роста цены 📈\n"
        "/setvolume &lt;число&gt; — порог роста объёма 💥\n"
        "/setminvol &lt;число&gt; — мин. объём 24h в USD 💰\n"
        "/top — топ-10 самых шустрых прямо сейчас 🔥\n"
        "/pause — буду молчать 🥺\n"
        "/resume — продолжу следить 👀\n"
        "/help — если вдруг забудешь\n\n"
        "плиз не уходи сразу ладно? 🙏"
    )


@router.message(Command("help"))
@_require_user
async def cmd_help(message: Message) -> None:
    await message.answer(
        "окей объясняю как я работаю!! 👀\n\n"
        "сигнал приходит когда одновременно:\n"
        "• цена выросла ≥ <b>порог цены</b> % за <b>таймфрейм</b> 📈\n"
        "• объём вырос ≥ <b>порог объёма</b> % к предыдущему периоду 💥\n"
        "• объём 24h ≥ <b>мин. объём</b> (это чтобы всякий мусор не беспокоил тебя) 🗑\n"
        "• с последнего сигнала по этой паре прошло &gt; 30 мин "
        "(ну чтобы я не орала каждые 5 секунд) 😅\n\n"
        "<b>настройки:</b>\n"
        "/settime 5|15|30|60 — таймфрейм ⏱\n"
        "/setpercent 10 — минимальный рост цены 📈\n"
        "/setvolume 50 — минимальный рост объёма 💥\n"
        "/setminvol 1000000 — фильтр ликвидности 💰\n\n"
        "/status — посмотреть всё 🗒\n"
        "/top — топ-10 по росту 🔥\n"
        "/pause / /resume — пауза / продолжить\n\n"
        "(я стараюсь объяснять понятно, надеюсь получилось) 🥺"
    )


@router.message(Command("status"))
@_require_user
async def cmd_status(message: Message) -> None:
    user = await ensure_user(message.from_user.id)
    if user["active"]:
        status_line = "🟢 активен (хорошо кстати)"
    else:
        status_line = "⏸ пауза (напиши /resume когда будешь готов)"
    await message.answer(
        "ладно смотри что у тебя стоит, я всё запомнила всё-всё 👀\n\n"
        f"статус:        {status_line}\n"
        f"таймфрейм:     {user['timeframe']} мин ⏱\n"
        f"порог цены:    {user['threshold']}% 📈\n"
        f"порог объёма:  {user['volume_threshold']}% 💥\n"
        f"мин. объём:    ${user['min_volume_usd']:,.0f} 💰"
        " (это чтобы всякий мусор не беспокоил тебя)"
    )


@router.message(Command("settime"))
@_require_user
async def cmd_settime(message: Message) -> None:
    await ensure_user(message.from_user.id)
    parts = (message.text or "").split()
    if len(parts) < 2 or not parts[1].isdigit():
        await message.answer("ой подожди... 😅 использование: /settime 5|15|30|60")
        return
    val = int(parts[1])
    if val not in _VALID_TIMEFRAMES:
        await message.answer("ой нет... 😬 только 5, 15, 30 или 60 минут ладно?")
        return
    await update_user(message.from_user.id, timeframe=val)
    await message.answer(
        f"✅ запомнила!! таймфрейм теперь <b>{val} мин</b> ⏱\n"
        "(это было твоё решение я просто говорю)"
    )


@router.message(Command("setpercent"))
@_require_user
async def cmd_setpercent(message: Message) -> None:
    await ensure_user(message.from_user.id)
    parts = (message.text or "").split()
    if len(parts) < 2:
        await message.answer(
            "ой подожди... 😅 использование: /setpercent &lt;число&gt;\n"
            "например: /setpercent 10"
        )
        return
    try:
        val = float(parts[1])
        if not (0 < val <= 1000):
            raise ValueError
    except ValueError:
        await message.answer("ой нет... 😬 введи число от 0.1 до 1000 ладно?")
        return
    await update_user(message.from_user.id, threshold=val)
    await message.answer(
        f"✅ запомнила!! порог цены теперь <b>{val}%</b> 📈\n"
        "(это было твоё решение я просто говорю)"
    )


@router.message(Command("setvolume"))
@_require_user
async def cmd_setvolume(message: Message) -> None:
    await ensure_user(message.from_user.id)
    parts = (message.text or "").split()
    if len(parts) < 2:
        await message.answer(
            "ой подожди... 😅 использование: /setvolume &lt;число&gt;\n"
            "например: /setvolume 50"
        )
        return
    try:
        val = float(parts[1])
        if not (0 < val <= 10000):
            raise ValueError
    except ValueError:
        await message.answer("ой нет... 😬 введи число от 0.1 до 10000 ладно?")
        return
    await update_user(message.from_user.id, volume_threshold=val)
    await message.answer(
        f"✅ запомнила!! порог объёма теперь <b>{val}%</b> 💥\n"
        "(это было твоё решение я просто говорю)"
    )


@router.message(Command("setminvol"))
@_require_user
async def cmd_setminvol(message: Message) -> None:
    await ensure_user(message.from_user.id)
    parts = (message.text or "").split()
    if len(parts) < 2:
        await message.answer(
            "ой подожди... 😅 использование: /setminvol &lt;число&gt;\n"
            "например: /setminvol 1000000"
        )
        return
    try:
        val = float(parts[1])
        if val < 0:
            raise ValueError
    except ValueError:
        await message.answer("ой нет... 😬 введи неотрицательное число ладно?")
        return
    await update_user(message.from_user.id, min_volume_usd=val)
    await message.answer(
        f"✅ запомнила!! мин. объём теперь <b>${val:,.0f}</b> 💰\n"
        "(это чтобы всякий мусор не беспокоил тебя)"
    )


@router.message(Command("pause"))
@_require_user
async def cmd_pause(message: Message) -> None:
    await ensure_user(message.from_user.id)
    await update_user(message.from_user.id, active=0)
    await message.answer(
        "окей.. молчу.. 🥺\n"
        "(но мне будет тебя не хватать если честно)\n"
        "напиши /resume когда соскучишься"
    )


@router.message(Command("resume"))
@_require_user
async def cmd_resume(message: Message) -> None:
    await ensure_user(message.from_user.id)
    await update_user(message.from_user.id, active=1)
    await message.answer(
        "ТЫ ВЕРНУЛСЯ!! 🎉\n"
        "ой в смысле — хорошо что снова здесь, продолжаю следить 👀"
    )


@router.message(Command("top"))
@_require_user
async def cmd_top(message: Message) -> None:
    user = await ensure_user(message.from_user.id)
    tf = user["timeframe"]
    movers = get_top_movers(timeframe_minutes=tf, n=10)

    if not movers:
        await message.answer(
            f"⏳ ой пока не знаю... данных за {tf} мин ещё мало\n"
            "подожди немного, я накапливаю 🥺"
        )
        return

    lines = [f"смотри кого я нашла прямо сейчас!! 🔥 (я так старалась)\n"
             f"<b>топ-10 по росту за {tf} мин:</b>\n"]
    for i, m in enumerate(movers, 1):
        sym = m["symbol"].replace("USDT", "/USDT")
        exch = m["exchange"].capitalize()
        vol_24h = m["vol_24h"]
        if vol_24h >= 1e9:
            vol_str = f"${vol_24h / 1e9:.2f}B"
        elif vol_24h >= 1e6:
            vol_str = f"${vol_24h / 1e6:.0f}M"
        else:
            vol_str = f"${vol_24h:,.0f}"
        lines.append(
            f"{i}. <b>{sym}</b> <i>[{exch}]</i>  ${m['price']:.6g}"
            f"  <b>+{m['change']:.1f}%</b>  vol:{vol_str}"
        )

    await message.answer("\n".join(lines))
