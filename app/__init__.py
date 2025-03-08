import os

import redis
from pyrogram import Client, idle

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.libs.logs import logger
from config import API_ID, API_HASH, BOT_TOKEN, REDIS_HOST, REDIS_PORT, REDIS_DB


os.environ["TZ"] = "Asia/Shanghai"
scheduler = AsyncIOScheduler()

app: Client = None


redis_cli = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=REDIS_DB)


async def start_app():
    from app import schedulers
    from app import models

    global app
    app = Client(
        "tgbot",
        api_id=API_ID,
        api_hash=API_HASH,
        bot_token=BOT_TOKEN,
        plugins=dict(root="app.commands"),
    )

    logger.info("启动主程序")
    await app.start()
    await models.create_all()
    scheduler.start()
    logger.info("监听主程序")
    await idle()
    await app.stop()
    logger.info("关闭主程序")


def get_app():
    global app
    return app
