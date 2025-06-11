import os

import redis
from pyrogram import Client, idle

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.libs.logs import logger
from config import API_ID, API_HASH, BOT_TOKEN, REDIS_HOST, REDIS_PORT, REDIS_DB


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


def get_app():
    global app
    return app
