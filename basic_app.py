import asyncio
import os

import redis
from pyrogram import Client, idle


from app.libs.logs import logger
from config import API_ID, API_HASH, BOT_TOKEN, REDIS_HOST, REDIS_PORT, REDIS_DB


os.environ["TZ"] = "Asia/Shanghai"


app: Client = None


redis_cli = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=REDIS_DB)


async def start_app():
    from app import models
    from app.commands import setup

    global app
    app = Client(
        "tgbot",
        api_id=API_ID,
        api_hash=API_HASH,
        bot_token=BOT_TOKEN,
        plugins=dict(
            root="app.commands",
            include=["bind", "info", "login", "cancel2fa"],
        ),
        skip_updates=False,
    )

    logger.info("启动主程序")
    await app.start()
    await models.create_all()
    await setup.get_admin()
    logger.info("监听主程序")
    await idle()
    await app.stop()
    logger.info("关闭主程序")


def get_app():
    global app
    return app


if __name__ == "__main__":
    asyncio.run(start_app())
