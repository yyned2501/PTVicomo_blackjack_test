import random
from datetime import datetime

from sqlalchemy import select
from pyrogram import filters, Client
from pyrogram.types import Message

from app.libs.decorators import auto_delete_message
from app.models import ASSession
from app.models.nexusphp import BotBinds, TgMessages, UserRoles, Users
from config import GROUP_ID, GIFT_RATE


def time_difference_in_seconds(date_time):
    current_time = datetime.now()
    specified_time = datetime.strptime(date_time, "%Y-%m-%d %H:%M:%S")
    time_diff = (current_time - specified_time).total_seconds()
    return time_diff


@Client.on_message(filters.chat(GROUP_ID[1]) & filters.command("water"))
@auto_delete_message()
async def qfz_water(client: Client, message: Message):
    async with ASSession() as session:
        async with session.begin():
            tgmessages = (
                (
                    await session.execute(
                        select(TgMessages)
                        .join(
                            BotBinds, TgMessages.tg_id == BotBinds.telegram_account_id
                        )
                        .join(UserRoles, BotBinds.uid == UserRoles.uid)
                        .where(UserRoles.role_id == 13)
                        .order_by(TgMessages.month_count.desc())
                    )
                )
                .scalars()
                .all()
            )
            ret = "本月任务情况"
            for tgmess in tgmessages:
                bonus = (tgmess.month_count - 450) * 400 + 100000
                ret += f"\n{tgmess.tg_name} 水群 {tgmess.month_count} 条，预计工资 {bonus if tgmess.month_count>450 else 0} 象草"
            return await message.reply(ret)


@Client.on_message(filters.chat(GROUP_ID) & filters.command("water"))
@auto_delete_message()
async def water(client: Client, message: Message):
    async with ASSession() as session:
        async with session.begin():
            tgmessages = (
                (
                    await session.execute(
                        select(TgMessages)
                        .where(TgMessages.day_count > 0)
                        .order_by(TgMessages.day_count.desc())
                        .limit(10)
                    )
                )
                .scalars()
                .all()
            )
            ret = "今日水群排行"
            for tgmess in tgmessages:
                ret += f"\n{tgmess.tg_name} 水群 {tgmess.day_count} 条"
            return await message.reply(ret)


@Client.on_message(filters.chat(GROUP_ID) & filters.text & ~filters.bot, group=1)
@auto_delete_message(delete_from_message=False)
async def message_count(client: Client, message: Message):
    if message.content.startswith(("/", "+")):
        return
    r = random.random()
    async with ASSession() as session:
        async with session.begin():
            tgmess = await TgMessages.get_tgmess_from_tgmessage(message)
            tgmess.send_message()
            if r < GIFT_RATE:
                user = await Users.get_user_from_tgmessage(message)
                if user:
                    bonus = int(r / GIFT_RATE * 500)
                    if bonus == 0:
                        bonus = 10000
                    await user.addbonus(bonus, "水群随机奖励")
                    return await message.reply(f"你的发言感动了岛神，赐予你{bonus}象草")


@Client.on_deleted_messages(
    filters.chat(GROUP_ID) & filters.text & ~filters.bot, group=1
)
async def message_discount(client: Client, message: Message):
    if message.content.startswith(("/", "+")):
        return
    if time_difference_in_seconds(message.date) < 3600:
        async with ASSession() as session:
            async with session.begin():
                tgmess = await TgMessages.get_tgmess_from_tgmessage(message)
                tgmess.send_message(-1)
