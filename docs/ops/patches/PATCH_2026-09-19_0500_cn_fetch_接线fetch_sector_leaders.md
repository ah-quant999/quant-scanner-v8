# 补丁：`v8_cn_fetch_cloud.yml` 接入 `fetch_sector_leaders.py`（板块龙头股字典随板块相对强度同轮生成）

- **出件**：2026-09-19 05:00（北京时间）· 阿狸咪的工程师
- **目标文件**：`.github/workflows/v8_cn_fetch_cloud.yml`（1040 行，LF，当前 tip `fcc24a6dd6`）
- **为什么需要小九**：阿狸咪的 PAT 无 `workflow` scope，改 `.github/workflows/` 必 403。
- **背景**：`scripts/fetch_sector_leaders.py` 自 09-17 建卡以来**从未接入任何自动链** —— 产物 `data/SECTOR_LEADERS.js` 全靠手动提交（最后 `dedeebbd7c` 09-18 20:12）。而它依赖的 `data/SECTOR_RS.js` 每 20 分~1 小时被 cn fetch 刷新 ⇒ 字典必然滞后。前端已于 `fcc24a6dd6` 改为「板块清单/阶段/涨跌幅现算自 SECTOR_RS，字典仅提供龙头股」，故**两卡一致性已不依赖本补丁**；本补丁解决的是**龙头股个股列表的新鲜度**。

## 1 插入位置（精确锚点）

在 **`id: soft_13`（🩺 刷新 HEALTH_CHECK.js）整步结束之后**、**`# 🛡 2026-08-27 主人令（盘中更新全断根因修复）` 注释之前**插入。

即：原 L639 `          fi` 之后空行、原 L641 注释之前。

**为什么必须在 `update_v8` 之后**：`fetch_sector_leaders.py` 读的是 `data/SECTOR_RS.js`，而该文件由 `update_v8.py` 从 `out/sector_rs.json` 转换产出（`fetch_sector_rs.py` 写的是 `BASE/../out/sector_rs.json`，**不是** `data/`）。若放在 `fetch_sector_rs.py` 那一步里调用，读到的会是**上一轮**的 RS，字典永远慢一拍。

**为什么必须在 `soft_14`（📤 推送重建的 data/*.js）之前**：该步用 `DATA_MANIFEST=$(git status --porcelain data/ | ...)` 自动收集所有变更的 data 文件 ⇒ **本步产出的 `data/SECTOR_LEADERS.js` 会被自动推送，无需新增推送逻辑**。

## 2 插入内容（原样可用）

```yaml
      # 🐲 2026-09-19 阿狸咪的工程师：板块龙头股字典随「板块相对强度」同轮生成
      #   （主人令「主升/启动 板块·龙头股 要跟着 板块资金趋势 变动而变动，对应清楚」）
      #   位置刻意放在 update_v8 之后（data/SECTOR_RS.js 已是本轮新值）+ soft_14 推送 data 之前
      #   ⇒ 本步产出的 data/SECTOR_LEADERS.js 会被 soft_14 的 `git status --porcelain data/`
      #     自动纳入 PUSH_FILES 一并推送，无需新增推送逻辑。
      #   上游：scripts/fetch_sector_leaders.py（读 data/SECTOR_RS.js 判主升/启动，
      #   再抓东财板块成分股取当日涨幅前 5；人工别名表覆盖「塑料制品/橡胶制品/汽车服务及其他」）。
      - name: "🐲 板块龙头股字典（SECTOR_LEADERS，仅 post_close）"
        id: soft_13b
        if: steps.cat.outputs.category == 'post_close'
        continue-on-error: true
        shell: bash
        run: |
          python scripts/fetch_sector_leaders.py

          # 🔴 与其它 soft_* 步同规：不阻断 job，但失败必须显式告警（防静默失败）
          _v8_rc=$?
          if [ "$_v8_rc" != "0" ]; then
            echo "::error title=v8-softfail:soft_13b(exit=$_v8_rc)::🐲 板块龙头股字典生成软失败（退出码 $_v8_rc）。前端「主升/启动 板块·龙头股」卡将沿用上轮龙头股列表 —— 板块清单与涨跌幅不受影响（与「板块资金趋势」卡同源 SECTOR_RS）。"
            exit 1
          fi
```

## 3 应用后验收命令

```bash
# ① 语法自证
python -c "import yaml,sys; yaml.safe_load(open('.github/workflows/v8_cn_fetch_cloud.yml',encoding='utf-8')); print('YAML OK')" \
  || echo "（仓库无 PyYAML 时改为）python -c \"import json,subprocess;print('跳过')\""

# ② 结构自证：新 step 存在且位置在 soft_13 之后、soft_14 之前
python - <<'PY'
import io, re
s = io.open('.github/workflows/v8_cn_fetch_cloud.yml', encoding='utf-8').read()
i13 = s.index('id: soft_13'); i13b = s.index('id: soft_13b'); i14 = s.index('id: soft_14')
assert i13 < i13b < i14, (i13, i13b, i14)
assert 'python scripts/fetch_sector_leaders.py' in s
print('结构 OK：soft_13 < soft_13b < soft_14，调用已在位')
PY

# ③ 跑完一轮 post_close 后，看该 step 日志应有：
#    [HH:MM:SS] source SECTOR_RS: update_time=... data_date=... sectors=90
#    [HH:MM:SS] em boards: exact=496 norm=456
#    [HH:MM:SS] OK 主升(3/3) 启动(39/39) js_bytes=... leaders_fail=0 no_match=0
#    期望：主升(x/x) 启动(y/y) 两数相等（= 本轮 SECTOR_RS 的主升/启动板基数）
```

## 4 回滚

删除 `- name: "🐲 板块龙头股字典（SECTOR_LEADERS，仅 post_close）"` 整段（L 至 `fi`）即可。该步 `continue-on-error: true`，**即使保留也不会阻断 job**。

## 5 附带说明（同批另两个待办，见交接件）

1. **P0**：`v8_build_deploy.yml` 重试路径「备份 → `git reset --hard FETCH_HEAD` → 盖回旧 index.html」的条件在 CI 中恒真 ⇒ 会静默覆盖他人改动（补丁件 `docs/ops/patches/PATCH_2026-09-18_2220_*.md`）。
2. **P1（本次新发现）**：`algorithms/fetch_sector_rs.py` 的 `data_date = now_str[:10]` 用**生成日**当交易日期 —— 周六产出 `data_date=2026-09-19`；且 09-18 19:51 那轮承载 09-17 的 K 线却标 09-18（无法自证陈旧）。详见审计件 §5。

---

*本补丁仅涉调度接线，不改任何算法口径。*
