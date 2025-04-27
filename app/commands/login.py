from sqlalchemy import select
from pyrogram import filters, Client
from pyrogram.types.messages_and_media import Message
from app.libs.decorators import auto_delete_message
from app.models import ASSession
from pyrogram.types import (
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)
from app.models.nexusphp import Settings, Users
from app.normal_reply import USER_BIND_NONE
from sqlalchemy.ext.asyncio import AsyncSession

BIND_SUCCESS = "绑定成功"
BIND_FAIL = "绑定成功"
BINDED = "您已经绑定了"
LOGIN_PERMITTION = "请勿在群聊中获取登陆连接"
UNBIND_SUCCESS = "解绑成功"
UNBINDED = "您还没有绑定账号"


async def get_setting(name: str, session: AsyncSession) -> str:
    setting = (
        await session.execute(select(Settings).filter(Settings.name == name))
    ).scalar_one_or_none()
    if setting:
        return setting.value


@Client.on_message(filters.private & filters.command("login"))
@auto_delete_message()
async def secret_login(client: Client, message: Message):
    async with ASSession() as session:
        async with session.begin():
            user = await Users.get_user_from_tgmessage(message)
            if not user:
                return await message.reply(USER_BIND_NONE)
            login_secret = await get_setting("security.login_secret", session)
            baseurl = await get_setting("basic.BASEURL", session)
            if login_secret:
                return await message.reply(
                    # f"https://{baseurl}/login.php?secret={login_secret}"
                    f"https://{baseurl}/{login_secret}/{user.passkey}"
                )


@Client.on_message(filters.command("login"))
@auto_delete_message()
async def group_login(client: Client, message: Message):
    name = (await client.get_me()).username
    return await message.reply(
        LOGIN_PERMITTION,
        reply_markup=InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(
                        "点击私聊机器人获取登陆连接!", url=f"https://t.me/{name}"
                    )
                ],
            ]
        ),
    )
