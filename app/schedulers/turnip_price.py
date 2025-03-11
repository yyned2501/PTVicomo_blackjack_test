from datetime import datetime
from sqlalchemy import select

from app import get_app, scheduler
from app.models import ASSession
from app.models.nexusphp import Custom_turnip_calendar
from config import GROUP_ID


async def schedule_turnip_price():
    app = get_app()
    async with ASSession() as session:
        async with session.begin():
            turnip = (
                await session.execute(
                    select(Custom_turnip_calendar)
                    .filter(Custom_turnip_calendar.date <= datetime.now())
                    .order_by(Custom_turnip_calendar.date.desc())
                    .limit(1)
                )
            ).scalar_one_or_none()
            if turnip:
                return await app.send_message(
                    GROUP_ID[0], f"#大头菜价\n当前{turnip.name}价格: {turnip.price}"
                )


scheduler.add_job(schedule_turnip_price, "cron", hour="0,12", minute="0", second="0")
