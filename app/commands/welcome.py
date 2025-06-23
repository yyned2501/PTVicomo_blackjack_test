from pyrogram import filters, Client
from pyrogram.types import Message, ChatMemberUpdated

from app import redis_cli
from app.libs.decorators import auto_delete_message
from config import GROUP_ID


@Client.on_chat_member_updated(filters.chat(GROUP_ID))
async def welcome_new_member(client: Client, update: ChatMemberUpdated):
    member = update.new_chat_member.user
    # 获取新成员的用户名或名字
    user_mention = member.mention if member.username else member.first_name
    # 发送欢迎消息
    welcome_str = redis_cli.get(f"welcome").decode("utf-8")
    await client.send_message(
        update.chat.id, f"欢迎 {user_mention} 加入群聊！🎉\n" f"{welcome_str}"
    )


@Client.on_message(filters.chat(GROUP_ID[1]) & filters.command("welcome_set"))
@auto_delete_message()
async def hint_set(client: Client, message: Message):
    """
    设置自动回复关键词及内容。用法: /welcome_set 关键词 回复内容
    仅限管理员群组使用。
    """
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        return await message.reply("用法: /welcome_set 回复内容")
    reply_message = args[1]
    redis_cli.set(f"welcome", reply_message)
    return await message.reply(f"已设置欢迎词")
