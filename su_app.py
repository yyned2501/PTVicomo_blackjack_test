import sys
from pyrogram import filters, Client
from pyrogram.types import Message
import subprocess

from config import GROUP_ID, API_ID, API_HASH, BOT_TOKEN

# from app.custom_client import Client

app = Client(
    "su_tgbot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN,
)


def send_command(commands):
    """
    使用 supervisorctl 重启指定的程序
    :param program_name: supervisor 配置中的程序名
    :return: (success, output)
    """
    try:
        result = subprocess.run(
            commands,
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


def restart_program(program_name):
    """
    使用 supervisorctl 重启指定的程序
    :param program_name: supervisor 配置中的程序名
    :return: (success, output)
    """
    return send_command(["supervisorctl", "restart", program_name])


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


@app.on_message(
    filters.chat(GROUP_ID[1])
    & filters.command(
        [
            "start_basic",
            "restart_basic",
            "stop_basic",
            "start_extra",
            "restart_extra",
            "stop_extra",
        ]
    )
)
async def restart_basic(client: Client, message: Message):
    command = message.command[0]
    func, gram = command.split("_")
    ok, output = send_command(["supervisorctl", func, gram])
    if ok:
        return await message.reply(f"{command} 成功！\n" + output)
    else:
        return await message.reply(f"{command} 失败！\n" + output)


@app.on_message(filters.chat(GROUP_ID[1]) & filters.command("reload"))
async def restart_all(client: Client, message: Message):
    """
    利用supervisor的重启机制类重启
    """
    return send_command(["supervisorctl", "reload"])


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
