from enum import Enum
import pyrogram
from pyrogram.types import (
    BotCommand,
    BotCommandScopeAllPrivateChats,
    BotCommandScopeChat,
    BotCommandScopeChatAdministrators,
)
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


class CommandScope(Enum):
    PRIVATE_CHATS = BotCommandScopeAllPrivateChats()
    GROUP_CHAT_ADMIN = BotCommandScopeChatAdministrators(chat_id=GROUP_ID[0])
    GROUP_CHAT = BotCommandScopeChat(chat_id=GROUP_ID[0])
    ADMIN_CHAT = BotCommandScopeChat(chat_id=GROUP_ID[1])


BOT_COMMANDS: list[tuple[BotCommand, list[CommandScope]]] = [
    (
        BotCommand("info", "查看绑定账号信息"),
        [CommandScope.PRIVATE_CHATS, CommandScope.GROUP_CHAT],
    ),
    (
        BotCommand("redpocket", "发拼手气红包"),
        [CommandScope.GROUP_CHAT, CommandScope.ADMIN_CHAT],
    ),
    (
        BotCommand("luckypocket", "发锦鲤红包"),
        [CommandScope.GROUP_CHAT, CommandScope.ADMIN_CHAT],
    ),
    (BotCommand("listredpocket", "未领红包列表"), [CommandScope.GROUP_CHAT]),
    (
        BotCommand("listredpocketall", "全部红包列表"),
        [CommandScope.GROUP_CHAT, CommandScope.ADMIN_CHAT],
    ),
    (
        BotCommand("drawredpocket", "手动结束红包"),
        [CommandScope.GROUP_CHAT, CommandScope.ADMIN_CHAT],
    ),
    (BotCommand("lottery", "开启一轮彩票"), [CommandScope.GROUP_CHAT]),
    (BotCommand("lotteryinfo", "彩票收益情况"), [CommandScope.GROUP_CHAT]),
    (BotCommand("lotteryinfoall", "全部玩家彩票收益情况"), [CommandScope.GROUP_CHAT]),
    (BotCommand("lotteryrank", "彩票收益排行榜"), [CommandScope.GROUP_CHAT]),
    (BotCommand("lotteryhistory", "历史彩票记录"), [CommandScope.GROUP_CHAT]),
    (
        BotCommand("blackjack", "开始一轮21点游戏"),
        [CommandScope.PRIVATE_CHATS, CommandScope.GROUP_CHAT],
    ),
    (
        BotCommand("blackjackrank", "21点游戏排行榜"),
        [CommandScope.PRIVATE_CHATS, CommandScope.GROUP_CHAT],
    ),
    (
        BotCommand("blackjackinfo", "21点收益情况"),
        [CommandScope.PRIVATE_CHATS, CommandScope.GROUP_CHAT],
    ),
    (BotCommand("blackjackinfoall", "全部玩家21点收益情况"), [CommandScope.GROUP_CHAT]),
    (
        BotCommand("water", "水群排行榜"),
        [CommandScope.GROUP_CHAT, CommandScope.ADMIN_CHAT],
    ),
    (BotCommand("bind", "绑定账号"), [CommandScope.PRIVATE_CHATS]),
    (BotCommand("unbind", "解除账号绑定"), [CommandScope.PRIVATE_CHATS]),
    (BotCommand("login", "获取登陆连接"), [CommandScope.PRIVATE_CHATS]),
    (BotCommand("cancel2fa", "取消两步验证"), [CommandScope.PRIVATE_CHATS]),
    (BotCommand("cancel2fa", "取消两步验证"), [CommandScope.PRIVATE_CHATS]),
    (BotCommand("ban", "禁言用户"), [CommandScope.GROUP_CHAT_ADMIN]),
    (BotCommand("unban", "取消禁言"), [CommandScope.GROUP_CHAT_ADMIN]),
]


async def setup_commands():
    app = get_app()
    scopes_dict: dict[str, list[BotCommand]] = {
        scope.name: [] for scope in CommandScope
    }
    # 清除旧命令
    await app.delete_bot_commands()

    # 设置新命令
    for cmd, scopes in BOT_COMMANDS:
        for scope in scopes:
            scopes_dict[scope.name].append(cmd)
    for scope, commands in scopes_dict.items():
        await app.set_bot_commands(commands, scope=CommandScope[scope].value)
