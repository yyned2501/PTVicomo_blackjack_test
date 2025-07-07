# 标准库
import asyncio
import sys
import logging

# 第三方库
from pyrogram import Client as _Client
from pyrogram.errors import (
    RPCError,
    FloodWait,
)

logger = logging.getLogger("main")


class Client(_Client):
    async def start(self, *args, invoke_retries: int = 5, max_pool: int = 10, **kargs):
        """
        重写 start 方法，在会话认证后设置 CustomSession。
        """
        await super().start(*args, **kargs)
        self._invoke_retries = invoke_retries
        self._pool_semaphore = asyncio.Semaphore(max_pool)
        self._session_invoke = self.session.invoke
        self.session.invoke = self._custom_invoke

    async def _custom_invoke(self, query, *args, **kwargs):
        retries = 0
        while retries < self._invoke_retries:
            async with self._pool_semaphore:
                try:
                    response = await self._session_invoke(query, *args, **kwargs)
                    return response
                except FloodWait as e:
                    wait_time = e.value
                    logger.warning(
                        f"FloodWait: 为 {query.__class__.__name__} 等待 {wait_time} 秒"
                    )
                    await asyncio.sleep(wait_time)
                    retries += 1

                except asyncio.TimeoutError as e:
                    await asyncio.sleep(1)
                    retries += 1
                    if retries < self._invoke_retries:
                        logger.warning(
                            f"TimeoutError for {query.__class__.__name__} 重试第{retries}/{self._invoke_retries}次"
                        )
                    else:
                        logger.error(
                            f"TimeoutError for {query.__class__.__name__}",
                            exc_info=True,
                        )

                except RPCError as e:
                    break

                except Exception as e:
                    await asyncio.sleep(1)
                    retries += 1
                    if retries < self._invoke_retries:
                        logger.warning(
                            f"意外错误 for {query.__class__.__name__} 重试第{retries}/{self._invoke_retries}次"
                        )
                    else:
                        logger.error(
                            f"意外错误 for {query.__class__.__name__}",
                            exc_info=True,
                        )
        # 超过最大重试次数后，尝试 get_me 判断是否需要重启
        if retries == self._invoke_retries:
            sys.exit(1)
