import json
import random
import logging
from sqlalchemy import column, desc, func, select

from app import redis_cli
from pyrogram import filters, Client
from pyrogram.types.messages_and_media import Message
from app.libs.async_user import User
from app.libs.decorators import auto_delete_message, s_delete_message
from app.models import ASSession
from app.models.nexusphp import BlackJackHistory, BotBinds
from app.normal_reply import USER_BIND_NONE, NOT_ENOUGH_BONUS_HALF
from config import GROUP_ID
from pyrogram.types import (
    Message,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    CallbackQuery,
)

TAX_RATE = 0.01
MAX_BONUS = 10000
logger = logging.getLogger("blackjack")


class Deck:
    def __init__(self, tg_id=None, tg_name=None, bonus=None):
        self.tg_id = tg_id
        self.tg_name = tg_name
        self.bonus = bonus
        self.dealer_hand = []
        self.player_hand = []
        self.cards = [
            f"{rank}{suit}"
            for rank in [
                "2",
                "3",
                "4",
                "5",
                "6",
                "7",
                "8",
                "9",
                "10",
                "J",
                "Q",
                "K",
                "A",
            ]
            for suit in ["♠", "♥", "♦", "♣"]
        ]
        random.shuffle(self.cards)

    def draw_card(self):
        if self.cards:
            return self.cards.pop()
        else:
            return None

    def dealer_draw(self):
        card = self.draw_card()
        if card:
            self.dealer_hand.append(card)
        return card

    def player_draw(self):
        card = self.draw_card()
        if card:
            self.player_hand.append(card)
        return card

    def calculate_hand_value(self, hand):
        value = 0
        aces = 0
        for card in hand:
            rank = card[:-1]
            if rank in ["J", "Q", "K"]:
                value += 10
            elif rank == "A":
                aces += 1
                value += 11
            else:
                value += int(rank)

        while value > 21 and aces:
            value -= 10
            aces -= 1

        return value

    def dealer_hand_value(self):
        return self.calculate_hand_value(self.dealer_hand)

    def player_hand_value(self):
        return self.calculate_hand_value(self.player_hand)

    def save_to_redis(self, chat_id, message_id):
        deck_data = {
            "dealer_hand": self.dealer_hand,
            "player_hand": self.player_hand,
            "cards": self.cards,
            "tg_id": self.tg_id,
            "bonus": self.bonus,
            "tg_name": self.tg_name,
        }
        redis_cli.set(f"blackjack:{chat_id}:{message_id}", json.dumps(deck_data))

    @classmethod
    def from_redis(cls, chat_id, message_id):
        deck_data = redis_cli.get(f"blackjack:{chat_id}:{message_id}")
        if deck_data:
            deck_data = json.loads(deck_data)
            deck = cls()
            deck.dealer_hand = deck_data["dealer_hand"]
            deck.player_hand = deck_data["player_hand"]
            deck.cards = deck_data["cards"]
            deck.tg_id = deck_data["tg_id"]
            deck.bonus = deck_data["bonus"]
            deck.tg_name = deck_data["tg_name"]
            return deck
        return None

    @property
    def user(self):
        return f"[{self.tg_name}](tg://user?id={self.tg_id})"

    def get_tg_message_reply(self, end_flag=False):
        ret_str = f"玩家：{self.user}\n象草：{self.bonus}\n"
        if end_flag:
            dealer_hand = " ".join(self.dealer_hand)
            ret_str += f"庄{self.dealer_hand_value()}点：{dealer_hand}\n"
        else:
            dealer_hand = "??? " + " ".join(self.dealer_hand[1:])
            ret_str += f"庄：{dealer_hand}\n"
        player_hand = " ".join(self.player_hand)
        return ret_str + f"你{self.player_hand_value()}点：{player_hand}"

    def get_tg_message_reply_text(self, end_flag=False):
        ret_str = f"玩家：{self.tg_name}\n象草：{self.bonus}\n"
        if end_flag:
            dealer_hand = " ".join(self.dealer_hand)
            ret_str += f"庄{self.dealer_hand_value()}点：{dealer_hand}\n"
        else:
            dealer_hand = "??? " + " ".join(self.dealer_hand[1:])
            ret_str += f"庄：{dealer_hand}\n"
        player_hand = " ".join(self.player_hand)
        return ret_str + f"你{self.player_hand_value()}点：{player_hand}"

    def calculate_result(self):
        while self.dealer_hand_value() < 17:
            self.dealer_draw()
        dealer_value = self.dealer_hand_value()
        player_value = self.player_hand_value()
        if player_value == dealer_value:
            if player_value == 21:
                if len(self.player_hand) == 2 and len(self.dealer_hand) == 2:
                    return 0
                elif len(self.player_hand) == 2:
                    return 1
                elif len(self.dealer_hand) == 2:
                    return -1
            return 0
        elif player_value > 21 and dealer_value > 21:
            return 0
        elif player_value > 21:
            return -1
        elif dealer_value > 21:
            return 1
        elif player_value > dealer_value:
            return 1
        elif player_value < dealer_value:
            return -1
        else:
            return 0


# 添加一个字典来记录每个游戏的 deck
game_decks: dict[str, Deck] = {}


def get_deck_by_message_id(chat_id, message_id):
    key = f"{chat_id}:{message_id}"
    deck = game_decks.get(key)
    if not deck:
        deck = Deck.from_redis(chat_id, message_id)
        if deck:
            game_decks[key] = deck
    return deck


reply_markup = InlineKeyboardMarkup(
    [
        [
            InlineKeyboardButton("拿牌", callback_data=f"add"),
            InlineKeyboardButton("不拿", callback_data=f"done"),
        ],
        [
            InlineKeyboardButton("刷新", callback_data=f"refresh"),
        ],
    ]
)
blackjackrank_reply_markup = InlineKeyboardMarkup(
    [
        [
            InlineKeyboardButton("全部榜单", callback_data="rank_all"),
            InlineKeyboardButton("昨日榜单", callback_data="rank_yesterday"),
            InlineKeyboardButton("今日榜单", callback_data="rank_today"),
        ],
    ]
)


@Client.on_message(filters.chat(GROUP_ID) & filters.command("blackjack"))
@Client.on_message(filters.private & filters.command("blackjack"))
async def blackjack(client: Client, message: Message):
    try:
        bonus = int(message.command[1])
        if bonus > MAX_BONUS:
            raise Exception
    except Exception as e:
        reply_message = await message.reply(
            f"请输入正确的命令\n格式：/blackjack <象草数量> 最大{MAX_BONUS:,}象草\n例如：`/blackjack {MAX_BONUS}`"
        )
        s_delete_message(message, 60)
        s_delete_message(reply_message, 60)
        return
    async with ASSession() as session:
        async with session.begin():
            async with User(message) as user:
                if not user.botbind:
                    s_delete_message(message, 60)
                    s_delete_message(await message.reply(USER_BIND_NONE), 60)
                    return
                if user.user.seedbonus / 2 < bonus:
                    s_delete_message(message, 60)
                    s_delete_message(await message.reply(NOT_ENOUGH_BONUS_HALF), 60)
                    return
                deck = Deck(user.tg_id, user.tg_name, bonus)
                user.user.addbonus(-bonus, "blackjack开局")
    for _ in range(2):
        deck.dealer_draw()
        deck.player_draw()
    if deck.player_hand_value() == 21 or deck.dealer_hand_value() == 21:
        result = await end_game(deck)
        s_delete_message(
            await message.reply(
                deck.get_tg_message_reply(True) + f"\n\n{result_map[result]}"
            ),
            60,
        )
        await message.delete()
        return
    key = f"{message.chat.id}:{message.id}"
    game_decks[key] = deck

    game_message = await client.send_message(
        message.chat.id,
        deck.get_tg_message_reply(),
        reply_markup=reply_markup,
        reply_to_message_id=message.id,
    )
    deck.save_to_redis(game_message.chat.id, game_message.id)


@Client.on_callback_query(filters.regex(r"add"))
async def handle_callback_query(client: Client, callback_query: CallbackQuery):
    message_id = callback_query.message.id
    chat_id = callback_query.message.chat.id
    key = f"{chat_id}:{message_id}"
    deck = get_deck_by_message_id(chat_id, message_id)
    if not deck:
        await callback_query.answer("无法找到游戏数据。", show_alert=True)
        return
    if callback_query.from_user.id != deck.tg_id:
        await callback_query.answer("不能操作别人的游戏", show_alert=True)
        return
    if (
        redis_message := deck.get_tg_message_reply_text()
    ) != callback_query.message.text:
        logger.info(redis_message)
        logger.info(callback_query.message.text)
        logger.info(redis_message == callback_query.message.text)
        if deck.player_hand_value() >= 21:
            result = await end_game(deck, key)
            await callback_query.message.edit_text(
                deck.get_tg_message_reply(True) + f"\n\n{result_map[result]}",
            )
            s_delete_message(callback_query.message, 60)
            await callback_query.message.reply_to_message.delete()
            return
        await callback_query.message.edit_text(
            redis_message,
            reply_markup=reply_markup,
        )
        return "数据不一致，为您刷新数据"
    if deck.dealer_hand_value() < 17:
        deck.dealer_draw()
    deck.player_draw()
    if deck.player_hand_value() >= 21:
        result = await end_game(deck, key)
        await callback_query.message.edit_text(
            deck.get_tg_message_reply(True) + f"\n\n{result_map[result]}",
        )
        s_delete_message(callback_query.message, 60)
        await callback_query.message.reply_to_message.delete()
        return
    await callback_query.message.edit_text(
        deck.get_tg_message_reply(),
        reply_markup=reply_markup,
    )
    deck.save_to_redis(chat_id, message_id)
    return


@Client.on_callback_query(filters.regex(r"done"))
async def handle_done_callback_query(client: Client, callback_query: CallbackQuery):
    message_id = callback_query.message.id
    chat_id = callback_query.message.chat.id
    key = f"{chat_id}:{message_id}"
    deck = get_deck_by_message_id(chat_id, message_id)
    if not deck:
        await callback_query.answer("无法找到游戏数据。", show_alert=True)
        return
    if callback_query.from_user.id != deck.tg_id:
        await callback_query.answer("不能操作别人的游戏", show_alert=True)
        return
    result = await end_game(deck, key)
    await callback_query.message.edit_text(
        deck.get_tg_message_reply(True) + f"\n\n{result_map[result]}",
    )
    s_delete_message(callback_query.message, 60)
    await callback_query.message.reply_to_message.delete()
    return


@Client.on_callback_query(filters.regex(r"refresh"))
async def handle_done_callback_query(client: Client, callback_query: CallbackQuery):
    message_id = callback_query.message.id
    chat_id = callback_query.message.chat.id
    key = f"{chat_id}:{message_id}"
    deck = get_deck_by_message_id(chat_id, message_id)
    if not deck:
        await callback_query.answer("无法找到游戏数据。", show_alert=True)
        return
    if callback_query.from_user.id != deck.tg_id:
        await callback_query.answer("不能操作别人的游戏", show_alert=True)
        return
    if deck.player_hand_value() >= 21:
        result = await end_game(deck, key)
        await callback_query.message.edit_text(
            deck.get_tg_message_reply(True) + f"\n\n{result_map[result]}",
        )
        s_delete_message(callback_query.message, 60)
        await callback_query.message.reply_to_message.delete()
        return
    redis_message = deck.get_tg_message_reply_text()
    if redis_message != callback_query.message.text:
        await callback_query.message.edit_text(
            redis_message,
            reply_markup=reply_markup,
        )
    await callback_query.answer("刷新成功")


result_map = {1: "你赢了！", 0: "平局！", -1: "你输了！"}


async def end_game(deck: Deck, key: str = None):
    result = deck.calculate_result()

    async with ASSession() as session:
        logger.info(f"{key},{session}")
        async with session.begin():
            botbind = (
                (
                    await session.execute(
                        select(BotBinds).filter(
                            BotBinds.telegram_account_id == deck.tg_id
                        )
                    )
                )
                .scalars()
                .one_or_none()
            )
            user = botbind.user
            win_bonus = 0
            if result == 1:
                win_bonus = deck.bonus * 2
            elif result == 0:
                win_bonus = deck.bonus
            tax = max(int((win_bonus - deck.bonus) * TAX_RATE), 0)
            session.add(
                BlackJackHistory(
                    user_id=user.id,
                    result=f"{deck.dealer_hand_value()}:{deck.player_hand_value()}",
                    bonus=deck.bonus,
                    win_bonus=win_bonus,
                    tax=tax,
                )
            )
            if win_bonus > 0:
                user.addbonus(win_bonus - tax, "blackjack结局")
    if key:
        del game_decks[key]
        redis_cli.delete(f"blackjack:{key}")
    return result


def get_blackjack_rank_query(date_filter):
    query = select(
        BotBinds.telegram_account_username,
        (
            func.sum(BlackJackHistory.win_bonus)
            - func.sum(BlackJackHistory.bonus)
            - func.sum(BlackJackHistory.tax)
        ).label("total_win_bonus"),
    ).join(BlackJackHistory, BotBinds.uid == BlackJackHistory.user_id)
    if date_filter is not None:
        query = query.filter(func.date(BlackJackHistory.create_time) == date_filter)
    query = query.group_by(BlackJackHistory.user_id, BotBinds.telegram_account_username)
    return query


async def generate_rank_message(date_filter):
    session = ASSession()
    async with session.begin_nested():
        win_result = await session.execute(
            get_blackjack_rank_query(date_filter)
            .having(column("total_win_bonus") > 0)
            .order_by(desc("total_win_bonus"))
            .limit(10)
        )
        lose_result = await session.execute(
            get_blackjack_rank_query(date_filter)
            .having(column("total_win_bonus") < 0)
            .order_by("total_win_bonus")
            .limit(10)
        )
        ret = "`高手榜`"
        for n, win_bonus_row in enumerate(win_result.fetchall()):
            ret += f"\n  `[{n+1:02d}] {win_bonus_row[0] } : {win_bonus_row[1]:,}`"
        ret += "\n\n`菜鸟榜`"
        for n, lose_bonus_row in enumerate(lose_result.fetchall()):
            ret += f"\n  `[{n+1:02d}] {lose_bonus_row[0]} : {lose_bonus_row[1]:,}`"
    return ret


@Client.on_message(filters.chat(GROUP_ID) & filters.command("blackjackrank"))
@Client.on_message(filters.private & filters.command("blackjackrank"))
@auto_delete_message(60)
async def blackjackrank(client: Client, message: Message):
    rank_message = await generate_rank_message(func.date(func.now()))
    return await message.reply(
        f"`21点今日榜单:`\n{rank_message}", reply_markup=blackjackrank_reply_markup
    )


@Client.on_callback_query(filters.regex(r"rank_(all|yesterday|today)"))
async def handle_rank_callback_query(client: Client, callback_query: CallbackQuery):
    query_type = callback_query.data.split("_")[1]
    if query_type == "all":
        date_filter = None
        rank_name = "历史榜单"
    elif query_type == "yesterday":
        date_filter = func.date(func.now()) - 1
        rank_name = "昨日榜单"
    elif query_type == "today":
        date_filter = func.date(func.now())
        rank_name = "今日榜单"

    rank_message = await generate_rank_message(date_filter)
    return await callback_query.message.edit_text(
        f"`21点{rank_name}:`\n{rank_message}",
        reply_markup=blackjackrank_reply_markup,
    )


async def get_blackjack_pool(user: User = None):
    session = ASSession()
    async with session.begin_nested():
        if user:
            result = await session.execute(
                select(
                    func.sum(BlackJackHistory.bonus),
                    func.sum(BlackJackHistory.win_bonus),
                    func.sum(BlackJackHistory.tax),
                )
                .filter(BlackJackHistory.user_id == user.user.id)
                .group_by(BlackJackHistory.user_id)
                .limit(1)
            )
        else:
            result = await session.execute(
                select(
                    func.sum(BlackJackHistory.bonus).label("total_bonus"),
                    func.sum(BlackJackHistory.win_bonus).label("total_win_bonus"),
                    func.sum(BlackJackHistory.tax).label("total_win_bonus"),
                ).limit(1)
            )
        row = result.fetchone()
        if row:
            row_tuple = row.tuple()
            bet = row_tuple[0]
            win = row_tuple[1]
            tax = row_tuple[2]
        else:
            bet = 0
            win = 0
            tax = 0
        return bet, win, tax


@Client.on_message(
    filters.chat(GROUP_ID) & filters.reply & filters.command("blackjackinfo")
)
@auto_delete_message(60)
async def lotteryinfo(client: Client, message: Message):
    async with ASSession() as session:
        async with session.begin():
            async with User(message.reply_to_message) as user:
                bet, win, tax = await get_blackjack_pool(user)
                return await message.reply(
                    f"`累计开局 : {bet:,}`\n`累计盈利 : {win:,}`\n`累计缴税 : { tax:,}`\n`累计净赚 : {win-bet-tax:,}`"
                )


@Client.on_message(filters.chat(GROUP_ID) & filters.command("blackjackinfo"))
@Client.on_message(filters.private & filters.command("blackjackinfo"))
@auto_delete_message(60)
async def lotteryinfo(client: Client, message: Message):
    async with ASSession() as session:
        async with session.begin():
            async with User(message) as user:
                bet, win, tax = await get_blackjack_pool(user)
                return await message.reply(
                    f"`累计开局 : {bet:,}`\n`累计盈利 : {win:,}`\n`累计缴税 : { tax:,}`\n`累计净赚 : {win-bet-tax:,}`"
                )


@Client.on_message(filters.chat(GROUP_ID) & filters.command("blackjackinfoall"))
@auto_delete_message(60)
async def blackjackinfoall(client: Client, message: Message):
    bet, win, tax = await get_blackjack_pool()
    return await message.reply(
        f"`累计开局 : {bet:,}`\n`累计盈利 : {win:,}`\n`累计缴税 : { tax:,}`\n`累计净赚 : {win-bet-tax:,}`"
    )


@Client.on_message(filters.command("setblackjackmax"))
@auto_delete_message()
async def ban(client: Client, message: Message):
    bonus = int(message.command[1])
    global MAX_BONUS

    async with ASSession() as session:
        async with session.begin():
            async with User(message) as user:
                if not user.botbind or user.user._class < 14:
                    return await message.reply("您没有此权限")
                MAX_BONUS = bonus
                return await message.reply(f"开局上限已修改为{MAX_BONUS}")
