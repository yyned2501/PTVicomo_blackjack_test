from app import app
from pyrogram import filters, Client
from pyrogram.types import Message
from config import CHANNEL_ID


async def channel_message(_, __, m: Message):
    return bool(m.sender_chat and m.sender_chat.id == CHANNEL_ID)


@app.on_message(filters.create(channel_message) & filters.regex(r"^新的官种"))
async def auto_unpin(client: Client, message: Message):
    await message.unpin()
