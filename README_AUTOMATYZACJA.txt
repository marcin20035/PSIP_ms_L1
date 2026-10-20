PSIP_ms_L1 — krok 35: automatyczne ładowanie H3 przez GitHub Actions

Pracuj w: C:\Users\hello\PSIP_ms_L1 (branch env-test).

ZAWARTOSC:
- docker-compose-remote.yml - nowa kompletna wersja (zastepuje poprzednia)
- .github/workflows/start_services.yml - nowa kompletna wersja (zastepuje poprzednia)
- docker/python/Dockerfile.remote - NOWY plik
- .dockerignore - NOWY plik

ZASADA BEZPIECZENSTWA:
Nie modyfikujemy lokalnego docker-compose-local.yml ani bazy env-test.
Workflow nie rusza istniejacych grid.h3_r7/r8/r9, jesli wszystkie sa obecne.
Nie rusza bdot.* ani grid.agg_h3_r7/r8/r9.
Jesli wykryje 1 lub 2 tabele H3, konczy sie bledem bez ich nadpisywania.
Na pustej bazie tworzy tabele H3 przez app/python/load.py.
Weryfikuje liczbe wierszy 302, 1885, 12460.

UWAGA:
Ten etap automatyzuje H3. BDOT10K i agregacje sa juz wykonane na env-test,
nie sa wykonywane automatycznie tym workflow.
Gałęzie env-qa i main muszą otrzymać zmiany w osobnym kontrolowanym etapie.
Sekrety POSTGRES_USER, POSTGRES_PASSWORD, POSTGRES_DB, POSTGRES_PORT
muszą istnieć dla każdego środowiska i porty muszą być unikatowe.

Zalecane dalsze kroki: najpierw wyswietl git diff i git status,
nastepnie zatwierdz/env-test; nie wypychaj jeszcze na env-qa/main.
