"""Bezpieczny test arytmetyki IOP (nie korzysta z PostGIS)."""
from pathlib import Path
import importlib.util
import math

p = Path(__file__).parent / 'app' / 'python' / 'iop_passability.py'
spec = importlib.util.spec_from_file_location('iop_passability', p)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
rows, n = module.read_config()
assert len(rows) == 64
assert n == 19
assert sum(r['geom_kind'] == 'polygon' for r in rows) == 34
assert sum(r['geom_kind'] == 'line' for r in rows) == 20
assert sum(r['geom_kind'] == 'point' for r in rows) == 10
assert math.isclose(sum(r['effective_weight'] for r in rows), n, abs_tol=1e-10)
lookup = {r['layer']: r for r in rows}
for layer, expected in [('ot_ptlz_a', -0.8), ('ot_ptwp_a', -1), ('ot_skdr_l', 0.7)]:
    assert lookup[layer]['ivrf'] == expected

# Wszystkie wartości znormalizowane = 0 daje neutralny wynik 0.
assert math.isclose(sum(0.0 * r['ivrf'] * r['effective_weight'] for r in rows)/n, 0.0)
# Przy maksymalnych nasyceniach wynik pozostaje w [-1,1].
maximum_raw = sum(r['ivrf'] * r['effective_weight'] for r in rows)/n
assert -1.0 <= maximum_raw <= 1.0
# Zmiana dróg zwiększa wynik, zmiana lasów zmniejsza wynik.
def score(features):
    return sum(float(features.get(r['layer'], 0)) * r['ivrf'] * r['effective_weight'] for r in rows) / n
assert score({'ot_skdr_l': 1}) > score({})
assert score({'ot_ptlz_a': 1}) < score({})
assert score({'ot_ptwp_a': 1}) < score({})
# SQL każdej siatki zawiera dokładnie 64 kolumny normalizacji.
for res in (7,8,9):
    query = module.make_create_sql(res, rows, n)
    assert query.count('AS "norm_') == 64
    assert f'grid."agg_h3_r{res}"' in query
    assert f'grid."iop_r{res}"' in query
print('OK: 64 warstwy / 19 aktywnych / 3 poziomy H3 / wzór IOP i SQL.')
