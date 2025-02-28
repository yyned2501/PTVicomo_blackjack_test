from pyrogram.types.messages_and_media import Message
from app.models.nexusphp import BotBinds, Users
from sqlalchemy import select
from app.models import ASSession


class User:
    def __init__(self, message: Message) -> None:
        if not message.from_user:
            if message.sender_chat:
                message.from_user = message.sender_chat
                message.from_user.first_name = message.sender_chat.title
                message.from_user.last_name = None
            if message.author_signature:
                from app.commands import ADMINS

                message.from_user = ADMINS[message.author_signature]
                message.from_user.first_name = message.author_signature
                message.from_user.last_name = None
        self.message = message
        self.tg_id = message.from_user.id
        self.tg_name = " ".join(
            [
                name
                for name in [message.from_user.first_name, message.from_user.last_name]
                if name
            ]
        )

    async def _async_init(self):
        self.session = ASSession()
        self.botbind = (
            (
                await self.session.execute(
                    select(BotBinds).filter(BotBinds.telegram_account_id == self.tg_id)
                )
            )
            .scalars()
            .one_or_none()
        )
        if self.botbind:
            self.user = self.botbind.user
            if self.botbind.telegram_account_username != self.tg_name:
                self.botbind.telegram_account_username = self.tg_name

    async def bind(self, passkey: str):
        user = (
            await self.session.execute(select(Users).filter(Users.passkey == passkey))
        ).scalar_one_or_none()
        if user:
            if user.bot_bind:
                user.bot_bind.uid = user.id
                user.bot_bind.telegram_account_id = self.tg_id
                user.bot_bind.telegram_account_username = self.tg_name
            else:
                self.botbind = BotBinds(
                    uid=user.id,
                    telegram_account_id=self.tg_id,
                    telegram_account_username=self.tg_name,
                )
                self.session.add(self.botbind)
            return True

    async def unbind(self):
        await self.session.delete(self.botbind)

    def cancel2fa(self):
        self.user.two_step_secret = ""

    async def __aenter__(self):
        await self._async_init()
        return self

    async def __aexit__(self, exc_type, exc_value, traceback):
        pass
