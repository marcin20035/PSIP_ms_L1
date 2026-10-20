# PSIP_ms_L1 / env-test
# This script uses Docker Desktop and updates BDOT tables and derived H3 aggregates.
# It does not replace public.powiat or grid.h3_r7/r8/r9.
$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
$repo = (Get-Location).Path
$dataDir = Join-Path $repo 'data'
$bdotDir = Join-Path $dataDir 'bdot10k'
New-Item -ItemType Directory -Force -Path $bdotDir | Out-Null

$gitignore = Join-Path $repo '.gitignore'
if (!(Test-Path $gitignore)) {
    New-Item -ItemType File -Path $gitignore | Out-Null
}
if (-not (Get-Content $gitignore | Where-Object { $_.Trim() -eq 'data/bdot10k/' })) {
    Add-Content -Path $gitignore -Value 'data/bdot10k/'
}

Write-Host 'Sprawdzam kontener PostGIS...' -ForegroundColor Cyan
$running = docker inspect remote-db-env-test-postgis-1 --format '{{.State.Running}}' 2>$null
if ($LASTEXITCODE -ne 0 -or $running.Trim() -ne 'true') {
    throw 'Kontener remote-db-env-test-postgis-1 nie dziala. Uruchom Docker Desktop.'
}

$files = @(Get-ChildItem -Path $bdotDir -Recurse -File |
    Where-Object { $_.Extension -in '.gpkg', '.shp' })
if ($files.Count -eq 0) {
    Write-Host 'Brak rozpakowanych danych BDOT10K. Probuje pobrac paczke powiatowa...' -ForegroundColor Cyan
    docker run --rm `
        --mount "type=bind,source=$repo\app,target=/app,readonly" `
        --mount "type=bind,source=$dataDir,target=/data" `
        psip_ms_l1-python python3 /app/python/bdot_download.py --out /data/bdot10k
    if ($LASTEXITCODE -ne 0) {
        throw 'Nie udalo sie pobrac BDOT10K. Sprawdz komunikat pobierania powyzej.'
    }
}

Write-Host 'Importuje BDOT10K do env-test (port 5444)...' -ForegroundColor Cyan
docker compose -f docker-compose-local.yml exec -T `
    -e PGHOST=host.docker.internal -e PGPORT=5444 `
    python python3 /app/python/bdot_import.py
if ($LASTEXITCODE -ne 0) {
    throw 'Import BDOT10K zakonczyl sie bledem.'
}

Write-Host 'Wykonuje agregacje BDOT10K w siatkach H3...' -ForegroundColor Cyan
docker compose -f docker-compose-local.yml exec -T `
    -e PGHOST=host.docker.internal -e PGPORT=5444 `
    python python3 /app/python/bdot_aggregate.py
if ($LASTEXITCODE -ne 0) {
    throw 'Agregacja BDOT10K zakonczyla sie bledem.'
}

Write-Host 'Sprawdzam tabele wynikowe...' -ForegroundColor Cyan
docker exec remote-db-env-test-postgis-1 psql -U psip -d psip -c `
    'SELECT ''agg_h3_r7'' AS tabela, COUNT(*) AS komorki FROM grid.agg_h3_r7 UNION ALL SELECT ''agg_h3_r8'', COUNT(*) FROM grid.agg_h3_r8 UNION ALL SELECT ''agg_h3_r9'', COUNT(*) FROM grid.agg_h3_r9;'
if ($LASTEXITCODE -ne 0) {
    throw 'Blad kontroli tabel wynikowych.'
}
Write-Host 'Gotowe! QGIS: PSIP Remote -> grid -> agg_h3_r7 / r8 / r9' -ForegroundColor Green
