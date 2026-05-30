$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $ProjectRoot

$env:PYTHONPATH = "src"
$Python = ".venv\Scripts\python.exe"
if (-not (Test-Path $Python)) {
    $Python = "python"
}

& $Python -m unittest discover -s tests
& $Python -m economic_news_bot.preflight --skip-gemini
& $Python -m economic_news_bot.main
