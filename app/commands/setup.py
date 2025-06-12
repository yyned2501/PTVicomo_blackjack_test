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
    try:
        async for m in app.get_chat_members(
            GROUP_ID[0], filter=pyrogram.enums.ChatMembersFilter.ADMINISTRATORS
        ):
            if m.custom_title:
                ADMINS[m.custom_title] = m.user
    except Exception as e:
        logger.error(f"获取管理员失败: {e}")
        return False


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
    (
        BotCommand("setblackjackmax", "设置21点最大下注金额"),
        [CommandScope.ADMIN_CHAT],
    ),
    (
        BotCommand("checkblackjack", "清理21点开局失败记录"),
        [CommandScope.ADMIN_CHAT],
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
    (BotCommand("ban", "禁言用户"), [CommandScope.GROUP_CHAT_ADMIN]),
    (BotCommand("unban", "取消禁言"), [CommandScope.GROUP_CHAT_ADMIN]),
    (
        BotCommand("hint_set", "设置自动回复关键词"),
        [CommandScope.ADMIN_CHAT],
    ),
    (
        BotCommand("hint_remove", "移除自动回复关键词"),
        [CommandScope.ADMIN_CHAT],
    ),
    (
        BotCommand("hint_list", "查询自动回复关键词"),
        [CommandScope.ADMIN_CHAT],
    ),
    (
        BotCommand("restart_extra", "重启 ex_app 程序"),
        [CommandScope.ADMIN_CHAT],
    ),
    (
        BotCommand("restart_basic", "重启 basic_app 程序"),
        [CommandScope.ADMIN_CHAT],
    ),
    (
        BotCommand("update", "更新代码"),
        [CommandScope.ADMIN_CHAT],
    ),
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
            # 群聊管理员命令也会被群聊命令覆盖
            if scope == CommandScope.GROUP_CHAT:
                scopes_dict[CommandScope.GROUP_CHAT_ADMIN.name].append(cmd)
            scopes_dict[scope.name].append(cmd)
    for scope, commands in scopes_dict.items():
        try:
            await app.set_bot_commands(commands, scope=CommandScope[scope].value)
        except Exception as e:
            logger.error(f"设置命令失败: {e}")
