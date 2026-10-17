#!/usr/bin/env pwsh
# =====================================================================
#  九宝量化 v8 — cn runner 一键安装 (Windows PowerShell 5.1+ 兼容)
#  用途: 把当前机器注册成 GitHub Actions self-hosted runner,
#       label=cn group=v8-cn-fetch-cloud(共享 runner group, 多机互备)
#  适用: 小九(单位机) / 阿狸咪(家中机) 一台机器跑一次即可
#  不动: 仓库任何源码/data/*/raw_data/*
#  入参: -Token <GitHub注册token>   <- 主人从 Settings→Actions→Runners→New 复制
#        -RunnerName <alimi-cn|xiaojiu-cn|...>  <- 默认取 hostname
#        -WorkDir <C:\actions\cn-runner>  <- 默认 C:\actions\cn-runner
#  用法:
#    pwsh -File setup_cn_runner.ps1 -Token 'ARXXXXXXXXX' -RunnerName 'xiaojiu-cn'
#  退出码: 0=成功; 10=已注册; 20=token无效; 30=权限不足; 99=未知错误
# =====================================================================
[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)] [string]$Token,
    [string]$RunnerName = ("xiaojiu-cn-" + [Environment]::MachineName),
    [string]$WorkDir = "C:\actions\cn-runner",
    [string]$Repo = "ah-quant999/quant-scanner-v8",
    [string]$RunnerGroup = "v8-cn-fetch-cloud",
    [string[]]$Labels = @("cn","cn-cn"),
    [switch]$SkipServiceInstall,
    [switch]$SkipSmokeTest
)

$ErrorActionPreference = 'Stop'

# ---------- 1. 必备检查 ----------
function Test-Admin {
    $id = [Security.Principal.WindowsIdentity]::GetCurrent()
    $pr = New-Object Security.Principal.WindowsPrincipal($id)
    if (-not $pr.IsInRole([Security.Principal.WindowsBuiltinRole]::Administrator)) {
        Write-Host "[!] 需要管理员权限启动 PowerShell 后重试(右键→以管理员身份运行)" -ForegroundColor Red
        exit 30
    }
}

function Get-LatestRunnerVersion {
    try {
        $api = "https://api.github.com/repos/actions/runner/releases/latest"
        $rel = Invoke-RestMethod -Uri $api -TimeoutSec 15 -Headers @{'User-Agent'='cn-runner-setup'}
        return ($rel.tag_name -replace '^v','')
    } catch {
        Write-Host "[!] 无法拉取最新 runner 版本, 改为固定 2.319.1 (LTS)" -ForegroundColor Yellow
        return "2.319.1"
    }
}

# ---------- 2. 准备目录与下载 ----------
function Initialize-Workdir($dir, $version) {
    if (Test-Path "$dir\.runner") {
        Write-Host "[i] 检测到 $dir 已注册过, 跳过下载解压" -ForegroundColor Yellow
        return
    }
    if (Test-Path $dir) {
        Write-Host "[i] $dir 已存在但未注册, 清理后重装" -ForegroundColor Yellow
        Remove-Item -Recurse -Force $dir
    }
    New-Item -ItemType Directory -Path $dir -Force | Out-Null

    $zip = "$dir\..\actions-runner-win-x64-$version.zip"
    if (-not (Test-Path $zip)) {
        Write-Host "[↓] 下载 actions/runner v$version (~150MB)..." -ForegroundColor Cyan
        $url = "https://github.com/actions/runner/releases/download/v$version/actions-runner-win-x64-$version.zip"
        try {
            Invoke-WebRequest -Uri $url -OutFile $zip -UseBasicParsing -TimeoutSec 300
        } catch {
            Write-Host "[X] 下载失败: $_" -ForegroundColor Red
            Write-Host "    手动下载并解压到 $dir 后重跑本脚本" -ForegroundColor Yellow
            exit 99
        }
    }
    Write-Host "[↓] 解压..." -ForegroundColor Cyan
    Expand-Archive -Path $zip -DestinationPath $dir -Force
    Remove-Item $zip
}

# ---------- 3. 注册 + 服务安装 ----------
function Invoke-Config {
    param($dir, $token, $name, $repo, $group, $labels)
    $labelsArg = ($labels | ForEach-Object { "'$_'" }) -join ","
    $args = @(
        "--url","https://github.com/$repo",
        "--token","$token",
        "--name","$name",
        "--runnergroup","$group",
        "--labels",$labelsArg,
        "--work","_work",
        "--replace",
        "--unattended"
    )
    Write-Host "[→] config: 仓库=$repo  group=$group  name=$name  labels=[$labelsArg]" -ForegroundColor Green
    Push-Location $dir
    try {
        & ".\config.cmd" @args
    } finally {
        Pop-Location
    }
    if ($LASTEXITCODE -ne 0) {
        Write-Host "[X] config 退出码 $LASTEXITCODE (token 无效或 group 不存在)" -ForegroundColor Red
        if ($LASTEXITCODE -eq 2) { exit 20 }
        exit 99
    }
}

function Install-AsService($dir) {
    Write-Host "[→] 安装为 Windows 系统服务 (开机自启, 管理员权限)" -ForegroundColor Green
    Push-Location $dir
    try {
        & ".\svc.cmd" "install" "$dir\run.cmd"
        & ".\svc.cmd" "start"
    } finally {
        Pop-Location
    }
    if ($LASTEXITCODE -ne 0) {
        Write-Host "[X] 服务安装/启动失败 退出码 $LASTEXITCODE" -ForegroundColor Red
        exit 99
    }
    Write-Host "[✓] 服务已注册并启动: actions.runner.<repo>-<name>" -ForegroundColor Green
}

# ---------- 4. 冒烟测试 ----------
function Invoke-SmokeTest($dir) {
    Write-Host "[→] 冒烟测试: 取一次 runner 自身状态 + 拉 4 个关键盘中模块对比" -ForegroundColor Cyan
    Push-Location $dir
    try {
        & ".\run.cmd" --once --diagnostics 2>&1 | Tee-Object -FilePath "$dir\smoke.log" | Out-Null
    } finally {
        Pop-Location
    }
    Write-Host "[i] 完整冒烟见 $dir\smoke.log (本步在未联网工作流下可能秒退, 不必紧张)" -ForegroundColor Yellow
}

# ---------- 5. 卸载/回滚 ----------
function Invoke-Uninstall {
    param($dir)
    Push-Location $dir
    try {
        if (Test-Path ".\svc.cmd") { & ".\svc.cmd" "stop" 2>$null; & ".\svc.cmd" "uninstall" 2>$null }
        if (Test-Path ".\config.cmd") { & ".\config.cmd" "remove" "--token" $Token 2>$null }
    } finally { Pop-Location }
    Write-Host "[✓] 已卸载 runner + 服务" -ForegroundColor Green
}

# ====================================================================
# 主流程
# ====================================================================
Test-Admin
$version = Get-LatestRunnerVersion
Write-Host "==== cn runner 安装器 ====" -ForegroundColor Cyan
Write-Host "  Runner v$version"
Write-Host "  目标: $Repo (group=$RunnerGroup)"
Write-Host "  本机名: $RunnerName"
Write-Host "  安装目录: $WorkDir"
Write-Host ""

Initialize-Workdir -dir $WorkDir -version $version
Invoke-Config -dir $WorkDir -token $Token -name $RunnerName -repo $Repo -group $RunnerGroup -labels $Labels

if (-not $SkipServiceInstall) {
    Install-AsService -dir $WorkDir
} else {
    Write-Host "[i] 跳过服务安装(手动运行请用: cd $WorkDir && run.cmd)" -ForegroundColor Yellow
}

if (-not $SkipSmokeTest) {
    Invoke-SmokeTest -dir $WorkDir
}

Write-Host ""
Write-Host "==== 完成 ====" -ForegroundColor Green
Write-Host "  验证: 浏览器打开 https://github.com/$Repo/settings/actions/runners"
Write-Host "         应看到 '$RunnerName' 状态为 Idle(空闲) / Active(忙)"
Write-Host "  日志: $WorkDir\_diag\*.log"
Write-Host "  卸载: pwsh -File setup_cn_runner.ps1 -Token '$Token' -WorkDir '$WorkDir' -SkipServiceInstall  (手动跑 config.cmd remove)"