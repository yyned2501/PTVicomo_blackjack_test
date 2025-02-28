import asyncio
import weakref
import logging

from sqlalchemy.ext.asyncio import (
    create_async_engine,
    async_sessionmaker,
    async_scoped_session,
    AsyncSession,
)

from app.models.base import Base

from config import MYSQL_USER, MYSQL_PASSWORD, MYSQL_HOST, MYSQL_DATABASE

logger = logging.getLogger("main")
active_sessions = weakref.WeakSet()


class TrackedAsyncSession(AsyncSession):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        active_sessions.add(self)
        logger.debug(f"{self} add")

    async def close(self):
        await super().close()
        logger.debug(f"{self} close")
        active_sessions.discard(self)

    def begin(self):
        logger.debug(f"{self} begin")
        if not self.in_transaction():
            return super().begin()
        else:
            logger.warning(f"{self} is begun use begin_nested instead")
            return self.begin_nested()


async_connection_string = (
    f"mysql+asyncmy://{MYSQL_USER}:{MYSQL_PASSWORD}@{MYSQL_HOST}/{MYSQL_DATABASE}"
)
async_engine = create_async_engine(async_connection_string)
ASSession = async_scoped_session(
    async_sessionmaker(bind=async_engine, class_=TrackedAsyncSession),
    asyncio.current_task,
)


async def check_open_sessions():
    logger.info(f"open_sessions:{[session for session in active_sessions]}")


async def create_all():
    from . import nexusphp

    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
