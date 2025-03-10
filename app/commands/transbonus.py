from jinja2 import Template
from pyrogram import filters, Client
from pyrogram.types.messages_and_media import Message

from app import app
from app.normal_reply import USER_BIND_NONE, NOT_ENOUGH_BONUS
from app.models import ASSession
from app.models.nexusphp import Users
from config import TAX_RATE, TRANS_MAX, TRANS_MIN

NOT_IN_RANGE = "转账范围 : {{min}}-{{max}} ,请输入范围内的象草"
REPLY_USER_BIND_NONE = "对方没有绑定账号，无法转账"
TRANSBONUS_SUCCESS = "```转账成功\n {{from_user}} 给 {{to_user}} 发送了 {{bonus}} 象草\n收取 {{rate*100}}% 税金，最终到账 {{bonus-tax}} 象草```"


@app.on_message(filters.reply & filters.regex(r"^\+(\d+)\s*$"))
async def transbonus(client: Client, message: Message):
    matches = message.matches
    bonus = int(matches[0].group(1))
    if bonus > TRANS_MAX or bonus < TRANS_MIN:
        return await message.reply(
            Template(NOT_IN_RANGE).render(min=TRANS_MIN, max=TRANS_MAX)
        )
    async with ASSession() as session:
        async with session.begin():
            from_user = await Users.get_user_from_tgmessage(message)
            if not from_user:
                return await message.reply(USER_BIND_NONE)
            to_user = await Users.get_user_from_tgmessage(message.reply_to_message)
            if not to_user:
                return await message.reply(REPLY_USER_BIND_NONE)
            if from_user.seedbonus < bonus:
                return await message.reply(NOT_ENOUGH_BONUS)
            await from_user.addbonus(-bonus, f"转账给 {to_user.username}")
            tax = bonus * TAX_RATE
            await to_user.addbonus(bonus - tax, f"收到 {from_user.username} 转账")
            return await message.reply(
                Template(TRANSBONUS_SUCCESS).render(
                    from_user=from_user.bot_bind.telegram_account_username,
                    to_user=to_user.bot_bind.telegram_account_username,
                    bonus=bonus,
                    tax=tax,
                    rate=TAX_RATE,
                )
            )


@app.on_message(filters.reply & filters.regex(r"^\-(\d+)\s*$"))
async def transbonus_(client: Client, message: Message):
    matches = message.matches
    bonus = int(matches[0].group(1))
    if bonus > TRANS_MAX or bonus < TRANS_MIN:
        return await message.reply(
            Template(NOT_IN_RANGE).render(min=TRANS_MIN, max=TRANS_MAX)
        )
    async with ASSession() as session:
        async with session.begin():
            user = await Users.get_user_from_tgmessage(message)
            if not user or user._class < 14:
                return await message.reply("您没有此权限")
            else:
                return await message.reply_to_message.reply(f"已扣除{bonus:,}象草")
