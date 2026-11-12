$ErrorActionPreference = 'Stop'
$projectPath = $PSScriptRoot
$venvPythonPath = Join-Path $projectPath '.venv\Scripts\python.exe'
$condaPythonPath = Join-Path $env:USERPROFILE 'miniconda3\python.exe'
if (Test-Path -LiteralPath $venvPythonPath) {
    $pythonPath = $venvPythonPath
} elseif (Test-Path -LiteralPath $condaPythonPath) {
    $pythonPath = $condaPythonPath
} else {
    $pythonPath = (Get-Command python -ErrorAction Stop).Source
}
Push-Location -LiteralPath $projectPath
try {
    & $pythonPath -X utf8 -m streamlit run app.py --server.address 127.0.0.1 --server.port 8510
} finally {
    Pop-Location
}

