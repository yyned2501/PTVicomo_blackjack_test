import asyncio
import datetime
import json
import logging
import random
import time

from sqlalchemy import column, desc, func, select
from app import app, redis_cli, scheduler
from pyrogram import filters, Client
from pyrogram.types.messages_and_media import Message
from app.libs.decorators import auto_delete_message, s_delete_message
from app.models.nexusphp import Users, LotteryHistory, LotteryBetHistory, BotBinds
from app.models import ASSession
from app.normal_reply import NOT_ENOUGH_BONUS, USER_BIND_NONE
from config import GROUP_ID

logger = logging.getLogger("test")

RULE = """```10选3规则：
参与方法：
回复本消息三个数字*象草，即可参与游戏。
要求：三个数字不能重复，象草不能包含小数点
如： 012*500 表示购买500象草，数字为[0,1,2]的彩票。

输赢方法：
系统将从[0到9]10个数字中，随机选择3个数字做为结果。
你购买的彩票每有一个数字与系统结果一致，赢得一倍下注象草
如果三个数字全部相同赢得下注金额的30倍!!
注意：兑奖上限为奖池金额的50%，如果超过上限，所有奖励按比例减少
盈利超过一倍将扣税1%
```
奖池金额: {bonus_pool:,}
创建时间: {create_time}
结算时间: {drawing_time}
总计投注: {bonus:,}"""

lock = asyncio.Lock()


def safe_remove_in_list(l: list, number_str: str, n=1):
    numbers = random.sample(number_str, n)
    for n in numbers:
        n = int(n)
        if n in l:
            l.remove(n)


def get_fake_list():
    data_str = redis_cli.get("lottery_number")
    number_all = list(range(10))
    ret_list = []
    logger.info(data_str)
    if data_str:
        redis_cli.delete("lottery_number")
        return list(map(int, set(char for char in str(data_str) if char.isdigit())))
    data_str = redis_cli.get("lottery")
    logger.info(data_str)
    if data_str:
        data: dict = json.loads(data_str)
        bet_numbers = {}
        sum_bonus = 0
        for tgid in data["users"]:
            for lottery_numbers in data["users"][tgid]["bet"]:
                bonus = data["users"][tgid]["bet"][lottery_numbers]
                bet_numbers[lottery_numbers] = (
                    bet_numbers.get(lottery_numbers, 0) + bonus
                )
                sum_bonus += bonus
        numbers_sorted_by_bonus = sorted(
            bet_numbers.items(), key=lambda item: item[1], reverse=True
        )
        logger.info(str(numbers_sorted_by_bonus))
        for lottery_numbers_tuple in numbers_sorted_by_bonus:
            logger.info(lottery_numbers_tuple)
            lottery_numbers = lottery_numbers_tuple[0]
            bonus = lottery_numbers_tuple[1]
            if len(number_all) > 3:
                if check_lottery(lottery_numbers, number_all) > 2:
                    if bonus > data["bonus_pool"] / 10:
                        safe_remove_in_list(number_all, lottery_numbers, 2)
                    elif bonus > data["bonus_pool"] / 300:
                        safe_remove_in_list(number_all, lottery_numbers, 1)
                    elif random.random() < 0.3:
                        safe_remove_in_list(number_all, lottery_numbers, 1)
                logger.info(str(number_all))
        return number_all
    return ret_list


def get_random_number():
    ret_list = get_fake_list()
    if len(ret_list) >= 3:
        return random.sample(ret_list, 3)
    else:
        number_all = [i for i in range(10) if i not in ret_list]
        ret_list += random.sample(number_all, 3 - len(ret_list))
        return ret_list


def create_lottery_info(data):
    bonus = sum([data["users"][tgid]["bonus"] for tgid in data["users"]])
    ret = RULE.format(
        bonus_pool=data["bonus_pool"],
        create_time=datetime.datetime.fromtimestamp(data["create_time"]).strftime(
            "%Y-%m-%d %H:%M:%S"
        ),
        drawing_time=datetime.datetime.fromtimestamp(data["drawing_time"]).strftime(
            "%Y-%m-%d %H:%M:%S"
        ),
        bonus=bonus,
    )
    if len(data["users"]) > 0:
        data["users"] = dict(
            sorted(
                data["users"].items(), key=lambda item: item[1]["bonus"], reverse=True
            )
        )
        redis_cli.set("lottery", json.dumps(data))
        bet_users = "\n".join(
            [
                f'  [{data["users"][tgid]["username"]}](tg://user?id={tgid}) : `{lottery_numbers} * {data["users"][tgid]["bet"][lottery_numbers]:,}`'
                for tgid in data["users"]
                for lottery_numbers in data["users"][tgid]["bet"]
            ]
        )
        ret += f"\n下注信息：\n{bet_users}"
    return ret


async def current_lottery_filter(_, __, message: Message):
    data_str = redis_cli.get("lottery")
    if data_str:
        data: dict = json.loads(data_str)
        return message.reply_to_message_id == data.get("message_id")


current_lottery = filters.create(current_lottery_filter)


@app.on_message(filters.chat(GROUP_ID[0]) & filters.command("lottery"))
@auto_delete_message(60, True, True)
async def lottery(client: Client, message: Message):
    async with lock:
        data_str = redis_cli.get("lottery")
        if data_str:
            return await message.reply("上局未结束")
        session = ASSession()
        async with session.begin():
            bet, win, _ = await get_lottery_pool()
        data = {}
        data["bonus_pool"] = int(bet - win)
        data["create_time"] = int(time.time())
        data["drawing_time"] = data["create_time"] + 60
        data["users"] = {}
        info_ret = create_lottery_info(data)
        ret_message = await message.reply(info_ret)
        data["message_id"] = ret_message.id
        redis_cli.set("lottery", json.dumps(data))
        scheduler.add_job(
            draw_lottery,
            "date",
            next_run_time=datetime.datetime.now() + datetime.timedelta(seconds=60),
        )
        async with session.begin():
            session.add(LotteryHistory(messageid=ret_message.id))
        return ret_message


@app.on_message(
    filters.chat(GROUP_ID[0])
    & current_lottery
    & filters.regex(r"(\d{3})\s*\*\s*([\d,]+)")
)
@auto_delete_message(10)
async def bet_lottery(client: Client, message: Message):
    async with lock:
        match = message.matches[0]
        lottery_numbers = sorted(match.group(1))
        bonus = int(match.group(2).replace(",", ""))
        data: dict = json.loads(redis_cli.get("lottery"))
        if len(lottery_numbers) != 3:
            return await message.reply("下注数字应是3位数")
        if len(set(lottery_numbers)) < 3:
            return await message.reply("下注数字不能重复")
        lottery_numbers = "".join(lottery_numbers)
        async with ASSession() as session:
            async with session.begin():
                user = await Users.get_user_from_tgmessage(message)
                if not user:
                    return await message.reply(USER_BIND_NONE)
                if user.seedbonus < bonus:
                    return await message.reply(NOT_ENOUGH_BONUS)
                await user.addbonus(-bonus, f"彩票下注{lottery_numbers}")
                tg_id = str(user.bot_bind.telegram_account_id)
                if tg_id not in data["users"]:
                    data["users"][tg_id] = {
                        "username": user.bot_bind.telegram_account_username,
                        "userid": user.id,
                        "bonus": 0,
                        "bet": {},
                    }
                if lottery_numbers not in data["users"][tg_id]["bet"]:
                    data["users"][tg_id]["bet"][lottery_numbers] = 0
                data["users"][tg_id]["bet"][lottery_numbers] += bonus
                data["users"][tg_id]["bonus"] += bonus
                data["bonus_pool"] += bonus
        redis_cli.set("lottery", json.dumps(data))
        info_ret = create_lottery_info(data)
        await message.reply_to_message.edit(info_ret)
        return await message.reply("下注成功")


def check_lottery(number: str, result: list[int]):
    return sum(1 for digit in number if int(digit) in result)


async def draw_lottery():
    async with lock:
        data_str = redis_cli.get("lottery")
        if data_str:
            data: dict = json.loads(data_str)
        else:
            return
        random_numbers = sorted(get_random_number())
        number_str = "".join(map(str, random_numbers))
        ret = f"`开奖啦，结果为 [{number_str}]`"
        session = ASSession()
        win = [0, 1, 2, 30]
        win_bonus_all = [
            data["users"][tgid]["bet"][lottery_numbers]
            * win[check_lottery(lottery_numbers, random_numbers)]
            for tgid in data["users"]
            for lottery_numbers in data["users"][tgid]["bet"]
        ]

        win_k = min(
            (
                data["bonus_pool"] * 0.5 / sum(win_bonus_all)
                if sum(win_bonus_all) > 0
                else 1
            ),
            1,
        )
        win = list(map(lambda a: a * win_k, win))
        async with session.begin():
            lottery_history = (
                await session.execute(
                    select(LotteryHistory).filter(
                        LotteryHistory.messageid == data["message_id"]
                    )
                )
            ).scalar_one_or_none()
            if not lottery_history:
                lottery_history = LotteryHistory(messageid=data["message_id"])
                session.add(lottery_history)
            lottery_history.number = number_str
            for tgid in data["users"]:
                user_ret = f'[{data["users"][tgid]["username"]}](tg://user?id={tgid})'
                user_id = data["users"][tgid]["userid"]
                win_bonus_sum = 0
                for lottery_numbers in data["users"][tgid]["bet"]:
                    same_count = check_lottery(lottery_numbers, random_numbers)
                    bet_bonus = data["users"][tgid]["bet"][lottery_numbers]
                    win_bonus = int(win[same_count] * bet_bonus)
                    tax = max(int((win_bonus - bet_bonus) * 0.01), 0)
                    win_bonus_sum += win_bonus - tax
                    session.add(
                        LotteryBetHistory(
                            history_id=lottery_history.id,
                            user_id=user_id,
                            number=lottery_numbers,
                            bonus=bet_bonus,
                            win_bonus=win_bonus,
                            tax=tax,
                        )
                    )
                    if same_count > 0:
                        ret += f"\n  {user_ret} : `[{lottery_numbers}]中奖[{same_count}]个数字 : {win_bonus:,} 扣税 {tax:,}`"
                if win_bonus_sum > 0:
                    user = await session.get(Users, data["users"][tgid]["userid"])
                    await user.addbonus(win_bonus_sum, f"彩票开奖 {number_str} 中奖")
            redis_cli.delete("lottery")
        s_delete_message(await app.send_message(GROUP_ID[0], ret), 120)


@app.on_message(filters.chat(GROUP_ID) & filters.reply & filters.command("lotteryinfo"))
@auto_delete_message(60)
async def lotteryinfo(client: Client, message: Message):
    async with ASSession() as session:
        async with session.begin():
            user = await Users.get_user_from_tgmessage(message)
            bet, win, tax = await get_lottery_pool(user)
            return await message.reply(
                f"`累计下注 : {bet:,}`\n`累计中奖 : {win:,}`\n`累计缴税 : {tax:,}`\n`累计净赚 : {win-bet-tax:,}`"
            )


@app.on_message(filters.private & filters.command("fakelottery"))
@auto_delete_message(60)
async def lotteryinfo(client: Client, message: Message):
    async with ASSession() as session:
        async with session.begin():
            user = await Users.get_user_from_tgmessage(message)
            if user and user._class >= 14:
                numbers = message.command[1]
                redis_cli.set("lottery_number", numbers)
                await message.reply("修改成功")


@app.on_message(filters.chat(GROUP_ID) & filters.command("lotteryhistory"))
@auto_delete_message(60)
async def lotteryinfo(client: Client, message: Message):
    async with ASSession() as session:
        async with session.begin():
            query = (
                select(LotteryHistory)
                .order_by(desc(LotteryHistory.id))
                .filter(LotteryHistory.number != "")
                .limit(20)
            )
            result = await session.execute(query)
            ret = "历史20次记录:"
            for history in result.scalars():
                number = history.number
                ret += f"\n 第[{history.id}期]{history.number} : " + "".join(
                    [f"{i}" if str(i) in number else "  " for i in range(10)]
                )
            return await message.reply(ret)


@app.on_message(filters.chat(GROUP_ID) & filters.command("lotteryinfo"))
@auto_delete_message(60)
async def lotteryinfo(client: Client, message: Message):
    async with ASSession() as session:
        async with session.begin():
            user = await Users.get_user_from_tgmessage(message)
            bet, win, tax = await get_lottery_pool(user)
            return await message.reply(
                f"`累计下注 : {bet:,}`\n`累计中奖 : {win:,}`\n`累计缴税 : { tax:,}`\n`累计净赚 : {win-bet-tax:,}`"
            )


@app.on_message(filters.chat(GROUP_ID) & filters.command("lotteryinfoall"))
@auto_delete_message(60)
async def lotteryinfoall(client: Client, message: Message):
    bet, win, tax = await get_lottery_pool()
    return await message.reply(
        f"`累计下注 : {bet:,}`\n`累计中奖 : {win:,}`\n`累计缴税 : { tax:,}`\n`累计净赚 : {win-bet-tax:,}`"
    )


@app.on_message(filters.chat(GROUP_ID) & filters.command("lotteryrank"))
@auto_delete_message(60)
async def lotteryrank(client: Client, message: Message):
    session = ASSession()
    async with session.begin():
        win_result = await session.execute(
            select(
                BotBinds.telegram_account_username,
                (
                    func.sum(LotteryBetHistory.win_bonus)
                    - func.sum(LotteryBetHistory.bonus)
                    - func.sum(LotteryBetHistory.tax)
                ).label("total_win_bonus"),
            )
            .join(LotteryBetHistory, BotBinds.uid == LotteryBetHistory.user_id)
            .group_by(LotteryBetHistory.user_id, BotBinds.telegram_account_username)
            .having(column("total_win_bonus") > 0)
            .order_by(desc("total_win_bonus"))
            .limit(10)
        )
        lose_result = await session.execute(
            select(
                BotBinds.telegram_account_username,
                (
                    func.sum(LotteryBetHistory.win_bonus)
                    - func.sum(LotteryBetHistory.bonus)
                    - func.sum(LotteryBetHistory.tax)
                ).label("total_win_bonus"),
            )
            .join(LotteryBetHistory, BotBinds.uid == LotteryBetHistory.user_id)
            .group_by(LotteryBetHistory.user_id)
            .having(column("total_win_bonus") < 0)
            .order_by("total_win_bonus")
            .limit(10)
        )
        ret = "`盈利榜`"
        for n, win_bonus_row in enumerate(win_result.fetchall()):
            ret += f"\n  `[{n+1:02d}] {win_bonus_row[0] } : {win_bonus_row[1]:,}`"
        ret += "\n\n`贡献榜`"
        for n, lose_bonus_row in enumerate(lose_result.fetchall()):
            ret += f"\n  `[{n+1:02d}] {lose_bonus_row[0]} : {lose_bonus_row[1]:,}`"
    return await message.reply(ret)


async def get_lottery_pool(user: Users = None):
    session = ASSession()
    if user:
        result = await session.execute(
            select(
                func.sum(LotteryBetHistory.bonus),
                func.sum(LotteryBetHistory.win_bonus),
                func.sum(LotteryBetHistory.tax),
            )
            .filter(LotteryBetHistory.user_id == user.id)
            .group_by(LotteryBetHistory.user_id)
            .limit(1)
        )
    else:
        result = await session.execute(
            select(
                func.sum(LotteryBetHistory.bonus).label("total_bonus"),
                func.sum(LotteryBetHistory.win_bonus).label("total_win_bonus"),
                func.sum(LotteryBetHistory.tax).label("total_win_bonus"),
            ).limit(1)
        )
    row = result.fetchone()
    if row:
        row_tuple = row.tuple()
        bet = row_tuple[0]
        win = row_tuple[1]
        tax = row_tuple[2]
    else:
        bet = 0
        win = 0
        tax = 0
    return bet, win, tax


async def safe_draw_lottery():
    data_str = redis_cli.get("lottery")
    if data_str:
        data: dict = json.loads(data_str)
        if time.time() > data.get("drawing_time") + 5:
            return await draw_lottery()


scheduler.add_job(safe_draw_lottery, "interval", seconds=10)
