import asyncio
from typing import Callable, Coroutine
from pyrogram.types import Message
from app import Client


def s_delete_message(message: Message, sleep_time=0):
    async def delayed_delete(message: Message, sleep_time=0):
        if message:
            await asyncio.sleep(sleep_time)
            await message.delete()

    return asyncio.create_task(delayed_delete(message, sleep_time))


def auto_delete_message(
    delay=30, delete_from_message=True, delete_from_message_immediately=False
):
    def decorator(
        func: Callable[
            [Client, Message],
            Coroutine[None, None, Message | tuple[Message, bool] | None],
        ],
    ):
        async def wrapper(client, message: Message):
            sent_message = await func(client, message)
            if delete_from_message_immediately:
                await message.delete()
            if delete_from_message and not delete_from_message_immediately:
                s_delete_message(message, delay)
            if isinstance(sent_message, tuple):
                sent_message, delete_message = sent_message
                if not delete_message:
                    return
            if sent_message:
                s_delete_message(sent_message, delay)

        return wrapper

    return decorator
