import datetime
import asyncio
import json

from sqlalchemy import delete, select

from app import app, scheduler, redis_cli
from pyrogram import filters, Client
from pyrogram.types import (
    Message,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    CallbackQuery,
)

from app.libs.decorators import auto_delete_message
from app.models import ASSession
from app.normal_reply import USER_BIND_NONE, NOT_ENOUGH_BONUS
from app.models.nexusphp import BotBinds, Redpocket, RedpocketClaimed, Users
from config import GROUP_ID, POCKET_MAX, POCKET_MIN
from app.filters.custom_filters import CallbackDataFromFilter

lock = asyncio.Lock()

NOT_IN_RANGE = (
    "单个红包范围 : {min}-{max} ,请输入范围内的象草,您输入的红包单个红包象草为：{bonus}"
)
EXAMPLE = (
    "请参照以下格式:\n/{command} 象草 个数 红包口令\n`/{command} 20000 10 象岛越来越好`"
)
CREATE_REDPOCKET = """```{redpocket.content}
感谢{redpocket.from_uname}的{redpocket.pocket_type}红包:
象草: {redpocket.remain_bonus}/{redpocket.bonus}
数量: {redpocket.remain_count}/{redpocket.count}```"""
TYPES = {"redpocket": "拼手气", "luckypocket": "锦鲤"}
ACTION = "redpocket"


def create_keyboard(redpocket: Redpocket):
    reply_markup = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "点击领取红包",
                    callback_data=json.dumps(
                        {
                            "id": redpocket.id,
                            "a": ACTION,
                        }
                    ),
                ),
            ]
        ]
    )
    return reply_markup


def init_message(message: Message):
    try:
        command = message.command[0]
        bonus = int(message.command[1])
        count = int(message.command[2])
        password = " ".join([s for s in message.command[3:] if s != ""])
    except Exception:
        raise BaseException(f"格式有误! {EXAMPLE.format(command=command)}")
    except BaseException as e:
        raise BaseException(e)
    pb = round(bonus / count, 1)
    if pb > POCKET_MAX or pb < POCKET_MIN:
        raise BaseException(
            NOT_IN_RANGE.format(min=POCKET_MIN, max=POCKET_MAX, bonus=pb)
        )
    return bonus, count, password


async def qfz_bonus(client: Client, user: Users, bonus: int):
    if user.is_role(13):
        qfz_bonus = int(redis_cli.get("qfz_bonus"))
        if qfz_bonus > 0:
            user_qfz_bonus = min(qfz_bonus, bonus)
            qfz_bonus -= user_qfz_bonus
            redis_cli.set("qfz_bonus", qfz_bonus)
            await client.send_message(GROUP_ID[1], f"气氛组红包余额 {qfz_bonus}")
            bonus -= user_qfz_bonus
    return bonus


async def create_redpocket(client: Client, message: Message, type_: int):
    try:
        bonus, count, content = init_message(message)
    except BaseException as e:
        return await message.reply(e)
    async with ASSession() as session, session.begin():
        user = await Users.get_user_from_tgmessage(message)
        if not user.bot_bind:
            return await message.reply(USER_BIND_NONE)
        if user.seedbonus < bonus:
            return await message.reply(NOT_ENOUGH_BONUS)
        async with lock:
            redpocket = await Redpocket.create(
                user.id,
                user.bot_bind.telegram_account_username,
                bonus,
                count,
                content,
                type_,
            )
            message_str = CREATE_REDPOCKET.format(redpocket=redpocket)
            bonus = await qfz_bonus(client, user, bonus)
            await user.addbonus(-bonus, f"发红包{content}")
            return (
                await message.reply(
                    message_str, reply_markup=create_keyboard(redpocket)
                ),
                False,
            )


@app.on_message(filters.chat(GROUP_ID) & filters.command("redpocket_new"))
@auto_delete_message()
async def redpocket(client: Client, message: Message):
    return await create_redpocket(client, message, 0)


@app.on_message(filters.chat(GROUP_ID) & filters.command("luckypocket_new"))
@auto_delete_message()
async def luckypocket(client: Client, message: Message):
    return await create_redpocket(client, message, 1)


@Client.on_callback_query(CallbackDataFromFilter(ACTION))
async def ydx_set_callback(client: Client, callback_query: CallbackQuery):
    callback_query.from_user.id
    data: dict = json.loads(callback_query.data)
    redpocket_id = data.get("id", None)
    async with ASSession() as session, session.begin():
        async with lock:
            user = await Users.get_user_from_tg_id(callback_query.from_user.id)
            if not user.bot_bind:
                return await callback_query.answer(USER_BIND_NONE, True)
            redpocket = await session.get(Redpocket, redpocket_id)
            if not redpocket:
                return await callback_query.answer("红包不存在", True)
            if user.id in redpocket.claimed:
                return await callback_query.answer("请勿重复领取", True)
            bonus = await redpocket.get(user.bot_bind.telegram_account_id)
            if redpocket._pocket_type == 0:
                await user.addbonus(
                    bonus, f"领取红包 {redpocket.id}:{redpocket.content}"
                )
                await callback_query.answer(f"成功领取红包，增加{bonus}象草")
                if redpocket.remain_count == 0:
                    await session.execute(
                        delete(RedpocketClaimed).where(
                            RedpocketClaimed.redpocket_id == redpocket.id
                        )
                    )
                    await session.delete(redpocket)
                    await callback_query.message.delete()
            elif redpocket._pocket_type == 1:
                await callback_query.answer(f"成功参加锦鲤红包抽奖")
                if redpocket.remain_count == 0:
                    await session.execute(
                        delete(RedpocketClaimed).where(
                            RedpocketClaimed.redpocket_id == redpocket.id
                        )
                    )
                    await session.delete(redpocket)
                    await callback_query.message.delete()
            await callback_query.edit_message_text(
                message_str=CREATE_REDPOCKET.format(redpocket=redpocket),
                reply_markup=create_keyboard(redpocket),
            )
