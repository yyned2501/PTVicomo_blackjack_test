from pyrogram import filters, Client
from pyrogram.types.messages_and_media import Message
from app.libs.decorators import auto_delete_message
from app.models import ASSession
from app.models.nexusphp import Users


CANCEL2FA_SUCCESS = "您已取消两步验证"
NON_CANCEL2FA = "您还没有启用两步验证"
UNBINDED = "您还没有绑定账号"


@Client.on_message(filters.command("cancel2fa"))
@auto_delete_message()
async def cancel2fa(client: Client, message: Message):
    async with ASSession() as session:
        async with session.begin():
            user = await Users.get_user_from_tgmessage(message)
            if user:
                if len(user.two_step_secret) > 0:
                    user.two_step_secret = ""
                    return await message.reply(CANCEL2FA_SUCCESS)
                else:
                    return await message.reply(NON_CANCEL2FA)
            else:
                return await message.reply(UNBINDED)
