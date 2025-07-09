from sqlalchemy import select
from pyrogram import filters, Client
from pyrogram.types import (
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)
from pyrogram.types.messages_and_media import Message

from app.libs.decorators import auto_delete_message
from app.models import ASSession
from app.models.nexusphp import Users, BotBinds
from config import GROUP_ID


BIND_REQUIRE = "请输入`/bind passkey`绑定账号"
BIND_SUCCESS = "绑定成功"
BIND_FAIL = "绑定失败，请输入正确的passkey"
BINDED = "您已经绑定了"
BIND_PERMITTION = "请勿在群聊中绑定账号"
UNBIND_SUCCESS = "解绑成功"
UNBINDED = "您还没有绑定账号"


@Client.on_message(filters.private & filters.command("bind"))
@auto_delete_message(delete_from_message_immediately=True)
async def secret_bind(client: Client, message: Message):
    if len(message.command) == 1:
        return await message.reply(BIND_REQUIRE)
    passkey = message.command[1]
    async with ASSession() as session:
        async with session.begin():
            user = await Users.get_user_from_tgmessage(message)
            if user:
                return await message.reply(BINDED)
            if await Users.bind(passkey, message):
                return await message.reply(BIND_SUCCESS)
            return await message.reply(BIND_FAIL)


@Client.on_message(filters.command("bind"))
@auto_delete_message()
async def group_bind(client: Client, message: Message):
    await message.delete()
    name = (await client.get_me()).username
    return await message.reply(
        BIND_PERMITTION,
        reply_markup=InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(
                        "点击私聊机器人绑定!", url=f"https://t.me/{name}"
                    )
                ],
            ]
        ),
    )


@Client.on_message(filters.chat(GROUP_ID[1]) & filters.command("bindid"))
@auto_delete_message()
async def bind_id(client: Client, message: Message):
    if len(message.command) == 1:
        return await message.reply(BIND_REQUIRE)
    try:
        userid = message.command[1]
        tg_id = message.command[2]
    except:
        return await message.reply("格式有误 /bindid userid tgid")
    async with ASSession() as session:
        async with session.begin():
            user = (
                await session.execute(select(Users).filter(Users.id == userid))
            ).scalar_one_or_none()
            if user:
                if user.bot_bind:
                    user.bot_bind.uid = user.id
                    user.bot_bind.telegram_account_id = tg_id
                else:
                    user.bot_bind = BotBinds(
                        uid=user.id,
                        telegram_account_id=tg_id,
                        telegram_account_username="",
                    )
                    session.add(user.bot_bind)
            else:
                return await message.reply(f"没有查询到用户{userid}")
        await message.reply(f"绑定用户{user.username}成功")


@Client.on_message(filters.command("unbind"))
@auto_delete_message()
async def unbind(client: Client, message: Message):
    async with ASSession() as session:
        async with session.begin():
            user = await Users.get_user_from_tgmessage(message)
            if user:
                await user.unbind()
                await message.reply(UNBIND_SUCCESS)
            else:
                await message.reply(UNBINDED)
