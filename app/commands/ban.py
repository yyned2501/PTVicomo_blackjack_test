from datetime import datetime, timedelta
from pyrogram import filters
from pyrogram.types import (
    Message,
    ChatPermissions,
)

from app import Client
from app.libs.decorators import auto_delete_message
from app.models import ASSession
from app.models.nexusphp import Users


@Client.on_message(filters.command("ban"))
@auto_delete_message()
async def ban(client: Client, message: Message):
    try:
        minutes = int(message.command[1])
    except:
        minutes = 60 * 24
    async with ASSession() as session:
        async with session.begin():
            async with Users.get_user_from_tgmessage(message) as user:
                if not user or user._class < 14:
                    return await message.reply("您没有此权限")
                if not message.reply_to_message:
                    return await message.reply("请回复一条消息")
                await client.restrict_chat_member(
                    message.chat.id,
                    message.reply_to_message.from_user.id,
                    ChatPermissions(),
                    datetime.now() + timedelta(minutes=minutes),
                )
                return await message.reply_to_message.reply(f"已禁言{minutes}分钟")


@Client.on_message(filters.command("unban"))
@auto_delete_message()
async def unban(client: Client, message: Message):
    async with ASSession() as session:
        async with session.begin():
            async with Users.get_user_from_tgmessage(message) as user:
                if not user or user._class < 14:
                    return await message.reply("您没有此权限")
                if not message.reply_to_message:
                    return await message.reply("请回复一条消息")
                await client.unban_chat_member(
                    message.chat.id, message.reply_to_message.from_user.id
                )
                return await message.reply_to_message.reply("解除禁言")
