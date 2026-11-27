param(
    [Parameter(Mandatory = $true)]
    [string]$LlamaBuildDir,
    [string]$Version = "dev"
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$out = Join-Path $root "dist"
$stage = Join-Path $out "lfhai-windows-x86_64-$Version"

if (Test-Path $stage) {
    Remove-Item -Recurse -Force $stage
}
New-Item -ItemType Directory -Force -Path (Join-Path $stage "bin") | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $stage "models") | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $stage "scripts") | Out-Null

python -m PyInstaller `
    --onefile `
    --name lfh `
    --distpath (Join-Path $stage "bin") `
    --workpath (Join-Path $out ".pyinstaller-windows") `
    --specpath (Join-Path $out ".pyinstaller-windows") `
    (Join-Path $root "packaging/cli_entry.py")

$llamaServer = Get-ChildItem -Path $LlamaBuildDir -Recurse -Filter "llama-server.exe" | Select-Object -First 1
$rpcServer = Get-ChildItem -Path $LlamaBuildDir -Recurse -Filter "ggml-rpc-server.exe" | Select-Object -First 1
if (-not $llamaServer -or -not $rpcServer) {
    throw "llama-server.exe and ggml-rpc-server.exe must be built first"
}
$binDir = $llamaServer.DirectoryName

Copy-Item $llamaServer.FullName (Join-Path $stage "bin/llama-server.exe")
Copy-Item $rpcServer.FullName (Join-Path $stage "bin/ggml-rpc-server.exe")
Get-ChildItem -Path $binDir -Filter "*.dll" | Copy-Item -Destination (Join-Path $stage "bin")
Copy-Item (Join-Path $root "README.md") $stage
Copy-Item (Join-Path $root "LICENSE") $stage
Copy-Item (Join-Path $root "packaging/windows/run-worker.ps1") (Join-Path $stage "run-worker.ps1")
Copy-Item (Join-Path $root "packaging/tailscale/setup-tailscale.ps1") (Join-Path $stage "scripts/setup-tailscale.ps1")

Compress-Archive -Path (Join-Path $stage "*") -DestinationPath (Join-Path $out "lfhai-windows-x86_64-$Version.zip") -Force
