import json
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
from app import redis_cli
from config import GROUP_ID, SENDER_EMAIL, SENDER_PASSWORD
from app.libs.mail import Mail

BIND_REQUIRE = "请输入`/bind passkey`绑定账号"
BIND_SUCCESS = "绑定成功"
BIND_FAIL = "绑定失败，请输入正确的passkey"
BINDED = "您已经绑定了"
BIND_PERMITTION = "请勿在群聊中绑定账号"
UNBIND_SUCCESS = "解绑成功"
UNBINDED = "您还没有绑定账号"
BINDUSER_REQUIRE = "请输入`/binduser 用户名`绑定账号"
BINDUSER_FAIL = "绑定失败，请输入正确的用户名"
BINDUSER_SUCCESS = (
    "验证码已发送至您绑定的邮箱，请在2分钟内输入验证码\n如未收到请检查垃圾箱"
)
EXPIRE_SEC = 300


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


@Client.on_message(filters.command(["bind", "binduser"]))
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


@Client.on_message(filters.private & filters.command("binduser"))
@auto_delete_message(delay=EXPIRE_SEC)
async def binduser(client: Client, message: Message):
    if len(message.command) == 1:
        return await message.reply(BINDUSER_REQUIRE)
    username = message.command[1]
    if redis_cli.get(f"binduser:{message.from_user.id}"):
        return await message.reply("您已经发送了验证码，请在2分钟后重试")
    async with ASSession() as session:
        async with session.begin():
            user = await Users.get_user_from_tgmessage(message)
            if user:
                return await message.reply(BINDED)
            user = await Users.get_user_by_username(username)
            if not user:
                return await message.reply(BINDUSER_FAIL)
            mail = Mail(SENDER_EMAIL, SENDER_PASSWORD)
            code = await mail.send_verification_email(user.email)
            if code:
                redis_cli.set(
                    f"binduser:{message.from_user.id}",
                    json.dumps({"username": user.username, "code": code}),
                    ex=EXPIRE_SEC,
                )
                return await message.reply(BINDUSER_SUCCESS)
            return await message.reply("邮件发送失败，请稍后重试")


async def code_filter(_, __, message: Message):
    # 检查尝试次数
    MAX_COUNT = 5
    redis_data = redis_cli.get(f"binduser:{message.from_user.id}")
    if redis_data:
        attempt_key = f"bind_attempts:{message.from_user.id}"
        if int(redis_cli.get(attempt_key) or 0) >= MAX_COUNT:
            await message.reply(f"您已输入错误超过{MAX_COUNT}次，请稍后重试")
            return False
        data = json.loads(redis_data)
        if message.text == data.get("code", ""):
            redis_cli.delete(attempt_key)  # 验证成功清除计数器
            return True
        # 验证失败增加计数器
        count = redis_cli.incr(attempt_key)
        redis_cli.expire(attempt_key, EXPIRE_SEC)  # 5分钟过期
        await message.reply(f"输入错误[{count}/{MAX_COUNT}]次")
    return False


@Client.on_message(filters.private & filters.create(code_filter))
@auto_delete_message(delay=60)
async def binduser_code(client: Client, message: Message):
    redis_data = redis_cli.get(f"binduser:{message.from_user.id}")
    if not redis_data:
        return await message.reply("验证码已过期，请重新获取")
    data = json.loads(redis_data)
    username = data.get("username", None)
    if not username:
        return await message.reply("验证数据无效，请重新获取验证码")
    tg_id = message.from_user.id
    async with ASSession() as session:
        async with session.begin():
            user = await Users.get_user_by_username(username)
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
            redis_cli.delete(f"binduser:{message.from_user.id}")
            return await message.reply("绑定成功")
