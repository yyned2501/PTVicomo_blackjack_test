import json
import logging

from app import scheduler, redis_cli, app
from app.models import ASSession
from app.models.nexusphp import Users

logger = logging.getLogger("main")


async def blackjack_message():
    # 获取所有以 "blackjack" 开头的键
    blackjack_messages_keys = redis_cli.keys("blackjack*")
    async with ASSession() as session:
        async with session.begin():
            if blackjack_messages_keys:
                for key in blackjack_messages_keys:
                    key_info_list = str(key)[1:-1].split(":")
                    chatid = int(key_info_list[1])
                    messageid = int(key_info_list[2])
                    value = redis_cli.get(key)
                    value_str: str = value.decode("utf-8")
                    data: dict[str, int | str] = json.loads(value_str)
                    tg_id = data.get("tg_id")
                    bonus = data.get("bonus")
                    message = await app.get_messages(chatid, messageid)
                    if message:
                        pass
                    else:
                        user = await Users.get_user_from_tg_id(tg_id)
                        await user.addbonus(bonus, "21点开局失败返还")
                        redis_cli.delete(key)


# 每秒钟执行一次 delete_message 函数
# scheduler.add_job(blackjack_message, "interval", seconds=60)
