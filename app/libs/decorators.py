import json
import time
from typing import Callable, Coroutine
from pyrogram.types import Message
from app import redis_cli, Client


def s_delete_message(message: Message, delay=0):
    if message and not message.empty:
        data = {
            "chatid": message.chat.id,
            "messageid": message.id,
            "deletetime": int(time.time()) + delay,
        }
        redis_cli.set(
            f"DM:{message.chat.id}:{message.id}",
            json.dumps(data),
        )


def auto_delete_message(
    delay=30, delete_from_message=True, delete_from_message_immediately=False
):
    def decorator(
        func: Callable[
            [Client, Message],
            Coroutine[None, None, Message | tuple[Message, bool] | None],
        ]
    ):
        async def wrapper(client, message: Message):
            sent_message = await func(client, message)
            if isinstance(sent_message, tuple):
                sent_message, delete_message = sent_message
                if not delete_message:
                    return
            if delete_from_message_immediately:
                await message.delete()
            if delete_from_message and not delete_from_message_immediately:
                s_delete_message(message, delay)
            if sent_message:
                s_delete_message(sent_message, delay)

        return wrapper

    return decorator
