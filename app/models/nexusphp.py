import logging
import random
import datetime

from sqlalchemy import (
    Column,
    ForeignKey,
    String,
    Integer,
    Float,
    BigInteger,
    Text,
    TIMESTAMP,
    SmallInteger,
    DateTime,
    Enum,
    func,
    select,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from pyrogram.types.messages_and_media import Message

from app.commands.setup import ADMINS
from app.models import ASSession
from app.models.base import Base
from app.libs.func import format_byte_size


logger = logging.getLogger("main")

CLASS_NAME = [
    "peasant(墨刑者)",
    "user(岛民)",
    "Power User(伍长)",
    "Elite User(什长)",
    "Crazy User(里正)",
    "Insane User(亭长)",
    "Veteran User(乡秩)",
    "Extreme User(县道)",
    "Ultimate User(郡府)",
    "Nexus Master(公卿)",
    "贵宾",
    "养老族",
    "发布员",
    "总版主",
    "管理员",
    "维护开发员",
    "岛主",
]


class BotBinds(Base):
    __tablename__ = "plugin_telegram_bot_binds"
    uid: Mapped[int] = mapped_column(ForeignKey("users.id"))
    telegram_account_id: Mapped[int] = mapped_column(BigInteger)
    telegram_account_username: Mapped[str] = mapped_column(String(255))
    user: Mapped["Users"] = relationship(back_populates="bot_bind", lazy="subquery")


class Users(Base):
    __tablename__ = "users"
    username: Mapped[str] = mapped_column(String(40))
    seedbonus: Mapped[float] = mapped_column(Float)
    email: Mapped[str] = mapped_column(String(80))
    passkey: Mapped[str] = mapped_column(String(32))
    uploaded: Mapped[int] = mapped_column(BigInteger)
    downloaded: Mapped[int] = mapped_column(BigInteger)
    vip_added: Mapped[str] = mapped_column(Enum("yes", "no"))
    vip_until: Mapped[DateTime] = mapped_column(TIMESTAMP)
    invites: Mapped[int] = mapped_column(SmallInteger)
    _class: Mapped[int] = mapped_column("class", SmallInteger)
    two_step_secret: Mapped[str] = mapped_column(String(255))
    attendance_card: Mapped[int] = mapped_column(Integer)
    bonuscomment: Mapped[str] = mapped_column(Text)
    bot_bind: Mapped["BotBinds"] = relationship(back_populates="user", lazy="subquery")
    user_roles: Mapped[list["UserRoles"]] = relationship(
        back_populates="user", lazy="subquery"
    )
    user_metas: Mapped[list["UserMetas"]] = relationship(
        back_populates="user", lazy="subquery"
    )
    roles_names: Mapped[list["Roles"]] = relationship(
        "Roles",
        secondary="user_roles",
        viewonly=True,
        back_populates="users",
        lazy="subquery",
    )
    bonus_logs: Mapped[list["BonusLogs"]] = relationship(
        "BonusLogs",
        back_populates="user",
        lazy="subquery",
    )

    @property
    def uploaded_str(self):
        return format_byte_size(self.uploaded)

    @property
    def downloaded_str(self):
        return format_byte_size(self.downloaded)

    @property
    def rate(self):
        if self.downloaded == 0:
            return "inf."
        return round(self.uploaded / self.downloaded, 2)

    @property
    def class_name(self):
        return CLASS_NAME[self._class]

    @property
    def role_names(self):
        return " ".join([role.name for role in self.roles_names])

    async def addbonus(self, bonus: float, comment=""):
        session = ASSession()
        old = self.seedbonus
        bonus = round(bonus, 1)
        new = round(self.seedbonus + bonus, 1)
        write_comment = f"[TG] {comment} {bonus} 象草"
        self.seedbonus = text(f"{bonus}+seedbonus")
        self.bonuscomment = func.concat(
            f'{datetime.datetime.now().strftime("%Y-%m-%d")} - {write_comment}\n',
            text("SUBSTRING_INDEX(bonuscomment, '\n', 99)"),
        )
        self.bonus_logs.append(
            BonusLogs(
                business_type=123,
                uid=self.id,
                old_total_value=old,
                value=abs(bonus),
                new_total_value=new,
                comment=write_comment,
                created_at=datetime.datetime.now(),
                updated_at=datetime.datetime.now(),
            )
        )
        await session.flush()
        logger.info(f"{self.id}|{old}|{bonus}|{new}|{comment}")

    def setvip(self, days=7):
        self._class = 10
        self.vip_added = "yes"
        self.vip_until = datetime.datetime.now() + datetime.timedelta(days=days)

    def add_rbid(self, days=7):
        if self.user_metas:
            for user_meta in self.user_metas:
                if user_meta.meta_key == "PERSONALIZED_USERNAME":
                    if not user_meta.deadline:
                        return False, days
                    if user_meta.deadline < datetime.datetime.now():
                        user_meta.deadline = (
                            datetime.datetime.now() + datetime.timedelta(days=days)
                        )
                        return False, 0
                    elif (
                        user_meta.deadline
                        > datetime.datetime.now() + datetime.timedelta(days=30)
                    ):
                        return False, days
                    else:
                        user_meta.deadline += datetime.timedelta(days=days)
                        return False, 0
        return (
            UserMetas(
                uid=self.id,
                meta_key="PERSONALIZED_USERNAME",
                deadline=datetime.datetime.now() + datetime.timedelta(days=days),
            ),
            0,
        )

    def is_role(self, n):
        role_ids = [role.role_id for role in self.user_roles]
        if n in role_ids:
            return True

    @classmethod
    async def bind(cls, passkey: str, message: Message):
        async with (session := ASSession()).begin():
            user = (
                await session.execute(select(cls).filter(cls.passkey == passkey))
            ).scalar_one_or_none()
            if user:
                tg_name = user.get_tg_name(message)
                tg_id = message.from_user.id
                if user.bot_bind:
                    user.bot_bind.uid = user.id
                    user.bot_bind.telegram_account_id = tg_id
                    user.bot_bind.telegram_account_username = tg_name
                else:
                    user.bot_bind = BotBinds(
                        uid=user.id,
                        telegram_account_id=tg_id,
                        telegram_account_username=tg_name,
                    )
                    session.add(user.bot_bind)
                return True

    async def unbind(self):
        async with (session := ASSession()).begin():
            if self.bot_bind:
                await session.delete(self.bot_bind)

    @classmethod
    async def get_user_from_tg_id(cls, tg_id: int):
        async with (session := ASSession()).begin():
            user = (
                await session.execute(
                    select(cls)
                    .join(BotBinds, cls.id == BotBinds.uid)
                    .filter(BotBinds.telegram_account_id == tg_id)
                )
            ).scalar_one_or_none()
            if user:
                return user

    @staticmethod
    def get_tg_name(message: Message):
        if not message.from_user:
            if message.author_signature:
                message.from_user = ADMINS[message.author_signature]
                message.from_user.first_name = message.author_signature
            if message.sender_chat:
                message.from_user = message.sender_chat
                message.from_user.first_name = message.sender_chat.title
        tg_name = " ".join(
            [
                name
                for name in [
                    message.from_user.first_name,
                    message.from_user.last_name,
                ]
                if name
            ]
        )
        return tg_name

    async def update_tg_name(self, message: Message):
        async with (session := ASSession()).begin():
            tg_name = self.get_tg_name(message)
            self.bot_bind.telegram_account_username = tg_name
            await session.flush()

    @classmethod
    async def get_user_from_tgmessage(cls, message: Message):
        async with (session := ASSession()).begin():
            user = await cls.get_user_from_tg_id(message.from_user.id)
            if user:
                await user.update_tg_name(message)
                return user


class BonusLogs(Base):
    __tablename__ = "bonus_logs"
    business_type: Mapped[int] = mapped_column(Integer)
    uid: Mapped[int] = mapped_column(ForeignKey("users.id"))
    old_total_value: Mapped[float] = mapped_column(Float)
    value: Mapped[float] = mapped_column(Float)
    new_total_value: Mapped[float] = mapped_column(Float)
    comment: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[DateTime] = mapped_column(TIMESTAMP)
    updated_at: Mapped[DateTime] = mapped_column(TIMESTAMP)
    user: Mapped["Users"] = relationship(back_populates="bonus_logs")


class UserMetas(Base):
    __tablename__ = "user_metas"
    uid: Mapped[int] = mapped_column(ForeignKey("users.id"))
    meta_key: Mapped[str] = mapped_column(String(255))
    deadline: Mapped[DateTime] = mapped_column(TIMESTAMP)
    user: Mapped["Users"] = relationship(back_populates="user_metas")


class UserRoles(Base):
    __tablename__ = "user_roles"
    uid: Mapped[int] = mapped_column(ForeignKey("users.id"))
    role_id: Mapped[int] = mapped_column(ForeignKey("roles.id"))
    user: Mapped["Users"] = relationship(back_populates="user_roles")
    roles: Mapped["Roles"] = relationship(back_populates="user_roles")


class Roles(Base):
    __tablename__ = "roles"
    name: Mapped[str] = mapped_column(String(255))
    user_roles: Mapped["UserRoles"] = relationship(back_populates="roles")
    users: Mapped[list["Users"]] = relationship(
        "Users", secondary="user_roles", viewonly=True, back_populates="roles_names"
    )


class Settings(Base):
    __tablename__ = "settings"
    name: Mapped[str] = mapped_column(String(255))
    value: Mapped[str] = mapped_column(Text)


class Custom_turnip_calendar(Base):
    __tablename__ = "custom_turnip_calendar"
    date: Mapped[DateTime] = mapped_column(TIMESTAMP)
    price: Mapped[float] = mapped_column(Float)
    name: Mapped[str] = mapped_column(String(255))


class Redpocket(Base):
    __tablename__ = "custom_redpockets_new"
    from_uid: Mapped[int] = mapped_column(BigInteger)
    from_uname: Mapped[str] = mapped_column(String(40))
    content: Mapped[str] = mapped_column(String(255))
    bonus: Mapped[int] = mapped_column(Integer)
    remain_bonus: Mapped[int] = mapped_column(Integer)
    count: Mapped[int] = mapped_column(Integer)
    remain_count: Mapped[int] = mapped_column(Integer)
    _pocket_type: Mapped[int] = mapped_column("pocket_type", Integer)
    claimed: Mapped[list["RedpocketClaimed"]] = relationship(
        "RedpocketClaimed", lazy="subquery"
    )
    tpye_name = ["拼手气红包", "锦鲤红包"]

    async def get(self):
        async with ASSession().begin():
            bonus = None
            if self._pocket_type == 0:
                avg_bonus = self.remain_bonus / self.remain_count
                if self.remain_bonus == 1:
                    bonus = self.remain_bonus
                else:
                    bonus = random.randint(int(avg_bonus * 0.5), int(avg_bonus * 1.5))
                self.remain_bonus = text(f"remain_bonus-{bonus}")
            self.remain_count = text(f"remain_count-1")
        return bonus

    def draw(self):
        n = len(self.claimed)
        lucky_n = random.randint(0, n - 1)
        lucky_user = self.claimed[lucky_n].tg_id
        return self.bonus, lucky_user

    @classmethod
    async def create(
        cls,
        from_uid: int,
        from_uname: str,
        bonus: int,
        count: int,
        content: str,
        type_: int,
    ):
        async with (session := ASSession()).begin():
            redpocket = cls(
                from_uid=from_uid,
                from_uname=from_uname,
                content=content,
                bonus=bonus,
                remain_bonus=bonus,
                count=count,
                remain_count=count,
                _pocket_type=type_,
            )
            session.add(redpocket)
            return redpocket

    @property
    def pocket_type(self):
        return self.tpye_name[self._pocket_type]


class RedpocketClaimed(Base):
    __tablename__ = "custom_redpockets_claimed"
    redpocket_id: Mapped[int] = mapped_column(ForeignKey("custom_redpockets.id"))
    tg_id: Mapped[int] = mapped_column(BigInteger)
    redpocket = relationship(
        "Redpocket",
        back_populates="claimed",
    )


class Torrents(Base):
    __tablename__ = "torrents"
    name: Mapped[str] = mapped_column(String(255))


class TorrentsTag(Base):
    __tablename__ = "torrent_tags"
    torrent_id: Mapped[int] = mapped_column(Integer)
    tag_id: Mapped[int] = mapped_column(Integer)


class News(Base):
    __tablename__ = "news"
    title: Mapped[str] = mapped_column(String(255))
    body: Mapped[str] = mapped_column(Text)
    added: Mapped[DateTime] = mapped_column(DateTime)


class TgMessages(Base):
    __tablename__ = "custom_tg_messages"
    tg_id: Mapped[int] = mapped_column(BigInteger)
    tg_name: Mapped[str] = mapped_column(String(255))
    day_count: Mapped[int] = mapped_column(Integer, default=0)
    month_count: Mapped[int] = mapped_column(Integer, default=0)
    total_count: Mapped[int] = mapped_column(Integer, default=0)

    @classmethod
    async def get_tgmess_from_tgmessage(cls, message: Message):
        tg_id = message.from_user.id
        async with (session := ASSession()).begin():
            tgmess = (
                await session.execute(select(cls).filter(cls.tg_id == tg_id))
            ).scalar_one_or_none()
            if not tgmess:
                tg_name = Users.get_tg_name(message)
                tgmess = cls(tg_id=tg_id, tg_name=tg_name)
                session.add(tgmess)
            return tgmess

    def send_message(self):
        self.day_count += 1
        self.month_count += 1
        self.total_count += 1

    def clean_day(self):
        self.day_count = 0

    def clean_month(self):
        self.month_count = 0


class LuckyDrawPrizes(Base):
    __tablename__ = "lucky_draw_prizes"
    type: Mapped[int] = mapped_column(Integer)
    amount: Mapped[int] = mapped_column(Integer)
    probability: Mapped[int] = mapped_column(Integer)
    up_probability = 0
    n = 0


class LuckyDrawPrizesNum(Base):
    __tablename__ = "custom_lucky_draw_prizes_num"
    name: Mapped[str] = mapped_column(String(300))
    current_num: Mapped[int] = mapped_column(Integer)
    n = 0


class LotteryHistory(Base):
    __tablename__ = "custom_lottery_history"
    messageid: Mapped[int] = mapped_column(Integer)
    number: Mapped[str] = mapped_column(String(3), nullable=True)
    create_time: Mapped[datetime.datetime] = mapped_column(DateTime, default=func.now())
    update_time: Mapped[datetime.datetime] = mapped_column(
        DateTime, default=func.now(), onupdate=func.now()
    )


class LotteryBetHistory(Base):
    __tablename__ = "custom_lottery_bet_history"
    history_id: Mapped[int] = mapped_column(BigInteger)
    user_id: Mapped[int] = mapped_column(BigInteger)
    number: Mapped[str] = mapped_column(String(3))
    bonus: Mapped[int] = mapped_column(Integer)
    win_bonus: Mapped[int] = mapped_column(Integer)
    tax: Mapped[int] = mapped_column(Integer, nullable=True)


class BlackJackHistory(Base):
    __tablename__ = "custom_blackjack_history"
    user_id: Mapped[int] = mapped_column(BigInteger)
    result: Mapped[str] = mapped_column(String(5))
    bonus: Mapped[int] = mapped_column(BigInteger)
    win_bonus: Mapped[int] = mapped_column(BigInteger)
    tax: Mapped[int] = mapped_column(BigInteger, nullable=True)
    create_time: Mapped[datetime.datetime] = mapped_column(DateTime, default=func.now())
