import re
from sqlalchemy import select
import logging

from app import scheduler, redis_cli, get_app
from app.models import ASSession
from app.models.nexusphp import News
from config import CHANNEL_ID


news_id = redis_cli.get("news_id")
logger = logging.getLogger("scheduler")


def remove_bbcode_tags(text):
    bbcodes_pattern = r"\[/?[a-zA-Z]+\b(?:=[^\]]*)?\]"
    cleaned_text = re.sub(bbcodes_pattern, "", text)
    cleaned_text = re.sub(r" {10,}", "\n", cleaned_text)
    return cleaned_text


async def get_news(news_id=0):
    news_id = int(news_id)
    query = (await ASSession.execute(select(News).filter(News.id > news_id))).scalars()

    return query.all()


async def post_news():
    global news_id
    app = get_app()
    async with ASSession() as session:
        async with session.begin():
            if not news_id:
                news_id = (
                    await session.execute(
                        select(News.id).order_by(News.id.desc()).limit(1)
                    )
                ).scalar_one_or_none()
                redis_cli.set("news_id", news_id)
            logger.info(f"已监听最新news_id：{news_id}")
            news = await get_news(news_id)
            for new in news:
                news_id = new.id
                logger.info(f"找到新公告news_id：{news_id}")
                message = await app.send_message(
                    CHANNEL_ID,
                    f"**[站点公告]{new.title}**\n\n{remove_bbcode_tags(new.body)}",
                )
                await message.pin()
            redis_cli.set("news_id", news_id)


scheduler.add_job(post_news, "interval", seconds=60)
