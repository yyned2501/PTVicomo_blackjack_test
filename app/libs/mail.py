from email.utils import formataddr
import random
import string
from email.mime.text import MIMEText
from email.header import Header
from aiosmtplib import SMTP
import logging


class Mail:
    SMTP_SERVER = "smtp.qq.com"  # SMTP服务器地址
    SMTP_PORT = 465  # SMTP服务器端口（SSL）

    def __init__(self, sender_email, sender_password):
        self.SENDER_EMAIL = sender_email
        self.SENDER_PASSWORD = sender_password

    @staticmethod
    def generate_verification_code(length=6):
        """生成指定长度的随机验证码"""
        characters = string.digits + string.ascii_uppercase
        return "".join(random.choice(characters) for _ in range(length))

    async def send_verification_email(self, receiver_email):
        """异步发送验证码邮件"""
        # 生成验证码
        verification_code = self.generate_verification_code()

        # 邮件内容
        subject = "您的验证码"
        content = f"""
        <html>
        <body>
            <h2>尊敬的用户：</h2>
            <p>您的验证码是：<strong>{verification_code}</strong></p>
            <p>请在2分钟内使用该验证码完成验证。</p>
            <p>如非本人操作，请忽略此邮件。</p>
            <hr>
            <p style="color:gray;">此为系统邮件，请勿直接回复。</p>
        </body>
        </html>
        """

        # 构造邮件
        message = MIMEText(content, "html", "utf-8")
        message["From"] = formataddr(("系统管理员", self.SENDER_EMAIL))
        message["To"] = receiver_email
        message["Subject"] = Header(subject, "utf-8")
        try:
            async with SMTP(
                hostname=self.SMTP_SERVER, port=self.SMTP_PORT, use_tls=False
            ) as smtp_client:
                await smtp_client.login(self.SENDER_EMAIL, self.SENDER_PASSWORD)
                await smtp_client.send_message(message)

            return verification_code
        except Exception as e:
            logging.error(f"发送邮件时出错: {e}", exc_info=True)
            return None
