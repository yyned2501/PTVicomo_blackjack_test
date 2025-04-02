from sqlalchemy import and_, exists, update, select

import logging

from app import get_app, scheduler
from app.models.nexusphp import BotBinds, TgMessages, UserRoles, Users
from app.models import ASSession
from config import GROUP_ID, WATER_BONUS

logger = logging.getLogger("scheduler")


async def day_water_bonus():
    app = get_app()
    ret = "#昨日水群前五名(已绑定，排除组员):"
    first = True
    async with ASSession() as session:
        async with session.begin():
            water_list = await session.execute(
                select(BotBinds.uid, TgMessages)
                .join(TgMessages, TgMessages.tg_id == BotBinds.telegram_account_id)
                .where(TgMessages.day_count > 0)
                .where(
                    ~(
                        exists().where(
                            and_(UserRoles.uid == BotBinds.uid, UserRoles.role_id == 13)
                        )
                    )
                )
                .order_by(TgMessages.day_count.desc())
                .limit(5)
            )
            for uid, tgmess in water_list.tuples():
                user = (
                    await session.execute(select(Users).filter(Users.id == uid))
                ).scalar_one_or_none()
                bonus = tgmess.day_count * WATER_BONUS
                ret += (
                    f"\n{tgmess.tg_name} 水群 {tgmess.day_count} 条，奖励 {bonus} 象草"
                )
                if first:
                    ret += f"(第一名额外奖励 {bonus} 象草)"
                    bonus += bonus
                    first = False
                await user.addbonus(bonus, "每日水群奖励")
            await app.send_message(GROUP_ID[0], ret)
            await session.execute(update(TgMessages).values(day_count=0))


async def month_water_bonus():
    ret = "#气氛组工资发放"
    app = get_app()
    async with ASSession() as session:
        async with session.begin():
            qfzgz = await session.execute(
                select(BotBinds.uid, TgMessages)
                .join(TgMessages, TgMessages.tg_id == BotBinds.telegram_account_id)
                .join(UserRoles, BotBinds.uid == UserRoles.uid)
                .where(UserRoles.role_id == 13)
                .order_by(TgMessages.month_count.desc())
            )
            for uid, tgmess in qfzgz.tuples():
                user = (
                    await session.execute(select(Users).filter(Users.id == uid))
                ).scalar_one_or_none()
                if tgmess.month_count > 450:
                    bonus = (tgmess.month_count - 450) * 400 + 100000
                    ret += f"\n{tgmess.tg_name} 水群 {tgmess.month_count} 条，奖励 {bonus} 象草"
                    await user.addbonus(bonus, "气氛组每月工资")
                else:
                    ret += f"\n{tgmess.tg_name} 水群 {tgmess.month_count} 条，没有达标"
            await app.send_message(GROUP_ID[1], ret)
            await session.execute(update(TgMessages).values(month_count=0))
            return


scheduler.add_job(day_water_bonus, "cron", hour="0", minute="0", second="0")
scheduler.add_job(month_water_bonus, "cron", day="1", hour="0", minute="0", second="0")
