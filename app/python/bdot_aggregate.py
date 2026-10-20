"""Aggregate BDOT10k classes into separate attributes on each H3 level.

Creates grid.agg_h3_r7, grid.agg_h3_r8, grid.agg_h3_r9 with H3 polygons
clipped to the county boundary, and columns per BDOT layer:
  polygon => area_<layer>_m2, line => length_<layer>_m,
  point => count_<layer>.
Area & length use metric EPSG:2180; point metric counts individual points.
"""
import os
import sys

import psycopg2
from psycopg2 import sql

DB = dict(host=os.environ.get('PGHOST', 'host.docker.internal'),
          port=os.environ.get('PGPORT', '5444'),
          dbname=os.environ.get('PGDATABASE', 'psip'),
          user=os.environ.get('PGUSER', 'psip'),
          password=os.environ.get('PGPASSWORD', 'psip'))


def main():
    conn = psycopg2.connect(**DB)
    conn.autocommit = True
    with conn.cursor() as cur:
        cur.execute('''SELECT table_name, geometry_kind
                       FROM bdot._import_manifest ORDER BY table_name''')
        layers = cur.fetchall()
    if not layers:
        raise RuntimeError('Brak zaimportowanych klas BDOT10k w bdot._import_manifest')
    for r in (7, 8, 9):
        grid = f'h3_r{r}'
        aggregate = f'agg_h3_r{r}'
        print('Przygotowuję grid.' + aggregate, flush=True)
        with conn.cursor() as cur:
            # Replace only the derived aggregate, never the original H3 source.
            cur.execute(sql.SQL('DROP TABLE IF EXISTS grid.{}').format(sql.Identifier(aggregate)))
            cur.execute(sql.SQL('''CREATE TABLE grid.{} AS
                WITH county AS (
                    SELECT ST_UnaryUnion(ST_Collect(ST_Transform(geom,2180))) AS geom
                    FROM public.powiat
                ), clipped AS (
                    SELECT h.h3_id, h.resolution,
                      ST_Multi(ST_CollectionExtract(
                          ST_Intersection(h.geom, c.geom), 3
                      ))::geometry(MultiPolygon,2180) AS geom
                    FROM grid.{} AS h CROSS JOIN county AS c
                    WHERE ST_Intersects(h.geom, c.geom)
                ) SELECT * FROM clipped WHERE NOT ST_IsEmpty(geom)
            ''').format(sql.Identifier(aggregate), sql.Identifier(grid)))
            cur.execute(sql.SQL('ALTER TABLE grid.{} ADD PRIMARY KEY (h3_id)').format(sql.Identifier(aggregate)))
            cur.execute(sql.SQL('CREATE INDEX {} ON grid.{} USING GIST (geom)').format(
                sql.Identifier('ix_' + aggregate + '_geom'), sql.Identifier(aggregate)))
            cur.execute(sql.SQL('ANALYZE grid.{}').format(sql.Identifier(aggregate)))
        for tab, kind in layers:
            if kind == 'polygon':
                col, datatype = 'area_' + tab + '_m2', 'double precision'
                expr = sql.SQL('SUM(ST_Area(ST_Intersection(a.geom, ST_MakeValid(b.geom))))')
            elif kind == 'line':
                col, datatype = 'length_' + tab + '_m', 'double precision'
                expr = sql.SQL('SUM(ST_Length(ST_Intersection(a.geom, ST_MakeValid(b.geom))))')
            elif kind == 'point':
                col, datatype = 'count_' + tab, 'bigint'
                expr = sql.SQL('SUM(ST_NumGeometries(ST_Intersection(a.geom, b.geom)))')
            else:
                raise RuntimeError('Nieznany typ geometrii: ' + kind)
            if len(col.encode('utf-8')) > 63:
                raise RuntimeError('Za długa nazwa kolumny: ' + col)
            print(f'  {tab} -> {col}', flush=True)
            with conn.cursor() as cur:
                cur.execute(sql.SQL('ALTER TABLE grid.{} ADD COLUMN {} {} NOT NULL DEFAULT 0').format(
                    sql.Identifier(aggregate), sql.Identifier(col), sql.SQL(datatype)))
                cur.execute(sql.SQL('''WITH totals AS (
                    SELECT a.h3_id, {} AS value
                    FROM grid.{} AS a
                    JOIN bdot.{} AS b
                    ON a.geom && b.geom AND ST_Intersects(a.geom, b.geom)
                    GROUP BY a.h3_id
                  )
                  UPDATE grid.{} AS g SET {} = t.value
                  FROM totals AS t WHERE g.h3_id = t.h3_id''').format(
                     expr, sql.Identifier(aggregate), sql.Identifier(tab),
                     sql.Identifier(aggregate), sql.Identifier(col)))
        with conn.cursor() as cur:
            cur.execute(sql.SQL('SELECT COUNT(*) FROM grid.{}').format(sql.Identifier(aggregate)))
            print(f'ZAKOŃCZONO: grid.{aggregate} / {cur.fetchone()[0]} heksagonów', flush=True)
    conn.close()
    print('GOTOWE: agregacja H3 dla wszystkich klas BDOT10k.', flush=True)


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        print('BŁĄD AGREGACJI:', exc, file=sys.stderr)
        raise SystemExit(1)
