#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""final_recommend.py — 跨策略共振 + 板块强度 生成最终推荐 Top3

输入：
  - raw_data/triple_consensus.json
  - raw_data/top10_daily.json   (四量终极 / 主站 TOP10)
  - raw_data/crds_card_data.json (逆势龙头)
  - raw_data/sector_rs.json     (板块相对强度)
  - raw_data/stock_profile.json (个股行业/概念)
  - raw_data/crisis_data.json   (危机雷达，决定是否并入逆势龙头)
  - raw_data/triple_track.json     (三重跟踪告警，用于 Top3 跟踪)
  - (2026-09-04 主人令：cockpit_tier_recommend / cockpit_backtest / lhb 数据源整段删除——驾驶舱/大牛股猎手已下线，
     backtest 输出字段一并移除，前端无消费方，verify_chain_outputs 不校验)

输出：
  - raw_data/final_recommend.json
  - data/FINAL_RECOMMEND_DATA.js

统一优先级分 = Σ(源强度分) + 共振次数×1.5 + 板块强度加分
"""
import json
import os
import re
import sys
import time
from collections import defaultdict
from datetime import datetime, timedelta

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW = os.path.join(ROOT, "raw_data")
DATA = os.path.join(ROOT, "data")

# 🔴 2026-09-11 修复（今夜 P0 事故·一劳永逸）：本文件 L509 用了 V8_OFFLINE，
#   但全仓从未定义过它（`grep -rn "V8_OFFLINE" .` = 仅 2 处「使用」、0 处「定义」）。
#   疑 commit 5393f4c66「V8_OFFLINE 完整实现」在 rebase/合并中把定义行丢了。
#   后果：**D 批（最终推荐）一跑就 NameError 崩** → data/FINAL_RECOMMEND_DATA.js
#   永远停在旧版（实测停在 2026-09-10 04:57:09）→ 主站「最终推荐」整天是昨天的。
#   语义：V8_OFFLINE=1 = 本机无外网/无 baostock 的离线模式（不等 FACTOR_LAB）。
V8_OFFLINE = os.environ.get("V8_OFFLINE", "0") == "1"

# 名称归一化共享模块（2026-08-14 抽出，消除与 build_candidate_pool/guanlan_extractor/scanner 的重复）
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from name_utils import norm_code, fix_name, strip_entitlement_prefix, STANDARD_NAME_MAP  # noqa: E402
from fundamental_helper import quality_veto  # noqa: E402  质差股一票否决（2026-09-07 主人令）

# ═══════════════════════════════════════════════════════════════════════════
# 🔴🔴 2026-09-18 主人令「噪音不该进池」·改动2a：噪音源前置过滤
# ───────────────────────────────────────────────────────────────────────────
# 判据（命中率 = 该源在候选池中的覆盖率；覆盖率越高越无选择性）：
#   ROE_TTM 43.9% / 异常换手率 39.8%  ⇒ ≈ 无选择性（谁都能命中，无选股信息量）
#   vs 四量终极 17.1% / 高手跟踪 3.8% / 三重共识 1.8%（强选择性）
# 实测问题：12 个真账本 top5 的 60 席中，10 席（16.7%）是「纯弱源单源」——
#   只被此二源之一命中，靠 base 1.5~2.0 + 共振 1.5 = 3.0~3.5 进榜。
# 改法：二源不再写 sources/source_scores ⇒ 不计共振、不计 strength ⇒ 无入池资格；
#       改写入 tags（展示用），signals 标签（高ROE/缩量强势）保留不变。
# 回退：V8_FUSION_NOISE_FILTER=0 → 恢复旧行为（旧写法），便于 A/B 验证。
# ═══════════════════════════════════════════════════════════════════════════
# ═══════════════════════════════════════════════════════════════════════════
# 🔴 2026-09-18 改动2a（**已按阿狸咪真回测证据修订**）
#
# 证据来源（阿狸咪 2026-09-18 真回测，9 信号日 / 463 条 / 170 只 / T+5 有效池 200 条）：
#   源            命中数   有该源均%   无该源均%   边际      有/无胜率
#   四量终极        25      +0.92      −3.24     +4.17pp   52.0 vs 18.9
#   ROE_TTM        89      −2.35      −3.03     +0.68pp   22.5 vs 23.4   ← 弱正，非负
#   高手跟踪        13      −4.37      −2.61     −1.76pp   30.8 vs 22.5   ← 负 alpha
#   异常换手率      85      −4.00      −1.78     −2.21pp   16.5 vs 27.8   ← 负 alpha
#   （她的原文结论：负 alpha 源与唯一正源同拿 +1.0 权重，于是数量优势把有效信号淹没。）
#
# ⚠️ 与「命中率判据」的关键差异（我方 12 账本复现 43.9%/39.8% 只是命中率，无收益）：
#   命中率低 ≠ 有正 alpha。高手跟踪命中率仅 3.8% 却被实测为 −1.76pp ⇒ 现按**真回测**取舍。
#
# 裁定（严守阿狸咪自划红线）：
#   ✅ P0-c「隔离负 alpha 源」——只剔除**边际为负**的两个源（不做权重重估）
#   ❌ P0-a「源权重 ∝ 实测边际」——她明确否决「绝不按 9 天调权重」⇒ 权重一律不动
#   ⚠️ ROE_TTM 边际 +0.68pp（弱正）⇒ **不清零**，只降档：2.0/1.5/1.0 → 1.0/0.75/0.5
#
# 回退：V8_FUSION_NOISE_FILTER=0 → 恢复旧行为（全部原样 + ROE 原档），便于 A/B 与紧急回滚。
# ═══════════════════════════════════════════════════════════════════════════
V8_FUSION_NOISE_FILTER = os.environ.get("V8_FUSION_NOISE_FILTER", "1").strip() != "0"
# 🆕🔴 2026-09-18 主人令「因子只做加减分」＋ 主人问「扣分标准科学吗？别一开始就犯错」：
#   放量弱势扣分（−0.5）是**本层唯一真正写进 final_score 的因子动作**，但它有两个问题：
#     ① **格式 bug** 导致其**从未生效**（详见下方 _weak 集合处：norm_code 不剥点 ⇒ 恒不匹配；
#        实测 29 轮 / 1333 条候选命中 **0 次**）——本补丁已修；
#     ② 该分档**没有 walk-forward 回测依据**（bottom 榜从未回测），属「凭空的惩罚」，
#        与 generate_top10.py P5 明文原则「反向档位无显著负 edge ⇒ 不给凭空的惩罚」冲突。
#   ⇒ 处置：**不改其值**（改权重违反「绝不按短样本调权重」红线），只给**一键开关**：
#        V8_FACTOR_WEAK_PENALTY=0 ⇒ −0.5 置 0（signals 照写、标签照展示，仅不减分）
#      并在产物 factor_chain 里如实标注 evidence="未回测"，前端显示 ⚠️，处置权交主人。
_WEAK_PENALTY_ON = os.environ.get("V8_FACTOR_WEAK_PENALTY", "1").strip() != "0"
# 🔴🔴 2026-09-18 主人令「改好后审计一遍算法链，把因子参与选股的部分删除干净」——死代码清理：
#   本处原有 NOISE_SOURCES / FUSION_NEG_ALPHA 两个集合 + V8_ROE_DEMOTE 开关 + _roe_score() 降档函数，
#   实测**三者全无使用点**（判据「注释≠真值须实测」）：
#     · NOISE_SOURCES / FUSION_NEG_ALPHA —— 全仓仅出现在本定义行，零引用；
#     · _roe_score() 的返回值 sc 在原「维度2 ROE_TTM」循环里算完后**从未写入 source_scores / sources**
#       （算完即弃）⇒ 注释所称「ROE_TTM 降档 1.0/0.75/0.5」**从未生效过**。
#   ⇒ 现整体移除，杜绝「注释说有、实际没有」的静默假象。
#   ⚠️ 将来若要让 ROE_TTM 真正计分：**必须先回测验证**（walk-forward 边际 edge>0 且 IS/OOS 同号、
#      Top 层胜率 ≥55%）再接入，并同步更新 data/FACTOR_PROGRESS.js 台账为「已接入」；
#      不可仅凭注释恢复。
# ═══════════════════════════════════════════════════════════════════════════
# 🔴 2026-09-18 改动12（主人令「都按你推荐的处理」）：融合器按边际 alpha 精选源。
#   背景：11 源 walk-forward 横比（by_factor 边际 edge，剔 β）显示 3 正 8 负：
#     正：sig_jinzuan +1.179 / sig_chan +0.898 / p4_lowvol45 +0.338（e5）
#     负：quality −3.266 / sig_jigou −2.227 / sig_trend −2.085 / p4_resid10 −1.476 /
#         p4_resid5 −1.080 / sector −0.525 / p4_lowvol55 −0.153 / fund −0.128
#   精选(3正源) vs 全量(11源等权) 边际差 = +1.58pp。
#   改动1 已让四量 src_score 按**动态 edge** 计分（负信号自动压 0），但存在
#   **回流漏洞**：qd(+0.5) / 60m(+0.5~0.8) 加分可把「无任何正 edge 信号」的
#   0 分票复活回独立源（负 alpha 借道回流，正是「单源票淹没强信号」的残余路径）。
#   修法：加分只授予**有正 edge 资格**的票（基础分>0）；资格由运行期动态 edge
#   自适应 —— 扩样复核（阿狸咪 40~60 信号日）后 edge 翻正的信号自动恢复，
#   无需改代码（融合器不写死）。信号标签照常展示，仅不计分。
#   逐项交待（诚实）：
#     · p4_lowvol45（e5 +0.338）**不新增**入融合：edge10 = −3.18 与 e5 异号
#       （generate_top10.py L513 同判据「证据矛盾，不启用」），薄样本证据不稳。
#     · quality/fund 无融合入口（仅在回测诊断里度量），无需动刀；
#     · sector 的 sec_add 板块加分是主人既定的独立机制、且薄样本 edge=−0.525
#       不足以动它 —— 不改，等扩样结论。
#   回退：V8_FUSION_ALPHA_SELECT=0 → 恢复旧行为（加分不设资格），便于 A/B 与紧急回滚。
V8_FUSION_ALPHA_SELECT = os.environ.get("V8_FUSION_ALPHA_SELECT", "1").strip() != "0"
# （_ROE_OLD_SCALE / _ROE_NEW_SCALE / _roe_score 已于 2026-09-18 移除：返回值从未落盘 ⇒ 死代码）


CRISIS_HIGH_THRESHOLD = 50  # 危机雷达≥50才并入逆势龙头
SECTOR_TOP_N = 15
TOP_N = 5  # 2026-08-13 主人令：从 3 扩到 5（共振优先 + 分数其次，覆盖更多共识强票）
# 2026-08-11 主人令：去掉港股降权+去掉 A 股保底——「谁好谁上」原则。
#   之前 HK_PENALTY=1.5 + hard_a=MIN_A_SHARES_IN_TOP-1=1 是「主做 A 股」假设下的保护，
#   实际效果是市场歧视（港股凭空少 1.5 分）。现在改公平竞争，靠数据说话。
#   监控兜底：Top3 出现「全港股」或「全 A 股」时，v8_health_check 会写 URGENT 告警，
#   用于发现数据源异常（如港股 API 挂导致共振虚高、A 股 mootdx 挂导致扫描失败）。
HK_PENALTY = 0          # 港股不再降权（之前 1.5）——2026-08-11 主人令
MIN_A_SHARES_IN_TOP = 0  # A 股硬保底关闭（之前 max(1, TOP_N-1)=2）——公平竞争


_STOCK_NAME_MAP = None
def _stock_name_map():
    """延迟加载 raw_data/stock_names.json → {code: name}，用于候选池 code-only 补名。
    2026-08-22 主人令：最终推荐候选池出现多个「只有代码没股票名」条目
    （601899/600206/000725），fix_name 在 name==code 时直接返回 code，需在此兜底补全。"""
    global _STOCK_NAME_MAP
    if _STOCK_NAME_MAP is None:
        _m = {}
        try:
            sp = os.path.join(ROOT, "raw_data", "stock_names.json")
            if os.path.exists(sp):
                d = json.load(open(sp, encoding="utf-8"))
                for it in (d.get("data") or []):
                    if isinstance(it, dict) and it.get("code") and it.get("name"):
                        _m[str(it["code"])] = str(it["name"])
        except Exception as e:
            print(f"[warn] stock_names 加载失败: {e}")
        _STOCK_NAME_MAP = _m
    return _STOCK_NAME_MAP


def _resolve_name(code, name):
    """fix_name 兜底后仍为纯代码（name==code/缺失）时，用 stock_names 映射补全真实股票名。"""
    n = fix_name(code, name)
    c = norm_code(code)
    if not n or n == c:
        m = _stock_name_map().get(code) or _stock_name_map().get(c)
        if m:
            return m
    return n





def load_js(name, var_name):
    """读取 data/xxx.js（window.X = {...}; 格式）并返回 JSON 对象"""
    path = os.path.join(DATA, name)
    if not os.path.exists(path):
        return {}
    try:
        with open(path, encoding="utf-8") as f:
            text = f.read()
        # 🔴 2026-09-11 一劳永逸修复（主人报「最终推荐/生命周期没算出来」排查中发现）：
        #   原逻辑要求 text **必须以 "window.<var>" 开头**才剥离前缀赋值。
        #   但部分生成器会在文件头写 `/* ... */` 说明注释（如某个策略生成器产出的
        #   data/*.js），于是 startswith 判假 → 前缀不剥离
        #   → json.loads("/* ... */\nwindow.X = {...}") → line 1 column 1 直接炸
        #   → 该路共振源被【静默丢弃】（长期少一路融合，且只打一行 warn 不易察觉）。
        #   现改为：先剥所有 /* */ 注释块，再按 window. 前缀剥离。
        text = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
        text = text.strip()
        if text.startswith("window."):
            text = text.split("=", 1)[1]
        text = text.rstrip(";\n ")
        return json.loads(text)
    except Exception as e:
        print(f"[warn] 读取 JS 失败 {name}: {e}")
        return {}


def load_json(name):
    path = os.path.join(RAW, name)
    if not os.path.exists(path):
        return {}
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"[warn] 读取失败 {name}: {e}")
        return {}


# ═══════════════════════════════════════════════════════════════════════════
# 🔴🔴 2026-09-18 主人令「融合器不能写死」·一劳永逸修复（改动1：去硬编码）
# ───────────────────────────────────────────────────────────────────────────
# 问题：本文件原 L590 把四信号 edge 写死为常量字典。而 edge 的真源是
#   raw_data/backtest_expectancy.json（E 批 walk-forward 回测产出，每日刷新）。
#   实测漂移（2026-09-18 07:06:51 线上真值 vs 写死值）：
#       jinzuan  8.11  →  8.581   (+0.471)
#       chan     3.68  →  4.408   (+0.728)
#       trend   -7.54  → -7.495   (+0.045)
#       jigou  -10.36  → -9.422   (+0.938)
#   ⇒ src_score 偏差 0.008~0.169，且回测重跑后**永不自动刷新**（写死即错）。
#
# 修法：运行期从 backtest_expectancy.json 动态加载（照抄 generate_top10.py:83-112
#   的成熟写法，保持全站同口径），读不到则回退硬编码默认值 **并显式告警 +
#   置降级标记**（绝不静默用旧值 —— 静默是主人反复强调的红线）。
#
# 时序说明（重要）：本脚本属 D 批（20:00），而 backtest_expectancy 属 E 批（21:00）
#   ⇒ 当前读到的是**前一日**的 edge（架构级时序倒挂）。改动5 会把
#   backtest_expectancy 前置到 B 批尾（18:10 后），此后本块读到当日值。
#   在那之前，本块读到的是 T-1 值 —— 但已比「永久不变的硬编码」准确。
# ═══════════════════════════════════════════════════════════════════════════
SIGNAL_EDGE_DEFAULT = {
    "jinzuan": 8.11,
    "chan":    3.68,
    "trend":  -7.54,
    "jigou": -10.36,
}
# 信号英文键 → by_factor 中的键名
_SIG_FACTOR_KEY = {
    "jinzuan": "sig_jinzuan",
    "chan":    "sig_chan",
    "trend":   "sig_trend",
    "jigou":   "sig_jigou",
}

SIGNAL_EDGE = dict(SIGNAL_EDGE_DEFAULT)   # 生效值（动态覆盖后）
SIGNAL_N = {}                             # 样本量（诊断/回显用）
SIGNAL_CONSISTENT = {}                    # T+5 与 T+10 符号是否一致
SIGNAL_EDGE_SOURCE = "hardcoded"          # hardcoded=回退默认 | backtest_expectancy@<generated>
SIGNAL_EDGE_DEGRADED = False              # True = 动态加载失败（降级），透传到产物

def _load_signal_edge_dynamic():
    """运行期加载四信号 edge。返回 (edge_dict, meta)。失败回退默认值并标降级。"""
    global SIGNAL_EDGE_SOURCE, SIGNAL_EDGE_DEGRADED
    edge = dict(SIGNAL_EDGE_DEFAULT)
    meta = {}
    bt_path = os.path.join(RAW, "backtest_expectancy.json")
    try:
        if not os.path.exists(bt_path):
            raise FileNotFoundError(bt_path)
        with open(bt_path, encoding="utf-8") as f:
            bt = json.load(f)
        by_factor = bt.get("by_factor") or {}
        if not by_factor:
            raise ValueError("by_factor 为空")
        _hit = 0
        for name, fkey in _SIG_FACTOR_KEY.items():
            v = by_factor.get(fkey) or {}
            e10 = v.get("edge10")
            if e10 is None or (isinstance(e10, str) and not e10.strip()):
                continue
            try:
                edge[name] = float(e10)
            except (TypeError, ValueError):
                continue
            SIGNAL_N[name] = int(v.get("n_on10") or 0)
            SIGNAL_CONSISTENT[name] = ((float(v.get("edge5") or 0) > 0)
                                       == (float(e10) > 0))
            _hit += 1
        if _hit == 0:
            raise ValueError("四信号 edge10 全部缺失")
        # 🔴 2026-09-18 小九实测修正（推送前拦下）：产物字段真实位置是
        #   **meta.generated**（实测 raw_data/backtest_expectancy.json：
        #   meta = {generated, method, horizons, n_snapshots, date_range, ...}），
        #   顶层并无 generated/update_time。原写法只读顶层 ⇒ 恒取到 "?"，
        #   等于「来源版本号失效」——降级诊断失效、交接档无法核对用的是哪一版 edge。
        #   故改为 meta 优先 + 顶层兼容回退（老产物/上游改版都不致静默取空）。
        _meta = bt.get("meta") or {}
        gen = str(_meta.get("generated") or _meta.get("update_time")
                  or bt.get("generated") or bt.get("update_time") or "?")
        SIGNAL_EDGE_SOURCE = f"backtest_expectancy@{gen}"
        meta = {"generated": gen, "hit": _hit,
                "n_snapshots": _meta.get("n_snapshots", bt.get("n_snapshots")),
                "date_range": _meta.get("date_range")}
        print(f"[信号edge] ✅ 动态加载 {_hit}/4 源 ← {SIGNAL_EDGE_SOURCE}")
        for _n in _SIG_FACTOR_KEY:
            _d = SIGNAL_EDGE_DEFAULT.get(_n, 0.0)
            _v = edge.get(_n, 0.0)
            _flag = "" if abs(_v - _d) < 1e-9 else f"  (写死值 {_d:+.2f} 漂移 {_v - _d:+.3f})"
            print(f"    {_n:8s} {_v:+8.3f}  n={SIGNAL_N.get(_n, 0)}{_flag}")
    except Exception as e:
        SIGNAL_EDGE_DEGRADED = True
        SIGNAL_EDGE_SOURCE = f"hardcoded(fallback: {e})"
        print(f"[信号edge] ⚠️ 动态加载失败，回退硬编码默认值（已标降级）: {e}")
        for _n in _SIG_FACTOR_KEY:
            print(f"    {_n:8s} {edge[_n]:+8.3f}  (硬编码)")
    return edge, meta


SIGNAL_EDGE, SIGNAL_EDGE_META = _load_signal_edge_dynamic()


def _signal_edge_of(code_signals):
    """给定某票的 signals dict，按**当前生效的** edge 加权求和。
    与旧写死实现同语义，仅数据源改为运行期动态值。"""
    if not code_signals:
        return 0.0
    tot = 0.0
    for k, v in code_signals.items():
        if v:
            tot += SIGNAL_EDGE.get(k, 0.0)
    return tot




def market_prefix(code):
    c = str(code or "").strip()
    if not c:
        return "sz"
    # 港股：5 位纯数字（A股为 6 位）
    if c.isdigit() and len(c) == 5:
        return "hk"
    if c.startswith(("300", "301")):
        return "sz"
    if c.startswith(("688", "689")):
        return "sh"
    if c.startswith(("8", "4", "92")):
        return "bj"
    if c.startswith(("6",)):
        return "sh"
    if c.startswith(("0", "3")):
        return "sz"
    return "sz"


def board_from_code(code, market=None):
    c = str(code or "")
    m = str(market or "").lower()
    # 港股：5 位纯数字（A股为 6 位），或显式 market 为港股
    if m in ("hk", "港股") or (c.isdigit() and len(c) == 5):
        return "港股"
    if c.startswith(("300", "301")):
        return "创业板"
    if c.startswith("688"):
        return "科创板"
    if c.startswith(("8", "4", "92")):
        return "北交所"
    return "主板"


def safe_float(x, default=0.0):
    try:
        return float(x)
    except Exception:
        return default


def num_or_none(x):
    """严格数值化：None / "" / 不可解析 → None。**绝不把缺失伪造成 0.0**。

    2026-09-11 A 类修复：原输出用 safe_float(s["pct_chg"])，缺失涨跌幅被写成 0.00，
    前端显示为「平盘」，而当日真实是 −5.42% / −4.67%（紫金矿业/国城矿业 09-11）。
    """
    if x is None or x == "":
        return None
    try:
        return float(x)
    except Exception:
        return None


def _num2(x):
    v = num_or_none(x)
    return round(v, 2) if v is not None else None


def _set_close(r, price, pct, src, date=None):
    """价格真实性闸门（2026-09-11 A 类修复）：只有「数据日期 == 今日」的价格才准进 close。

    事故：最终推荐 Top2 的 close 用的是 09-10 收盘价（34.11 / 27.63），pct_chg 被写成
      0.00 → 止损/目标价/盈亏比/跟踪收益全部建立在过期价上。根因是各处用
      `s.get("close") or r["close"]` 覆盖式赋值（后写者赢，因子源最后跑把当日价顶掉）。
    日期不可验证的价格一律不采信，只记进 _price_rejected 便于排查。
    """
    p = num_or_none(price)
    if not p:
        return False
    _today = datetime.now().strftime("%Y-%m-%d")
    if not date or str(date)[:10] != _today:
        r.setdefault("_price_rejected", []).append(
            "%s:%s" % (src, "无日期" if not date else str(date)[:10]))
        return False
    r["close"] = p
    _pc = num_or_none(pct)
    if _pc is not None:
        r["pct_chg"] = _pc
    r["close_date"] = _today
    r["close_source"] = src
    r["close_verified"] = True
    return True


_QUOTE_SNAP = None


def _quote_snapshot():
    """当日有效行情快照 {6位code: {"price","pct"}}，带**日期校验**。

    数据源优先级（均要求 update_time 日期 == 今日，否则整份作废）：
      ① STOCK_QUOTE.js     —— 15:02 收盘快照，覆盖全 A（含 price/pct/prev_close）
      ② CANDIDATE_QUOTES.js —— 候选池行情（raw_data/candidate_quotes.json 的 js 版，含 chg）
    这是最终推荐价格的**唯一权威来源**：因子实验室 FACTOR_LAB 记录里的 close 是
    「上次算到这只票那天」的快照（roe 按季缓存 asof_q / abn 按月缓存 asof_ym），
    实测 roe TOP30 的 close 30/30 全部等于当日昨收 —— 根本不是报价，不可用于定价。
    """
    global _QUOTE_SNAP
    if _QUOTE_SNAP is not None:
        return _QUOTE_SNAP
    today = datetime.now().strftime("%Y-%m-%d")
    snap = {"date": None, "source": None, "map": {}}

    _sq = load_js("STOCK_QUOTE.js", "STOCK_QUOTE") or {}
    _d = str(_sq.get("update_time") or "")[:10]
    if _d == today:
        _m = {}
        for _k, _v in (_sq.get("stocks") or {}).items():
            if not isinstance(_v, dict):
                continue
            _c = norm_code(_k).lstrip(".")
            _p = num_or_none(_v.get("price"))
            if _c and _p:
                _m[_c] = {"price": _p, "pct": num_or_none(_v.get("pct"))}
        if _m:
            snap = {"date": _d, "source": "STOCK_QUOTE", "map": _m}

    if not snap["map"]:
        _cq = load_js("CANDIDATE_QUOTES.js", "CANDIDATE_QUOTES") or {}
        _d2 = str(_cq.get("update_time") or "")[:10]
        if _d2 == today:
            _m = {}
            for _it in (_cq.get("items") or []):
                if not isinstance(_it, dict):
                    continue
                _c = norm_code(_it.get("code") or "").lstrip(".")
                _p = num_or_none(_it.get("price"))
                if _c and _p:
                    _m[_c] = {"price": _p, "pct": num_or_none(_it.get("chg"))}
            if _m:
                snap = {"date": _d2, "source": "CANDIDATE_QUOTES", "map": _m}

    _QUOTE_SNAP = snap
    if snap["map"]:
        print(f"[行情] 价格闸门启用：{snap['source']} @ {snap['date']}，覆盖 {len(snap['map'])} 只")
    else:
        print("[warn] ⚠️ 无当日行情快照（STOCK_QUOTE / CANDIDATE_QUOTES 均缺失或非当日）→ "
              "close/pct_chg 一律写 null（不再伪造 0.00%）")
    return snap


def build_sector_maps(sector_rs):
    sectors = sector_rs.get("sectors") or []
    strong_rel = sector_rs.get("strong_relative_5d") or []
    strong_abs = sector_rs.get("strong_5d") or []

    rel_set = set()
    abs_set = set()
    score_map = {}

    for s in sectors:
        name = s.get("name")
        if not name:
            continue
        score_map[name] = {
            # 🔴 2026-09-13 一劳永逸（不得假成功）：**展示类**字段一律 num_or_none。
            #   原用 safe_float ⇒ 缺失被写成 0.0，前端显示「+0.00%」＝平盘，
            #   而真实可能是 −5.42%（2026-09-11 紫金矿业实测）。
            "relative_5d": num_or_none(s.get("relative_5d")),
            "pct_5d": num_or_none(s.get("pct_5d")),
            "pct_20d": num_or_none(s.get("pct_20d")),
        }

    for item in strong_rel[:SECTOR_TOP_N]:
        if isinstance(item, dict):
            rel_set.add(item.get("name"))
        else:
            rel_set.add(item)
    for item in strong_abs[:SECTOR_TOP_N]:
        if isinstance(item, dict):
            abs_set.add(item.get("name"))
        else:
            abs_set.add(item)

    # 额外把贵金属/黄金概念/小金属/有色金属也纳入强板块集合
    for s in sectors:
        name = s.get("name", "")
        if any(k in name for k in ("贵金属", "黄金", "小金属", "有色金属")):
            rel_set.add(name)
            if safe_float(s.get("relative_5d")) > 0 or safe_float(s.get("pct_5d")) > 0:
                score_map.setdefault(name, {})

    return rel_set, abs_set, score_map


def sector_score_for(stock, rel_set, abs_set, score_map):
    """返回 (板块加分, [hit对象, ...])。
    hit 对象含 name/pct_5d/relative_5d/strong，便于前端展示「关联板块资金」。
    """
    hits = []
    score = 0.0
    seen = set()

    CONCEPT_ALIASES = {
        "黄金概念": "贵金属",
        "小金属概念": "小金属",
        "稀土永磁": "小金属",
        "有色金属": "有色金属",
        "半导体概念": "半导体",
    }

    def make_hit(name):
        info = score_map.get(name) or {}
        return {
            "name": name,
            # 🔴 2026-09-13：展示字段一律 num_or_none（缺失=null，绝不伪造成 0.0）
            "pct_5d": num_or_none(info.get("pct_5d")),
            "relative_5d": num_or_none(info.get("relative_5d")),
            "strong": name in rel_set,
        }

    def hit(name):
        nonlocal score
        if name in seen:
            return
        seen.add(name)
        if name in rel_set:
            hits.append(make_hit(name))
            score += 1.0
        elif name in abs_set:
            hits.append(make_hit(name))
            score += 0.5

    def hit_alias(name):
        hit(name)
        alias = CONCEPT_ALIASES.get(name)
        if alias and alias != name:
            hit(alias)

    ind = stock.get("industry") or ""
    if ind:
        hit_alias(ind)

    for c in stock.get("concepts") or []:
        hit_alias(c)

    # 名称/行业/概念中显含贵金属/黄金/小金属/有色的，直接补分
    name = stock.get("name", "")
    has_metal_keyword = (
        any(k in name for k in ("黄金", "中金", "银泰", "赤峰", "山东", "紫金", "湖南")) and "金" in name
    )
    for raw in [ind] + (stock.get("concepts") or []):
        if isinstance(raw, str) and any(k in raw for k in ("黄金", "贵金属", "小金属", "有色金属")):
            has_metal_keyword = True
            break
    if has_metal_keyword and not any("黄金" in h["name"] or "贵金属" in h["name"] or "小金属" in h["name"] or "有色" in h["name"] for h in hits):
        score += 0.8
        hits.append({"name": "贵金属/有色(关键词)", "pct_5d": 0.0, "relative_5d": 0.0, "strong": True})

    return round(score, 2), hits


def main():
    # 🛡 2026-08-20 主人令·一劳永逸：所有选股策略必须 18:00 后才能跑。
    # final_recommend 是跨策略共振最终产物，依赖港股/龙虎榜/北向/板块资金等全部盘后数据。
    # 此前 16:18 本地手动跑 + 17:13 CRDS 提前出结果，均因数据未全就绪导致结果不准。
    # 加统一选股策略守门：早于 18:00 直接 sys.exit(1)；应急可设 TIME_GATE_BYPASS=1。
    from utils.time_gate import check_stock_picking_ready
    check_stock_picking_ready(by='final_recommend')
    triple = load_json("triple_consensus.json")
    top10 = load_json("top10_daily.json")
    crds = load_json("crds_card_data.json")
    sector_rs = load_json("sector_rs.json")
    profile = load_json("stock_profile.json")
    crisis = load_json("crisis_data.json")
    gold_pool = load_json("gold_pool.json")

    # ── 质差股一票否决（2026-09-07 主人令·贝塔派审计缺口补齐）──
    # CRDS/板块龙头等旁路源不经过 generate_top10 漏斗，需在此汇总口兜底拦截。
    # 构建 纯数字code→fq 查找（fq 键形如 sh_600030/hk_00005）。
    _fq_stocks = (load_json("fundamental_quality.json") or {}).get("stocks") or {}
    _fq_by_digits = {}
    for _k, _v in _fq_stocks.items():
        _d = re.sub(r"\D", "", _k)
        if _d and _d not in _fq_by_digits:
            _fq_by_digits[_d] = _v

    rel_set, abs_set, score_map = build_sector_maps(sector_rs)

    # 读取 STOCK_STOP_DATA.js（支撑/压力/ATR）
    stop_data = load_js("STOCK_STOP_DATA.js", "STOCK_STOP_DATA")
    stop_stocks = stop_data.get("stocks") or {}

    # ── 读取四量终极共振数据（多周期确认）──
    # 🛡 2026-08-26 一劳永逸：优先 60min 版(FOUR_VOLUME_60M)；但其 update_time 非今日
    #   （baostock 60min 源常滞后，曾陈旧到 8/22）→ 回退读日线版 FOUR_VOLUME.js（新鲜），
    #   避免最终推荐用几天前的陈旧四量汇总（"逻辑不对"根因）。两份 schema 兼容(stocks[])。
    _four_vol_raw = load_js("FOUR_VOLUME_60M.js", "FOUR_VOLUME_60M")
    _four_vol_src = "60m"
    try:
        _ut = _four_vol_raw.get("update_time", "")
        _ut_date = datetime.strptime(_ut, "%Y-%m-%d %H:%M:%S").date()
        # 🔴 2026-09-11 A 类修复：原判据只看 update_time —— 但只要 60m 文件是"今天生成的空壳"
        #   （实测 09-11 21:33 的 FOUR_VOLUME_60M.js：total=0 / stocks=[]），就被当成有效
        #   数据源，日线版 FOUR_VOLUME.js（11 只命中）**永远不被读取** → 60m 多周期共振加分
        #   恒为 0，且看不出一丝异常。现补「空数据」判据：命中数 0 视同不可用。
        _n60 = len(_four_vol_raw.get("hits") or _four_vol_raw.get("stocks") or [])
        if _ut_date < datetime.now().date():
            _four_vol_raw = load_js("FOUR_VOLUME.js", "FOUR_VOLUME")
            _four_vol_src = "day(60m陈旧回退)"
            print(f"[warn] 60m 四量 update_time={_ut} 非今日，回退读日线四量终极")
        elif _n60 == 0:
            _four_vol_raw = load_js("FOUR_VOLUME.js", "FOUR_VOLUME")
            _four_vol_src = "day(60m空数据回退)"
            print(f"[warn] ⚠️ 60m 四量 update_time={_ut} 是今日但命中数=0（空壳），回退读日线四量终极")
    except Exception as e:
        print(f"[warn] 四量新鲜度校验失败，沿用 60m: {e}")
    _60m_hits = {}  # norm_code → {reason, signals[], qd, pct_chg, ...}
    for item in (_four_vol_raw.get("hits") or _four_vol_raw.get("stocks") or []):
        c = norm_code(item.get("code") or item.get("code"))
        if c:
            _60m_hits[c] = item
    print(f"[info] 四量数据({_four_vol_src}): 加载 {len(_60m_hits)} 只命中")

    # 2026-09-04 主人令：cockpit_backtest 死数据源整段删除（生成器 09-03 下线，load 恒空，仅产出全零 backtest 垃圾）
    tt = load_json("triple_track.json")
    tt_alerts = {}
    for a in tt.get("alerts") or []:
        code = a.get("code")
        if not code:
            continue
        tt_alerts.setdefault(code, []).append(a)

    crisis_score = safe_float(crisis.get("score"), 0.0)
    crisis_high = crisis_score >= CRISIS_HIGH_THRESHOLD

    # ── 市场状态 regime 门控（回测验证提升胜率，见 backtest_tdx.json optimized_summary）──
    # stabilize / rebound_diverge = 好状态：历史回测该阶段 ≥3 共振信号整体负期望 → 应少推/观察
    # grind / panic               = 可开仓状态 → 正常推
    # 🔴 2026-09-11 A 类修复（统一失败语义）：原 except 分支写 `_open_regime = True` 并注释
    #   「失败时默认正常推」—— 但 get_current_regime() 取不到数时是 **return None 而非抛异常**，
    #   except 永不触发，实际走的是 bool(None and ...) = False（=观望、推票数 5→2），**注释与
    #   行为相反**；同一时刻 generate_top10 写 "stabilize"、export_optimized_strategy 写
    #   "grind/可开仓" → 同一次失败三种结论。
    #   现统一走 get_current_regime_safe()：ok=False ⇒ regime=None + 不开仓（显式保守），
    #   并把 ok/reason 写进产物，前端与巡检可核对"这条结论是算出来的还是降级来的"。
    #   （若将来决定「失败时按正常推」，改这里一处即可，三个消费方自动同步。）
    _regime_info = None
    _regime_ok = False
    _regime_reason = "unavailable"
    _open_regime = False
    try:
        from regime_filter import get_current_regime_safe, is_open_regime
        _regime_info, _regime_ok, _regime_reason = get_current_regime_safe()
        _open_regime = bool(_regime_ok and is_open_regime((_regime_info or {}).get("regime")))
    except Exception as e:
        print(f"  [warn] regime 门控不可用: {e}")
        _regime_reason = f"import/exception:{e}"
    _regime_name = (_regime_info or {}).get("regime") if _regime_ok else None
    _regime_date = (_regime_info or {}).get("date") if _regime_ok else None
    if not _regime_ok:
        print(f"  [warn] ⚠️ regime 不可用（{_regime_reason}）→ 按保守处置：观望、推票数 {TOP_N}→{max(2, TOP_N // 2)}")
    _effective_top_n = TOP_N if _open_regime else max(2, TOP_N // 2)
    _action_label = "买入" if _open_regime else "观察（市场企稳/反弹，历史回测负期望）"
    print(f"[regime] 市场状态={_regime_name or '未知'}({_regime_date}) ok={_regime_ok} "
          f"开仓={_open_regime} 推票数 {TOP_N}→{_effective_top_n}")

    profiles = (profile or {}).get("profiles") or {}

    pool = defaultdict(lambda: {
        "code": "",
        "name": "",
        "market": "",
        "board": "",
        "close": None,
        "pct_chg": None,
        "stop_loss": None,
        "target_price": None,
        "risk_reward": None,
        "support": None,
        "resistance": None,
        "atr": None,
        "sources": [],
        "source_scores": {},
        "industry": "",
        "concepts": [],
        "reasons": [],
        "signals": [],
        "tags": [],           # 中文信号标签
        "enter_dates": [],         # 各源记录的入选日
        "sector_hits": [],         # 板块命中（带涨幅）
    })

    def ensure(code, name, market, board):
        # 2026-09-03 主人令修复：FACTOR_LAB/外部源代码带 '.' 前缀（如 '.601899'），
        #   norm_code 不剥点 → pool key 带点 → 画像/止损/行情 lookup 全失配，
        #   Top5 第1/2名 concepts=0、reason 空、止损/目标/盈亏比全 None（第3名四量终极源正常）。
        _nc = norm_code(code).lstrip('.')
        r = pool[_nc]
        if not r["code"]:
            r["code"] = _nc
            r["name"] = fix_name(_nc, name)
            r["market"] = market or market_prefix(_nc)
            r["board"] = board or board_from_code(_nc)
            # 从 STOCK_STOP_DATA 预填支撑/压力/ATR/止损/目标（如存在）
            ss = stop_stocks.get(_nc) or stop_stocks.get(code)
            if ss:
                for k in ["support", "resistance", "atr", "stop_loss", "target_price", "risk_reward"]:
                    if ss.get(k) is not None:
                        r[k] = ss[k]
        else:
            # 已有记录时，若旧 name 为空/等于 code，尝试用新 name/映射表更新
            if not r["name"] or r["name"] == r["code"]:
                r["name"] = fix_name(code, name)
        return r

    def _factor_in_pool(code):
        """因子侧专用：**只查不建**。返回该票是否已被其他源选进 pool。

        🔴🔴 2026-09-18 主人令：「因子只是加分减分项，不是选股策略」。
           ensure() 对**不在池内**的票会新建记录（pool 是 defaultdict）⇒ 因子榜的票会被
           无条件创造进最终推荐候选集，那是「因子参与选股」，不是「加分」。
           本函数只做成员判断 ⇒ 因子只能给**已经选出来的股**加减分。
        ⚠️ 探测绝不能用 pool[_nc]：defaultdict 取值会**创建空记录并留在池里**，
           那正是本判据要禁止的「进池」，故必须先 in 判断。"""
        return norm_code(code).lstrip('.') in pool

    # 1) 三重共识
    for s in triple.get("stocks") or []:
        code = s.get("code")
        if not code:
            continue
        r = ensure(code, s.get("name"), s.get("market"), s.get("board"))
        score = safe_float(s.get("total_score") or s.get("score"))
        # 2026-08-13 公平性修复：去掉 score>=25 硬门槛（低于直接出局=歧视），
        # 改为统一归一化；入选即给基础分，避免强三重共识信号被误杀。
        src_score = min(4.0, max(0.5, score / 25.0))
        if src_score > 0:
            r["sources"].append("三重共识")
            r["source_scores"]["三重共识"] = round(src_score, 2)
            _set_close(r, s.get("close"), s.get("pct_chg"), "三重共识", triple.get("update_time"))
            r["stop_loss"] = s.get("stop_loss") or r["stop_loss"]
            r["target_price"] = s.get("target_price") or r["target_price"]
            r["risk_reward"] = s.get("risk_reward") or r["risk_reward"]
            r["industry"] = r["industry"] or (s.get("industry") or "")
            r["concepts"] = list(set((r["concepts"] or []) + (s.get("concepts") or [])))
            r["reasons"].append(f"三重共识 评分{score:.0f}")
            r["signals"].append("跨策略共振")
            if s.get("enter_date"):
                r["enter_dates"].append(s["enter_date"])

    # 2026-09-03 主人令：#2 驾驶舱 A/B 档 source 整段下线（cockpit.* 不再读，sources 也不再 append "驾驶舱A档/B档"）
    # 2026-09-07 一劳永逸：清理该次下线遗留的孤儿代码块（仍引用已删除的 label/tech/qs/tier），
    #   导致 UnboundLocalError 崩溃 → D 档 final_recommend 持续未产出（红灯 all_FINAL_RECOMMEND_DATA）。

    # 3) 四量终极 (top10_daily.top10)
    SIG_MAP = {
        "chan": "缠论买点",
        "jinzuan": "金钻信号",
        "jigou": "机构变红",
        "trend": "上涨趋势",
        "form_A": "形态A",
    }
    _alpha_skipped = 0   # 改动12：因「无正 edge 资格」被拦下的四量票数（诊断回显）
    for s in top10.get("top10") or []:
        code = s.get("code")
        if not code:
            continue
        r = ensure(code, s.get("name"), s.get("market"), s.get("board"))
        sig_count = safe_float(s.get("sig_count"))
        qd = bool(s.get("qd"))
        # 🔴 2026-09-14 阿狸咪修复（回测驱动·最高ROI）：原 src_score = sig_count*0.6 对所有信号
        #   （含强负的 trend/jigou）等量计数 → 反向奖励回测亏钱组合（by_signal 0,0,1,1 胜率仅39%、edge -2.42）。
        #   现改用与 generate_top10.py 同源的 walk-forward T+10 边际加权（jinzuan+8.11/chan+3.68/
        #   trend-7.54/jigou-10.36）：正edge组合高分、负edge组合压到0（剔除），与回测证据方向一致。
        _sig_d = s.get("signals", {}) or {}
        # 🔴 2026-09-18 改动1：edge 改由模块级 SIGNAL_EDGE 提供（运行期从
        #   backtest_expectancy.json 动态加载，见文件头 _load_signal_edge_dynamic）。
        #   读不到时回退硬编码默认值并已置 SIGNAL_EDGE_DEGRADED 降级标记。
        _edge = _signal_edge_of(_sig_d)
        src_score = max(0.0, min(4.5, 1.5 + _edge * 0.18))
        # 🔴 2026-09-18 改动12：按边际 alpha 精选源 —— 基础分≤0 = 无任何正 edge
        #   信号命中（如纯 trend/jigou 负 alpha 组合）⇒ 不给加分资格，防负 alpha
        #   票借 qd/60m 加分复活成独立源。资格随动态 edge 自适应（扩样后自动跟随）。
        #   V8_FUSION_ALPHA_SELECT=0 可回退旧行为。
        _alpha_qualified = (src_score > 0.0) or (not V8_FUSION_ALPHA_SELECT)
        if V8_FUSION_ALPHA_SELECT and not _alpha_qualified:
            _alpha_skipped += 1
        if qd and _alpha_qualified:
            src_score += 0.5
        # ── 60min 多周期共振加分（同算法不同时间框架 = 经典共振）──
        _60m_item = _60m_hits.get(norm_code(code))
        if _60m_item:
            _60m_qd = bool(_60m_item.get("qd") or _60m_item.get("XG"))
            _60m_bonus = 0.8 if _60m_qd else 0.5
            if _alpha_qualified:
                src_score += _60m_bonus
            # 🔴 2026-09-11 A 类修复：标签必须与真实口径一致。_four_vol_src 非 60m
            #   （60m 陈旧/空壳回退日线）时不得再标「60min多周期共振」—— 那是日线共振。
            if _four_vol_src.startswith("60m"):
                r["signals"].append("60min多周期共振")
                r["_60m_resonance"] = True
            else:
                r["signals"].append("多周期共振(日线口径)")
        # ── end 60m ──
        src_score = round(min(4.5, max(0.0, src_score)), 2)
        if src_score > 0:
            r["sources"].append("四量终极")
            r["source_scores"]["四量终极"] = src_score
            _set_close(r, s.get("close"), s.get("pct_chg"), "四量终极", top10.get("update_time"))
            r["stop_loss"] = s.get("stop_loss") or r["stop_loss"]
            r["target_price"] = s.get("target_price") or r["target_price"]
            r["risk_reward"] = s.get("risk_reward") or r["risk_reward"]
            r["industry"] = r["industry"] or ""
            r["concepts"] = list(set((r["concepts"] or []) + (s.get("sectors") or [])))
            r["reasons"].append(f"四量终极 信号{sig_count:.0f}项")
            for k, label in SIG_MAP.items():
                if s.get("signals", {}).get(k):
                    r["signals"].append(label)
            if qd:
                r["signals"].append("主力动量翻多")
            if s.get("enter_date"):
                r["enter_dates"].append(s["enter_date"])
            elif top10.get("update_time"):
                r["enter_dates"].append(top10["update_time"][:10])
    # 🔴 2026-09-18 改动12：拦截情况回显（不许静默——被拦了多少只必须可见）
    if V8_FUSION_ALPHA_SELECT and _alpha_skipped:
        print(f"[改动12] alpha精选：{_alpha_skipped} 只四量票因无正edge信号命中被拦（不计独立源，标签仍展示）")

    # 2026-09-03 主人令：#4 全站精选 source 整段下线（allsite.* 不再读）

    # 5) 逆势龙头：仅在危机雷达高位时并入
    if crisis_high:
        for tier, label, base in [
            ("elite", "逆势龙头·精锐", 3.0),
            ("advanced", "逆势龙头·进阶", 2.0),
            ("watch", "逆势龙头·观察", 1.0),
        ]:
            for s in crds.get(tier) or []:
                code = s.get("code")
                if not code:
                    continue
                r = ensure(code, s.get("name"), "", "")
                r["sources"].append(label)
                r["source_scores"][label] = round(base, 2)
                r["reasons"].append(f"{label} 评分{s.get('score')}")
                r["signals"].append(f"{label}")
                if s.get("enter_date"):
                    r["enter_dates"].append(s["enter_date"])

    # 2026-09-03 主人令：#6 大牛股猎手 source 整段下线（不再 append "大牛股猎手"，lhb 数据仍可被其他源使用）
    # 2026-09-03 主人令：#7 板块龙头 source 整段下线（不再 append "板块龙头"，sec_score 仍可用于其他源加分）
    # ── 第8节 因子实验室因子（方案B：智能融合，非简单硬加权）──
    # 维度1 异常换手率：缩量=因子高=强势（abnormal_turnover.top 前30）；放量弱势=bottom（扣0.5）
    # 维度2 ROE_TTM：全市场主板大市值档 Top30（高 ROE=质量）
    # 分层加权：前5名 +2.0 / 6-15名 +1.5 / 16-30名 +1.0
    # 择时控权：非开仓期(_open_regime=False) 因子权重 ×0.3（弱加成，避免逆势放大因子噪声）
    # 放量弱势：bottom 入池则打「放量弱势」信号，最终分 −0.5（弱势扣分）
    # 名字兜底：ROE 票 baostock 常返回 '1' → _resolve_name + stock_names 映射补全
    # 🛡 2026-09-09 主人令：最终推荐必须等因子实验室产出后才能推荐（因子为更好选股而存在）。
    #   校验 FACTOR_LAB.js 为当日新鲜；缺失/陈旧则有限等待（覆盖 B 批生成器偶发延迟），超时仍不可用则降级跳过融合。
    fl = None
    _fl_degraded = False   # 🔴 2026-09-17：因子因**内容陈旧**而降级（透到 data_degraded，不许静默）
    _fl_last_dd = ""       # 诊断用：最近一次读到的因子 data_date（日志/降级说明里回显）
    # 🆕🔴 2026-09-18 主人令「对当天产生的股票做加减分的排列，才会知道到底逻辑有没有出错」：
    #   因子侧此前只往内存里的 tags/signals/reasons 写字，**产物完全不落盘** ⇒ 前端无从验证逻辑。
    #   现于每条池内记录挂 factor_actions[]，并在产物顶层输出 factor_chain / factor_trace。
    #   adj 语义**严格照实现**：能进 final_score 公式的才写非 0，仅展示的写 0（不许美化）。
    _n_at_hit = 0          # 异常换手率：命中池内票数
    _n_roe_hit = 0         # ROE_TTM：命中池内票数
    _n_weak_hit = 0        # 放量弱势：扣分票数
    _today = datetime.now().strftime("%Y-%m-%d")
    _fl_max_wait = 0 if V8_OFFLINE else 20  # 离线模式本机无 baostock 注定取不到 FACTOR_LAB，直接跳过等待
    # 🔴 2026-09-17 阿狸咪的工程师：非交易周（周六/周日）豁免 —— 周末 baostock 无新数据，
    #   因子的 data_date 合理地停在本周最后交易日（周五）。不豁免会把「周末正常产物」误判成陈旧。
    #   ⚠️ 残留边界（已登记交接件）：法定节假日不在豁免内（本仓无节假日历），节假日当天可能多
    #   一次**保守方向**的降级 —— 宁可少用一次因子，也不用昨日数据冒充今日（禁假新鲜）。
    _fl_wd = datetime.now().weekday()   # 0=周一 … 6=周日
    _fl_floor = ((datetime.now() - timedelta(days=_fl_wd - 4)).strftime("%Y-%m-%d")
                 if _fl_wd >= 5 else _today)
    for _wi in range(_fl_max_wait):  # 最多等 ~20min（正常 19:40 前 B 批已产完，此处通常 0 等待）
        _cand = load_js("FACTOR_LAB.js", "FACTOR_LAB")
        # 🔴 2026-09-17 阿狸咪的工程师（小九 20:25 回执第⑤项授权落地）：**内容级新鲜校验**。
        #   原实现只看 update_time 的**日期**是否=今天 ⇒ 2026-09-17 04:49 那版
        #   （update_time 日期=09-17，但 data_date=2026-09-16、用的是 09-16 的池）
        #   **整轮被当新鲜** ⇒「用昨日因子算今日推荐」，当日生产事故的直接成因。
        #   现要求 data_date 亦达「数据日」。边界（小九指定，逐条落实）：
        #     ① data_date 滞后 ⇒ **不判失败中止**，仍等满 _fl_max_wait 后降级（fl=None）并置
        #        data_degraded=True —— 否则会造出比现状更糟的「D 批不出推荐」；
        #     ② 老版本产物无 data_date 字段 ⇒ 回退 update_time 单口径（保守兼容）。
        _fl_dd = str((_cand or {}).get("data_date") or "").strip()
        _fl_dd_ok = (not _fl_dd) or (_fl_dd == _today) or (_fl_wd >= 5 and _fl_dd >= _fl_floor)
        if _cand and str(_cand.get("update_time", "")).startswith(_today) and _fl_dd_ok:
            fl = _cand
            break
        if _cand and _fl_dd and not _fl_dd_ok:
            _fl_last_dd = _fl_dd
        # 💓 2026-09-12 主人令·方案①：等待 FACTOR_LAB 当日新鲜数据期间逐分钟打印心跳，
        #   避免被 run_algorithms 监督器 15min 静默杀（SILENCE_KILL_SEC=900）误杀——
        #   误杀会让 final_recommend 永远跑不到出结果那步，FINAL_RECOMMEND_DATA 永久停旧版。
        #   纯打印、不改任何数据口径/筛选条件，仅保活；FACTOR_LAB 就绪即 break，永不伪造数据。
        _fl_hint = ("；周末豁免 data_date≥%s" % _fl_floor) if _fl_wd >= 5 else ""
        if _fl_last_dd:
            _fl_hint += "；当前 data_date=%s" % _fl_last_dd
        print(f"  💓 等待 FACTOR_LAB.js 当日新鲜数据（因子实验室，要求 data_date={_today}{_fl_hint}）"
              f"… 已等 {_wi+1}/{_fl_max_wait} 分钟", flush=True)
        time.sleep(60)
    if fl:
        _at_top = (fl.get("abnormal_turnover") or {}).get("top") or []
        _at_bot = (fl.get("abnormal_turnover") or {}).get("bottom") or []
        _roe_top = (fl.get("roe_largecap") or {}).get("top") or []

        # 流动性闸门（2026-09-11 A 类修复）：停牌/零成交股不进因子榜（产物已标 liquid=False）
        _at_top = [x for x in _at_top if x.get("liquid", True)]
        _roe_top = [x for x in _roe_top if x.get("liquid", True)]
        _at_rank = sorted(_at_top, key=lambda x: safe_float(x.get("factor_at")), reverse=True)
        for i, s in enumerate(_at_rank):
            code = s.get("code")
            if not code:
                continue
            _pure = norm_code(code)
            _pure6 = _pure.lstrip('.')
            _nm = _stock_name_map()
            display_name = (_nm.get(_pure6) or _nm.get(_pure) or _nm.get(code)
                           or (profiles.get(_pure6) or {}).get("name") or s.get("name") or "")
            # 🔴🔴 2026-09-18 主人令：因子不产池 —— 只给「已被其他源选出的票」加减分。
            #   原为 r = ensure(...)：ensure 会对不在池内的票**新建记录**（pool 是 defaultdict）
            #   ⇒ 等于让因子榜 30 只票无条件进入最终推荐候选集。现改为未在池内即跳过。
            if not _factor_in_pool(code):
                continue
            r = ensure(code, display_name, "", "")
            sc = 2.0 if i < 5 else (1.5 if i < 15 else 1.0)
            sc *= (1.0 if _open_regime else 0.3)
            # 🔴 2026-09-18 改动2a：异常换手率 = 负 alpha 源（边际 −2.21pp，命中 85 条）
            #   ⇒ 整源剔除、不进 sources（不计共振/strength）；写 tags 仅作展示。
            #   V8_FUSION_NOISE_FILTER=0 可回退旧行为。
            if V8_FUSION_NOISE_FILTER:
                r["tags"].append("异常换手率")
            else:
                r["sources"].append("异常换手率")
                r["source_scores"]["异常换手率"] = round(sc, 2)
            r["signals"].append("缩量强势")
            # 🆕 留痕（口径照实现）：NOISE_FILTER=1 时只写 tags ⇒ **不计共振、不计 strength、不进 final_score**
            _n_at_hit += 1
            r.setdefault("factor_actions", []).append({
                "factor": "异常换手率",
                "adj": 0.0 if V8_FUSION_NOISE_FILTER else round(sc, 2),
                "scored": (not V8_FUSION_NOISE_FILTER),
                "note": ("缩量强势 排名第%d／tags 展示，不计分（边际 −2.21pp 负 alpha ⇒ 整源剔除）"
                         % (i + 1)) if V8_FUSION_NOISE_FILTER
                        else ("缩量强势 排名第%d／计入 source_scores=%.2f（V8_FUSION_NOISE_FILTER=0 回退态）"
                              % (i + 1, sc)),
            })
            if s.get("first_date"):
                r["enter_dates"].append(s["first_date"])

        _roe_rank = sorted(_roe_top, key=lambda x: safe_float(x.get("roe_ttm")), reverse=True)
        for i, s in enumerate(_roe_rank):
            code = s.get("code")
            if not code:
                continue
            _pure = norm_code(code)
            _pure6 = _pure.lstrip('.')
            _nm = _stock_name_map()
            display_name = (_nm.get(_pure6) or _nm.get(_pure) or _nm.get(code)
                           or (profiles.get(_pure6) or {}).get("name") or s.get("name") or "")
            # 🔴🔴 2026-09-18 主人令：同上（因子不产池）。ROE_TTM 只对已在池内的票降档加分。
            if not _factor_in_pool(code):
                continue
            r = ensure(code, display_name, "", "")
            # 🔴 2026-09-18 改动2a：ROE_TTM 边际 +0.68pp = **弱正**（非负 alpha）
            #   ⇒ 与异常换手率同口径：**不写 sources / source_scores**（不计共振、不计 strength）。
            #   依据：阿狸咪实测 ROE_TTM 有该源均 −2.35%、无该源均 −3.03%，虽是相对正贡献，
            #   但命中 89 条（数量优势）仍会淹没有效信号；且命中率 43.9% ≈ 无选择性。
            # 🔴🔴 2026-09-18 审计补正（主人令「才会知道到底逻辑有没有出错」）：
            #   本处原有一行 `sc = _roe_score(i)` / `sc *= (1.0 if _open_regime else 0.3)`，
            #   但 sc **从未写入任何计分字段**（算完即弃）⇒ 注释所称「降档加分」是**假的**。
            #   现已删除该两行与 _roe_score() 定义；ROE_TTM 的真实角色 = **仅 signals/reasons 展示**。
            r["signals"].append("高ROE")
            _n_roe_hit += 1
            r.setdefault("factor_actions", []).append({
                "factor": "ROE_TTM",
                "adj": 0.0,
                "scored": False,
                "note": ("高ROE 排名第%d／signals+reasons 展示，不计分（边际 +0.68pp 弱正，不足与强源同权）"
                         % (i + 1)),
            })
            # 2026-09-03 主人令：补入选依据与行情（之前第1/2名 reason 空、无价格→分析不如第3名）
            r["reasons"].append(f"基本面因子 高ROE 排名第{i + 1}")
            # 🔴 2026-09-11 A 类修复：**不再从因子榜取价**。FACTOR_LAB 的 close 是
            #   「上次算到这只票那天」的快照（roe 按季 asof_q / abn 按月 asof_ym 缓存，
            #   实测 roe TOP30 的 close 30/30 等于当日昨收），把它当当日价正是本轮
            #   「最终推荐价格是昨天的、涨跌幅被写成 0.00%」的直接原因。
            #   价格改由 _quote_snapshot()（当日 STOCK_QUOTE/CANDIDATE_QUOTES）统一填充。
            if s.get("first_date"):
                r["enter_dates"].append(s["first_date"])

        # 🔴🔴 2026-09-18 审计修复（主人问「扣分标准科学吗？别一开始就犯错」）——原写法有**格式 bug**：
        #   原为 `_weak = {norm_code(x.get("code")) ...}`，而 norm_code 只去 sh/sz/bj/hk 前缀、**不剥点**
        #   ⇒ norm_code("sh.600479") == ".600479"（带点）；
        #   而 pool 的 key 一律是 norm_code(code).lstrip(".") == "600479"（无点）
        #   ⇒ `if key in _weak` **恒为 False** ⇒ 「放量弱势」**从未写入过 signals**。
        #   实测铁证（29 轮产物 / 1333 条候选）：signals 含「放量弱势」= **0 次**
        #   （同期「缩量强势」410 次 /「高ROE」454 次 /「高手共振」37 次）
        #   ⇒ L1160 的 weak_penalty(−0.5) **从未生效过一次**，是**死代码**。
        #   ⚠️ 同类坑本文件已犯过一次：L706 注释「norm_code 不剥点 → pool key 带点 → lookup 全失配」，
        #      当时只修了 ensure 侧，漏修此处。
        #   修法：与 pool key 同口径 —— 补 `.lstrip('.')`。
        _weak = {norm_code(x.get("code")).lstrip('.') for x in _at_bot if x.get("code")}
        for key, r in pool.items():
            if key in _weak:
                r["signals"].append("放量弱势")
                # 🆕 留痕：这是**唯一写进 final_score 的因子动作**
                #   （L1160 weak_penalty：`0.5 if "放量弱势" in signals else 0.0` ⇒ final_score −0.5）
                #   ⚠️ 但截至 2026-09-18，该分档**没有 walk-forward 回测依据**（bottom 榜从未回测），
                #      属「凭空的惩罚」——与 generate_top10.py P5 的明文原则
                #      「只加分不扣分：反向档位在 walk-forward 里无显著负 edge，不给凭空的惩罚」冲突。
                #      ⇒ 本处**不改动它的值**（改权重违反「绝不按短样本调权重」红线），
                #        但在产物里如实标注 evidence="未回测"，并在因子实验室卡上显示 ⚠️；
                #        处置权交主人：回测出显著负 edge ⇒ 保留/加权；否则按 P5 原则降为「仅标注」。
                #      开关：V8_FACTOR_WEAK_PENALTY=0 ⇒ 扣分置 0（仅写 signals 展示，一键回退）。
                _n_weak_hit += 1
                r.setdefault("factor_actions", []).append({
                    "factor": "放量弱势",
                    "adj": -0.5 if _WEAK_PENALTY_ON else 0.0,
                    "scored": bool(_WEAK_PENALTY_ON),
                    "evidence": "未回测",
                    "note": ("FACTOR_LAB.bottom 命中 ⇒ signals「放量弱势」⇒ final_score −0.5（weak_penalty）"
                             "　⚠️ 本档未经 walk-forward 回测，依据待补")
                            if _WEAK_PENALTY_ON else
                            ("FACTOR_LAB.bottom 命中 ⇒ 仅写 signals「放量弱势」展示（V8_FACTOR_WEAK_PENALTY=0）"),
                })

        # 🆕🔴 因子在算法链里的**真实计分作用**落盘（读实现行为，不写死文案）
        _factor_chain_meta = {
            "update_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "score_formula": "final_score = strength + resonance*1.5 + sec_add - weak_penalty",
            "where": "algorithms/final_recommend.py :: 方案B 因子融合 + scored 计分",
            "gate": {
                "V8_FUSION_NOISE_FILTER": int(V8_FUSION_NOISE_FILTER),
                "regime_open": bool(_open_regime),
                "regime_coef_note": "非开仓期(_open_regime=False) 因子权重 ×0.3（仅对真计分的因子生效）",
            },
            "integrated": [
                {"key": "weak", "name": "放量弱势", "role": "扣分",
                 "scored": bool(_WEAK_PENALTY_ON), "adj": (-0.5 if _WEAK_PENALTY_ON else 0.0),
                 "where": "scored 计分：final_score −0.5（weak_penalty）", "n_hit": _n_weak_hit,
                 "evidence": "未回测",
                 "why": "FACTOR_LAB 异常换手率 **bottom 档**（放量=弱势）命中池内票即扣分"
                        "　⚠️ 三重问题（2026-09-18 实测取证）："
                        "① **无依据** —— 本档从未纳入 walk-forward 回测"
                        "（−2.21pp 是 **top 档**的实测值，bottom 档无同类证据），"
                        "属「凭空的惩罚」，与 P5 明文原则「反向档位无显著负 edge 不给惩罚」冲突；"
                        "② **设计上不相交** —— bottom 榜 = 极端放量股（abn 最大，弱势特征），"
                        "而候选池由选股策略产出、天然偏缩量强势，两集合语义相反；"
                        "实测 bottom ∩ pool = **0** ⇒ 本条几乎恒为 0 分；"
                        "③ **代码失配（已修）** —— _weak 集合原缺 .lstrip('.') 导致恒不匹配，"
                        "29 轮 / 1333 条候选命中 0 次"},
                {"key": "abn", "name": "异常换手率", "role": "仅展示", "scored": False, "adj": 0.0,
                 "where": "写 tags（V8_FUSION_NOISE_FILTER=1），不写 sources/source_scores", "n_hit": _n_at_hit,
                 "evidence": "薄样本(9 信号日 / 85 命中)",
                 "why": "实测边际 −2.21pp（负 alpha，命中 85 条）⇒ 整源剔除，不计共振/strength"},
                {"key": "roe", "name": "ROE_TTM", "role": "仅展示", "scored": False, "adj": 0.0,
                 "where": "写 signals「高ROE」+ reasons，不写 sources/source_scores", "n_hit": _n_roe_hit,
                 "evidence": "薄样本(9 信号日 / 89 命中)",
                 "why": "实测边际 +0.68pp（弱正，命中 89 条 ≈ 43.9% 覆盖率，无选择性）⇒ 不足与强源同权"},
            ],
            # 🔴 2026-09-18 主人问「扣分标准科学吗？别一开始就犯错」——本字段就是答案，**不许美化**：
            #   · 唯一真进 final_score 的因子动作（放量弱势 −0.5）**没有任何回测依据**；
            #   · 另两项的边际来自 **9 信号日薄样本**（阿狸咪实测），且按红线「绝不按短样本调权重」，
            #     故一律**不计分**，只做展示；
            #   · 真正经得起 walk-forward 检验的 K 线因子（amt60/turntrend，IR_OOS 0.877/0.872、
            #     7/8 年 Top 层胜率 >55%）在 **候选池层（generate_top10.py P5，+6/+3）**，不在本层。
            "evidence_note": ("计分依据分级："
                              "①「未回测」= 无任何样本外证据（放量弱势）；"
                              "②「薄样本」= 9 信号日实测边际，样本不足以定权重，故不计分（异常换手率/ROE_TTM/高手跟踪）；"
                              "③「walk-forward」= ≥4/5 年 OOS 检验通过才给分（候选池层 P5 的 amt60/turntrend，+6/+3）。"
                              "本层当前**没有任何因子持有第③级证据** ⇒ 除放量弱势外全部为 0 分，属**有意的保守**。"
                              "　🔴 结论（2026-09-18 主人问「扣分标准科学吗？别一开始就犯错」）："
                              "本层唯一记分的「放量弱势 −0.5」有**三重问题** —— ①无回测依据"
                              "（bottom 榜从未回测）；②设计上不相交（bottom=极端放量股 vs 候选池=缩量强势，"
                              "实测交集 0 ⇒ 几乎恒不触发）；③上游 _weak 集合曾因 norm_code 未剥点而恒失配"
                              "（29 轮命中 0 次，本补丁已修）。⇒ **因子在本层的实际计分影响 = 0**，"
                              "现状等于「全部只做标注」；要让它真正成为加减分项，须先补 walk-forward 回测"
                              "（流程见下方 ③ 待接入队列 / 明细见本页 🧪 因子审计卡）。"),

            "dedup_note": "因子只对**池内已有票**动作（_factor_in_pool 只查不建）⇒ 不产池、不决定谁能进榜",
        }
    else:
        _fl_degraded = True
        print("[warn] FACTOR_LAB.js 缺失/内容陈旧（update_time 或 data_date 未达 %s%s），"
              "等待 %d 次后仍不可用，跳过因子实验室方案B融合（降级推荐）"
              % (_today, ("（实际 data_date=%s）" % _fl_last_dd) if _fl_last_dd else "", 20))
        _factor_chain_meta = {
            "update_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "score_formula": "final_score = strength + resonance*1.5 + sec_add - weak_penalty",
            "where": "algorithms/final_recommend.py :: 方案B 因子融合",
            "gate": {"V8_FUSION_NOISE_FILTER": int(V8_FUSION_NOISE_FILTER),
                     "regime_open": bool(_open_regime)},
            "integrated": [],
            "skipped": True,
            "skip_reason": "本轮 FACTOR_LAB.js 缺失/内容陈旧 ⇒ 方案B 因子融合整体跳过（数据降级）",
        }

    # ── 第8.5节 高手共振（外部共振源之一：ima 高手强势股跟踪池）──
    # 与 v8 选股池 code 命中且 IMA 状态仍有效（非见顶/走弱）→ 独立外部共识信号，最终分 +1
    # 择时控权：非开仓期(_open_regime=False) 权重 ×0.3（弱加成）
    ima = load_js("IMA_STRONG_STOCK.js", "IMA_STRONG_STOCK")
    # 🔴 2026-09-11 A 类修复：原实现只判 `if ima:`，**从不校验 update_time** → 文件陈旧时
    #   仍照常给 +1.0 共振分（假成功）。
    _ima_ut = str((ima or {}).get("update_time") or "")[:10]
    # 🔴 2026-09-17 阿狸咪的工程师：**同类缺陷第二处**（与上面 FACTOR_LAB 同一个病因）。
    #   `update_time` 是**抓取时刻** —— 源笔记停更时它每天照变，只看它 = 放行假新鲜。
    #   实证（2026-09-17 主人截图质疑「都没变化啊」）：源分享页 document.title
    #   =「强势股跟踪日报 2026-09-02」、页内自述「更新时间：2026.09.02 15:41」、
    #   每行「最新交易日」= 2026-09-02；而卡片自 09-03 起每天忠实抓同一份静止笔记，
    #   价格字段指纹（207238cb37e4）连续 20 次抓取一字未改，update_time 却天天是「今天」
    #   ⇒ 本块会把 **09-02 的名单**当成今日共识给 +1.0 分（静默污染最终推荐）。
    #   修法（与抓取端同日补丁配套）：抓取端落 data_date/source_stale ⇒ 源侧停更即不参与
    #   共振加分；源恢复当天即自动回来。边界：老产物无这两个字段 ⇒ 不判停更（保守兼容），
    #   此时退回原有「update_time 非当日才跳过」的单口径判断。
    _ima_dd = str((ima or {}).get("data_date") or "").strip()
    if ima and ((ima or {}).get("source_stale") is True or (_ima_dd and _ima_dd != _today)):
        print(f"[warn] ⚠️ IMA_STRONG_STOCK 源侧停更（data_date={_ima_dd or '缺失'} / "
              f"update_time={_ima_ut or '缺失'}）→ 跳过高手共振融合（内容级判据，非抓取失败）")
        ima = {}
    elif ima and _ima_ut != _today:
        print(f"[warn] ⚠️ IMA_STRONG_STOCK 非当日（update_time={_ima_ut or '缺失'}）→ 跳过高手共振融合")
        ima = {}
    if ima:
        _ima_norm = {}
        for s in (ima.get("stocks") or []):
            _c = s.get("code")
            _st = (s.get("status") or "")
            if not _c:
                continue
            if _st in ("见顶", "走弱"):
                continue
            _ima_norm[norm_code(_c).lstrip('.')] = s
        _hit = 0
        for key, r in pool.items():
            _k = key.lstrip('.') if key.startswith('.') else key
            if _k in _ima_norm:
                sc = 1.0 * (1.0 if _open_regime else 0.3)
                # 🔴 2026-09-18 改动2a：高手跟踪 = 负 alpha 源（边际 −1.76pp / 13 命中 / 胜率 30.8 vs 22.5）
                #   这里原本给它 **固定 +1.0**，与四量终极同权 ⇒ 正是「数量优势淹没有效信号」的来源之一。
                #   ⇒ 整源剔除、不进 sources（不计共振/strength）；写 tags 仅作展示。
                if V8_FUSION_NOISE_FILTER:
                    r["tags"].append("高手跟踪")
                else:
                    r["sources"].append("高手跟踪")
                    r["source_scores"]["高手跟踪"] = round(sc, 2)
                r["signals"].append("高手共振")
                r["reasons"].append("高手强势股跟踪池共振（IMA 状态有效）")
                _hit += 1
        print("[ok] 高手共振命中 v8 池 %d 只" % _hit)
    else:
        print("[warn] IMA_STRONG_STOCK.js 缺失，跳过高手共振融合")

    # 🗑 2026-09-19 主人令：原第8.6节「强势突破共振」已随强势突破全站删除而移除。
    # ── 第8.7节 动量共识共振（2026-09-04 主人令接入：外部共振源 momentum_common_filter 无未来函数版）──
    # 与 v8 选股池 code 命中（candidates = S1/S2/S3 三重规则过滤后名单）→ 独立外部共识信号，最终分 +1
    # 择时控权：非开仓期(_open_regime=False) 权重 ×0.3（弱加成，与 IMA 同款）
    mf = load_js("MOMENTUM_FILTER.js", "MOMENTUM_FILTER")
    if mf:
        _mf_norm = {}
        for s in (mf.get("candidates") or []):
            _c = s.get("code")
            if not _c:
                continue
            _mf_norm[norm_code(_c).lstrip('.')] = s
        _hit = 0
        for key, r in pool.items():
            _k = key.lstrip('.') if key.startswith('.') else key
            if _k in _mf_norm:
                sc = 1.0 * (1.0 if _open_regime else 0.3)
                r["sources"].append("动量共识")
                r["source_scores"]["动量共识"] = round(sc, 2)
                r["signals"].append("动量共识")
                r["reasons"].append("动量共识筛选共振（无未来函数版）")
                _hit += 1
        print("[ok] 动量共识共振命中 v8 池 %d 只（候选 %d 只）" % (_hit, len(_mf_norm)))
    else:
        print("[warn] MOMENTUM_FILTER.js 缺失，跳过动量共识共振融合")

    # 补齐个股画像（行业/概念/名称）
    for key, r in pool.items():
        prof = profiles.get(key) or profiles.get(norm_code(key))
        if prof:
            if not r["name"] or r["name"] == r["code"]:
                r["name"] = fix_name(r["code"], prof.get("name"))
            if not r["industry"]:
                r["industry"] = prof.get("industry") or ""
            if prof.get("concepts"):
                r["concepts"] = list(set(r["concepts"] + prof.get("concepts")))

    # ── 价格真实性闸门（2026-09-11 A 类修复，替换原 CANDIDATE_QUOTES 兜底）──
    # 原兜底恒为空：data/CANDIDATE_QUOTES.js 在远端**根本不存在**（update_v8.py 的
    # candidate_quotes.json 映射被注释掉，理由「前端零引用」—— 但本文件是 Python 侧消费方，
    # grep 前端自然查不到），于是 ROE_TTM/高手跟踪单源票永远拿不到当日价，
    # safe_float(None) 再把 pct_chg 写成 0.00。现改为：
    #   ① 当日行情快照（STOCK_QUOTE.js，15:02 收盘快照，覆盖全 A）为准；
    #   ② 快照没覆盖到的票，一律 close/pct_chg = None（前端显示"待行情"），绝不拿旧价充数；
    #   ③ 同时把覆盖情况写进结果 meta，便于巡检发现"行情源整体缺失"。
    _qs = _quote_snapshot()
    _qs_map = _qs["map"]
    _px_hit = 0
    _px_keep = 0
    for key, r in pool.items():
        _q = _qs_map.get(key)
        if _q:
            r["close"] = _q["price"]
            r["pct_chg"] = _q["pct"]
            r["close_date"] = _qs["date"]
            r["close_source"] = _qs["source"]
            r["close_verified"] = True
            _px_hit += 1
        elif r.get("close_verified"):
            # 该票不在此快照覆盖内（如港股），但已由带当日日期的源价通过闸门 → 保留
            _px_keep += 1
        else:
            r["close"] = None
            r["pct_chg"] = None
            r["close_date"] = None
            r["close_source"] = None
            r["close_verified"] = False
    print(f"[行情] 价格闸门：快照命中 {_px_hit} 只，源价保真 {_px_keep} 只，"
          f"其余 {len(pool) - _px_hit - _px_keep} 只 close/pct_chg 写 null（来源={_qs['source']}）")

    # 计算板块加分 与 最终分
    scored = []
    for key, r in pool.items():
        if len(r["sources"]) == 0:
            continue
        # ── 质差股一票否决兜底（2026-09-07 主人令）：拦旁路源（CRDS/板块龙头等）──
        _vr = quality_veto(r["name"], _fq_by_digits.get(re.sub(r"\D", "", key), {}))
        if _vr:
            print(f"  ⛔ 最终推荐一票否决 {r['name']}({key}): {_vr}")
            continue
        sec_score, fresh_hits = sector_score_for(r, rel_set, abs_set, score_map)
        # 合并板块命中（板块龙头已写入部分命中）
        existing = {h["name"] for h in r["sector_hits"]}
        for h in fresh_hits:
            if h["name"] not in existing:
                r["sector_hits"].append(h)
                existing.add(h["name"])
        resonance = len(set(r["sources"]))
        strength = sum(r["source_scores"].values())
        # 2026-08-13 公平性修复：若已是板块龙头源，板块强度已在源分体现，
        # 此处只对非板块龙头票加全局板块加分，避免板块被双重计价。
        sec_add = 0.0 if "板块龙头" in r["sources"] else sec_score
        # 方案B 放量弱势扣分：被异常换手率 bottom 命中的票，若同时被其他源选中则 −0.5
        # 🔴🔴 2026-09-18 审计（主人问「扣分标准科学吗？别一开始就犯错」）——本行是全链**唯一**
        #   给因子记分的落点，但它有**两个**问题，且必须同时说清：
        #   ① **上行失配（已修）**：其数据源 `_weak` 集合原写 `{norm_code(x)}`，
        #      而 norm_code 不剥点（norm_code("sh.600479")==".600479"），pool 的 key 却是
        #      `norm_code(code).lstrip(".")`（=="600479"）⇒ `if key in _weak` **恒为 False**
        #      ⇒ 「放量弱势」29 轮从未写入 signals ⇒ **本行 −0.5 从未执行过一次**（死代码）。
        #   ② **依据缺失（未修，交主人）**：本档扣的是 FACTOR_LAB.bottom（放量榜），
        #      而该榜**从未纳入 walk-forward 回测** —— 有实测边际的是 **top 榜**（−2.21pp），
        #      两者不是同一集合。按 generate_top10.py P5 的明文原则
        #      「只加分不扣分：反向档位在 walk-forward 里无显著负 edge，**不给凭空的惩罚**」，
        #      本档属「凭空的惩罚」，**不应在无证据时给分**。
        #   ⇒ 处置原则：**不改数值**（改权重违反「绝不按短样本调权重」红线，且底部榜 vs 顶部榜
        #      谁负谁正尚无证据），改为**可开关 + 如实公示**：
        #        V8_FACTOR_WEAK_PENALTY=1（默认）⇒ 维持 −0.5，产物标 evidence="未回测"
        #        V8_FACTOR_WEAK_PENALTY=0        ⇒ 置 0（signals 照写、标签照展示，只是不减分）
        #      待 bottom 榜 walk-forward 回测出显著负 edge ⇒ 保留并加权；否则按 P5 原则降为「仅标注」。
        weak_penalty = (0.5 if _WEAK_PENALTY_ON else 0.0) if "放量弱势" in r.get("signals", []) else 0.0
        final_score = strength + resonance * 1.5 + sec_add - weak_penalty
        # 港股惩罚：用户主做 A 股，港股不应因多源共振天然霸榜
        if r.get("board") == "港股" or market_prefix(r.get("code", "")) == "hk":
            final_score -= HK_PENALTY
        scored.append({
            **r,
            "key": key,
            "resonance": resonance,
            "strength": round(strength, 2),
            "sector_score": sec_score,
            "sector_hits": r["sector_hits"],
            "final_score": round(final_score, 2),
        })

    # 排序：先按共振次数，再按综合分，再按源强度（多源共振优先）
    # 2026-08-13 公平性修复：排序第一关键字改为 final_score（分数优先），
    # 共振数/强度作次级 tie-breaker——公平计分后"最强"=分数最高，而非最多策略选中。
    scored.sort(key=lambda x: (x["final_score"], x["resonance"], x["strength"]), reverse=True)

    # ── Top3 选取（2026-08-11 主人令：公平竞争，谁好谁上）──
    # 之前 A 股硬保底逻辑：先灌 A 股 + 余下从全局高分（已被 HK_PENALTY 减分）填。
    #   实际效果：港股被歧视 + A 股被强保——两边都不公平。
    # 现改为：完全去掉 A 股硬保底（hard_a=0），直接取 scored 全局高分前 TOP_N 名。
    #   排序 key=(resonance, final_score, strength)——多源共振优先，分数次之，强度兜底。
    # 监控兜底：v8_health_check 检查 Top3 市场分布，全港股/全 A 股写 URGENT 告警（数据源异常）。
    a_shares = [s for s in scored if s.get("board") != "港股" and market_prefix(s.get("code", "")) != "hk"]
    hk_stocks = [s for s in scored if s.get("board") == "港股" or market_prefix(s.get("code", "")) == "hk"]
    top = []
    # 1) A 股硬保底 = 0（已关闭），直接进第 2 步
    hard_a = MIN_A_SHARES_IN_TOP  # 现 = 0，立即 break
    for s in a_shares:
        if len(top) >= _effective_top_n or len(top) >= hard_a:
            break
        top.append(s)
    # 2) 余下 slot 从 scored 全局高分填补（A 股 + 港股，按 (resonance, final_score, strength) 排序）
    top_codes = {t["key"] for t in top}
    for s in scored:
        if len(top) >= _effective_top_n:
            break
        if s["key"] in top_codes:
            continue
        top.append(s)
        top_codes.add(s["key"])
    # 3) 双轨排名（2026-08-13 主人令：共振最强 + 分数最强分开展示）
    #    top = 分数最强（公平计分后"绝对最强"）
    #    consensus_top = 共振最强（多策略交叉验证，抗单一策略失效）
    top.sort(key=lambda x: (x["final_score"], x["resonance"], x["strength"]), reverse=True)
    top = top[:_effective_top_n]
    # ── 共振最强副本（独立排序，不覆盖 top）──
    consensus_sorted = sorted(scored, key=lambda x: (x["resonance"], x["final_score"], x["strength"]), reverse=True)
    consensus_top = consensus_sorted[:_effective_top_n]
    # ── end 公平竞争 ──

    def horizon_for(sources, resonance=0, is_top=False):
        """horizon 判定
        is_top=True (top3/Allsite A/B档 持仓层):
          严格按 sources——主推"短线择时买入"，跨策略仍标"短线/中线共振"
        is_top=False (候选池/research 视角):
          仅含中线策略源(mid)归"中长线"；纯短线策略源保持"短线"（2026-08-13 公平性修复：标签须反映策略真实属性）
        2026-08-11 主人令：候选池的中长线列之前永远"暂无"——是判定过严。
        """
        short = {"四量终极"}  # 2026-09-03 主人令：大牛股猎手/板块龙头已下线
        mid = {"三重共识"}  # 2026-09-12 主人令：禁止为出数据放宽条件；mid 只保留真实中长线源「三重共识」
        defense = {"逆势龙头·精锐", "逆势龙头·进阶", "逆势龙头·观察"}
        srcs = set(sources)
        has_short = bool(srcs & short)
        has_mid = bool(srcs & mid)
        has_defense = bool(srcs & defense)
        if has_defense:
            return "中线防御"
        if is_top:
            # 严格按 sources 划分（top3 仍按短线择时语义）
            if has_short and has_mid: return "短线/中线共振"
            if has_short: return "短线"
            if has_mid: return "中长线"
            return "短线"
        # 候选池放宽：含中线策略源(mid)归中长线；纯短线共振≥2(多源交叉)也升中长线
        if has_mid:
            return "中长线"
        if has_short and resonance >= 2:
            return "中长线"
        return "短线"

    # 清理输出字段
    out_stocks = []
    for s in top:
        code = norm_code(s["code"]).lstrip('.')  # 2026-09-03 主人令：剥点（与 R1 ensure 对齐）
        # market 统一为交易所前缀；原始 s["market"] 可能是中文描述，不可靠
        market = market_prefix(code)
        board = s["board"] or board_from_code(code)
        close = num_or_none(s.get("close"))
        stop = s["stop_loss"]
        target = s["target_price"]
        rr = s["risk_reward"]
        # 若缺少精确 stop/target，用 fixedP10/rrK1.5 兜底
        if close and not stop:
            pct = 0.90 if board in ("创业板", "科创板") else 0.93
            stop = round(close * pct, 2)
            target = round(close * (1 + (1 - pct) * 1.5), 2)
            rr = 1.5
        # 关联板块资金：取命中板块涨幅前 4
        sector_fund = []
        for h in (s.get("sector_hits") or [])[:4]:
            if "关键词" in h["name"]:
                continue
            sector_fund.append({
                "name": h["name"],
                "pct_5d": round(h["pct_5d"], 2),
                "relative_5d": round(h["relative_5d"], 2),
                "strong": h["strong"],
            })
        # 入选日：取各源最早日期，无则使用当前 update_time
        enter_dates = [d for d in (s.get("enter_dates") or []) if d]
        enter_date = min(enter_dates) if enter_dates else datetime.now().strftime("%Y-%m-%d")
        signals = sorted(set(s.get("signals") or []))
        if not signals:
            # 兜底：根据来源生成一句信号
            signals = [f"{src}共振" for src in sorted(set(s["sources"]))]

        # ---- 回测 & 跟踪（当前 Top3 股票的历史表现与入选后状态） ----
        alerts = tt_alerts.get(code, [])

        if close:
            # 没有历史跟踪记录：以今日入选价 = 当前价展示
            tracking = {
                "entry_date": enter_date,
                "entry_price": round(close, 2),
                "latest_price": round(close, 2),
                "return_pct": 0.0,
                "hold_days": 1,
                "exit_type": "hold",
                "note": "今日新入选，自动开始跟踪",
            }
        else:
            tracking = {"entry_date": enter_date, "entry_price": None, "latest_price": None, "return_pct": None, "hold_days": 1, "exit_type": "hold", "note": "等待行情数据开始跟踪"}

        if alerts:
            tracking["alerts"] = alerts[:3]

        out_stocks.append({
            "rank": len(out_stocks) + 1,
            "code": code,
            "name": fix_name(code, s["name"]),
            "market": market,
            "board": board,
            "horizon": horizon_for(s["sources"], s.get("resonance",0), is_top=True),
            "close": round(close, 2) if close else None,
            "close_date": s.get("close_date"),
            "close_source": s.get("close_source"),
            "close_verified": bool(s.get("close_verified")),
            "pct_chg": _num2(s.get("pct_chg")),
            "stop_loss": round(safe_float(stop), 2) if stop else None,
            "target_price": round(safe_float(target), 2) if target else None,
            "risk_reward": round(safe_float(rr), 2) if rr else None,
            "support": round(safe_float(s.get("support")), 2) if s.get("support") else None,
            "resistance": round(safe_float(s.get("resistance")), 2) if s.get("resistance") else None,
            "atr": round(safe_float(s.get("atr")), 2) if s.get("atr") else None,
            "sources": sorted(set(s["sources"])),
            "source_scores": s["source_scores"],
            "resonance": s["resonance"],
            "strength": s["strength"],
            "sector_score": s["sector_score"],
            "sector_hits": s["sector_hits"],
            "sector_fund": sector_fund,
            "final_score": s["final_score"],
            "buy_score": s["final_score"],
            "enter_date": enter_date,
            "signals": signals[:8],
            "_60m_resonance": s.get("_60m_resonance", False),
            "reason": "；".join(s["reasons"][:3]),
            "industry": s["industry"],
            "concepts": s["concepts"][:8],  # 2026-09-03 主人令：6→8
            "tracking": tracking,
            "action": _action_label,
            "market_regime": _regime_name,
        })

    # ── 共振最强列表（双轨排名第二轨）──
    consensus_stocks = []
    for s in consensus_top:
        code = s["key"]
        # 去重：已在分数最强中的不再重复构建完整数据
        # 但 consensus_stocks 需要独立 rank 和排序语义，所以仍完整构建
        market = {"sh": "沪市", "sz": "深市", "bj": "北交所", "hk": "港股"}.get((s["market"] or market_prefix(code)).lower(), s["market"] or market_prefix(code))
        board = s["board"] or board_from_code(code, s["market"])
        close = num_or_none(s.get("close"))   # 价格真实性闸门：缺失写 None，不伪造 0.0
        stop = s.get("stop_loss")
        target = s.get("target_price")
        rr = s.get("risk_reward")
        enter_date = s.get("enter_dates")[0] if s.get("enter_dates") else ""
        alerts = [a for a in (s.get("alerts") or []) if a not in ("已入库",)]
        if enter_date and close:
            tracking = {
                "entry_date": enter_date,
                "entry_price": round(close, 2),
                "latest_price": round(close, 2),
                "return_pct": 0.0,
                "hold_days": 1,
                "exit_type": "hold",
                "note": "今日新入选，自动开始跟踪",
            }
        else:
            tracking = {"entry_date": enter_date, "entry_price": None, "latest_price": None, "return_pct": None, "hold_days": 1, "exit_type": "hold", "note": "等待行情数据开始跟踪"}
        if alerts:
            tracking["alerts"] = alerts[:3]
        consensus_stocks.append({
            "rank": len(consensus_stocks) + 1,
            "code": code,
            "name": fix_name(code, s["name"]),
            "market": market,
            "board": board,
            "horizon": horizon_for(s["sources"], s.get("resonance",0), is_top=True),
            "close": round(close, 2) if close else None,
            "close_date": s.get("close_date"),
            "close_source": s.get("close_source"),
            "close_verified": bool(s.get("close_verified")),
            "pct_chg": _num2(s.get("pct_chg")),
            "stop_loss": round(safe_float(stop), 2) if stop else None,
            "target_price": round(safe_float(target), 2) if target else None,
            "risk_reward": round(safe_float(rr), 2) if rr else None,
            "support": round(safe_float(s.get("support")), 2) if s.get("support") else None,
            "resistance": round(safe_float(s.get("resistance")), 2) if s.get("resistance") else None,
            "atr": round(safe_float(s.get("atr")), 2) if s.get("atr") else None,
            "sources": sorted(set(s["sources"])),
            "source_scores": s["source_scores"],
            "resonance": s["resonance"],
            "strength": s["strength"],
            "final_score": s["final_score"],
            "sector_score": s.get("sector_score", 0),
            "sector_hits": s.get("sector_hits", []),
            "enter_date": enter_date,
            "signals": s["signals"][:8],
            "_60m_resonance": s.get("_60m_resonance", False),
            "reason": "；".join(s["reasons"][:3]),
            "industry": s["industry"],
            "concepts": s["concepts"][:8],  # 2026-09-03 主人令：6→8
            "tracking": tracking,
            "action": _action_label,
            "market_regime": _regime_name,
        })
    # ── end 双轨 ──

    # 🔴🔴 2026-09-18 主人令：「因子只是加分减分项，不是选股策略」——
    #   此处原有一段 `_factor_extra`：把 30 名之外带因子标签的票**强制纳入候选池**
    #   （其原注释自述"否则方案B不可见"）⇒ 这是「因子参与选股」的第二处 ——
    #   因子不仅能决定谁进池，还能把已排在池外的票**捞回池内**。已**整体删除**。
    #   现状：候选池 = scored[:30]，纯由各源得分决定；因子只在**得分阶段**加减分
    #   （命中 ⇒ source_scores 加权 / 放量弱势 ⇒ −0.5），不再影响**谁能进池**。
    _top30 = scored[:30]

    # 🚪 数据降级标记（2026-09-12 主人令·一劳永逸）：
    #   上游（A 采集批）长坏 >2 交易日时，批次闸门会降级放行 B 批，并把
    #   DEGRADED_UPSTREAM=1 / degrade_lag_days=N 经 workflow env 传到这里。
    #   **必须写进产物并透到前端** —— 主人拍板原话：「宁可给带降级标记的结果，
    #   也不要永久空白（标记可见就不算假成功）」。没有这行，降级放行出来的
    #   最终推荐会和正常结果长得一模一样 ⇒ 又变成一种新的假成功。
    # 🔴 2026-09-17 阿狸咪的工程师：**因子内容级降级也计入 data_degraded**。
    #   原先只认 DEGRADED_UPSTREAM 环境变量 ⇒「因子用昨日数据算今日推荐」这件事
    #   在前端/看板上**完全不可见**（09-17 事故：04:49 那版 data_date=09-16 被当新鲜）。
    #   主人拍板原话：「宁可给带降级标记的结果，也不要永久空白（标记可见就不算假成功）」
    #   —— 因子降级同理，必须显形。
    # 🔴 2026-09-18 改动1：信号 edge 动态加载失败亦视为降级（不许静默用写死值）
    _degraded = ((str(os.environ.get("DEGRADED_UPSTREAM", "")).strip() == "1")
                 or _fl_degraded or SIGNAL_EDGE_DEGRADED)
    _degrade_lag = str(os.environ.get("DEGRADE_LAG_DAYS", "")).strip()

    # 🔴 2026-09-18 改动1：在产物里固化「本次用的是哪一版 edge」——
    #   改动4 的最终推荐回测要靠它复现历史打分（否则回测用的是今天的分不是当天的分）。
    _signal_edge_meta = {
        "source": SIGNAL_EDGE_SOURCE,
        "degraded": bool(SIGNAL_EDGE_DEGRADED),
        "effective": {k: round(float(v), 4) for k, v in SIGNAL_EDGE.items()},
        "hardcoded_default": dict(SIGNAL_EDGE_DEFAULT),
        "n_on10": dict(SIGNAL_N),
        "consistent": dict(SIGNAL_CONSISTENT),
        "loaded": dict(SIGNAL_EDGE_META or {}),
        # 🔴 2026-09-18 改动12：alpha 精选运行时真相（回测复现/看板核对用）
        "alpha_select": {
            "enabled": bool(V8_FUSION_ALPHA_SELECT),
            "skipped_no_positive_edge": int(_alpha_skipped),
        },
    }

    result = {
        "update_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "crisis_score": round(crisis_score, 1),
        "crisis_high": crisis_high,
        "crisis_note": "逆势龙头已并入" if crisis_high else "危机雷达未达高位，逆势龙头暂不并入",
        "total_candidates": len(scored),
        "top_n": _effective_top_n,
        "data_degraded": _degraded,
        # 🔴 2026-09-18 改动1：信号 edge 的运行时真相（来源/生效值/降级/样本量）
        "signal_edge": _signal_edge_meta,
        "degrade_note": (
            f"⚠️ 数据降级：上游采集（A 批）已落后 {_degrade_lag or '?'} 个交易日（阈值 2），"
            f"本结果为「降级放行」产物 —— 排序与信号有效，但底层行情可能不是最新交易日。"
            f"请勿据此判断当日市场状态。" if _degraded else None
        ),
        "market_regime": {
            "date": _regime_date,
            "regime": _regime_name,
            "open": _open_regime,
            "ok": _regime_ok,
            "reason": _regime_reason,
            "note": "grind/panic=可开仓(正常推)；stabilize/rebound=历史回测≥3共振负期望，应观察/少推；"
                    "ok=false 表示 regime 取数失败已按保守处置（regime=null、不推满仓）",
        },
        "price_source": {
            "date": _qs["date"],
            "source": _qs["source"],
            "covered": _px_hit,
            "total": len(pool),
            "note": "价格唯一权威来源（当日有效快照）；未覆盖的票 close/pct_chg 为 null，不伪造 0.00%",
        },
        "strong_sectors": sorted(rel_set)[:20],
        "stocks": out_stocks,
        "consensus_stocks": consensus_stocks,  # 2026-08-13 双轨：共振最强排名（独立于 stocks 分数最强）
        "all_candidates": [
            {
                "code": x["key"],
                "name": _resolve_name(x["key"], x["name"]),
                "market": {"sh": "沪市", "sz": "深市", "bj": "北交所", "hk": "港股"}.get((x["market"] or market_prefix(x["key"])).lower(), x["market"] or market_prefix(x["key"])),
                "board": x["board"] or board_from_code(x["key"], x["market"]),
                "horizon": horizon_for(x["sources"], x.get("resonance",0)),
                "close": round(num_or_none(x.get("close")), 2) if num_or_none(x.get("close")) else None,
                "close_date": x.get("close_date"),
                "close_verified": bool(x.get("close_verified")),
                "pct_chg": _num2(x.get("pct_chg")),
                "final_score": x["final_score"],
                "resonance": x["resonance"],
                "sources": sorted(set(x["sources"])),
                "signals": sorted(set(x.get("signals") or []))[:6],
                "industry": x.get("industry", ""),
                "concepts": x.get("concepts", [])[:8],  # 2026-09-03 主人令：6→8
                "enter_date": (min([d for d in x.get("enter_dates", []) if d]) if x.get("enter_dates") else None) or datetime.now().strftime("%Y-%m-%d"),
                "stop_loss": round(safe_float(x.get("stop_loss")), 2) if x.get("stop_loss") is not None else None,
                "target_price": round(safe_float(x.get("target_price")), 2) if x.get("target_price") is not None else None,
                "risk_reward": round(safe_float(x.get("risk_reward")), 2) if x.get("risk_reward") is not None else None,
                "support": round(safe_float(x.get("support")), 2) if x.get("support") is not None else None,
                "resistance": round(safe_float(x.get("resistance")), 2) if x.get("resistance") is not None else None,
                # 🆕 2026-09-18：本票被哪些因子动作触及（[] = 未触及）；adj 严格照实现，仅展示的为 0
                "factor_actions": x.get("factor_actions") or [],
            }
            for x in _top30
        ],
        # 🆕🔴 2026-09-18 主人令：因子实验室卡的「已接入因子 / 当日加减分排列」两段数据源。
        #   factor_chain = 因子清单 + 本日命中统计（读实现行为）
        #   factor_trace = 当日**全部**被因子触及的池内票（含 final_score），供「知道逻辑有没有出错」
        "factor_chain": _factor_chain_meta,
        "factor_trace": [
            {
                "code": x["key"],
                "name": _resolve_name(x["key"], x["name"]),
                "final_score": x["final_score"],
                "resonance": x["resonance"],
                "sources": sorted(set(x["sources"])),
                "actions": x.get("factor_actions") or [],
                "adj_total": round(sum(float(a.get("adj") or 0.0) for a in (x.get("factor_actions") or [])), 2),
            }
            for x in scored if x.get("factor_actions")
        ],
    }

    # 写 raw_data json
    out_path = os.path.join(RAW, "final_recommend.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(f"[ok] {out_path}  top3={len(out_stocks)} total_candidates={len(scored)}")

    # 写 data js
    js_path = os.path.join(DATA, "FINAL_RECOMMEND_DATA.js")
    js = "window.FINAL_RECOMMEND_DATA = " + json.dumps(result, ensure_ascii=False, indent=2) + ";"
    with open(js_path, "w", encoding="utf-8") as f:
        f.write(js)
    print(f"[ok] {js_path}")

    # 🗂 历史归档（all_site_backtest.py 已删除）：按 update_time 日期落盘 raw_data/history
    # 与 calc_crds.py 同源思路——只有落盘「每日 dated 快照」回测才有过去信号日可算前向收益。
    try:
        _dt = (result.get("update_time") or "")[:10].replace("-", "")
        if len(_dt) == 8 and _dt.isdigit():
            _hist_dir = os.path.join(RAW, "history")
            os.makedirs(_hist_dir, exist_ok=True)
            _hist_path = os.path.join(_hist_dir, f"final_recommend_{_dt}.json")
            with open(_hist_path, "w", encoding="utf-8") as f:
                json.dump(result, f, ensure_ascii=False, indent=2)
            print(f"[ok] history archive {_hist_path}")
    except Exception as e:
        print(f"[warn] final_recommend history archive skipped: {e}")

    # 打印 top3
    for s in out_stocks:
        print(f"  #{s['rank']} {s['name']}({s['code']}) 综合{s['final_score']} 共振{s['resonance']} 板块+{s['sector_score']} 来源{','.join(s['sources'])}")


if __name__ == "__main__":
    main()
