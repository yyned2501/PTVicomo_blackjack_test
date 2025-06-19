from sqlalchemy import BigInteger
from sqlalchemy.orm import mapped_column, DeclarativeBase, Mapped
from sqlalchemy.ext.asyncio import AsyncAttrs

from app.models import ASSession


class Base(AsyncAttrs, DeclarativeBase):
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)

    @classmethod
    async def get(cls, id):
        async with ASSession() as session, session.begin():
            return await session.get(cls, id)
