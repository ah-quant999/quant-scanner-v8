#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""双机通用 · 把 WorkBuddy「批量删除确认阈值」提到 2000（幂等，可反复执行）。

═══ 背景（2026-09-23 客户端源码级取证）═══════════════════════════════════════
safe-delete 批量删除守卫（safe-delete-bulk-guard.cjs）的阈值**只认环境变量**
    CODEBUDDY_SAFE_DELETE_BULK_THRESHOLD
该变量由 WorkBuddy 客户端**启动时**注入 bash，取自
    ~/.workbuddy/settings.json  →  sandbox.safeDeleteBulkThreshold
（客户端原文：saveExperimentalFeaturesToSettings() → console「Saved experimentalFeatures to settings.json」；
  默认值 DEFAULT_EXPERIMENTAL_FEATURES.safeDeleteBulkThreshold = 50，合法区间 1..99999。）

默认 50 的后果（实测）：一轮内删除 >50 个文件 ⇒ 守卫抛
    [safe-delete][SAFE_DELETE_BULK_CONFIRM_REQUIRED]
⇒ **整条命令被硬阻断**（例：`.github/scripts/pre_deploy_audit.py` 门禁只跑完 [1/8] 就被掐死，rc=1），
   表现为「门禁莫名失败 / 清理脚本莫名中断」，极易被误判成代码问题。

═══ 用法 ═══════════════════════════════════════════════════════════════════
  python docs/ops/scripts/v8_set_safe_delete_threshold.py          # 提到 2000（默认）
  python docs/ops/scripts/v8_set_safe_delete_threshold.py 5000     # 自定义阈值
  python docs/ops/scripts/v8_set_safe_delete_threshold.py --check  # 只读检查，不写
  python docs/ops/scripts/v8_set_safe_delete_threshold.py --path <file>  # 指定配置文件（离线自测用）

═══ 生效条件（2026-09-23 实测修正）═══════════════════════════════════════════
  ✅ **改完即刻生效，无需重启**：客户端是**每次派发命令时**读取 settings.json 再注入环境变量。
     实测小九机：写入前 `$CODEBUDDY_SAFE_DELETE_BULK_THRESHOLD` = 50；写入后**同一会话**内
     下一条命令读到的已是 2000。
  （客户端设置界面在保存时会弹「需重启」，那是针对 versionControl/ProjFS 那类实验特性；
    本键不需要。若你那边仍读到旧值，重启客户端兜底。）

═══ 安全 ═══════════════════════════════════════════════════════════════════
  · 只动 settings.json 的 sandbox.safeDeleteBulkThreshold 一个键，其余字节不动（锚点插入法）；
  · 写前自动备份到 <tmp>/v8_settings_backup/，可逆；
  · 幂等：已是目标值则不动文件；
  · 不联网、不碰仓库、不碰任何业务数据。
"""

from __future__ import annotations

import json
import os
import re
import shutil
import sys
import time
from pathlib import Path

DEFAULT_TARGET = 2000
MIN_V, MAX_V = 1, 99999
KEY = "safeDeleteBulkThreshold"

CANDIDATES = [
    Path.home() / ".workbuddy" / "settings.json",
    Path.home() / ".codebuddy" / "settings.json",
]


def log(msg: str) -> None:
    print(msg, flush=True)


def backup_dir() -> Path:
    """与 v8 既有约定一致：优先 E:/v8data/qs8-tmp，其次系统临时目录。"""
    for c in (Path("E:/v8data/qs8-tmp"), Path("D:/v8data/qs8-tmp")):
        if c.is_dir():
            d = c / "v8_settings_backup"
            d.mkdir(parents=True, exist_ok=True)
            return d
    import tempfile

    d = Path(tempfile.gettempdir()) / "v8_settings_backup"
    d.mkdir(parents=True, exist_ok=True)
    return d


def pick_settings() -> Path | None:
    for p in CANDIDATES:
        if p.is_file():
            return p
    return None


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _newline(text: str) -> str:
    """沿用文件原有换行风格（LF / CRLF 都要能治）。"""
    return "\r\n" if "\r\n" in text else "\n"


def count_sandbox_keys(text: str) -> int:
    return len(re.findall(r'"sandbox"\s*:', text))


def surgical_insert(text: str, value: int) -> tuple[str, str]:
    """锚点插入，保留其余字节。返回 (新文本, 方式说明)。

    🔴 2026-09-23 血训（离线四场景实测抓出，已修）：
       旧版用字面量 '  "sandbox": {\\n' 当锚点 —— 一旦文件是 **CRLF** 行尾就**匹配不到**，
       于是落进「新建 sandbox 段」分支，在文件头又插了一个 `"sandbox"`，
       造成**重复键**：JSON 照样解析通过，但后出现的旧段胜出 ⇒
       **阈值静默为 None**（rc 还能是 0/1 看分叉），是典型「假绿」。
       现改为：① 正则匹配、行尾风格无关；② 写入后强制校验 sandbox 键唯一。
    """
    nl = _newline(text)

    # 情况 1：已有 sandbox 段 → 插在其 `{` 之后（正则，兼容 CRLF）
    m = re.search(r'"sandbox"\s*:\s*\{', text)
    if m:
        ins = nl + '    "%s": %d,' % (KEY, value)
        at = m.end()
        return text[:at] + ins + text[at:], "锚点插入（sandbox 段首）"

    # 情况 2：无 sandbox 段 → 在首个 `{` 之后新建一个
    if text.lstrip().startswith("{"):
        i = text.index("{") + 1
        block = nl + '  "sandbox": {' + nl + '    "%s": %d' % (KEY, value) + nl + "  },"
        return text[:i] + block + text[i:], "新增 sandbox 段"

    raise ValueError("无法定位插入锚点")


def process(path: Path, target: int, check_only: bool) -> int:
    raw = path.read_bytes()
    text = raw.decode("utf-8")
    try:
        data = json.loads(text)
    except Exception as exc:  # noqa: BLE001
        log("❌ [%s] JSON 解析失败，拒绝改写：%s" % (path, exc))
        return 1

    cur = (data.get("sandbox") or {}).get(KEY)
    log("配置文件 : %s" % path)
    log("当前阈值 : %s" % ("未设置（等同客户端默认 50）" if cur is None else cur))
    log("目标阈值 : %d" % target)

    if check_only:
        ok = isinstance(cur, int) and cur == target
        log("%s [只读检查] %s" % ("✅" if ok else "⚠️", "已是目标值" if ok else "需要写入"))
        return 0 if ok else 2

    if isinstance(cur, int) and cur == target:
        log("✅ 已是目标值，无需改动（幂等）")
        return 0

    bdir = backup_dir()
    bak = bdir / ("settings.json.bak_%s" % time.strftime("%Y%m%d_%H%M%S"))
    shutil.copy2(path, bak)
    log("已备份   : %s (%d 字节)" % (bak, bak.stat().st_size))

    if cur is None:
        try:
            new_text, how = surgical_insert(text, target)
        except Exception as exc:  # noqa: BLE001
            log("⚠️ 锚点插入失败(%s)，回退为整体 JSON 重写" % exc)
            data.setdefault("sandbox", {})[KEY] = target
            new_text = json.dumps(data, ensure_ascii=False, indent=2) + "\n"
            how = "整体重写"
    else:
        # 已有该键但值不对 → 精确替换该键的数值
        pat = re.compile(r'("%s"\s*:\s*)-?\d+' % KEY)
        if len(pat.findall(text)) == 1:
            new_text = pat.sub(lambda mm: mm.group(1) + str(target), text, count=1)
            how = "精确替换数值"
        else:
            data["sandbox"][KEY] = target
            new_text = json.dumps(data, ensure_ascii=False, indent=2) + "\n"
            how = "整体重写"

    path.write_bytes(new_text.encode("utf-8"))

    # ── 写后四重校验（任一不过 ⇒ 立即回滚，绝不留下坏文件）──
    disk = path.read_text(encoding="utf-8")
    try:
        back = json.loads(disk)
    except Exception as exc:  # noqa: BLE001
        shutil.copy2(bak, path)
        log("❌ 写后 JSON 解析失败(%s)，已从备份回滚" % exc)
        return 1
    got = (back.get("sandbox") or {}).get(KEY)
    dup = count_sandbox_keys(disk)
    before_wo = {k: v for k, v in data.items() if k != "sandbox"}
    after_wo = {k: v for k, v in back.items() if k != "sandbox"}
    sb_before = dict(data.get("sandbox") or {})
    sb_after = dict(back.get("sandbox") or {})
    sb_before.pop(KEY, None)
    sb_after.pop(KEY, None)

    ok_val = isinstance(got, int) and got == target
    ok_dup = dup == 1
    ok_other = (before_wo == after_wo) and (sb_before == sb_after)

    log("写入方式 : %s" % how)
    log("写入后   : %s" % got)
    log("字节     : %d -> %d" % (len(raw), path.stat().st_size))
    log("  · 取值达标      : %s" % ("✅" if ok_val else "❌"))
    log("  · sandbox 键唯一: %s（出现 %d 次）" % ("✅" if ok_dup else "❌", dup))
    log("  · 其余键零改动  : %s" % ("✅" if ok_other else "❌"))

    if ok_val and ok_dup and ok_other:
        log("✅ 校验：重新读盘解析，sandbox.%s = %s" % (KEY, got))
        return 0
    shutil.copy2(bak, path)
    log("❌ 校验未通过，已从备份回滚（文件已还原为改动前状态）")
    return 1


def main() -> int:
    argv = [a for a in sys.argv[1:]]
    check_only = "--check" in argv
    argv = [a for a in argv if a != "--check"]
    override = None
    if "--path" in argv:
        i = argv.index("--path")
        if i + 1 >= len(argv):
            log("❌ --path 缺少取值")
            return 1
        override = Path(argv[i + 1])
        del argv[i : i + 2]
    target = DEFAULT_TARGET
    if argv:
        try:
            target = int(argv[0])
        except ValueError:
            log("❌ 阈值必须是整数：%r" % argv[0])
            return 1
    if not (MIN_V <= target <= MAX_V):
        log("❌ 阈值越界，客户端合法区间 %d..%d（源码 SAFE_DELETE_BULK_THRESHOLD_MAX=99999）" % (MIN_V, MAX_V))
        return 1

    if override is not None:
        path = override
        if not path.is_file():
            log("❌ --path 指定的文件不存在：%s" % path)
            return 1
    else:
        path = pick_settings()
        if path is None:
            log("❌ 未找到 settings.json，已查找：")
            for c in CANDIDATES:
                log("     %s" % c)
            return 1

    rc = process(path, target, check_only)
    log("")
    if rc == 0 and not check_only:
        log("✅ 已生效（客户端每次派发命令时读取本键，无需重启）。")
        log("   自检：echo $CODEBUDDY_SAFE_DELETE_BULK_THRESHOLD   → 应输出目标值。")
        log("   （设置界面路径：设置 → 安全中心 → 安全特性 → 批量删除阈值，区间 1..99999）")
    return rc


if __name__ == "__main__":
    sys.exit(main())
