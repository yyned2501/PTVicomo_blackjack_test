import json
import logging

from app import scheduler, redis_cli, get_app
from app.models import ASSession
from app.models.nexusphp import Users

logger = logging.getLogger("main")


async def blackjack_message():
    # 获取所有以 "blackjack" 开头的键
    app = get_app()
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
                        logger.info(f"{message.id}:{message.text}")
                        if not message.text or message.text[:3] != "玩家：":
                            user = await Users.get_user_from_tg_id(tg_id)
                            await user.addbonus(bonus, "21点开局失败返还")
                            redis_cli.delete(key)
                    else:
                        user = await Users.get_user_from_tg_id(tg_id)
                        await user.addbonus(bonus, "21点开局失败返还")
                        redis_cli.delete(key)


scheduler.add_job(blackjack_message, "interval", seconds=300)
