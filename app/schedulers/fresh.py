"""
此模块包含一个名为 `fresh` 的异步函数，并将其添加到调度器中以每隔60秒运行一次。
函数:
    fresh: 异步函数，调用 `commands.get_admin()`。
调度器:
    将 `fresh` 函数添加到调度器中，以每隔60秒的间隔运行一次。
"""

from app.commands import setup
from app import scheduler


async def fresh():
    await setup.get_admin()


scheduler.add_job(fresh, "interval", seconds=60)
