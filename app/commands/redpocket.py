import datetime
import asyncio

from sqlalchemy import select

from app import app, scheduler, redis_cli
from pyrogram import filters, Client
from pyrogram.types import Message
from app.libs.decorators import auto_delete_message
from app.models import ASSession
from app.normal_reply import USER_BIND_NONE, NOT_ENOUGH_BONUS
from app.libs.async_repocket import RedPockets
from app.models.nexusphp import BotBinds, Redpocket, RedpocketClaimed, Users
from config import GROUP_ID, POCKET_MAX, POCKET_MIN

lock = asyncio.Lock()
redpockets = RedPockets()

NOT_IN_RANGE = (
    "单个红包范围 : {min}-{max} ,请输入范围内的象草,您输入的红包单个红包象草为：{bonus}"
)
EXAMPLE = (
    "请参照以下格式:\n/{command} 象草 个数 红包口令\n`/{command} 20000 10 象岛越来越好`"
)
NOT_COMMAND_START = "红包口令不能以/+-开头"
NOT_COMMAND_WITHIN = "红包口令中不能包含`@"
CREATE_REDPOCKET = "```\n已创建{type_}红包:\n象草: {bonus}\n数量: {count}\n口令: {password}```\n点击复制 => `{password}`"
TYPES = {"redpocket": "口令", "luckypocket": "锦鲤"}


def init_message(message: Message, command):
    try:
        bonus = int(message.command[1])
        count = int(message.command[2])
        password = " ".join([s for s in message.command[3:] if s != ""])
        if password.startswith(("/", "+", "-")):
            raise BaseException(NOT_COMMAND_START)
        if any(char in password for char in {"@", "`"}):
            raise BaseException(NOT_COMMAND_WITHIN)
        if password == "":
            raise BaseException(f"格式有误! {EXAMPLE.format(command=command)}")
    except Exception:
        raise BaseException(f"格式有误! {EXAMPLE.format(command=command)}")
    except BaseException as e:
        raise BaseException(e)
    pb = round(bonus / count, 1)
    if pb > POCKET_MAX or pb < POCKET_MIN:
        raise BaseException(
            NOT_IN_RANGE.format(min=POCKET_MIN, max=POCKET_MAX, bonus=pb)
        )
    if password in redpockets.redpockets_claimeds:
        raise BaseException(
            f"已存在相同口令的红包，请更换口令! {EXAMPLE.format(command=command)}"
        )
    return bonus, count, password


def in_claimed(tg_id, redpocket_text: str):
    claimeds = redpockets.redpockets_claimeds[redpocket_text]
    for claimed_id in claimeds:
        if tg_id == claimed_id:
            return True
    return False


async def qfz_bonus(client: Client, user: Users, bonus: int):
    if user.is_role(13):
        qfz_bonus = int(redis_cli.get("qfz_bonus"))
        if qfz_bonus > 0:
            user_qfz_bonus = min(qfz_bonus, bonus)
            qfz_bonus -= user_qfz_bonus
            redis_cli.set("qfz_bonus", qfz_bonus)
            await client.send_message(GROUP_ID[1], f"气氛组红包余额 {qfz_bonus}")
            bonus -= user_qfz_bonus
    return bonus


async def in_redpockets_filter(_, __, message: Message):
    if not message.from_user:
        return False
    if message.text in redpockets.redpockets_claimeds.keys():
        return bool(
            message.from_user and not in_claimed(message.from_user.id, message.text)
        )
    return False


in_redpockets = filters.create(in_redpockets_filter)


async def create_redpocket(client: Client, message: Message, command: str, type_: int):
    try:
        bonus, count, password = init_message(message, command)
    except BaseException as e:
        return await message.reply(e)
    async with ASSession() as session, session.begin():
        user = await Users.get_user_from_tgmessage(message)
        if not user.bot_bind:
            return await message.reply(USER_BIND_NONE)
        if user.seedbonus < bonus:
            return await message.reply(NOT_ENOUGH_BONUS)
        async with lock:
            redpockets.post_redpocket(user.user.id, bonus, count, password, type_)
            message_str = CREATE_REDPOCKET.format(
                bonus=bonus,
                count=count,
                password=password,
                type_=TYPES[command],
            )
            bonus = await qfz_bonus(client, user, bonus)
            await user.addbonus(-bonus, f"发红包{password}")
            return (
                await message.reply(message_str),
                False,
            )


@app.on_message(filters.chat(GROUP_ID) & filters.command("redpocket"))
@auto_delete_message()
async def redpocket(client: Client, message: Message):
    return await create_redpocket(client, message, "redpocket", 0)


@app.on_message(filters.chat(GROUP_ID) & filters.command("luckypocket"))
@auto_delete_message()
async def luckypocket(client: Client, message: Message):
    return await create_redpocket(client, message, "luckypocket", 1)


@app.on_message(filters.chat(GROUP_ID) & filters.command("listredpocket"))
@auto_delete_message()
async def listredpocket(client: Client, message: Message):
    user = await Users.get_user_from_tgmessage(message)
    if not user.bot_bind:
        return await message.reply(USER_BIND_NONE)
    ret = []
    async with ASSession() as session, session.begin():
        results = await session.execute(
            select(Redpocket)
            .outerjoin(
                RedpocketClaimed,
                (Redpocket.id == RedpocketClaimed.redpocket_id)
                & (RedpocketClaimed.tg_id == message.from_user.id),
            )
            .filter(RedpocketClaimed.redpocket_id.is_(None))
        )
        for redpocket in results.scalars():
            ret.append(
                f"{redpocket.id}-{redpocket.pocket_type}-{redpocket.bonus}-{redpocket.count}-`{redpocket.password}`"
            )
        ret_text = "\n".join(ret)
        return await message.reply(f"未领红包如下：\n{ret_text}")


@app.on_message(filters.chat(GROUP_ID) & filters.command("listredpocketall"))
@auto_delete_message()
async def listredpocket(client: Client, message: Message):
    async with ASSession() as session, session.begin():
        user = await Users.get_user_from_tgmessage(message)
        if not user.bot_bind:
            return await message.reply(USER_BIND_NONE)
        ret = []
        results = await session.execute(select(Redpocket))
        for redpocket in results.scalars():
            ret.append(
                f"{redpocket.id}-{redpocket.pocket_type}-{redpocket.bonus}-{redpocket.count}-`{redpocket.password}`"
            )
        ret_text = "\n".join(ret)
        return await message.reply(f"全部红包如下：\n{ret_text}")


@app.on_message(filters.chat(GROUP_ID) & filters.command("drawredpocket"))
@auto_delete_message()
async def drawredpocket(client: Client, message: Message):
    async with ASSession() as session, session.begin():
        user = await Users.get_user_from_tgmessage(message)
        try:
            redpocket_id = int(message.command[1])
        except:
            if not user.bot_bind:
                return await message.reply(USER_BIND_NONE)
            ret = []
            results = await session.execute(
                select(Redpocket).filter(Redpocket.from_uid == user.id)
            )
            for redpocket in results.scalars():
                ret.append(
                    f"`{redpocket.id}`-{redpocket.pocket_type}-{redpocket.bonus}-{redpocket.count}-`{redpocket.password}`"
                )
            ret_text = "\n".join(ret)
            return await message.reply(
                f"请填写要结束的红包id\n你发的红包如下：\n{ret_text}"
            )

        redpocket = (
            await session.execute(
                select(Redpocket).filter(Redpocket.id == redpocket_id)
            )
        ).scalar_one_or_none()
        if not user.bot_bind or (user._class < 14 and redpocket.from_uid != user.id):
            return await message.reply("您没有此权限")
        if redpocket:
            if redpocket._pocket_type == 1 and len(redpocket.claimed) > 0:
                run_date = datetime.datetime.now() + datetime.timedelta(seconds=1)
                scheduler.add_job(
                    draw_luckypocket,
                    "date",
                    run_date=run_date,
                    args=[redpocket],
                )
            else:
                user = await session.get(Users, redpocket.from_uid)
                await user.addbonus(redpocket.bonus, f"回收红包 {redpocket.password}")
                await redpockets.delete_redpocket(redpocket.password)
        return await message.reply(f"手动结束红包 {redpocket.password} ")


@app.on_message(filters.chat(GROUP_ID) & in_redpockets)
@auto_delete_message(delete_from_message=True)
async def get_pocket(client: Client, message: Message):
    async with ASSession() as session, session.begin():
        user = await Users.get_user_from_tgmessage(message)
        if not user.bot_bind:
            return await message.reply(USER_BIND_NONE)
        async with lock:
            bonus, redpocket = await redpockets.get_pocket(
                message.from_user.id, message.text
            )
            redpocket = await redpockets.search_pocket(message.text)
            if redpocket._pocket_type == 0:
                await user.addbonus(bonus, f"领取红包 {redpocket.password}")
                if redpocket.count == 0:
                    await redpockets.delete_redpocket(message.text)
                reply_message = f"成功领取口令红包，增加{bonus}象草\n\n" + (
                    f"该红包还剩 {redpocket.count} 个, {redpocket.bonus} 象草"
                    if redpocket.count > 0
                    else "该红包已经领完"
                )
            elif redpocket._pocket_type == 1:
                if redpocket.count == 0:
                    run_date = datetime.datetime.now() + datetime.timedelta(seconds=1)
                    scheduler.add_job(
                        draw_luckypocket,
                        "date",
                        run_date=run_date,
                        args=[redpocket],
                    )
                reply_message = "成功参加锦鲤红包抽奖\n\n" + (
                    f"该红包还剩 {redpocket.count} 个，抽满后开奖"
                    if redpocket.count > 0
                    else "该红包已经领完，马上开奖"
                )
            return await message.reply(reply_message)


async def draw_luckypocket(redpocket: Redpocket):
    async with ASSession() as session, session.begin():
        redpocket = await session.merge(redpocket)
        bonus, tg_id = redpocket.draw()
        bot_bind = (
            await session.execute(
                select(BotBinds).filter(BotBinds.telegram_account_id == tg_id)
            )
        ).scalar_one_or_none()
        bot_bind.user.addbonus(redpocket.bonus, f"锦鲤红包 {redpocket.password} 中奖")
        async with lock:
            await redpockets.delete_redpocket(redpocket.password)
            reply_user = f"[{bot_bind.telegram_account_username}](tg://user?id={tg_id})"
            return await app.send_message(
                GROUP_ID[0],
                f"恭喜锦鲤 {reply_user} \n获得锦鲤红包 {redpocket.password} 的奖励\n成功获得 {bonus} 象草",
            )
