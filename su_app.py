from pyrogram import Client, filters
from pyrogram.types import Message
import subprocess

from config import GROUP_ID, API_ID, API_HASH, BOT_TOKEN

app = Client(
    "su_tgbot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN,
)


def restart_program(program_name):
    """
    使用 supervisorctl 重启指定的程序
    :param program_name: supervisor 配置中的程序名
    :return: (success, output)
    """
    try:
        result = subprocess.run(
            ["supervisorctl", "restart", program_name],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode == 0:
            return True, result.stdout.strip()
        else:
            return False, result.stderr.strip() or result.stdout.strip()
    except Exception as e:
        return False, str(e)


def git_pull():
    """
    执行 git pull 命令
    :return: (success, output)
    """
    try:
        result = subprocess.run(
            ["git", "pull"], capture_output=True, text=True, timeout=20
        )
        if result.returncode == 0:
            return True, result.stdout.strip()
        else:
            return False, result.stderr.strip() or result.stdout.strip()
    except Exception as e:
        return False, str(e)


@app.on_message(filters.chat(GROUP_ID[1]) & filters.command("restart_basic"))
async def restart_basic(client: Client, message: Message):
    """
    重启 basic_app 程序
    """
    ok, output = restart_program("basic")
    if ok:
        return await message.reply("basic_app 重启成功！\n" + output)
    else:
        return await message.reply("basic_app 重启失败！\n" + output)


@app.on_message(filters.chat(GROUP_ID[1]) & filters.command("restart_extra"))
async def restart_extra(client: Client, message: Message):
    """
    重启 ex_app 程序
    """
    ok, output = restart_program("extra")
    if ok:
        return await message.reply("ex_app 重启成功！\n" + output)
    else:
        return await message.reply("ex_app 重启失败！\n" + output)


@app.on_message(filters.chat(GROUP_ID[1]) & filters.command("update"))
async def git_pull_cmd(client: Client, message: Message):
    """
    执行 git pull 命令
    """
    ok, output = git_pull()
    if ok:
        return await message.reply("git pull 执行成功！\n" + output)
    else:
        return await message.reply("git pull 执行失败！\n" + output)


if __name__ == "__main__":
    app.run()
