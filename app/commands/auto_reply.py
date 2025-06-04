from pyrogram import filters, Client
from pyrogram.types import Message

from app import redis_cli
from app.libs.decorators import auto_delete_message
from config import GROUP_ID


class Hint:
    hint = {}

    @classmethod
    async def save_to_redis(cls, keyword, reply_message):
        await redis_cli.set(f"hint:{keyword}", reply_message)
        await redis_cli.sadd("hint:keywords", keyword)
        cls.hint[keyword] = reply_message

    @classmethod
    async def load_from_redis(cls):
        keywords = await redis_cli.smembers("hint:keywords")
        for keyword in keywords:
            reply = await redis_cli.get(f"hint:{keyword}")
            if reply:
                cls.hint[keyword] = reply

    @classmethod
    async def remove_from_redis(cls, keyword):
        await redis_cli.delete(f"hint:{keyword}")
        await redis_cli.srem("hint:keywords", keyword)
        cls.hint.pop(keyword, None)


# 启动时加载


@Client.on_message(filters.chat(GROUP_ID[1]) & filters.command("hint_set"))
@auto_delete_message()
async def hint_set(client: Client, message: Message):
    # /hint_set keyword reply_message
    args = message.text.split(maxsplit=2)
    if len(args) < 3:
        await message.reply("用法: /hint_set 关键词 回复内容")
        return
    keyword, reply_message = args[1], args[2]
    await Hint.save_to_redis(keyword, reply_message)
    await message.reply(f"已设置关键词：{keyword}")


@Client.on_message(filters.chat(GROUP_ID[1]) & filters.command("hint_list"))
@auto_delete_message()
async def hint_list(client: Client, message: Message):
    if not Hint.hint:
        await message.reply("暂无关键词。")
        return
    text = "关键词列表：\n"
    for keyword, reply in Hint.hint.items():
        text += f"- {keyword}：{reply}\n"
    await message.reply(text)


@Client.on_message(
    filters.chat(GROUP_ID[0])
    & filters.regex("|".join([f"({k})" for k in Hint.hint.keys()]))
)
async def auto_reply(client: Client, message: Message):
    for keyword, reply in Hint.hint.items():
        if keyword in message.text:
            await message.reply(reply)
            break


@Client.on_message(filters.chat(GROUP_ID[1]) & filters.command("hint_remove"))
@auto_delete_message()
async def hint_remove(client: Client, message: Message):
    # /hint_remove keyword
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        await message.reply("用法: /hint_remove 关键词")
        return
    keyword = args[1]
    if keyword not in Hint.hint:
        await message.reply("关键词不存在。")
        return
    await Hint.remove_from_redis(keyword)
    await message.reply(f"已移除关键词：{keyword}")
