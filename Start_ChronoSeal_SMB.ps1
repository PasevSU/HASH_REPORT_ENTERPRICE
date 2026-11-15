$ErrorActionPreference = "Stop"

$root = $PSScriptRoot

if (-not (Test-Path -LiteralPath $root)) {
    throw "Project directory not found: $root"
}

$drive = "R"

if (Get-PSDrive -Name $drive -ErrorAction SilentlyContinue) {
    throw "Drive R: is already in use."
}

try {
    New-PSDrive -Name $drive `
        -PSProvider FileSystem `
        -Root $root `
        -Persist `
        -Scope Global | Out-Null

    $bat = "${drive}:\Start_ChronoSeal.bat"

    if (-not (Test-Path -LiteralPath $bat)) {
        throw "Start_ChronoSeal.bat not found"
    }

    & cmd.exe /d /c "call `"$bat`""
    $result = $LASTEXITCODE

    Write-Host "Startup exit code: $result"
}
finally {
    Remove-PSDrive -Name $drive -Force `
        -ErrorAction SilentlyContinue
}
