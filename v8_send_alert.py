#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
v8 告警邮件发送器（QQ邮箱 SMTP）—— 全站邮件告警的 **统一出口 / 统一闸门**
==========================================================================
2026-08-30 23:1x 一劳永逸升级（主人令「邮件怎么还在报警，赶紧查改一劳永逸式修复」）：

背景：全站告警脚本（v8_cloud_watchdog.py / v8_health_check.py / v8_bloat_check.py）
都 `from v8_send_alert import send_alert`，即本文件是**唯一出口**。但原实现是个
「无脑透传」：谁调都发、不知道是谁发的、周末数据陈旧也照发 →
主人收件箱长期被"看不出来源、周末结构性误报"的邮件淹没，且无法从主题判断该修哪里。

本次把「透传管道」升级为「统一闸门」，一次性解决三件事：
  1. **告警溯源**：主题统一加 `[v8·<机器名>]` 前缀，正文末尾加发送方 trace。
     今后再收到邮件，一眼就能看出是哪台机器发的，不用再全仓排查。
     机器名取 V8_ALERT_HOST 环境变量，未设则取本机 hostname
     （可在 .workbuddy/v8_smtp_config.json 里写 "host_label": "小九单位机"）。
  2. **分级告警（level）**：
       infra —— 基础设施真故障（runner 离线 / 站点 5xx / workflow 显式 failure）
                任何时间都发（周末/夜间同样告警，绝不静默）
       stale —— 数据陈旧类（周末/非交易日无新数据源属设计预期）
                默认**仅交易日发**，周末与节假日静默
                （可用 V8_ALERT_STALE_WEEKEND=1 打开）
       info  —— 知会类（已自愈确认等）默认不发（V8_ALERT_INFO=1 打开）
     调用方不传 level 时按 infra 处理（保持历史行为，不漏报真故障）。
  3. **总开关**：V8_ALERT_DISABLE=1 全局停发（仍写 .workbuddy/v8_alert_trace.log 留痕）。

配置仍在 .workbuddy/v8_smtp_config.json（gitignored，不落仓库），可加：
    {"host_label": "小九单位机", "disable": false, "stale_on_weekend": false}

- 命令行：python v8_send_alert.py "主题" "正文" [level]
- 自检：  python v8_send_alert.py --selftest   （不发信，只打印闸门判定与主题预览）
"""
import json
import os
import smtplib
import socket
import sys
from datetime import datetime
from email.header import Header
from email.mime.text import MIMEText
from pathlib import Path

CONFIG_PATHS = [
    Path(".workbuddy/v8_smtp_config.json"),
    Path.home() / ".workbuddy" / "v8_smtp_config.json",
]

TRACE_LOG = Path(".workbuddy/v8_alert_trace.log")

# ── 分级 ─────────────────────────────────────────────────────────────────
LEVEL_INFRA = "infra"   # 基础设施真故障 —— 永远发
LEVEL_STALE = "stale"   # 数据陈旧类   —— 默认仅交易日发
LEVEL_INFO = "info"     # 知会类       —— 默认不发
_VALID_LEVELS = (LEVEL_INFRA, LEVEL_STALE, LEVEL_INFO)

# 2026 年中国法定节假日（MM-DD）——与 v8_health_check.py 口径保持一致
_HOLIDAYS_2026 = {
    "01-01", "01-02", "01-03",            # 元旦
    "02-15", "02-16", "02-17", "02-18", "02-19", "02-20", "02-21",  # 春节
    "04-04", "04-05", "04-06",            # 清明
    "05-01", "05-02", "05-03",            # 劳动节
    "06-19", "06-20", "06-21",            # 端午
    "09-25", "09-26", "09-27",            # 中秋
    "10-01", "10-02", "10-03", "10-04", "10-05", "10-06", "10-07",  # 国庆
}


def load_config():
    for p in CONFIG_PATHS:
        if p.exists():
            try:
                return json.loads(p.read_text(encoding="utf-8"))
            except Exception as e:
                print(f"[{datetime.now()}] [WARN] SMTP 配置解析失败 {p}: {e}")
                return None
    return None


def host_label(cfg=None):
    """告警溯源用的机器标识（环境变量 > 配置文件 > hostname）。"""
    lab = os.environ.get("V8_ALERT_HOST", "").strip()
    if lab:
        return lab
    cfg = cfg or {}
    lab = str(cfg.get("host_label", "") or "").strip()
    if lab:
        return lab
    try:
        return socket.gethostname()
    except Exception:
        return "unknown-host"


def _trace(subject, body, level, decision, reason=""):
    """无论发不发都留痕，便于事后审计（本机运行态，不进仓库）。"""
    try:
        TRACE_LOG.parent.mkdir(parents=True, exist_ok=True)
        with TRACE_LOG.open("a", encoding="utf-8") as f:
            f.write(f"{datetime.now().isoformat(timespec='seconds')}\t"
                    f"host={host_label()}\tlevel={level}\tdecision={decision}\t"
                    f"reason={reason}\tsubject={subject}\n")
    except Exception:
        pass
    print(f"[{datetime.now()}] [GATE] {decision}（level={level}"
          f"{'，' + reason if reason else ''}）: {subject}")


def gate(level, cfg=None):
    """统一闸门：返回 (是否放行, 原因)。

    infra 永远放行 —— 主人明确要求「开盘前必须知道所有错误」，真故障绝不静默。
    stale 周末/节假日静默 —— 非交易日没有新数据源，"陈旧"是设计预期而非故障。
    info  默认不放行 —— 避免"已自愈"类知会邮件刷屏。
    """
    cfg = cfg or {}
    level = (level or LEVEL_INFRA).lower()
    if level not in _VALID_LEVELS:
        level = LEVEL_INFRA

    def _env_flag(name, default=False):
        v = os.environ.get(name, "")
        if v == "":
            return default
        return v.strip().lower() in ("1", "true", "yes", "on")

    if _env_flag("V8_ALERT_DISABLE", bool(cfg.get("disable", False))):
        return False, "全局停发 V8_ALERT_DISABLE"
    if level == LEVEL_INFO and not _env_flag("V8_ALERT_INFO", False):
        return False, "info 级默认不发"
    if level == LEVEL_STALE:
        now = datetime.now()
        weekend = now.weekday() >= 5
        holiday = now.strftime("%m-%d") in _HOLIDAYS_2026
        if (weekend or holiday) and not _env_flag(
                "V8_ALERT_STALE_WEEKEND", bool(cfg.get("stale_on_weekend", False))):
            return False, f"非交易日({now.strftime('%m-%d')})数据陈旧属预期，静默"
    return True, ""


def send_alert(subject, body, config=None, level=None):
    """发送告警邮件（经统一闸门）。level 见模块 docstring 的分级说明。"""
    cfg = config or load_config()
    level = (level or LEVEL_INFRA).lower()
    if level not in _VALID_LEVELS:
        level = LEVEL_INFRA

    ok, reason = gate(level, cfg)
    if not ok:
        _trace(subject, body, level, "SKIP", reason)
        return False

    if not cfg:
        print(f"[{datetime.now()}] [WARN] 找不到 SMTP 配置，跳过邮件告警")
        _trace(subject, body, level, "SKIP", "无 SMTP 配置")
        return False

    sender = cfg.get("sender", "")
    receiver = cfg.get("receiver", sender)
    host = cfg.get("smtp_host", "smtp.qq.com")
    port = int(cfg.get("smtp_port", 465))
    ssl = cfg.get("smtp_ssl", True)
    auth_code = cfg.get("auth_code", "")

    # ── 溯源：主题加机器前缀，正文加 trace 尾巴 ──────────────────────────
    tag = f"[v8·{host_label(cfg)}]"
    subject_tagged = subject if subject.startswith(tag) else f"{tag} {subject}"
    body_tagged = (
        f"{body}\n\n"
        f"————————————\n"
        f"发送主机: {host_label(cfg)}\n"
        f"告警级别: {level}（infra=基础设施故障 / stale=数据陈旧 / info=知会）\n"
        f"发送时间: {datetime.now().isoformat(timespec='seconds')}\n"
        f"闸门说明: 非交易日仅发 infra 级（数据陈旧属预期不骚扰）；\n"
        f"          如需临时停发，设环境变量 V8_ALERT_DISABLE=1。\n"
    )

    msg = MIMEText(body_tagged, "plain", "utf-8")
    msg["Subject"] = Header(subject_tagged, "utf-8")
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
        print(f"[{datetime.now()}] [INFO] 告警邮件已发送: {subject_tagged}")
        _trace(subject_tagged, body, level, "SENT")
        return True
    except Exception as e:
        print(f"[{datetime.now()}] [ERROR] 邮件发送失败: {e}")
        _trace(subject_tagged, body, level, "SEND_FAIL", str(e)[:80])
        return False


def selftest():
    """不发信，只验证闸门判定与主题渲染（供人工核对分级是否符合预期）。"""
    cfg = load_config()
    print(f"SMTP 配置: {'已加载' if cfg else '未找到（将跳过发送）'}")
    print(f"机器标识 : {host_label(cfg)}")
    print("闸门判定:")
    for lv in _VALID_LEVELS:
        ok, why = gate(lv, cfg)
        print(f"  level={lv:6s} -> {'放行' if ok else '静默'}  {why}")
    tag = f"[v8·{host_label(cfg)}]"
    print(f"  主题预览: {tag} 【v8看门狗告警】3项异常 @ 2026-08-30 23:15:00")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
    if len(sys.argv) >= 2 and sys.argv[1] == "--selftest":
        selftest()
    elif len(sys.argv) >= 3:
        send_alert(sys.argv[1], sys.argv[2],
                   level=(sys.argv[3] if len(sys.argv) >= 4 else None))
    else:
        send_alert("九宝量化 v8 自检邮件", "v8 邮件告警通道测试成功。", level=LEVEL_INFRA)
