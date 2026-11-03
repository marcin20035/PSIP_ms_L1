"""IOP v2: exclusive area coverage; env-test only. No v1 writes."""
import csv, json, subprocess, sys, pathlib, hashlib
import psycopg2

ROOT = pathlib.Path(__file__).resolve().parents[2]
OUT = pathlib.Path(sys.argv[1]).resolve()
OUT.mkdir(parents=True, exist_ok=True)
CONTAINER = 'remote-db-env-test-postgis-1'
info = json.loads(subprocess.check_output(['docker','inspect',CONTAINER]))[0]
assert info['Name'] == '/'+CONTAINER
assert any(m.get('Name') == 'remote-db-env-test-pgdata' for m in info['Mounts'])
assert any(p['HostPort']=='5444' for p in info['NetworkSettings']['Ports']['5432/tcp'])
env = dict(e.split('=',1) for e in info['Config']['Env'])
conn = psycopg2.connect(host='localhost',port=5444,dbname=env['POSTGRES_DB'],user=env['POSTGRES_USER'],password=env['POSTGRES_PASSWORD'])
cur = conn.cursor()
cur.execute("SET statement_timeout='180s'; SET lock_timeout='5s'")
cur.execute("SELECT jpt_kod_je FROM public.powiat")
assert {r[0] for r in cur.fetchall()} == {'1412'}
rows = json.loads((ROOT/'app/python/iop_weights.json').read_text(encoding='utf-8'))['rows']
assert len(rows)==64
# Order is explicit spatial precedence. Every square metre contributes ONCE.
# Scenario coefficients, not probabilities or validated vehicle performance.
groups = [
 ('hard',-1.0,['ot_bubd_a','ot_ptwp_a','ot_buzt_a']),
 ('wet',-.9,['ot_oimk_a','ot_oisz_a']),
 ('urban',-.65,['ot_ptzb_a']),
 ('forest',-.8,['ot_ptlz_a']),
 ('excavation',-.75,['ot_ptwz_a']),
 ('waste',-.7,['ot_ptso_a']),
 ('shrub',-.55,['ot_ptrk_a']),
 ('orchard',-.45,['ot_ptut_a']),
 ('square',.45,['ot_ptpl_a']),
 ('grass',.25,['ot_pttr_a']),
 ('unused',.2,['ot_ptgn_a']),
 ('other_open',.15,['ot_ptnz_a'])]
active = {t:(name,val) for name,val,tables in groups for t in tables}
barriers = ['ot_biub_l','ot_buhd_l','ot_buuo_l','ot_buzm_l','ot_sktr_l','ot_swkn_l','ot_swrm_l','ot_swrs_l']

def export(name, sql):
    cur.execute(sql)
    with (OUT/name).open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.writer(f,delimiter=';'); w.writerow([d.name for d in cur.description]); w.writerows(cur.fetchall())

def fingerprints():
    result={}
    for r in (7,8,9):
        cur.execute(f"SELECT count(*),md5(string_agg(h3_id::text||':'||iop::text||':'||iop_raw::text,'|' ORDER BY h3_id)) FROM grid.iop_r{r}")
        result[r]=cur.fetchone()
    return result

before=fingerprints()
(OUT/'v1_before.json').write_text(json.dumps(before),encoding='utf-8')
audit=[]
for row in rows:
    t=row['layer']; reason=row['reason']; role='excluded'; coefficient=None
    if t in active:
        role,coefficient=active[t]
        reason='Udzial rzeczywistej powierzchni po unii i odjeciu grup wyzszego priorytetu; wspolczynnik scenariuszowy.'
        if role=='urban': reason+=' PTZB bez obrysow budynkow i innych przeszkod juz policzonych: bez podwojnego liczenia.'
    elif t=='ot_skdr_l': role='road_only'; reason='Osobno km drog/km2 i obecność drogi. Nie podnosi IOP pozadrogowego; gestosc nie dowodzi przejazdu.'
    elif t in barriers: role='barrier_flag'; reason='Flaga i gestosc potencjalnej bariery; bez arbitralnego bufora i kary. Brak szerokosci/wysokosci oraz topologii przejsc.'
    elif t.startswith('ot_ku'): reason='Kompleks funkcjonalny: nie oznacza jednolitej przeszkody; geometria zabudowy/pokrycia jest liczona osobno.'
    elif t.startswith('ot_oi'): reason+=' Nie przyjmujemy liczby obiektow jako powierzchni ani nieznanego podtypu jako bariery.'
    elif t=='ot_suln_l': reason='Linia napowietrzna nie blokuje calego pasa terenu; brak obrysu slupow i przeswitu.'
    elif t=='ot_supr_l': reason='Przewod moze byc podziemny; bez polozenia i wymiarow nie tworzymy bariery.'
    cur.execute(f'SELECT count(*) FROM bdot.{t}'); count=cur.fetchone()[0]
    cur.execute("SELECT column_name FROM information_schema.columns WHERE table_schema='bdot' AND table_name=%s AND column_name='rodzaj'",(t,))
    types=''
    if cur.fetchone():
        cur.execute(f'SELECT rodzaj,count(*) FROM bdot.{t} GROUP BY 1 ORDER BY 2 DESC')
        types=json.dumps(cur.fetchall(),ensure_ascii=False)
    audit.append([t,row['name_pl'],row['ivrf'],row['priority'],role,coefficient,count,reason,types])
with (OUT/'IOP_V2_ANALIZA_64.csv').open('w',encoding='utf-8-sig',newline='') as f:
    w=csv.writer(f,delimiter=';'); w.writerow(['layer','name_v1','ivrf_v1','priority_v1','role_v2','coefficient_v2','objects','reason','observed_types']); w.writerows(audit)
print('Audyt 64 klas gotowy',flush=True)
# Transform source geometry once; temporary tables disappear on disconnect.
for name,val,tables in groups:
    query=' UNION ALL '.join(f'SELECT ST_Transform(ST_MakeValid(geom),2180) geom FROM bdot.{t}' for t in tables)
    cur.execute(f'CREATE TEMP TABLE src_{name} AS {query}; CREATE INDEX ON src_{name} USING gist(geom); ANALYZE src_{name}')
sql_log=[]
for res,expected in [(7,302),(8,1885),(9,12460)]:
    print(f'Obliczam R{res}',flush=True)
    cur.execute(f'SELECT count(*) FROM grid.agg_h3_r{res}'); assert cur.fetchone()[0]==expected
    cur.execute(f'''CREATE TEMP TABLE cells AS SELECT h3_id, ST_Transform(geom,2180) g,
        ST_Area(ST_Transform(geom,2180)) area_m2,
        ST_GeomFromText('POLYGON EMPTY',2180) used, 0.0::double precision score
        FROM grid.agg_h3_r{res}; CREATE INDEX ON cells USING gist(g)''')
    for name,val,tables in groups:
        cur.execute(f'ALTER TABLE cells ADD COLUMN fraction_{name} double precision NOT NULL DEFAULT 0')
        cur.execute(f'''WITH clips AS (
          SELECT c.h3_id, ST_UnaryUnion(ST_Collect(ST_Intersection(c.g,b.geom))) geom
          FROM cells c JOIN src_{name} b ON c.g && b.geom AND ST_Intersects(c.g,b.geom)
          GROUP BY c.h3_id
        ), exclusive AS (
          SELECT c.h3_id,ST_Difference(p.geom,c.used) geom FROM cells c JOIN clips p USING(h3_id)
        ) UPDATE cells c SET fraction_{name}=ST_Area(e.geom)/NULLIF(c.area_m2,0),
          score=c.score+({val})*ST_Area(e.geom)/NULLIF(c.area_m2,0),
          used=ST_Union(c.used,e.geom) FROM exclusive e WHERE c.h3_id=e.h3_id''')
    fractions=','.join('c.fraction_'+g[0] for g in groups)
    barrier_sum='+'.join('COALESCE(a.length_'+t+'_m,0)' for t in barriers)
    query=f'''CREATE TABLE grid.iop_v2_r{res} AS SELECT a.*, c.area_m2,{fractions},
       GREATEST(0,1-ST_Area(c.used)/c.area_m2) AS unknown_fraction,
       c.score AS iop_offroad,c.score AS iop,
       a.length_ot_skdr_l_m/1000/(c.area_m2/1e6) AS road_km_km2,
       a.length_ot_skdr_l_m>0 AS has_road,
       ({barrier_sum})>0 AS barrier_present,
       ({barrier_sum})/1000/(c.area_m2/1e6) AS barrier_km_km2,
       'screening_v2_unvalidated'::text AS model_status
       FROM grid.agg_h3_r{res} a JOIN cells c USING(h3_id)'''
    # Intentionally fail rather than overwrite an existing v2 run.
    cur.execute(query); sql_log.append(query+';')
    cur.execute(f'''ALTER TABLE grid.iop_v2_r{res} ADD PRIMARY KEY(h3_id);
      ALTER TABLE grid.iop_v2_r{res} ADD CHECK(iop BETWEEN -1.00000001 AND 1.00000001 AND area_m2>0);
      CREATE INDEX ON grid.iop_v2_r{res} USING gist(geom)''')
    cur.execute(f'SELECT count(*),count(*) FILTER(WHERE iop IS NULL),min(iop),max(iop) FROM grid.iop_v2_r{res}')
    result=cur.fetchone(); assert result[0]==expected and result[1]==0; print(result,flush=True)
    cur.execute('DROP TABLE cells')
assert fingerprints()==before
queries=[]
for r in (7,8,9):
    queries.append(f'''SELECT {r} resolution,count(*) cells,sum(n.area_m2)/1e6 area_km2,
      min(n.iop) min_v2,max(n.iop) max_v2,sum(n.iop*n.area_m2)/sum(n.area_m2) area_mean_v2,
      avg(o.iop) mean_v1,avg(n.iop) mean_v2,corr(o.iop,n.iop) correlation,
      count(*) FILTER(WHERE n.fraction_urban+n.fraction_hard>=.5) built_or_hard_cells,
      avg(n.iop) FILTER(WHERE n.fraction_urban>=.5) urban_v2,
      avg(o.iop) FILTER(WHERE n.fraction_urban>=.5) urban_v1,
      count(*) FILTER(WHERE n.barrier_present) barrier_cells,
      sum(n.unknown_fraction*n.area_m2)/sum(n.area_m2) unknown_area_fraction
      FROM grid.iop_v2_r{r} n JOIN grid.iop_r{r} o USING(h3_id)''')
comparison=' UNION ALL '.join(queries)
export('POROWNANIE_R7_R8_R9.csv',comparison)
coverage=[]
for r in (7,8,9):
    coverage.append(f'''SELECT {r} resolution,ST_Area(ST_SymDifference(g.geom,p.geom)) missing_or_extra_m2
      FROM (SELECT ST_UnaryUnion(ST_Collect(ST_Transform(geom,2180))) geom FROM grid.iop_v2_r{r}) g
      CROSS JOIN (SELECT ST_UnaryUnion(ST_Collect(ST_Transform(geom,2180))) geom FROM public.powiat) p''')
export('KONTROLA_ZASIEGU.csv',' UNION ALL '.join(coverage))
cur.execute(' UNION ALL '.join(coverage)); assert all(v<1 for r,v in cur.fetchall())
(OUT/'KONTROLA_SQL.sql').write_text(comparison+';\n'+' UNION ALL '.join(coverage)+';',encoding='utf-8')
conn.commit()
(OUT/'v1_after.json').write_text(json.dumps(fingerprints()),encoding='utf-8')
conn.close()
print('COMMIT OK: tylko grid.iop_v2_r7/r8/r9; v1 bez zmian.',flush=True)
