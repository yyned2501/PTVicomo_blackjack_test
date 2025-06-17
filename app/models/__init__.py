import asyncio
import logging

from sqlalchemy.ext.asyncio import (
    create_async_engine,
    async_sessionmaker,
    async_scoped_session,
    AsyncSession as _AsyncSession,
)

from app.models.base import Base

from config import MYSQL_USER, MYSQL_PASSWORD, MYSQL_HOST, MYSQL_DATABASE

logger = logging.getLogger("main")


class AsyncSession(_AsyncSession):
    def begin(self):
        if not self.in_transaction():
            return super().begin()
        else:
            return self.begin_nested()


def scope_task(loop):
    return asyncio.current_task(loop)


async_connection_string = (
    f"mysql+asyncmy://{MYSQL_USER}:{MYSQL_PASSWORD}@{MYSQL_HOST}/{MYSQL_DATABASE}"
)

async_engine = create_async_engine(
    async_connection_string,
    pool_size=10,
    max_overflow=20,
    pool_timeout=30,
    pool_recycle=3600,
)
ASSession = async_scoped_session(
    async_sessionmaker(bind=async_engine, expire_on_commit=False, class_=AsyncSession),
    asyncio.current_task,
)


async def create_all():
    from . import nexusphp

    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
