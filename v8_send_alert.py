#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
v8 告警邮件发送器（QQ邮箱 SMTP）
- 配置从 .workbuddy/v8_smtp_config.json 读取（gitignored，不落仓库）
- 命令行：python v8_send_alert.py "主题" "正文"
"""
import json
import smtplib
import sys
from datetime import datetime
from email.header import Header
from email.mime.text import MIMEText
from pathlib import Path

CONFIG_PATHS = [
    Path(".workbuddy/v8_smtp_config.json"),
    Path.home() / ".workbuddy" / "v8_smtp_config.json",
]


def load_config():
    for p in CONFIG_PATHS:
        if p.exists():
            return json.loads(p.read_text(encoding="utf-8"))
    return None


def send_alert(subject, body, config=None):
    cfg = config or load_config()
    if not cfg:
        print(f"[{datetime.now()}] [WARN] 找不到 SMTP 配置，跳过邮件告警")
        return False

    sender = cfg.get("sender", "")
    receiver = cfg.get("receiver", sender)
    host = cfg.get("smtp_host", "smtp.qq.com")
    port = int(cfg.get("smtp_port", 465))
    ssl = cfg.get("smtp_ssl", True)
    auth_code = cfg.get("auth_code", "")

    msg = MIMEText(body, "plain", "utf-8")
    msg["Subject"] = Header(subject, "utf-8")
    msg["From"] = sender
    msg["To"] = receiver

    try:
        if ssl:
            server = smtplib.SMTP_SSL(host, port, timeout=15)
        else:
            server = smtplib.SMTP(host, port, timeout=15)
            server.starttls()
        server.login(sender, auth_code)
        server.sendmail(sender, [receiver], msg.as_string())
        server.quit()
        print(f"[{datetime.now()}] [INFO] 告警邮件已发送: {subject}")
        return True
    except Exception as e:
        print(f"[{datetime.now()}] [ERROR] 邮件发送失败: {e}")
        return False


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
    if len(sys.argv) >= 3:
        send_alert(sys.argv[1], sys.argv[2])
    else:
        send_alert("九宝量化 v8 自检邮件", "v8 邮件告警通道测试成功。")
