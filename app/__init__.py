import asyncio
import os
import traceback

import pyrogram
import pyrogram.errors
import redis
import pyrogram
from pyrogram import Client as _Client
from pyrogram import idle

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app import models
from app.libs.logs import logger
from app.libs.async_token_bucket import AsyncTokenBucket
from config import API_ID, API_HASH, BOT_TOKEN, REDIS_HOST, REDIS_PORT, REDIS_DB


class Client(_Client):
    def __init__(self, *arg, **karg):
        super().__init__(*arg, **karg)
        self.bucket = AsyncTokenBucket(capacity=10, fill_rate=5)

    async def invoke(self, *arg, err=0, **kargs):
        if err < 3:
            await self.bucket.consume()
            try:
                return await super().invoke(*arg, **kargs)
            except TimeoutError as e:
                logger.error(traceback.format_exc())
                asyncio.sleep(1)
                return await self.invoke(*arg, err=err + 1, **kargs)
            except pyrogram.errors.exceptions.bad_request_400.QueryIdInvalid:
                logger.error(traceback.format_exc())
            except pyrogram.errors.exceptions.bad_request_400.MessageNotModified:
                logger.error(traceback.format_exc())
            except Exception as e:
                logger.error(traceback.format_exc())
                asyncio.sleep(1)
                return await self.invoke(*arg, err=err + 1, **kargs)


os.environ["TZ"] = "Asia/Shanghai"
scheduler = AsyncIOScheduler()

app: Client = None


redis_cli = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=REDIS_DB)


async def start_app():
    global app
    from app import schedulers

    app = Client(
        "tgbot",
        api_id=API_ID,
        api_hash=API_HASH,
        bot_token=BOT_TOKEN,
        plugins=dict(root="app.commands"),
    )

    logger.info("启动主程序")
    await app.start()
    scheduler.start()
    logger.info("监听主程序")
    await idle()
    await app.stop()
    logger.info("关闭主程序")


def get_app():
    global app
    return app
