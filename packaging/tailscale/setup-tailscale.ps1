param(
    [string]$AuthKey = $env:TAILSCALE_AUTHKEY,
    [string]$ExtraArgs = $env:TAILSCALE_EXTRA_ARGS
)

$ErrorActionPreference = "Stop"
$tailscale = Get-Command tailscale.exe -ErrorAction SilentlyContinue
if (-not $tailscale) {
    throw "Install Tailscale from https://tailscale.com/download/windows first"
}

$upArgs = @("up", "--ssh")
if ($ExtraArgs) {
    $upArgs += $ExtraArgs.Split(" ")
}
if ($AuthKey) {
    $upArgs += "--authkey=$AuthKey"
}
& tailscale.exe @upArgs

& tailscale.exe status
& tailscale.exe ip -4
