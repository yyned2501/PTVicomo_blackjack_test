import pyrogram
from app import get_app
from config import GROUP_ID
import logging

logger = logging.getLogger("main")

ADMINS: dict[str, pyrogram.types.User] = {}


async def get_admin():
    app = get_app()
    async for m in app.get_chat_members(
        GROUP_ID[0], filter=pyrogram.enums.ChatMembersFilter.ADMINISTRATORS
    ):
        if m.custom_title:
            ADMINS[m.custom_title] = m.user
