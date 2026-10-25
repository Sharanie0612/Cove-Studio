"""Repair only links targeting this Cove installation; never execute a shortcut."""
import base64
import json
import os
from pathlib import Path
import subprocess


def create_desktop_shortcut(installation, folder):
    """Create an opted-in shortcut, preserving any unrelated existing file."""
    folder.mkdir(parents=True, exist_ok=True)
    script = r'''
$ErrorActionPreference = 'Stop'
$root = [IO.Path]::GetFullPath($env:COVE_SHORTCUT_ROOT).TrimEnd('\')
$entry = Join-Path $root 'Cove.exe'
$path = Join-Path $env:COVE_SHORTCUT_FOLDER 'Cove.lnk'
$shell = New-Object -ComObject WScript.Shell
if (Test-Path -LiteralPath $path) {
  $file = Get-Item -LiteralPath $path
  if ($file.Attributes -band [IO.FileAttributes]::ReparsePoint) { throw 'Linked shortcut' }
  $existing = $shell.CreateShortcut($path)
  if ($existing.TargetPath -ine $entry) { throw 'Unrelated existing shortcut' }
} else {
  $link = $shell.CreateShortcut($path)
  $link.TargetPath = $entry
  $link.WorkingDirectory = $root
  $link.IconLocation = "$entry,0"
  $link.Save()
}
'''
    command = str(Path(os.environ['SystemRoot'])/'System32/WindowsPowerShell/v1.0/powershell.exe')
    result = subprocess.run([command,'-NoProfile','-NonInteractive','-EncodedCommand',
        base64.b64encode(script.encode('utf-16-le')).decode('ascii')],
        env={**os.environ,'COVE_SHORTCUT_ROOT':str(installation.resolve()),'COVE_SHORTCUT_FOLDER':str(folder.resolve())},
        capture_output=True, timeout=20, creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
    if result.returncode:
        raise OSError('Unable to create the Cove desktop shortcut')


def repair_shortcuts(installation, folders):
    folders = [str(Path(folder).resolve()) for folder in folders if Path(folder).is_dir()]
    if not folders or os.name != 'nt':
        return []
    # WScript.Shell reads .lnk metadata without launching its target. All input
    # paths are environment data, not interpolated PowerShell source.
    script = r'''
$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [Text.UTF8Encoding]::new($false)
$root = [IO.Path]::GetFullPath($env:COVE_SHORTCUT_ROOT).TrimEnd('\')
$prefix = $root + '\'
$shell = New-Object -ComObject WScript.Shell
$changed = @()
foreach ($folder in (ConvertFrom-Json $env:COVE_SHORTCUT_FOLDERS)) {
  foreach ($file in (Get-ChildItem -LiteralPath $folder -Filter '*.lnk' -File)) {
    if ($file.Attributes -band [IO.FileAttributes]::ReparsePoint) { continue }
    try {
      $link = $shell.CreateShortcut($file.FullName)
      $target = [IO.Path]::GetFullPath($link.TargetPath)
    } catch { continue }
    if (-not $target.StartsWith($prefix, [StringComparison]::OrdinalIgnoreCase)) { continue }
    $relative = $target.Substring($prefix.Length)
    if ($relative -notmatch '^(?:versions\\[0-9]+\.[0-9]+\.[0-9]+\\)?Cove\.exe$') { continue }
    $entry = Join-Path $root 'Cove.exe'
    if ($target -ieq $entry -and $link.WorkingDirectory -ieq $root -and $link.IconLocation -ieq "$entry,0") { continue }
    $link.TargetPath = $entry
    $link.WorkingDirectory = $root
    $link.IconLocation = "$entry,0"
    $link.Save()
    $changed += $file.FullName
  }
}
ConvertTo-Json -InputObject @($changed) -Compress
'''
    command = str(Path(os.environ['SystemRoot']) / 'System32/WindowsPowerShell/v1.0/powershell.exe')
    result = subprocess.run([command, '-NoProfile', '-NonInteractive', '-EncodedCommand',
                             base64.b64encode(script.encode('utf-16-le')).decode('ascii')],
                            env={**os.environ, 'COVE_SHORTCUT_ROOT': str(installation.resolve()),
                                 'COVE_SHORTCUT_FOLDERS': json.dumps(folders)},
                            capture_output=True, encoding='utf-8', timeout=20,
                            creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
    if result.returncode:
        raise OSError('无法更新 Cove 快捷方式，请关闭快捷方式属性窗口后重试')
    return json.loads(result.stdout.strip() or '[]')
