import json
import time
import logging
import traceback

from app import scheduler, redis_cli, get_app


logger = logging.getLogger("test")


async def delete_message():
    # 获取所有以 "DM" 开头的键
    app = get_app()
    delete_messages_keys = redis_cli.keys("DM*")
    delete_messages_dict: dict[int, list[int]] = {}
    if delete_messages_keys:
        for key in delete_messages_keys:
            value = redis_cli.get(key)
            value_str: str = value.decode("utf-8")
            data: dict[str, int] = json.loads(value_str)
            chatid = data.get("chatid")
            messageid = data.get("messageid")
            deletetime = data.get("deletetime")
            if deletetime:
                # 检查是否到了删除时间
                if deletetime <= time.time():
                    if not chatid in delete_messages_dict.keys():
                        delete_messages_dict[chatid] = []
                    delete_messages_dict[chatid].append(messageid)
    try:
        for chatid in delete_messages_dict:
            await app.delete_messages(chatid, delete_messages_dict[chatid])
            redis_cli.delete(
                *[
                    f"DM:{chatid}:{messageid}"
                    for messageid in delete_messages_dict[chatid]
                ]
            )
    except Exception as e:
        # 捕获异常并记录错误信息
        traceback.print_exc()
        logger.error(f"Error deleting message: {e}")


# 每秒钟执行一次 delete_message 函数
scheduler.add_job(delete_message, "interval", seconds=2)
