<#
.SYNOPSIS
  每 10 分钟（整 :00 / :10 / :20 …）：把 input/{domain} 下所有 .md 的修改时间批量改成"当前时间"，
  然后立刻跑一次 --sqlite 增量构建（不带 --reset）。

  用途：复现服务器上「定时任务先改一批文件的 mtime，再调构建接口」这个场景。

.EXAMPLE
  # 前台常驻，每 10 分钟一轮（对齐整十分），Ctrl+C 退出
  .\scripts\touchAndBuild.ps1 -Domain test1

.EXAMPLE
  # 只跑一轮（手动复现一次）
  .\scripts\touchAndBuild.ps1 -Domain test1 -Once

.EXAMPLE
  # 只改 31 个文件的 mtime（贴近服务器那次 "Detected 31 changed"），并 5 分钟后判定卡死强杀
  .\scripts\touchAndBuild.ps1 -Domain test1 -TouchLimit 31 -TimeoutSeconds 300 -Once

.EXAMPLE
  # 根目录不在脚本上一级时显式指定（例如服务器 C:/Project/quartz-fullstack）
  .\scripts\touchAndBuild.ps1 -Domain test1 -Root C:\Project\quartz-fullstack -EngineDir C:\Project\quartz-fullstack\quartz5
#>
[CmdletBinding()]
param(
  # 业务域（同时也是 settings/input/output/cache 四个根目录下的同名目录名）
  [Parameter(Mandatory = $true)][string]$Domain,

  # 项目根（含 settings/ input/ output/ cache/），默认取脚本上一级目录
  [string]$Root = (Split-Path -Parent $PSScriptRoot),

  # v5 引擎目录（含 quartz/bootstrap-cli.mjs），默认 $Root\quartz5
  [string]$EngineDir,

  # 间隔分钟数；脚本会对齐到"整 $IntervalMinutes 分"
  [int]$IntervalMinutes = 10,

  # 只跑一轮就退出
  [switch]$Once,

  # 只随机挑 N 个 .md 改 mtime；0（默认）= 全部
  [int]$TouchLimit = 0,

  # 改完 mtime 后等待几秒再构建（模拟调度器先改文件、稍后才调接口）
  [int]$SettleSeconds = 0,

  # 构建超时秒数；0（默认）= 不超时（想抓"卡死"就别设）
  [int]$TimeoutSeconds = 0,

  # 给构建进程开 inspector 端口；0（默认）= 不开。开了之后卡住时用 scripts/dumpJsStack.mjs 抓 JS 栈
  [int]$InspectPort = 0
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

if (-not $EngineDir) { $EngineDir = Join-Path $Root 'quartz5' }

# ---------- 路径：与 Go server 的拼法保持一致（四个根目录 + 同名域目录） ----------
$settings = Join-Path $Root "settings\$Domain"
$inputDir = Join-Path $Root "input\$Domain"
$output   = Join-Path $Root "output\$Domain"
$cache    = Join-Path $Root "cache\$Domain"

foreach ($p in @($settings, $inputDir, $EngineDir)) {
  if (-not (Test-Path -LiteralPath $p)) {
    throw "路径不存在：$p`n请用 -Root / -EngineDir 指定正确位置。"
  }
}
New-Item -ItemType Directory -Force -Path $output, $cache | Out-Null

# Go server 是把路径转成正斜杠后再传给 node（toUnixPath），这里保持一致
function ConvertTo-ForwardSlash([string]$p) { return ($p -replace '\\', '/') }

$logDir = Join-Path $PSScriptRoot 'logs'
New-Item -ItemType Directory -Force -Path $logDir | Out-Null

function Invoke-Round {
  $tick = Get-Date
  $stamp = $tick.ToString('yyyyMMdd-HHmmss')
  $taskLog = Join-Path $logDir "touchbuild-$Domain-$stamp.log"

  # ---------- 1) 批量改 mtime（内容一字不动） ----------
  $files = @(Get-ChildItem -LiteralPath $inputDir -Recurse -File -Filter *.md)
  if ($TouchLimit -gt 0 -and $files.Count -gt $TouchLimit) {
    $files = @(Get-Random -InputObject $files -Count $TouchLimit)
  }

  $now = Get-Date
  foreach ($f in $files) { $f.LastWriteTime = $now }

  $head = @(
    "[$($tick.ToString('HH:mm:ss'))] 触碰 mtime：$($files.Count) 个 .md 全部改为 $($now.ToString('yyyy-MM-dd HH:mm:ss'))",
    "业务域:   $Domain",
    "Input:    $(ConvertTo-ForwardSlash $inputDir)",
    "Settings: $(ConvertTo-ForwardSlash $settings)",
    "Output:   $(ConvertTo-ForwardSlash $output)",
    "Cache:    $(ConvertTo-ForwardSlash $cache)"
  )
  $head | ForEach-Object { Write-Host $_ }
  Set-Content -LiteralPath $taskLog -Value $head -Encoding UTF8

  if ($SettleSeconds -gt 0) { Start-Sleep -Seconds $SettleSeconds }

  # ---------- 2) 立即构建：--sqlite，不带 --reset ----------
  $argList = @(
    '--no-deprecation', './quartz/bootstrap-cli.mjs', 'build', '--sqlite',
    '--settings', (ConvertTo-ForwardSlash $settings),
    '-d', (ConvertTo-ForwardSlash $inputDir),
    '-o', (ConvertTo-ForwardSlash $output),
    '--cacheDir', (ConvertTo-ForwardSlash $cache)
  )
  if ($InspectPort -gt 0) { $argList = @("--inspect=127.0.0.1:$InspectPort") + $argList }
  $cmdLine = 'node ' + ($argList -join ' ')
  Add-Content -LiteralPath $taskLog -Encoding UTF8 -Value @(
    '',
    "启动时间: $($tick.ToString('yyyy-MM-dd HH:mm:ss'))",
    "工作目录: $EngineDir",
    "完整命令: $cmdLine",
    '',
    '--- 命令输出开始 ---'
  )
  Write-Host "[$($tick.ToString('HH:mm:ss'))] 构建开始（$EngineDir）"
  Write-Host $cmdLine

  # stdout 与 stderr 合并进同一个文件（顺序与服务器任务日志一致）：cmd /c "... >> 日志 2>&1"
  $redirect = '>> "' + $taskLog + '" 2>&1'
  $sw = [System.Diagnostics.Stopwatch]::StartNew()
  $proc = Start-Process -FilePath 'cmd.exe' `
    -ArgumentList @('/c', ($cmdLine + ' ' + $redirect)) `
    -WorkingDirectory $EngineDir -NoNewWindow -PassThru

  $timedOut = $false
  if ($TimeoutSeconds -gt 0) {
    if (-not $proc.WaitForExit($TimeoutSeconds * 1000)) {
      $timedOut = $true
      Write-Warning "超过 $TimeoutSeconds 秒仍未结束，判定卡死，强杀进程树（pid=$($proc.Id)）"
      taskkill /PID $proc.Id /T /F 2>&1 | Write-Host
      $proc.WaitForExit()
    }
  }
  else {
    $proc.WaitForExit()
  }
  $sw.Stop()

  $exitCode = $null
  try { $exitCode = $proc.ExitCode } catch { }

  $text = (Get-Content -LiteralPath $taskLog -Encoding UTF8) -join "`n"
  if ($timedOut) {
    $status = "卡死（>$TimeoutSeconds s，已强杀）"
  }
  elseif ($text -match 'Done incremental build in' -or $text -match 'Done processing \d+ files') {
    $status = '成功'
  }
  elseif ($null -ne $exitCode -and $exitCode -eq 0) {
    $status = '成功'
  }
  else {
    $status = "失败（exit=$exitCode）"
  }

  Add-Content -LiteralPath $taskLog -Encoding UTF8 -Value @(
    '--- 命令输出结束 ---',
    "结果: $status",
    "耗时: $($sw.Elapsed.TotalSeconds.ToString('0.0'))s",
    ''
  )
  Write-Host "[$((Get-Date).ToString('HH:mm:ss'))] $status，耗时 $($sw.Elapsed.TotalSeconds.ToString('0.0'))s，日志: $taskLog"
}

# 距离下一个「整 $IntervalMinutes 分」还有多少秒（12:03 → 到 12:10）
function Get-SecondsToNextSlot([int]$minutes) {
  $now = Get-Date
  $slot = [int][math]::Floor($now.Minute / $minutes) * $minutes
  $next = $now.Date.AddHours($now.Hour).AddMinutes($slot + $minutes)
  return [int][math]::Max(1, [math]::Ceiling(($next - $now).TotalSeconds))
}

if ($Once) {
  Invoke-Round
  return
}

Write-Host "常驻模式：每 $IntervalMinutes 分钟（对齐整 $IntervalMinutes 分）触碰 mtime 并跑一次增量构建。Ctrl+C 退出。"
while ($true) {
  $wait = Get-SecondsToNextSlot $IntervalMinutes
  Write-Host "[$(Get-Date -Format 'HH:mm:ss')] 距下一轮 $wait 秒"
  Start-Sleep -Seconds $wait
  try { Invoke-Round } catch { Write-Warning $_ }
}
