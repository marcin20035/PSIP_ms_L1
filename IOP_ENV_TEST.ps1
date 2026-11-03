param([switch]$Apply)

# Uwaga: tylko istniejący projekt PSIP_ms_L1 i tylko env-test.
# Bez parametru -Apply: jedynie kontrola, bez modyfikacji bazy.
$ErrorActionPreference = "Stop"
$project = $PSScriptRoot
Set-Location $project

$scriptFile = Join-Path $project "app\python\iop_passability.py"
$configFile = Join-Path $project "app\python\iop_weights.json"
if (-not (Test-Path $scriptFile) -or -not (Test-Path $configFile)) {
    throw "Brak plikow IOP. Najpierw rozpakuj paczke do katalogu PSIP_ms_L1."
}

$container = "remote-db-env-test-postgis-1"
$inspection = docker inspect $container | ConvertFrom-Json
if ($LASTEXITCODE -ne 0 -or @($inspection).Count -ne 1) {
    throw "Brak kontenera env-test w Docker Desktop."
}
$info = @($inspection)[0]
$volume = @($info.Mounts | Where-Object { $_.Destination -eq '/var/lib/postgresql/data' })
if ($volume.Count -ne 1 -or $volume[0].Name -ne 'remote-db-env-test-pgdata') {
    throw "Niezgodny wolumen env-test. Przerwano dla bezpieczenstwa."
}
if ($info.State.Health.Status -ne "healthy") {
    throw "Baza env-test nie ma stanu healthy."
}

# Odczytaj konfigurację działającego env-test bez ujawniania hasła.
foreach ($entry in $info.Config.Env) {
    if ($entry -match '^(POSTGRES_USER|POSTGRES_PASSWORD|POSTGRES_DB)=(.*)$') {
        [Environment]::SetEnvironmentVariable($matches[1], $matches[2], 'Process')
    }
}
foreach ($key in @('POSTGRES_USER', 'POSTGRES_PASSWORD', 'POSTGRES_DB')) {
    if ([string]::IsNullOrWhiteSpace([Environment]::GetEnvironmentVariable($key))) {
        throw "Brak konfiguracji $key."
    }
}
$env:POSTGRES_PORT = '5444'
$env:ENVIRONMENT = 'env-test'

if ($Apply) {
    # Bez świeżej kopii zapasowej nie wykonujemy zapisu.
    $backupFolder = Join-Path $env:USERPROFILE ("Desktop\PSIP_IOP_backup_" + (Get-Date -Format 'yyyyMMdd_HHmmss'))
    New-Item -ItemType Directory -Path $backupFolder -Force | Out-Null
    $backupFile = Join-Path $backupFolder 'env-test-przed-IOP.dump'
    Write-Host "Tworze kopie zapasowa env-test ..."
    docker exec $container pg_dump -U psip -d psip -Fc -f /tmp/env-test-przed-IOP.dump
    if ($LASTEXITCODE -ne 0) { throw 'pg_dump nie powiodl sie. Przerwano.' }
    docker cp "${container}:/tmp/env-test-przed-IOP.dump" $backupFile
    if ($LASTEXITCODE -ne 0) { throw 'docker cp kopii nie powiodl sie. Przerwano.' }
    if ((Get-Item $backupFile).Length -lt 100000) {
        throw 'Podejrzanie mala kopia zapasowa. Przerwano.'
    }
    Write-Host "Kopia zapasowa: $backupFile"
    $mode = '--apply'
} else {
    Write-Host 'TRYB TESTOWY: tylko odczyt, brak zapisu do bazy.'
    $mode = '--dry-run'
}

# --no-deps: nie odtwarzamy/nie modyfikujemy kontenera PostGIS.
# Środowisko Compose -p remote-db-env-test ustawia wewnętrzny serwer postgis.
docker compose -f docker-compose-remote.yml -p remote-db-env-test --profile loader run --rm --no-deps --build -e PSIP_IOP_CONFIRM=ENV_TEST_ONLY python python3 /app/python/iop_passability.py $mode
if ($LASTEXITCODE -ne 0) { throw 'Obliczanie IOP nie powiodlo sie.' }

if ($Apply) {
    Write-Host 'GOTOWE: wyniki zapisane w grid.iop_r7/r8/r9 i grid.iop_weights na env-test.' -ForegroundColor Green
} else {
    Write-Host 'KONTROLA ZAKONCZONA: niczego nie zmieniono.' -ForegroundColor Green
}
