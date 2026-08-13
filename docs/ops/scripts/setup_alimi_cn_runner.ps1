#!/usr/bin/env pwsh
# =====================================================================
#  九宝量化 v8 — 阿狸咪(家中机) cn runner 一键安装
#  差异: 默认 RunnerName=alimi-cn, 默认装到 D:\actions\cn-runner(避开 C 盘)
#  适用: Windows 10/11 + PowerShell 5.1+
#  用法:
#    pwsh -File setup_alimi_cn_runner.ps1 -Token 'ARXXXXXX...'
#  退出码: 0=成功; 20=token无效; 30=非管理员; 99=未知错误
#  说明:
#    - D 盘是坚果云同步盘或家用机数据盘, 不污染系统盘; 若只有 C 盘请加 -WorkDir 'C:\actions\cn-runner'
#    - label=cn 与 group=v8-cn-fetch-cloud 与小九本机一致, GitHub 自动调度任一在线即可
# =====================================================================
[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)] [string]$Token,
    [string]$RunnerName = "alimi-cn",
    [string]$WorkDir = "D:\actions\cn-runner",
    [string]$Repo = "ah-quant999/quant-scanner-v8",
    [string]$RunnerGroup = "v8-cn-fetch-cloud",
    [string[]]$Labels = @("cn","cn-cn"),
    [switch]$SkipServiceInstall,
    [switch]$SkipSmokeTest
)

# 复用 setup_cn_runner.ps1 主体
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
& "$here\setup_cn_runner.ps1" `
    -Token $Token `
    -RunnerName $RunnerName `
    -WorkDir $WorkDir `
    -Repo $Repo `
    -RunnerGroup $RunnerGroup `
    -Labels $Labels `
    -SkipServiceInstall:$SkipServiceInstall `
    -SkipSmokeTest:$SkipSmokeTest
exit $LASTEXITCODE