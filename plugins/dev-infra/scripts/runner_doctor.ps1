<#
Self-hosted runner doctor for Windows (Android builds).

  runner_doctor.ps1                      native Windows runner: host, network, runner service, toolchain
  runner_doctor.ps1 -HostOnly            only Windows host settings (use with a WSL2 runner)
  runner_doctor.ps1 -RunnerDir D:\actions-runner

Exit code: 0 no failures (warnings allowed), 1 at least one failure.
#>
param(
  [string]$RunnerDir = "C:\actions-runner",
  [switch]$HostOnly
)

$script:Fails = 0; $script:Warns = 0
function Ok($m)   { Write-Host "OK    $m" }
function Warn($m) { Write-Host "WARN  $m"; $script:Warns++ }
function Fail($m) { Write-Host "FAIL  $m"; $script:Fails++ }
function Section($m) { Write-Host "`n== $m ==" }
function Have($c) { [bool](Get-Command $c -ErrorAction SilentlyContinue) }
$InActions = $env:GITHUB_ACTIONS -eq "true"

Section "Host"
Ok "$([Environment]::OSVersion.VersionString)"
$drive = Get-PSDrive -Name ($RunnerDir.Substring(0,1)) -ErrorAction SilentlyContinue
if ($drive) {
  $freeGb = [int]($drive.Free / 1GB)
  if ($freeGb -lt 20) { Fail "free disk ${freeGb}GB < 20GB" } else { Ok "free disk ${freeGb}GB" }
}
# Laptop: sleep on AC and lid close both kill the runner.
$acIdx = ((powercfg /query SCHEME_CURRENT SUB_SLEEP STANDBYIDLE) | Select-String "Current AC Power Setting Index: (0x[0-9a-f]+)").Matches.Groups[1].Value
if ($acIdx -and [Convert]::ToInt32($acIdx, 16) -ne 0) { Warn "sleeps after $([Convert]::ToInt32($acIdx,16)/60) min on AC; run 'powercfg /change standby-timeout-ac 0'" } elseif ($acIdx) { Ok "no sleep on AC" }
$lidIdx = ((powercfg /query SCHEME_CURRENT SUB_BUTTONS LIDACTION) | Select-String "Current AC Power Setting Index: (0x[0-9a-f]+)").Matches.Groups[1].Value
if ($lidIdx -and [Convert]::ToInt32($lidIdx, 16) -ne 0) { Warn "closing the lid on AC sleeps/hibernates; set 'When I close the lid' (plugged in) to 'Do nothing'" } elseif ($lidIdx) { Ok "lid close on AC does nothing" }
if (Have wsl) {
  $wslState = (wsl -l -v 2>$null) -join " "
  if ($wslState -match "Running") { Ok "WSL distro running" } else { Warn "no WSL distro running (a WSL2 runner needs it started; see vmIdleTimeout / a startup task)" }
}
if ($HostOnly) { Write-Host "`n$script:Fails failure(s), $script:Warns warning(s)"; exit [int]($script:Fails -gt 0) }

Section "Network"
$hosts = "github.com","api.github.com","codeload.github.com","pipelines.actions.githubusercontent.com",
  "results-receiver.actions.githubusercontent.com","broker.actions.githubusercontent.com",
  "objects.githubusercontent.com","pkg.actions.githubusercontent.com","registry.npmjs.org",
  "api.expo.dev","firebase.googleapis.com","dl.google.com","services.gradle.org","repo.maven.apache.org"
foreach ($h in $hosts) {
  try {
    $r = Invoke-WebRequest -Uri "https://$h" -Method Head -TimeoutSec 10 -UseBasicParsing -ErrorAction Stop
    Ok "https://$h (HTTP $($r.StatusCode))"
  } catch {
    if ($_.Exception.Response) { Ok "https://$h (HTTP $([int]$_.Exception.Response.StatusCode))" } else { Fail "cannot reach https://$h" }
  }
}

Section "Runner"
if ($InActions) { Ok "running inside a GitHub Actions job on runner '$env:RUNNER_NAME'" }
elseif (-not (Test-Path "$RunnerDir\.runner")) { Fail "no runner configured in $RunnerDir (run config.cmd)" }
else {
  $cfg = Get-Content "$RunnerDir\.runner" -Raw | ConvertFrom-Json
  Ok "configured: name=$($cfg.agentName) url=$($cfg.gitHubUrl)"
  $svc = Get-Service -Name "actions.runner.*" -ErrorAction SilentlyContinue
  if (-not $svc) { Fail "no actions.runner.* service (configure with --runasservice)" }
  elseif ($svc.Status -ne "Running") { Fail "service $($svc.Name) is $($svc.Status)" }
  else { Ok "service $($svc.Name) running ($($svc.StartType))" }
}

Section "Toolchain"
if (Have git) { Ok "$(git --version)" } else { Fail "git not found" }
if (Have node) {
  $major = [int]((node -v).TrimStart("v").Split(".")[0])
  if ($major -lt 20) { Fail "node $(node -v) < 20" } else { Ok "node $(node -v)" }
} else { Fail "node not found" }
if (Have java) {
  $jv = (cmd /c "java -version 2>&1" | Select-Object -First 1)
  if ($jv -match '"17') { Ok "Java 17" } else { Warn "$jv; React Native/Expo builds expect JDK 17" }
} else { Fail "java not found (install JDK 17)" }
$sdk = if ($env:ANDROID_HOME) { $env:ANDROID_HOME } else { $env:ANDROID_SDK_ROOT }
if (-not $sdk -or -not (Test-Path $sdk)) { Fail "ANDROID_HOME not set (machine-level env var, then restart the runner service)" }
else {
  Ok "Android SDK at $sdk"
  if (Test-Path "$sdk\platform-tools") { Ok "platform-tools present" } else { Fail "platform-tools missing" }
  if (Test-Path "$sdk\build-tools") { Ok "build-tools: $((Get-ChildItem "$sdk\build-tools").Name -join ' ')" } else { Fail "build-tools missing" }
}
if ((Get-ItemProperty "HKLM:\SYSTEM\CurrentControlSet\Control\FileSystem" -ErrorAction SilentlyContinue).LongPathsEnabled -ne 1) {
  Warn "long paths disabled; node_modules/Gradle paths can exceed 260 chars"
} else { Ok "long paths enabled" }

Write-Host "`n$script:Fails failure(s), $script:Warns warning(s)"
exit [int]($script:Fails -gt 0)
