#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""新周期判定卡（雪球 @白河愁博士）盘前日频流水线助手。

为什么需要它：
  · 本仓工作树在部分机器上长期落后，`git fetch` 又常被沙箱/网络环境打死 ⇒ 一律走 GitHub API：
    sync = 按 raw 通道拉取当日所需文件；push = Git Data API 建 blob/tree/commit 后 fast-forward 推 main。
  · 抓取依赖真实浏览器（雪球主域有阿里云 WAF + SPA），只能在本机 Windows 的 Chrome/Edge headless 跑。

典型日频用法（一条命令拿到当期原文，供 AI 出解析）：
    python scripts/baihechou_daily.py prep
  → sync 最新脚本/产物 → 抓取原文 → 打印当期主帖与回复全文
  然后 AI 写解析 JSON，注入并推送：
    python scripts/set_baihechou_analysis.py analysis.json
    python scripts/baihechou_daily.py push "feat(新周期判定): 09-16 盘前原文 + 当期 AI 解析"

子命令：
    sync            只同步（fetcher / 注入器 / 产物）
    fetch           只抓原文（调用 scripts/fetch_baihechou_v8.py）
    show            只打印当期原文（读 raw_data/baihechou_posts.json）
    prep            sync + fetch + show（日频主路径）
    push "<msg>"    推产物（带防倒退守卫）
    status          对比远端/本地 update_time

环境变量：
    V8_REPO_DIR     仓库根目录（默认 E:\\workspace\\stock-scanner）
    V8_GH_PAT_FILE  PAT 单点文件（默认 ~/.workbuddy/v8_gh_pat）
    V8_AGENT_NAME   署名（默认 阿狸咪的工程师）

铁律：
  · push 前必重取远端真值 + 防倒退：远端 update_time 比本地新 ⇒ 拒推（禁覆盖他人新鲜产物）。
  · 任何失败如实打印原因并返回非 0，绝不假成功。
"""
import base64
import gzip
import json
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

REPO = 'ah-quant999/quant-scanner-v8'
API = 'https://api.github.com/repos/' + REPO

REPO_DIR = os.environ.get('V8_REPO_DIR') or r'E:\workspace\stock-scanner'
PAT_FILE = os.environ.get('V8_GH_PAT_FILE') or os.path.join(
    os.path.expanduser('~'), '.workbuddy', 'v8_gh_pat')
AGENT = os.environ.get('V8_AGENT_NAME') or '阿狸咪的工程师'

SYNC_FILES = [
    'scripts/fetch_baihechou_v8.py',
    'scripts/set_baihechou_analysis.py',
]
PUSH_FILES = [
    'data/BAIHECHOU_MACRO.js',
    'raw_data/baihechou_posts.json',
]
RAW_JSON = os.path.join(REPO_DIR, 'raw_data', 'baihechou_posts.json')


def pat():
    with open(PAT_FILE, 'r', encoding='utf-8') as f:
        return f.read().strip()


def req(url, method='GET', body=None, tries=4, raw=False, token=None):
    last = None
    for i in range(tries):
        try:
            data = json.dumps(body).encode('utf-8') if body is not None else None
            h = {
                'Authorization': 'Bearer ' + (token or pat()),
                'Accept': 'application/vnd.github+json',
                'User-Agent': 'v8-baihechou-daily',
                'Accept-Encoding': 'gzip',
                'Cache-Control': 'no-cache',
            }
            if data:
                h['Content-Type'] = 'application/json'
            r = urllib.request.Request(url, data=data, headers=h, method=method)
            with urllib.request.urlopen(r, timeout=180) as resp:
                b = resp.read()
                if resp.headers.get('Content-Encoding') == 'gzip':
                    b = gzip.decompress(b)
            return b if raw else json.loads(b.decode('utf-8'))
        except urllib.error.HTTPError as e:
            d = ''
            try:
                d = e.read().decode('utf-8')[:200]
            except Exception:
                pass
            last = 'HTTP %s %s %s' % (e.code, e.reason, d)
            if e.code in (401, 403, 404, 422):
                break
            time.sleep(2 + i * 3)
        except Exception as e:
            last = e
            time.sleep(2 + i * 3)
    print('  [FAIL] %s %s -> %s' % (method, url, last))
    return None


def tip():
    c = req(API + '/commits/main')
    return c['sha'] if c else None


def _ut_of(text):
    """从 JS/JSON 文本里取 update_time（YYYY-MM-DD HH:MM:SS）"""
    m = re.search(r'"update_time"\s*:\s*"([^"]+)"', text)
    return m.group(1) if m else ''


def _local(p):
    return os.path.join(REPO_DIR, p.replace('/', os.sep))


# ────────────────────────── 子命令 ──────────────────────────

def cmd_sync():
    sha = tip()
    if not sha:
        return 1
    print('远端 tip = %s' % sha)
    ok = 0
    todo = SYNC_FILES + PUSH_FILES
    for p in todo:
        u = 'https://raw.githubusercontent.com/%s/%s/%s' % (REPO, sha, urllib.parse.quote(p))
        b = req(u, raw=True)
        if b is None:
            print('  [x] %s 拉取失败' % p)
            continue
        dst = _local(p)
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        with open(dst, 'wb') as f:
            f.write(b)
        print('  [v] %-42s %8d bytes' % (p, len(b)))
        ok += 1
    print('同步完成 %d/%d' % (ok, len(todo)))
    return 0 if ok == len(todo) else 2


def cmd_fetch():
    f = _local('scripts/fetch_baihechou_v8.py')
    if not os.path.exists(f):
        print('  [x] 缺 %s（先跑 sync）' % f)
        return 2
    r = subprocess.run([sys.executable, f], cwd=REPO_DIR, capture_output=True, text=True,
                       encoding='utf-8', errors='replace')
    out = (r.stdout or '') + (r.stderr or '')
    print(out.rstrip())
    if r.returncode != 0:
        print('  [x] 抓取失败（exit %d）—— 产物保持不动，不做任何写操作' % r.returncode)
        return 3
    return 0


def cmd_show():
    if not os.path.exists(RAW_JSON):
        print('  [x] 缺 %s（先跑 fetch）' % RAW_JSON)
        return 2
    with open(RAW_JSON, 'r', encoding='utf-8') as f:
        d = json.load(f)
    ps = d.get('posts') or []
    if not ps:
        print('  [x] 池内 0 条 —— 不产出解析（禁空解析冒充）')
        return 3
    print('=' * 70)
    print('当期原文 · 池内 %d 条 · 抓取于 %s' % (len(ps), d.get('update_time')))
    print('=' * 70)
    n_main = n_rep = 0
    for p in ps:
        if p.get('is_reply'):
            n_rep += 1
        else:
            n_main += 1
    print('\n── 主帖 %d 条（按时间倒序）──' % n_main)
    for p in ps:
        if p.get('is_reply'):
            continue
        print('\n[%s] id=%s%s' % (p.get('time') or p.get('rel') or '?', p.get('id'),
                                 '  ★置顶' if p.get('pinned') else ''))
        if (p.get('title') or '').strip():
            print('  标题：%s' % p['title'].strip())
        print('  %s' % (p.get('text') or '').strip()[:1500])
        if p.get('img'):
            print('  [配图] %s' % p['img'])
    print('\n── 回复 %d 条 ──' % n_rep)
    for p in ps:
        if not p.get('is_reply'):
            continue
        t = (p.get('text') or '').strip()
        if not t:
            continue
        print('\n[%s] %s' % (p.get('time') or p.get('rel') or '?', t[:800]))
    print('\n' + '=' * 70)
    print('下一步：据以上原文写解析 JSON（verdict + sections[market/sector/position]'
          ' 各含 tag/tension/delta/align + window + generated_at + by）')
    print('        然后 python scripts/set_baihechou_analysis.py <json> && push')
    print('⚠️ 无新增论点时如实写「边际变化小」，禁为凑字数编造')
    return 0


def cmd_status():
    sha = tip()
    if not sha:
        return 1
    print('远端 tip = %s' % sha)
    for p in PUSH_FILES:
        rc = req(API + '/contents/%s?ref=%s' % (urllib.parse.quote(p), sha))
        r_ut = l_ut = '?'
        if rc and rc.get('download_url'):
            rb = req(rc['download_url'], raw=True)
            if rb:
                r_ut = _ut_of(rb.decode('utf-8', 'replace')) or '?'
        lp = _local(p)
        if os.path.exists(lp):
            l_ut = _ut_of(open(lp, 'rb').read().decode('utf-8', 'replace')) or '?'
        else:
            l_ut = '(缺)'
        flag = ''
        if r_ut != '?' and l_ut not in ('?', '(缺)'):
            flag = '  本地领先✅' if l_ut > r_ut else ('  远端领先（勿推）' if r_ut > l_ut else '  一致')
        print('  %-38s 远端=%s / 本地=%s%s' % (p, r_ut, l_ut, flag))
    return 0


def cmd_push(msg):
    sha = tip()
    if not sha:
        return 1
    tipc = req(API + '/commits/main')
    tree = tipc['commit']['tree']['sha']
    print('推前基线（重取）= %s' % sha)

    blobs = {}
    for p in PUSH_FILES:
        local = _local(p)
        if not os.path.exists(local):
            print('  [x] 本地缺 %s' % p)
            return 2
        lb = open(local, 'rb').read()
        lt = lb.decode('utf-8', 'replace')
        rc = req(API + '/contents/%s?ref=%s' % (urllib.parse.quote(p), sha))
        if rc:
            rb = req(rc['download_url'], raw=True) if rc.get('download_url') else None
            if rb is None:
                rb = req('https://raw.githubusercontent.com/%s/%s/%s'
                         % (REPO, sha, urllib.parse.quote(p)), raw=True)
            if rb:
                r_ut, l_ut = _ut_of(rb.decode('utf-8', 'replace')), _ut_of(lt)
                print('  %-38s 远端 update_time=%s / 本地=%s' % (p, r_ut or '?', l_ut or '?'))
                if r_ut and l_ut and r_ut > l_ut:
                    print('  🔴 防倒退：远端产物比本地新 ⇒ 拒推本文件（避免覆盖他人新鲜产物）')
                    return 3
        b = req(API + '/git/blobs', 'POST',
                {'content': base64.b64encode(lb).decode('ascii'), 'encoding': 'base64'})
        if not b:
            return 2
        blobs[p] = b['sha']

    tr = req(API + '/git/trees', 'POST', {
        'base_tree': tree,
        'tree': [{'path': p, 'mode': '100644', 'type': 'blob', 'sha': s} for p, s in blobs.items()],
    })
    if not tr:
        return 2
    cm = req(API + '/git/commits', 'POST', {
        'message': msg,
        'tree': tr['sha'],
        'parents': [sha],
        'author': {'name': AGENT, 'email': '2814546@qq.com'},
        'committer': {'name': AGENT, 'email': '2814546@qq.com'},
    })
    if not cm:
        return 2
    upd = req(API + '/git/refs/heads/main', 'PATCH', {'sha': cm['sha'], 'force': False})
    if upd and upd.get('object', {}).get('sha') == cm['sha']:
        print('  ✅ PUSHED %s' % cm['sha'])
        return 0
    print('  ⚠ ref 未更新（基线被抢推），请重跑一次 push（会重取基线）')
    return 4


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return 1
    cmd = sys.argv[1]
    if cmd == 'sync':
        return cmd_sync()
    if cmd == 'fetch':
        return cmd_fetch()
    if cmd == 'show':
        return cmd_show()
    if cmd == 'status':
        return cmd_status()
    if cmd == 'prep':
        rc = cmd_sync()
        if rc not in (0,):
            print('  ⚠ sync 未全成功（rc=%d），继续尝试抓取' % rc)
        rc = cmd_fetch()
        if rc != 0:
            return rc
        return cmd_show()
    if cmd == 'push':
        return cmd_push(sys.argv[2] if len(sys.argv) > 2
                        else 'chore(新周期判定): 盘前白河愁原文 + AI 解析')
    print('未知命令 %s' % cmd)
    return 1


if __name__ == '__main__':
    sys.exit(main())
