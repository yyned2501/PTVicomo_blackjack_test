import os

import redis
from pyrogram import idle

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.libs.logs import logger
from config import (
    API_ID,
    API_HASH,
    BOT_TOKEN,
    REDIS_HOST,
    REDIS_PORT,
    REDIS_DB,
    GROUP_ID,
)
from app.custom_client import Client

os.environ["TZ"] = "Asia/Shanghai"

scheduler = AsyncIOScheduler(
    {
        "job_defaults": {
            "max_instances": 5,  # 全局设置最大并发实例数为 5
            "coalesce": True,  # 可选：合并跳过的任务
            "misfire_grace_time": 2,  # 可选：设置宽限时间（秒）
        }
    }
)

app: Client = None


redis_cli = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=REDIS_DB)

basic_plugins = [
    "bind",
    "info",
    "login",
    "cancel2fa",
    "auto_reply",
]


def get_app():
    global app
    return app


async def start_basic_app():
    from app import models
    from app.commands import setup

    global app
    app = Client(
        "basic_tgbot",
        api_id=API_ID,
        api_hash=API_HASH,
        bot_token=BOT_TOKEN,
        plugins=dict(
            root="app.commands",
            include=basic_plugins,
        ),
    )
    logger.info("启动主程序")
    await app.start()
    await models.create_all()
    await setup.get_admin()
    logger.info("监听主程序")
    await app.send_message(GROUP_ID[1], "basic_app login")
    await idle()
    await app.stop()
    logger.info("关闭主程序")


async def start_ex_app():
    from app import schedulers
    from app import models
    from app.commands import setup
    from app.commands.auto_reply import Hint

    global app
    app = Client(
        "ex_tgbot",
        api_id=API_ID,
        api_hash=API_HASH,
        bot_token=BOT_TOKEN,
        plugins=dict(
            root="app.commands",
            exclude=basic_plugins,
        ),
    )

    logger.info("启动主程序")
    await app.start()
    await models.create_all()
    await setup.get_admin()
    logger.info("设置命令")
    await setup.setup_commands()
    scheduler.start()
    logger.info("监听主程序")
    await app.send_message(GROUP_ID[1], "ex_app login")
    await idle()
    await app.stop()
    logger.info("关闭主程序")
