from app import app
from pyrogram import filters, Client
from jinja2 import Template
from pyrogram.types.messages_and_media import Message
from app.libs.decorators import auto_delete_message
from app.models import ASSession
from app.models.nexusphp import Users
from app.normal_reply import USER_BIND_NONE
from pyrogram.types import (
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)
from config import GROUP_ID

INFO_ALL = """账号信息如下：

UID: {{user.id}}
用户名：{{user.username}}
等级：{% if user.role_names %}{{user.role_names}}{% else %}{{user.class_name}}{% endif %}
上传量：{{user.uploaded_str}}
下载量：{{user.downloaded_str}}
分享率：{{user.rate}}
魔力值：{{user.seedbonus}}"""


@app.on_message(filters.private & filters.command("info"))
@auto_delete_message()
async def secret_info(client: Client, message: Message):
    async with ASSession() as session:
        async with session.begin():
            user = await Users.get_user_from_tgmessage(message)
            if not user:
                return await message.reply(USER_BIND_NONE)
            return await message.reply(Template(INFO_ALL).render(user=user))


@app.on_message(filters.chat(GROUP_ID) & filters.reply & filters.command("info"))
@auto_delete_message(delete_from_message_immediately=True)
async def group_reply_info(client: Client, message: Message):
    async with ASSession() as session:
        async with session.begin():
            user = await Users.get_user_from_tgmessage(message)
            if user and user._class >= 14:
                reply_user = await Users.get_user_from_tgmessage(
                    message.reply_to_message
                )
                if not reply_user:
                    await client.send_message(message.from_user.id, "Ta还没有绑定账号")
                    return
                await client.send_message(
                    message.from_user.id,
                    Template(INFO_ALL).render(user=reply_user),
                )


@app.on_message(filters.chat(GROUP_ID) & filters.command("info"))
@auto_delete_message()
async def group_info(client: Client, message: Message):
    async with ASSession() as session:
        async with session.begin():
            user = await Users.get_user_from_tgmessage(message)
            if not user:
                return await message.reply(USER_BIND_NONE)
            name = (await client.get_me()).username
            return await message.reply(
                f"您有 {user.seedbonus} 象草",
                reply_markup=InlineKeyboardMarkup(
                    [
                        [
                            InlineKeyboardButton(
                                "私聊机器人可获取更多信息!",
                                url=f"https://t.me/{name}",
                            )
                        ],
                    ]
                ),
            )
