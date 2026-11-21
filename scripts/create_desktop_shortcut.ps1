$ErrorActionPreference = "Stop"
$projectDir = Split-Path -Parent $PSScriptRoot
$pythonw = (Get-Command pythonw.exe -ErrorAction SilentlyContinue).Source
if (-not $pythonw) {
    throw "pythonw.exe not found in PATH. Install Python 3.10+ first."
}
$desktop = [Environment]::GetFolderPath('Desktop')
$lnkPath = Join-Path $desktop "Phone Control.lnk"

$wsh = New-Object -ComObject WScript.Shell
$sc = $wsh.CreateShortcut($lnkPath)
$sc.TargetPath = $pythonw
$sc.Arguments = "`"$projectDir\main.py`""
$sc.WorkingDirectory = $projectDir
$sc.Description = "Phone Control - Lightweight scrcpy & ADB Control Panel"
$sc.IconLocation = "$env:SystemRoot\System32\imageres.dll,114"
$sc.Save()

Write-Output "Created Desktop shortcut: $lnkPath"
