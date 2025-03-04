import asyncio

from sqlalchemy.ext.asyncio import (
    create_async_engine,
    async_sessionmaker,
    async_scoped_session,
)

from app.models.base import Base

from config import MYSQL_USER, MYSQL_PASSWORD, MYSQL_HOST, MYSQL_DATABASE


async_connection_string = (
    f"mysql+asyncmy://{MYSQL_USER}:{MYSQL_PASSWORD}@{MYSQL_HOST}/{MYSQL_DATABASE}"
)
async_engine = create_async_engine(async_connection_string)
ASSession = async_scoped_session(
    async_sessionmaker(bind=async_engine),
    asyncio.current_task,
)


async def create_all():
    from . import nexusphp

    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
