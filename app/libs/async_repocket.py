import asyncio

from sqlalchemy import delete, select

from app.models.nexusphp import Redpocket, RedpocketClaimed
from app.models import ASSession

lock = asyncio.Lock()


class RedPockets:
    redpockets_claimeds: dict[str, list[int]] = {}
    
    async def async_init(self):
        redpockets = await ASSession.execute(select(Redpocket))
        for redpocket in redpockets.scalars():
            if redpocket.count > 0:
                self.redpockets_claimeds[redpocket.password] = [
                    claimed.tg_id for claimed in redpocket.claimed
                ]
            else:
                await ASSession.delete(redpocket)

    def post_redpocket(
        self,
        from_uid: int,
        bonus: int,
        count: int,
        password: str,
        type_: int,
    ) -> Redpocket:
        redpocket = Redpocket(
            from_uid=from_uid,
            bonus=bonus,
            count=count,
            password=password,
            _pocket_type=type_,
        )
        self.redpockets_claimeds[password] = []
        ASSession.add(redpocket)
        return redpocket

    async def search_pocket(self, password: str) -> Redpocket:
        if password in self.redpockets_claimeds.keys():
            redpocket = (
                await ASSession.execute(
                    select(Redpocket).filter(Redpocket.password == password)
                )
            ).scalar_one()
            return redpocket

    async def get_pocket(self, tg_id: int, password: str):
        session = ASSession()
        async with lock:
            redpocket = await self.search_pocket(password)
            claimed = RedpocketClaimed(redpocket_id=redpocket.id, tg_id=tg_id)
            bonus = redpocket.get()
            self.redpockets_claimeds.get(password, []).append(tg_id)
            session.add(claimed)
            return bonus, redpocket

    async def delete_redpocket(self, password: str):
        session = ASSession()
        async with lock:
            redpocket = await self.search_pocket(password)
            await session.execute(
                delete(RedpocketClaimed).where(
                    RedpocketClaimed.redpocket_id == redpocket.id
                )
            )
            await session.delete(redpocket)
            del self.redpockets_claimeds[password]
