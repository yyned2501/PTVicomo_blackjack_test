import sys

if sys.platform != "win32":
    import uvloop

    uvloop.install()

import asyncio
from pyrogram import Client, idle

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app import app, get_app, scheduler
from app.libs.logs import logger
from config import API_ID, API_HASH, BOT_TOKEN


async def start_app():
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
            exclude=["bind", "info", "login", "cancel2fa"],
        ),
    )

    logger.info("启动主程序")
    await app.start()
    await models.create_all()
    await setup.get_admin()
    logger.info("设置命令")
    await setup.setup_commands()
    Hint.load_from_redis()
    scheduler.start()
    logger.info("监听主程序")
    await idle()
    await app.stop()
    logger.info("关闭主程序")


if __name__ == "__main__":

    asyncio.run(start_app())
