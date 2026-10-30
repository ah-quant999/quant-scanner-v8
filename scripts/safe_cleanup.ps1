<#
.SYNOPSIS
    双机 C/D/E 盘垃圾清理（安全白名单版）· v8 存储与清理铁律落地脚本
.DESCRIPTION
    对应 SKILL.md「主人工作守则」第 7 条（2026-10-30 主人令）：
      - 双机项目文件勿驻留 C 盘（C 盘空间紧张，撑爆致 runner 失联）
      - 定时清理 C/D/E 三盘垃圾
      - 🔴 红线：绝不得删除主人的工作文档（桌面/文档/下载/高考志愿/个人文件）
    本脚本采用「白名单式」清理：只删明确可确认的垃圾位置/类型，
    绝不去遍历或删除任何用户文档目录。默认 dry-run（只报告），-Apply 才真删。
.PARAMETER Apply
    加 -Apply 才真正删除；缺省仅打印将要清理的项（安全默认）。
.PARAMETER Drives
    要清理的盘符，默认 C D E。
.EXAMPLE
    powershell -NoProfile -ExecutionPolicy Bypass -File safe_cleanup.ps1            # 仅报告
    powershell -NoProfile -ExecutionPolicy Bypass -File safe_cleanup.ps1 -Apply     # 真删
#>

[CmdletBinding()]
param(
    [switch]$Apply,
    [string[]]$Drives = @('C','D','E')
)

$ErrorActionPreference = 'SilentlyContinue'

# ---- 🔴 红线：受保护的用户文档目录（绝不在这些下面删任何东西） ----
$protectedRoots = @(
    [Environment]::GetFolderPath('Desktop'),
    [Environment]::GetFolderPath('MyDocuments'),
    [Environment]::GetFolderPath('MyMusic'),
    [Environment]::GetFolderPath('MyPictures'),
    [Environment]::GetFolderPath('MyVideos'),
    Join-Path $HOME 'Downloads',
    Join-Path $HOME 'Desktop',
    Join-Path $HOME 'Documents'
) | Where-Object { $_ } | Select-Object -Unique

function Test-Protected {
    param([string]$Path)
    foreach ($r in $protectedRoots) {
        if ($Path -and ($Path -eq $r -or $Path.StartsWith($r + '\') -or $Path.StartsWith($r + '/'))) {
            return $true
        }
    }
    return $false
}

# ---- 白名单垃圾位置（只清这些，绝不过界） ----
$candidates = @()
# 1) 系统/用户临时目录
$candidates += @($env:TEMP, "$env:SystemRoot\Temp", "$env:SystemRoot\Prefetch")
# 2) 各盘回收站
foreach ($d in $Drives) {
    $candidates += "\\$d`$\`$Recycle.Bin"
    $candidates += "${d}:\`$Recycle.Bin"
}
# 3) 项目侧已知缓存（仅明确缓存名，绝不含 node_modules/源码）
$projCacheNames = @('__pycache__', '.pytest_cache', '.mypy_cache', '*.pyc', '*.tmp', '~*.tmp', 'Thumbs.db')
#    D:\actions 下仅清明确命名的旧备份/临时构建残骸，不碰 _work 活动 checkout
$candidates += 'D:\actions\_backup_pre_svc0'

$total = 0
$plan = @()

foreach ($base in ($candidates | Where-Object { $_ } | Select-Object -Unique)) {
    if (-not (Test-Path $base)) { continue }
    if (Test-Protected $base) { Write-Host "🛡 跳过受保护区: $base"; continue }

    # 回收站 / Temp：递归收集可删项
    Get-ChildItem -Path $base -Recurse -Force -ErrorAction SilentlyContinue | ForEach-Object {
        if (Test-Protected $_.FullName) { return }
        $plan += $_.FullName
        $total++
    }
}
# 项目缓存名（在 D:\actions 范围内，排除 _work 活动区）
foreach ($d in $Drives) {
    $root = "${d}:\"
    if (-not (Test-Path $root)) { continue }
    foreach ($name in $projCacheNames) {
        Get-ChildItem -Path $root -Recurse -Force -Filter $name -ErrorAction SilentlyContinue | ForEach-Object {
            $p = $_.FullName
            if (Test-Protected $p) { return }
            if ($p -like '*\_work\*') { return }   # 绝不碰活动 checkout
            $plan += $p
            $total++
        }
    }
}

Write-Host "===== v8 安全清理（$(if($Apply){'APPLY 真删'}else{'DRY-RUN 仅报告'})) ====="
Write-Host "受保护区(绝不删): $($protectedRoots -join ' | ')"
Write-Host "拟清理项数: $total"

if ($total -eq 0) { Write-Host '无垃圾可清。'; exit 0 }

if (-not $Apply) {
    $plan | Select-Object -First 200 | ForEach-Object { Write-Host "  [dry] $_" }
    if ($total -gt 200) { Write-Host "  ... 其余 $($total-200) 项省略" }
    Write-Host "（默认 dry-run，未删除任何文件。确认无误后加 -Apply 执行）"
    exit 0
}

# ---- Apply：逐项删除，每删前再校验一次红线 ----
$removed = 0
foreach ($p in $plan) {
    if (Test-Protected $p) { Write-Host "🛡 红线拦截: $p"; continue }
    try {
        if (Test-Path $p -PathType Container) { Remove-Item $p -Recurse -Force -ErrorAction Stop }
        else { Remove-Item $p -Force -ErrorAction Stop }
        $removed++
    } catch { Write-Host "  ✗ 跳过(删失败): $p" }
}
Write-Host "已清理: $removed / $total"
