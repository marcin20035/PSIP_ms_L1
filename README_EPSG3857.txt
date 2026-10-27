PSIP_ms_L1 — poprawka EPSG:3857

Zakres zmian
- app/python/load.py: public.powiat i grid.h3_r7/r8/r9 zapisywane w EPSG:3857.
- app/python/bdot_import.py: nowe importy BDOT10K zapisywane w EPSG:3857.
- app/python/bdot_aggregate.py: geometrie wynikowe agg_h3_r7/r8/r9 w EPSG:3857; powierzchnie i dlugosci liczone po transformacji do EPSG:2180.
- app/sql/migrate_geometry_to_3857.sql: migracja istniejacych kolumn geometry.

WAZNE
1. Najpierw wykonaj kopie zapasowe baz env-test, env-qa i main.
2. Nie uruchamiaj automatyzacji w ciemno ani nie kasuj wolumenow Dockera.
3. Wykonaj migracje SQL osobno na kazdej bazie.
4. Na env-test po migracji uruchom zaktualizowany bdot_aggregate.py, aby odtworzyc agregacje.
5. Sprawdz SRID w public.geometry_columns oraz liczby komorek: r7=302, r8=1885, r9=12460.

Plik h3_generator.py nie wymaga zmiany: GeoJSON generowany dla biblioteki H3 ma wspolrzedne lon/lat (WGS84). Dopiero import do PostGIS transformuje geometrie do EPSG:3857.
