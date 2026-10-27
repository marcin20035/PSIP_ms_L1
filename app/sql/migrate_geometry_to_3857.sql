-- Migracja geometrii z EPSG:2180 / EPSG:4326 do EPSG:3857.
-- Celowo nie zmienia wartosci atrybutow agregacji; po migracji env-test nalezy
-- uruchomic zaktualizowany bdot_aggregate.py, aby odtworzyc warstwy agg_h3_r7/r8/r9.
BEGIN;
SET LOCAL lock_timeout = '30s';

DO $migration$
DECLARE
    item record;
    remaining integer;
BEGIN
    FOR item IN
        SELECT f_table_schema, f_table_name, f_geometry_column, srid, type
        FROM public.geometry_columns
        WHERE f_table_schema IN ('bdot', 'grid')
           OR (f_table_schema = 'public' AND f_table_name = 'powiat')
        ORDER BY f_table_schema, f_table_name
    LOOP
        IF item.srid = 3857 THEN
            CONTINUE;
        END IF;

        IF item.srid NOT IN (2180, 4326) THEN
            RAISE EXCEPTION 'Nieoczekiwany SRID % w %.%.%; przerwano bez zatwierdzenia zmian',
                item.srid, item.f_table_schema, item.f_table_name, item.f_geometry_column;
        END IF;

        IF item.type !~ '^[A-Z0-9]+$' THEN
            RAISE EXCEPTION 'Nieoczekiwany typ geometrii % w %.%',
                item.type, item.f_table_schema, item.f_table_name;
        END IF;

        RAISE NOTICE 'Przeliczam %.% (% -> 3857)', item.f_table_schema, item.f_table_name, item.srid;
        EXECUTE format(
            'ALTER TABLE %I.%I ALTER COLUMN %I TYPE geometry(%s,3857) USING ST_Transform(%I,3857)',
            item.f_table_schema, item.f_table_name, item.f_geometry_column, item.type, item.f_geometry_column
        );
        EXECUTE format('ANALYZE %I.%I', item.f_table_schema, item.f_table_name);
    END LOOP;

    SELECT count(*) INTO remaining
    FROM public.geometry_columns
    WHERE (f_table_schema IN ('bdot', 'grid')
       OR (f_table_schema = 'public' AND f_table_name = 'powiat'))
      AND srid <> 3857;

    IF remaining <> 0 THEN
        RAISE EXCEPTION 'Po migracji pozostalo % kolumn geometrii poza EPSG:3857', remaining;
    END IF;
END
$migration$;

COMMIT;
