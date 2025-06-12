from pyrogram import filters, Client
from pyrogram.types import Message

from app import redis_cli, logger
from app.libs.decorators import auto_delete_message
from config import GROUP_ID


class Hint:
    """
    自动回复关键词管理类，负责关键词的存储、加载和移除。
    """

    hints = {}

    def save_to_redis(self, keyword, reply_message):
        """
        保存关键词及回复内容到redis，并同步到内存字典。
        :param keyword: 关键词
        :param reply_message: 回复内容
        """
        redis_cli.set(f"hint:{keyword}", reply_message)
        self.hints[keyword] = reply_message

    def load_from_redis(self):
        """
        从redis加载所有关键词及其回复内容到内存字典。
        """
        keywords = redis_cli.keys("hint*")
        for keyword in keywords:
            _keyword = keyword.decode("utf-8").split(":")[1]  # 提取关键词
            logger.debug(f"从redis加载关键词: {keyword}")
            reply = redis_cli.get(keyword)
            if reply:
                _reply = reply.decode("utf-8")
                logger.debug(f"关键词: {_keyword}，回复内容: {_reply}")
                self.hints[_keyword] = _reply
            else:
                redis_cli.delete(keyword)

    def remove_from_redis(self, keyword):
        """
        从redis和内存字典中移除指定关键词。
        :param keyword: 关键词
        """
        if keyword not in self.hints:
            logger.warning(f"尝试移除不存在的关键词: {keyword}")
            return
        redis_cli.delete(f"hint:{keyword}")
        self.hints.pop(keyword, None)


# 启动时加载redis中的关键词
hint = Hint()
hint.load_from_redis()


@Client.on_message(filters.chat(GROUP_ID[1]) & filters.command("hint_set"))
@auto_delete_message()
async def hint_set(client: Client, message: Message):
    """
    设置自动回复关键词及内容。用法: /hint_set 关键词 回复内容
    仅限管理员群组使用。
    """
    args = message.text.split(maxsplit=2)
    if len(args) < 3:
        return await message.reply("用法: /hint_set 关键词 回复内容")

    keyword, reply_message = args[1], args[2]
    hint.save_to_redis(keyword, reply_message)
    return await message.reply(f"已设置关键词：{keyword}")


@Client.on_message(filters.chat(GROUP_ID[1]) & filters.command("hint_list"))
@auto_delete_message()
async def hint_list(client: Client, message: Message):
    """
    查询所有自动回复关键词及内容。仅限管理员群组使用。
    """
    if not hint.hints:
        return await message.reply("暂无关键词。")

    text = "关键词列表：\n"
    for keyword, reply in hint.hints.items():
        text += f"- {keyword}：{reply}\n"
    return await message.reply(text)


@Client.on_message(filters.chat(GROUP_ID[1]) & filters.command("hint_remove"))
@auto_delete_message()
async def hint_remove(client: Client, message: Message):
    """
    移除自动回复关键词。用法: /hint_remove 关键词
    仅限管理员群组使用。
    """
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        return await message.reply("用法: /hint_remove 关键词")
    keyword = args[1]
    if keyword not in hint.hints:
        return await message.reply("关键词不存在。")
    hint.remove_from_redis(keyword)
    return await message.reply(f"已移除关键词：{keyword}")


@Client.on_message(
    filters.chat(GROUP_ID)
    & filters.create(lambda _, __, ___: len(hint.hints) > 0)
    & filters.regex("|".join([f"{k}" for k in hint.hints.keys()]))
)
@auto_delete_message(60, delete_from_message=False)
async def auto_reply(client: Client, message: Message):
    """
    监听普通群组消息，检测是否包含关键词，自动回复对应内容。
    """
    logger.info(f"监听到内容: {message.text}，检测关键词...")
    for keyword, reply in Hint.hints.items():
        if keyword in message.text:
            logger.debug(f"检测到关键词: {keyword}，回复内容: {reply}")
            return await message.reply(reply)
