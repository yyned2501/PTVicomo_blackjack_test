# 标准库
import asyncio
import sys
import traceback
import logging

# 第三方库
from pyrogram import Client as _Client
from pyrogram.errors import (
    RPCError,
    FloodWait,
    Unauthorized,
    AuthKeyInvalid,
)

logger = logging.getLogger("main")


class Client(_Client):
    async def start(self):
        """
        重写 start 方法，在会话认证后设置 CustomSession。
        """
        await super().start()
        # 确保 auth_key 和 dc_id 可用
        self.original_invoke = self.session.invoke
        self.session.invoke = self.custom_invoke

    async def custom_invoke(self, query, *args, max_retries: int = 3, **kwargs):
        retries = 0
        while retries < max_retries:
            try:
                logger.debug(
                    f"调用 {query.__class__.__name__} (尝试 {retries + 1}/{max_retries})"
                )
                response = await self.original_invoke(query, *args, **kwargs)
                logger.debug(f"请求 {query.__class__.__name__} 成功")
                return response
            except FloodWait as e:
                wait_time = e.value
                logger.warning(
                    f"FloodWait: 为 {query.__class__.__name__} 等待 {wait_time} 秒"
                )
                await asyncio.sleep(wait_time)
                retries += 1
            except asyncio.TimeoutError as e:
                logger.error(f"TimeoutError for {query.__class__.__name__}")
                await asyncio.sleep(1)
                retries += 1
                if retries == max_retries:
                    traceback.print_exc()
            except RPCError as e:
                logger.error(f"RPCError for {query.__class__.__name__}")
                if isinstance(e, (Unauthorized, AuthKeyInvalid)):
                    raise
                await asyncio.sleep(1)
                retries += 1
                if retries == max_retries:
                    traceback.print_exc()
            except Exception as e:
                logger.error(f"意外错误 for {query.__class__.__name__}")
                retries += 1
                if retries == max_retries:
                    traceback.print_exc()

        logger.critical(
            f"超过最大重试次数 ({max_retries}) for {query.__class__.__name__}。触发 Supervisor 重启。"
        )
        try:
            await self.stop()
        except Exception as e:
            logger.error(f"关闭会话失败: {traceback.format_exc()}")
        sys.exit(1)
