import os
import subprocess

import psycopg2
from psycopg2 import sql

from h3_generator import main as generate_grids
from h3_generator import SOURCE, OUTPUT, RESOLUTIONS


# Domyslne ustawienia lokalne; srodowiska CI moga je nadpisac.
environment = os.environ.copy()
defaults = {
    "PGHOST": "postgis",
    "PGPORT": "5432",
    "PGDATABASE": "psip",
    "PGUSER": "psip",
    "PGPASSWORD": "psip",
}
for key, value in defaults.items():
    environment.setdefault(key, value)


def connect():
    return psycopg2.connect(
        host=environment["PGHOST"],
        port=environment["PGPORT"],
        dbname=environment["PGDATABASE"],
        user=environment["PGUSER"],
        password=environment["PGPASSWORD"],
    )


def import_layer(path, table, target_crs):
    subprocess.run(
        [
            "ogr2ogr",
            "-f", "PostgreSQL",
            "PG:",
            str(path),
            "-nln", table,
            "-t_srs", target_crs,
            "-lco", "GEOMETRY_NAME=geom",
            "-overwrite",
        ],
        env=environment,
        check=True,
    )
    print(f"Zapisano: {table} ({target_crs})", flush=True)


def main():
    # H3 jest generowane w GeoJSON WGS84; zapis geometrii w bazie jest 3857.
    generate_grids()

    with connect() as connection:
        with connection.cursor() as cursor:
            cursor.execute("CREATE SCHEMA IF NOT EXISTS grid")

    import_layer(SOURCE, "public.powiat", "EPSG:3857")

    for resolution in RESOLUTIONS:
        name = f"h3_r{resolution}"
        path = OUTPUT / f"{name}.geojson"
        import_layer(path, f"grid.{name}", "EPSG:3857")

        with connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    sql.SQL("CREATE UNIQUE INDEX {} ON grid.{} (h3_id)").format(
                        sql.Identifier(f"{name}_h3_id_idx"),
                        sql.Identifier(name),
                    )
                )
                cursor.execute(
                    sql.SQL("CREATE INDEX {} ON grid.{} USING GIST (geom)").format(
                        sql.Identifier(f"ix_{name}_geom"),
                        sql.Identifier(name),
                    )
                )
                cursor.execute(
                    sql.SQL("SELECT COUNT(*) FROM grid.{}").format(sql.Identifier(name))
                )
                count = cursor.fetchone()[0]

        print(f"grid.{name}: {count} komorek w bazie", flush=True)

    print("Gotowe: granica i trzy siatki zapisane w EPSG:3857.", flush=True)


if __name__ == "__main__":
    main()
