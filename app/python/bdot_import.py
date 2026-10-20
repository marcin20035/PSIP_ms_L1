"""Import county BDOT10k layers into env-test PostgreSQL schema bdot.

Expected: archive downloaded/unpacked under /data/bdot10k, PostGIS reachable
via PGHOST, PGPORT, PGDATABASE, PGUSER and PGPASSWORD environment variables.
Existing grids / public.powiat are not modified.
"""
import os
import re
import subprocess
import sys
from pathlib import Path

from osgeo import ogr
import psycopg2
from psycopg2 import sql

ROOT = Path(os.environ.get('BDOT_DIR', '/data/bdot10k'))
DB = dict(
    host=os.environ.get('PGHOST', 'host.docker.internal'),
    port=os.environ.get('PGPORT', '5444'),
    dbname=os.environ.get('PGDATABASE', 'psip'),
    user=os.environ.get('PGUSER', 'psip'),
    password=os.environ.get('PGPASSWORD', 'psip'),
)


def valid_name(name):
    stem = re.sub(r'[^a-z0-9_]', '_', name.lower())
    stem = re.sub(r'_+', '_', stem).strip('_')
    return stem[:58]  # PostgreSQL 63 byte identifier limit


def geom_kind(ogr_type):
    flat = ogr.GT_Flatten(ogr_type)
    if flat in (ogr.wkbPolygon, ogr.wkbMultiPolygon):
        return 'polygon'
    if flat in (ogr.wkbLineString, ogr.wkbMultiLineString):
        return 'line'
    if flat in (ogr.wkbPoint, ogr.wkbMultiPoint):
        return 'point'
    return None


def sources():
    if not ROOT.is_dir():
        raise RuntimeError('Brak katalogu /data/bdot10k z danymi GUGiK')
    gpkg_files = sorted(ROOT.rglob('*.gpkg'))
    # Prefer GeoPackage over shapefiles if the package contains both formats.
    if gpkg_files:
        return gpkg_files
    return sorted(ROOT.rglob('*.shp'))


def pg_env():
    env = os.environ.copy()
    for k, v in [('PGHOST', DB['host']), ('PGPORT', DB['port']),
                 ('PGDATABASE', DB['dbname']), ('PGUSER', DB['user']),
                 ('PGPASSWORD', DB['password'])]:
        env[k] = v
    return env


def main():
    ogr.UseExceptions()
    found = sources()
    if not found:
        raise RuntimeError('Nie znaleziono *.gpkg ani *.shp. Najpierw pobierz i rozpakuj powiatową paczkę BDOT10k.')

    conn = psycopg2.connect(**DB)
    conn.autocommit = True
    with conn.cursor() as cur:
        cur.execute('CREATE SCHEMA IF NOT EXISTS bdot')
        cur.execute('''CREATE TABLE IF NOT EXISTS bdot._import_manifest (
            table_name text PRIMARY KEY, source_name text NOT NULL,
            source_layer text NOT NULL, geometry_kind text NOT NULL,
            imported_at timestamptz NOT NULL DEFAULT now()
        )''')

    loaded = 0
    used = set()
    for file in found:
        dataset = ogr.Open(str(file))
        if dataset is None:
            print('Pomijam plik (OGR nie otworzył):', file, flush=True)
            continue
        for i in range(dataset.GetLayerCount()):
            layer = dataset.GetLayerByIndex(i)
            layer_name = layer.GetName()
            kind = geom_kind(layer.GetGeomType())
            if kind is None:
                print('Pomijam klasę bez obsługiwanej geometrii:', layer_name, flush=True)
                continue
            if not layer.GetSpatialRef():
                raise RuntimeError(f'Warstwa bez układu współrzędnych: {file} / {layer_name}')
            name = valid_name(layer_name if file.suffix.lower() == '.gpkg' else file.stem)
            if not name:
                raise RuntimeError(f'Niepoprawna nazwa warstwy: {layer_name}')
            if name in used:
                raise RuntimeError(f'Powtarza się nazwa docelowej tabeli bdot.{name}. '
                                   'Użyj paczki jednego powiatu i jednego formatu.')
            used.add(name)
            cmd = ['ogr2ogr', '-f', 'PostgreSQL', 'PG:', str(file),
                   '-nln', f'bdot.{name}', '-t_srs', 'EPSG:2180',
                   '-lco', 'GEOMETRY_NAME=geom', '-overwrite', '-progress']
            if file.suffix.lower() == '.gpkg':
                cmd.append(layer_name)
            print(f'Import {layer_name} -> bdot.{name} ({kind})', flush=True)
            subprocess.run(cmd, env=pg_env(), check=True)
            with conn.cursor() as cur:
                cur.execute(sql.SQL('CREATE INDEX IF NOT EXISTS {} ON {}.{} USING GIST (geom)').format(
                    sql.Identifier('ix_' + name[:50] + '_geom'), sql.Identifier('bdot'), sql.Identifier(name)))
                cur.execute(sql.SQL('ANALYZE {}.{}').format(sql.Identifier('bdot'), sql.Identifier(name)))
                cur.execute('''INSERT INTO bdot._import_manifest
                    (table_name, source_name, source_layer, geometry_kind, imported_at)
                    VALUES (%s,%s,%s,%s,now())
                    ON CONFLICT (table_name) DO UPDATE SET
                        source_name=excluded.source_name,
                        source_layer=excluded.source_layer,
                        geometry_kind=excluded.geometry_kind,
                        imported_at=now()''',
                    (name, str(file.relative_to(ROOT)), layer_name, kind))
            loaded += 1
    conn.close()
    if loaded == 0:
        raise RuntimeError('Nie znaleziono żadnej klasy przestrzennej BDOT10k do importu.')
    print(f'GOTOWE: {loaded} klas BDOT10k w schemacie bdot.', flush=True)


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        print('BŁĄD IMPORTU:', exc, file=sys.stderr)
        raise SystemExit(1)
