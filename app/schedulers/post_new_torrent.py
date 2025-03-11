import logging

from sqlalchemy import select

from app import scheduler, redis_cli, get_app
from app.models.nexusphp import Torrents, TorrentsTag, Settings
from app.models import ASSession
from config import CHANNEL_ID

torrent_id = redis_cli.get("torrent_id")
baseurl = None
logger = logging.getLogger("scheduler")


async def get_setting(name: str) -> str:
    setting = (
        await ASSession.execute(select(Settings).filter(Settings.name == name))
    ).scalar_one_or_none()

    if setting:
        return setting.value


async def get_new_torrents(torrent_id=0, tag_id=3):
    torrent_id = int(torrent_id)
    query = (
        await ASSession.execute(
            select(Torrents)
            .join(TorrentsTag, Torrents.id == TorrentsTag.torrent_id)
            .filter(TorrentsTag.tag_id == tag_id)
            .filter(Torrents.id > torrent_id)
        )
    ).scalars()

    return query.all()


async def post_new_torrent():
    global baseurl, torrent_id
    app = get_app()
    async with ASSession() as session:
        async with session.begin():
            if not baseurl:
                baseurl = await get_setting("basic.BASEURL")
            if not torrent_id:
                torrent_id = (
                    await session.execute(
                        select(Torrents.id).order_by(Torrents.id.desc()).limit(1)
                    )
                ).scalar_one_or_none()
                redis_cli.set("torrent_id", torrent_id)
            logger.info(f"已监听最新torrent_id：{torrent_id}")
            new_torrents = await get_new_torrents(torrent_id)
            for torrent in new_torrents:
                torrent_id = torrent.id
                logger.info(f"找到官种torrent_id：{torrent_id}")
                await app.send_message(
                    CHANNEL_ID,
                    f"**新的官种发布**\n[{torrent.name}](https://{baseurl}/details.php?id={torrent.id})",
                )
            redis_cli.set("torrent_id", torrent_id)


scheduler.add_job(post_new_torrent, "interval", seconds=60)
