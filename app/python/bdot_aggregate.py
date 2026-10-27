"""Aggregate BDOT10k classes into attributes on each H3 level.

Output geometries are stored in EPSG:3857. Metric area and length calculations
are performed in EPSG:2180 to avoid using Web Mercator for measurements.
"""
import os
import sys

import psycopg2
from psycopg2 import sql

DB = dict(
    host=os.environ.get("PGHOST", "host.docker.internal"),
    port=os.environ.get("PGPORT", "5444"),
    dbname=os.environ.get("PGDATABASE", "psip"),
    user=os.environ.get("PGUSER", "psip"),
    password=os.environ.get("PGPASSWORD", "psip"),
)


def main():
    conn = psycopg2.connect(**DB)
    conn.autocommit = True
    with conn.cursor() as cur:
        cur.execute("SELECT table_name, geometry_kind FROM bdot._import_manifest ORDER BY table_name")
        layers = cur.fetchall()
    if not layers:
        raise RuntimeError("Brak zaimportowanych klas BDOT10k w bdot._import_manifest")

    for resolution in (7, 8, 9):
        grid = f"h3_r{resolution}"
        aggregate = f"agg_h3_r{resolution}"
        print(f"Przygotowuje grid.{aggregate}", flush=True)

        with conn.cursor() as cur:
            # Rebuild only the derived aggregate table; keep source grids and BDOT layers.
            cur.execute(sql.SQL("DROP TABLE IF EXISTS grid.{}").format(sql.Identifier(aggregate)))
            cur.execute(
                sql.SQL(
                    """CREATE TABLE grid.{} AS
                       WITH county_metric AS (
                         SELECT ST_UnaryUnion(ST_Collect(ST_Transform(geom, 2180))) AS geom
                         FROM public.powiat
                       ), clipped_metric AS (
                         SELECT h.h3_id, h.resolution,
                           ST_Multi(ST_CollectionExtract(
                             ST_Intersection(ST_Transform(h.geom, 2180), c.geom), 3
                           ))::geometry(MultiPolygon, 2180) AS geom
                         FROM grid.{} AS h CROSS JOIN county_metric AS c
                         WHERE ST_Intersects(ST_Transform(h.geom, 2180), c.geom)
                       )
                       SELECT h3_id, resolution,
                         ST_Transform(geom, 3857)::geometry(MultiPolygon, 3857) AS geom
                       FROM clipped_metric
                       WHERE NOT ST_IsEmpty(geom)"""
                ).format(sql.Identifier(aggregate), sql.Identifier(grid))
            )
            cur.execute(sql.SQL("ALTER TABLE grid.{} ADD PRIMARY KEY (h3_id)").format(sql.Identifier(aggregate)))
            cur.execute(
                sql.SQL("CREATE INDEX {} ON grid.{} USING GIST (geom)").format(
                    sql.Identifier("ix_" + aggregate + "_geom"), sql.Identifier(aggregate)
                )
            )
            cur.execute(sql.SQL("ANALYZE grid.{}").format(sql.Identifier(aggregate)))

        for table, kind in layers:
            if kind == "polygon":
                column, datatype = "area_" + table + "_m2", "double precision"
                expression = sql.SQL(
                    "SUM(ST_Area(ST_Intersection(ST_Transform(a.geom, 2180), "
                    "ST_Transform(ST_MakeValid(b.geom), 2180))))"
                )
            elif kind == "line":
                column, datatype = "length_" + table + "_m", "double precision"
                expression = sql.SQL(
                    "SUM(ST_Length(ST_Intersection(ST_Transform(a.geom, 2180), "
                    "ST_Transform(ST_MakeValid(b.geom), 2180))))"
                )
            elif kind == "point":
                column, datatype = "count_" + table, "bigint"
                expression = sql.SQL(
                    "SUM(ST_NumGeometries(ST_Intersection(ST_Transform(a.geom, 2180), "
                    "ST_Transform(b.geom, 2180))))"
                )
            else:
                raise RuntimeError("Nieznany typ geometrii: " + kind)

            if len(column.encode("utf-8")) > 63:
                raise RuntimeError("Za dluga nazwa kolumny: " + column)
            print(f"  {table} -> {column}", flush=True)

            with conn.cursor() as cur:
                cur.execute(
                    sql.SQL("ALTER TABLE grid.{} ADD COLUMN {} {} NOT NULL DEFAULT 0").format(
                        sql.Identifier(aggregate), sql.Identifier(column), sql.SQL(datatype)
                    )
                )
                cur.execute(
                    sql.SQL(
                        """WITH totals AS (
                             SELECT a.h3_id, {} AS value
                             FROM grid.{} AS a
                             JOIN bdot.{} AS b
                               ON a.geom && b.geom AND ST_Intersects(a.geom, b.geom)
                             GROUP BY a.h3_id
                           )
                           UPDATE grid.{} AS g SET {} = t.value
                           FROM totals AS t WHERE g.h3_id = t.h3_id"""
                    ).format(
                        expression,
                        sql.Identifier(aggregate),
                        sql.Identifier(table),
                        sql.Identifier(aggregate),
                        sql.Identifier(column),
                    )
                )

        with conn.cursor() as cur:
            cur.execute(sql.SQL("SELECT COUNT(*) FROM grid.{}").format(sql.Identifier(aggregate)))
            count = cur.fetchone()[0]
            cur.execute(sql.SQL("ANALYZE grid.{}").format(sql.Identifier(aggregate)))
            print(f"ZAKONCZONO: grid.{aggregate} / {count} heksagonow (EPSG:3857)", flush=True)

    conn.close()
    print("GOTOWE: agregacja H3; geometrie 3857, pomiary metryczne 2180.", flush=True)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print("BLAD AGREGACJI:", exc, file=sys.stderr)
        raise SystemExit(1)
