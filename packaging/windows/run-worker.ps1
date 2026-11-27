param(
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$WorkerArgs
)

$ErrorActionPreference = "Stop"
$dir = Split-Path -Parent $PSCommandPath
$env:PATH = "$dir\bin;$env:PATH"
$controller = if ($env:LFHAI_CONTROLLER) { $env:LFHAI_CONTROLLER } else { "http://127.0.0.1:8001" }

$argsList = @(
    "worker",
    "start",
    "--llamacpp-bin",
    "$dir\bin\llama-server.exe",
    "--rpc-bin",
    "$dir\bin\ggml-rpc-server.exe",
    "--model-dir",
    $(if ($env:LFHAI_MODEL_DIR) { $env:LFHAI_MODEL_DIR } else { "$dir\models" })
)
if ($env:LFHAI_RPC_BIND) {
    $argsList += @("--rpc-bind", $env:LFHAI_RPC_BIND)
}
if ($env:LFHAI_RPC_CPU_MEMORY_MB) {
    $argsList += @("--rpc-cpu", "--rpc-cpu-memory-mb", $env:LFHAI_RPC_CPU_MEMORY_MB)
}
if ($env:LFHAI_RPC_GPU_MEMORY_MB) {
    $argsList += @("--rpc-gpu", "--rpc-gpu-memory-mb", $env:LFHAI_RPC_GPU_MEMORY_MB)
}
if ($env:LFHAI_FIT_TARGET_MIB) {
    $argsList += @("--fit-target-mib", $env:LFHAI_FIT_TARGET_MIB)
}
if ($WorkerArgs) {
    $argsList += $WorkerArgs
}

& "$dir\bin\lfh.exe" -c $controller @argsList
exit $LASTEXITCODE
