param([string]$OutputDirectory = (Join-Path $PSScriptRoot 'reports\iop_v2'))
$ErrorActionPreference = 'Stop'
# Python independently checks container name, volume, published port and county.
# Creates only new v2 tables in one transaction. Refuses to overwrite v2.
py (Join-Path $PSScriptRoot 'app\python\iop_v2.py') $OutputDirectory
if ($LASTEXITCODE -ne 0) { throw 'IOP v2 failed; transaction rolled back. Read error above.' }
