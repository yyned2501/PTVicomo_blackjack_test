from app import scheduler, redis_cli, get_app
from config import GROUP_ID


async def refresh_qfz_bonus():
    redis_cli.set("qfz_bonus", 50000)
    app = get_app()
    await app.send_message(GROUP_ID[1], f"气氛组红包余额 {50000}")


scheduler.add_job(refresh_qfz_bonus, "cron", hour="0", minute="0", second="0")
