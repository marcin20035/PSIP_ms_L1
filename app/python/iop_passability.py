"""Model testowy IOP dla 64 metryk BDOT10K i H3 R7/R8/R9.

Uruchamiaj WYŁĄCZNIE w env-test. Domyślnie tryb kontroli bez zapisu.
  python3 /app/python/iop_passability.py --dry-run
  python3 /app/python/iop_passability.py --apply

Model: unormowane do [0,1] cechy x_j, IVRF_j [-1,1], priorytety p_j >= 0.
Wagi w_j = p_j * n / sum(p), n = liczba niezerowych priorytetów.
IOP_raw = sum_j(x_j * IVRF_j * w_j) / n, ograniczone do [-1,1].
IOP = 2*(IOP_raw-min)/(max-min)-1: skala względna, do wizualizacji [-1,1].
Jest to adaptacja metody Pokoniecznego 2018, nie dokładna replikacja.
"""
from __future__ import annotations

import argparse
import json
import math
import os
from pathlib import Path
import re
import sys

CONFIG_PATH = Path(__file__).with_name("iop_weights.json")
EXPECTED_COUNTS = {7: 302, 8: 1885, 9: 12460}
NAME_RE = re.compile(r"^[a-z][a-z0-9_]*$")


def ident(name):
    if not NAME_RE.fullmatch(name):
        raise ValueError(f"Niebezpieczna lub niepoprawna nazwa SQL: {name!r}")
    return '"' + name + '"'


def read_config():
    data = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    rows = data["rows"]
    if len(rows) != 64 or len({r["layer"] for r in rows}) != 64:
        raise RuntimeError("Macierz wag musi zawierać dokładnie 64 różne klasy.")
    metric_columns = set()
    for r in rows:
        code, metric = r["layer"], r["metric_column"]
        ident(code)
        ident(metric)
        ident("norm_" + code)
        if metric in metric_columns:
            raise RuntimeError("Zdublowany wskaźnik: " + metric)
        metric_columns.add(metric)
        score, importance = float(r["ivrf"]), float(r["priority"])
        if not (math.isfinite(score) and -1 <= score <= 1):
            raise RuntimeError("IVRF poza zakresem [-1,1]: " + code)
        if not (math.isfinite(importance) and importance >= 0):
            raise RuntimeError("Waga priorytetu musi być nieujemna: " + code)
        if (score == 0) != (importance == 0):
            raise RuntimeError("IVRF i priorytet muszą być jednocześnie 0 lub niezerowe: " + code)
    active = [r for r in rows if float(r["priority"]) > 0]
    if not active:
        raise RuntimeError("Brak aktywnych kryteriów.")
    n = len(active)
    total_priority = sum(float(r["priority"]) for r in active)
    for r in rows:
        r["effective_weight"] = float(r["priority"]) * n / total_priority
    if abs(sum(r["effective_weight"] for r in rows) - n) > 1e-8:
        raise RuntimeError("Błąd normalizacji wag.")
    return rows, n


def db_settings():
    return dict(host=os.environ.get("PGHOST", "postgis"),
                port=os.environ.get("PGPORT", "5432"),
                dbname=os.environ.get("PGDATABASE", "psip"),
                user=os.environ.get("PGUSER", "psip"),
                password=os.environ.get("PGPASSWORD", "psip"),
                connect_timeout=10)


def connection_preflight(conn, rows):
    """Weryfikacja 64 źródeł, portu, rozmiarów, CRS i schematu BEZ zmian."""
    with conn.cursor() as cur:
        cur.execute("SELECT current_database(), current_user")
        db, user = cur.fetchone()
        if db != "psip" or user != "psip":
            raise RuntimeError("Odmowa: oczekiwana baza psip i użytkownik psip.")
        cur.execute("SELECT to_regclass('bdot._import_manifest')")
        if cur.fetchone()[0] is None:
            raise RuntimeError("Odmowa: brak BDOT10K. To prawdopodobnie nie env-test.")
        cur.execute("SELECT table_name FROM bdot._import_manifest")
        existing_layers = {r[0] for r in cur.fetchall()}
        expected_layers = {r["layer"] for r in rows}
        if existing_layers != expected_layers:
            raise RuntimeError("Niezgodna lista 64 BDOT10K. Brakujące: " + str(sorted(expected_layers - existing_layers))
                               + "; dodatkowe: " + str(sorted(existing_layers - expected_layers)))
        for res, expected_count in EXPECTED_COUNTS.items():
            tab = f"agg_h3_r{res}"
            cur.execute("SELECT to_regclass(%s)", (f"grid.{tab}",))
            if cur.fetchone()[0] is None:
                raise RuntimeError(f"Brak grid.{tab}")
            cur.execute("SELECT column_name FROM information_schema.columns "
                        "WHERE table_schema='grid' AND table_name=%s", (tab,))
            cols = {x[0] for x in cur.fetchall()}
            missing = {r["metric_column"] for r in rows} - cols
            if missing:
                raise RuntimeError(f"grid.{tab}: brak kolumn: {', '.join(sorted(missing))}")
            cur.execute(f"SELECT COUNT(*), MIN(ST_SRID(geom)), MAX(ST_SRID(geom)) "
                        f"FROM grid.{ident(tab)}")
            size, srid_min, srid_max = cur.fetchone()
            if size != expected_count or srid_min != 3857 or srid_max != 3857:
                raise RuntimeError(f"grid.{tab}: {size} komórek, SRID={srid_min}/{srid_max}. "
                                   f"Oczekiwano {expected_count}, 3857.")
            if cur is not None:
                max_expr = ", ".join(
                    f"MAX(COALESCE({ident(r['metric_column'])},0)::double precision)"
                    for r in rows)
                cur.execute(f"SELECT {max_expr} FROM grid.{ident(tab)}")
                maxima = cur.fetchone()
                empty_active = [r["layer"] for r, mx in zip(rows, maxima)
                                if float(r["priority"]) > 0 and (mx is None or mx <= 0)]
                print(f"KONTROLA R{res}: {size} komórek, SRID 3857; "
                      f"aktywne wskaźniki z zerowym maksimum: {empty_active or 'brak'}")
    print("KONTROLA OK: 64 klasy i 3 kompletne agregacje env-test.", flush=True)


def make_create_sql(res, rows, n):
    source = ident(f"agg_h3_r{res}")
    output = ident(f"iop_r{res}")
    maxima = ",\n         ".join(
        f"MAX(COALESCE({ident(r['metric_column'])},0)::double precision) AS "
        f"{ident('max_' + r['layer'])}"
        for r in rows)
    normalized = []
    for r in rows:
        col = ident(r["metric_column"])
        maximum = ident("max_" + r["layer"])
        newcol = ident("norm_" + r["layer"])
        normalized.append(
            f"CASE WHEN m.{maximum} > 0 THEN "
            f"LEAST(1.0, GREATEST(0.0, COALESCE(a.{col},0)::double precision / m.{maximum})) "
            f"ELSE 0.0 END AS {newcol}")
    norm_select = ",\n        ".join(normalized)
    terms = [f"({r['ivrf']:.12g} * {r['effective_weight']:.12g} * "
             f"n.{ident('norm_' + r['layer'])})"
             for r in rows if r["priority"] > 0]
    raw_expr = '(' + ' + '.join(terms) + f') / {n}.0'
    return f"""CREATE TABLE grid.{output} AS
WITH maxima AS (
    SELECT {maxima}
    FROM grid.{source}
),
normalized AS (
    SELECT a.*, {norm_select}
    FROM grid.{source} a CROSS JOIN maxima m
),
scored AS (
    SELECT n.*, ({raw_expr})::double precision AS iop_raw
    FROM normalized n
)
SELECT s.*,
   CASE WHEN MAX(s.iop_raw) OVER () > MIN(s.iop_raw) OVER () THEN
      (2.0 * (s.iop_raw - MIN(s.iop_raw) OVER ()) /
       (MAX(s.iop_raw) OVER () - MIN(s.iop_raw) OVER ()) - 1.0)::double precision
   ELSE 0.0::double precision END AS iop
FROM scored s"""


def apply(conn, rows, n):
    with conn.cursor() as cur:
        # Transakcja obejmuje wszystkie 3 wyniki. W razie wyjątku rollback
        # przywróci poprzednie tabele wyjściowe.
        cur.execute("DROP TABLE IF EXISTS grid.iop_weights")
        cur.execute("""CREATE TABLE grid.iop_weights (
            layer text PRIMARY KEY,
            metric_column text UNIQUE NOT NULL,
            name_pl text NOT NULL,
            geom_kind text NOT NULL,
            ivrf double precision NOT NULL,
            priority double precision NOT NULL,
            weight double precision NOT NULL,
            source text NOT NULL,
            reason text NOT NULL,
            CONSTRAINT c_ivrf CHECK (ivrf BETWEEN -1 AND 1),
            CONSTRAINT c_priority CHECK (priority >= 0),
            CONSTRAINT c_weight CHECK (weight >= 0)
        )""")
        cur.executemany(
            "INSERT INTO grid.iop_weights "
            "(layer,metric_column,name_pl,geom_kind,ivrf,priority,weight,source,reason) "
            "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)",
            [(r["layer"],r["metric_column"],r["name_pl"],r["geom_kind"],
              r["ivrf"],r["priority"],r["effective_weight"],r["source"],r["reason"])
             for r in rows])
        for res, expected_count in EXPECTED_COUNTS.items():
            print(f"Obliczam IOP R{res}...", flush=True)
            tab = f"iop_r{res}"
            cur.execute(f"DROP TABLE IF EXISTS grid.{ident(tab)}")
            cur.execute(make_create_sql(res, rows, n))
            cur.execute(f"ALTER TABLE grid.{ident(tab)} ADD PRIMARY KEY (h3_id)")
            cur.execute(f"CREATE INDEX {ident('ix_' + tab + '_geom')} "
                        f"ON grid.{ident(tab)} USING GIST (geom)")
            cur.execute(f"ALTER TABLE grid.{ident(tab)} ADD CONSTRAINT "
                        f"{ident('chk_' + tab + '_bounds')} CHECK ("
                        "iop BETWEEN -1.00000001 AND 1.00000001 AND "
                        "iop_raw BETWEEN -1.00000001 AND 1.00000001)")
            cur.execute(f"SELECT COUNT(*), MIN(iop_raw), MAX(iop_raw), MIN(iop), MAX(iop), "
                        f"COUNT(*) FILTER (WHERE iop IS NULL OR iop_raw IS NULL) "
                        f"FROM grid.{ident(tab)}")
            count, raw_min, raw_max, io_min, io_max, nulls = cur.fetchone()
            if count != expected_count or nulls:
                raise RuntimeError(f"Niezgodna tabela {tab}: count={count}, nulls={nulls}")
            print(f"  R{res}: {count} heksagonów; surowy "
                  f"[{raw_min:.6f}, {raw_max:.6f}], skala mapy "
                  f"[{io_min:.6f}, {io_max:.6f}]", flush=True)
            cur.execute(f"ANALYZE grid.{ident(tab)}")
    conn.commit()
    print("SUKCES: 3 tabele IOP + 64 wagi zapisano TYLKO w env-test.", flush=True)


def main():
    parser = argparse.ArgumentParser(description="IOP H3 BDOT10K, tylko env-test")
    flag = parser.add_mutually_exclusive_group(required=True)
    flag.add_argument("--dry-run", action="store_true", help="wyłącznie odczyt bazy")
    flag.add_argument("--apply", action="store_true", help="zapisuje tylko grid.iop_* i grid.iop_weights")
    args = parser.parse_args()
    rows, n = read_config()
    print(f"Macierz: {len(rows)} klas, {n} aktywnych, "
          f"suma wag efektywnych={sum(r['effective_weight'] for r in rows):.8f}")
    print("Źródłowe IVRF z artykułu: PTLZ=-0.8, PTWP=-1.0, SKDR=+0.7")
    if args.apply and os.environ.get("PSIP_IOP_CONFIRM", "") != "ENV_TEST_ONLY":
        raise RuntimeError("Dla zapisu wymagane PSIP_IOP_CONFIRM=ENV_TEST_ONLY")
    import psycopg2
    conn = psycopg2.connect(**db_settings())
    try:
        connection_preflight(conn, rows)
        if args.dry_run:
            conn.rollback()  # wyłącznie odczyt, nawet bez transakcyjnego śladu
            print("DRY-RUN OK: żadna tabela nie została zmieniona.")
            return
        # Poprzedni SELECT rozpoczął transakcję. Zapis jest dalej w tej samej
        # transakcji i kończy się COMMIT tylko po pozytywnej kontroli wszystkich R.
        apply(conn, rows, n)
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print("BŁĄD IOP:", exc, file=sys.stderr)
        sys.exit(1)
