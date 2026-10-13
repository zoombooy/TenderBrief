$ErrorActionPreference = "Stop"
Set-Location -LiteralPath $PSScriptRoot

$python = $env:TENDERBRIEF_PYTHON
if (-not $python) {
    $projectPython = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
    if (Test-Path -LiteralPath $projectPython) { $python = $projectPython }
}
if (-not $python) {
    $found = Get-Command python3, python -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($found) { $python = $found.Source }
}
if ($python) {
    & $python -c "import fastapi, uvicorn, pydantic, docx, fitz, httpx, dotenv, multipart"
    if ($LASTEXITCODE -ne 0) {
        throw "缺少依赖。请先运行：python -m pip install -r requirements.txt"
    }
    $env:TENDERBRIEF_PYTHON = $python
}
else {
    $launcher = Get-Command py -ErrorAction SilentlyContinue
    if (-not $launcher) { throw "需要 Python 3.10+。也可设置 TENDERBRIEF_PYTHON 指向 python.exe。" }
    & $launcher.Source -3 -c "import fastapi, uvicorn, pydantic, docx, fitz, httpx, dotenv, multipart"
    if ($LASTEXITCODE -ne 0) { throw "请先安装依赖：py -3 -m pip install -r requirements.txt" }
    $env:TENDERBRIEF_PYTHON = $launcher.Source
    $env:TENDERBRIEF_PYTHON_ARGS = "-3"
}
Write-Host "TenderBrief Agent starting. Press Ctrl+C to stop."
node .\server.mjs
