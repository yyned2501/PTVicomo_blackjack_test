import json

# 第三方库
from pyrogram.types import CallbackQuery
from pyrogram.filters import Filter


class CallbackDataFromFilter(Filter):
    def __init__(self, from_value):
        self.from_value = from_value

    async def __call__(self, _, callback_query: CallbackQuery):
        try:
            data = json.loads(callback_query.data)
        except Exception:
            return False
        return data.get("a") == self.from_value
