<#
Copy verified release bytes into a new delivery folder without inheriting a
build workspace's Low integrity label. Run from a normal PowerShell session.
This does not change ACLs, integrity labels, TEMP/TMP, or Windows protection.
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$Destination
)

$ErrorActionPreference = 'Stop'
$workspace = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..')).TrimEnd('\')
$version = (Get-Content -LiteralPath (Join-Path $workspace 'package.json') -Raw | ConvertFrom-Json).version
if ($version -notmatch '^\d+\.\d+\.\d+$') { throw 'Expected a numeric release version.' }
$destinationPath = [IO.Path]::GetFullPath($Destination).TrimEnd('\')
if ($destinationPath -eq $workspace -or $destinationPath.StartsWith($workspace + '\', [StringComparison]::OrdinalIgnoreCase)) {
    throw 'Use a new delivery folder outside the build workspace.'
}
if (Test-Path -LiteralPath $destinationPath) { throw 'The delivery folder already exists. Choose a new folder; no files were overwritten.' }
$parent = [IO.Path]::GetDirectoryName($destinationPath)
if (-not (Test-Path -LiteralPath $parent -PathType Container)) { throw 'The delivery parent folder must already exist.' }
for ($entry = Get-Item -LiteralPath $parent; $null -ne $entry; $entry = $entry.Parent) {
    if ($entry.Attributes -band [IO.FileAttributes]::ReparsePoint) { throw 'Refusing a delivery path through a junction or symbolic link.' }
}

if (-not ('Cove.ReleaseIntegrity' -as [type])) {
    Add-Type -TypeDefinition @'
using System;
using System.ComponentModel;
using System.Runtime.InteropServices;
namespace Cove {
    public static class ReleaseIntegrity {
        [DllImport("advapi32.dll", CharSet = CharSet.Unicode)]
        static extern uint GetNamedSecurityInfoW(string name, int kind, uint info,
            IntPtr owner, IntPtr group, IntPtr dacl, out IntPtr sacl, out IntPtr descriptor);
        [DllImport("advapi32.dll", CharSet = CharSet.Unicode, SetLastError = true)]
        static extern bool ConvertSecurityDescriptorToStringSecurityDescriptorW(
            IntPtr descriptor, uint revision, uint info, out IntPtr text, out uint length);
        [DllImport("kernel32.dll")] static extern IntPtr LocalFree(IntPtr memory);
        public static string ReadLabel(string path) {
            IntPtr sacl, descriptor, text = IntPtr.Zero;
            uint error = GetNamedSecurityInfoW(path, 1, 0x10, IntPtr.Zero, IntPtr.Zero,
                IntPtr.Zero, out sacl, out descriptor);
            if (error != 0) throw new Win32Exception((int)error);
            try {
                uint length;
                if (!ConvertSecurityDescriptorToStringSecurityDescriptorW(descriptor, 1, 0x10, out text, out length))
                    throw new Win32Exception(Marshal.GetLastWin32Error());
                return Marshal.PtrToStringUni(text);
            } finally {
                if (text != IntPtr.Zero) LocalFree(text);
                LocalFree(descriptor);
            }
        }
    }
}
'@
}
function Assert-NormalDeliveryLabel([string]$Path) {
    $label = [Cove.ReleaseIntegrity]::ReadLabel($Path)
    if ($label -match ';(?:LW|UN|S-1-16-(?:0|4096))\)') {
        throw "Delivery path has Low or Untrusted integrity: $Path. Choose a normal user folder; do not change sandbox permissions."
    }
    return $label
}
$parentLabel = Assert-NormalDeliveryLabel $parent
$sources = @('setup.exe', 'windows.zip', 'bundle.zip', 'source.zip') | ForEach-Object {
    $path = Join-Path $workspace "artifacts\Cove-$version-$_"
    $file = Get-Item -LiteralPath $path
    if ($file.Attributes -band [IO.FileAttributes]::ReparsePoint) { throw 'Release sources must be regular files.' }
    [pscustomobject]@{ Path = $file.FullName; Name = $file.Name; Bytes = $file.Length; Sha256 = (Get-FileHash -LiteralPath $file.FullName -Algorithm SHA256).Hash }
}
New-Item -ItemType Directory -Path $destinationPath | Out-Null
$destinationLabel = Assert-NormalDeliveryLabel $destinationPath
$files = @($sources | ForEach-Object {
    $target = Join-Path $destinationPath $_.Name
    Copy-Item -LiteralPath $_.Path -Destination $target
    $copiedHash = (Get-FileHash -LiteralPath $target -Algorithm SHA256).Hash
    if ($copiedHash -ne $_.Sha256) { throw "Release copy failed verification: $target" }
    $label = Assert-NormalDeliveryLabel $target
    [ordered]@{ path = $target; bytes = $_.Bytes; sha256 = $copiedHash; source = $_.Path; integrityLabel = $label }
})
$checksums = @($files | ForEach-Object { $_.sha256.ToLowerInvariant() + '  ' + [IO.Path]::GetFileName($_.path) })
$checksums | Set-Content -LiteralPath (Join-Path $destinationPath 'SHA256SUMS.txt') -Encoding ascii
$result = [ordered]@{
    version = $version; destination = $destinationPath; files = $files
    parentLabel = $parentLabel; directoryLabel = $destinationLabel
    byteIdentical = $true; signatureStatus = [string](Get-AuthenticodeSignature -LiteralPath $files[0].path).Status
    note = 'Export does not sign binaries, grant SmartScreen reputation, or prove installation. Verify this exact delivery path with the normal system TEMP.'
}
$result | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath (Join-Path $destinationPath 'release-copy.json') -Encoding utf8
$result | ConvertTo-Json -Depth 6
