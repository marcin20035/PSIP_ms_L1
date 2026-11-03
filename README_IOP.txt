PSIP / IOP H3 — ETAP TESTOWY, 3 listopada 2026 r.
=================================================

LOKALIZACJA: istniejący projekt C:\Users\hello\PSIP_ms_L1.
GAŁĄŹ GIT: pozostań na aktualnej; brak commit i push na tym etapie.
ENV: wyłącznie env-test / Docker: remote-db-env-test-postgis-1 / port 5444.
NIE WOLNO: uruchamiać plików w env-qa/main.

PODSTAWA:
K. Pokonieczny (2018), "Comparison of land passability maps created with use
of different spatial data bases", Geografie 123(3), s. 317-352:
https://geografie.cz/media/pdf/geo_2018123030317.pdf

IVRF POTWIERDZONE PRZEZ ARTYKUŁ (Tabela 1, s. 325):
    OT_PTLZ_A lasy: -0,8
    OT_PTWP_A wody powierzchniowe (przykład: jeziora): -1,0
    OT_SKDR_L drogi: +0,7
Pozostałe 61 ocen są roboczymi propozycjami eksperckimi albo założeniem
neutralności, NIE wartościami podanymi przez Pokoniecznego.

MODELOWANIE:
- 64 kryteria wejściowe BDOT10K, 19 aktywnych w modelu v1, 45 neutralnych.
- Oddzielna analiza dla H3 R7/R8/R9, każde kryterium normalizowane względem
  swojego maksimum w danej siatce nad całym powiatem:
    z_ij = x_ij / max_i(x_ij), gdy maksimum > 0; inaczej 0.
- x_ij >= 0; brak obiektów = 0 (nie traktujemy braku drogi jako "ujemnej drogi").
- IVRF_j [-1,1]: znak i siła oddziaływania, a nie waga istotności.
- priority_j >= 0: ekspercka waga istotności; przy neutralnej klasie 0.
- n = 19; w_j = priority_j * n / SUM(priority), więc SUM(w)=n.
- Surowy IOP_raw = SUM(w_j * IVRF_j * z_ij) / n.
  Matematycznie -1 <= IOP_raw <= 1, choć skrajne -1/+1 mogą nie wystąpić.
- Wskaźnik mapowy IOP = 2*(IOP_raw - min)/(max - min)-1.
  W przypadku jednakowych wartości otrzymujemy 0.
  IOP jest WZGLĘDNY dla danej rozdzielczości w powiecie;
  +1 nie gwarantuje fizycznej przejezdności, a -1 jej braku.

ODSTĘPSTWA / OGRANICZENIA:
- Oryginalna publikacja używa pól kwadratowych, a tutaj H3.
- Oryginalna publikacja przedstawia wynik 0..1; tutaj wymagana jest
  adaptacja do -1..+1, czerwony (min) -> biały (max).
- Wagi priority i pozostałe IVRF są propozycjami, do walidacji na danych.
- Nie uwzględniono rzeczywistego typu/masy pojazdu, nośności gruntu,
  nachylenia i pogody; wynik nie jest operacyjną gwarancją przejazdu.
- SKJZ_L i SKDR_L mogą dublować drogi; SKJZ jest neutralna.
- PTZB_A może dublować budynki BUBD_A; PTZB jest neutralna.
- PTWP_A i SWRS_L/SWKN_L mogą dublować wody; cieki i kanały neutralne.
- Klasy zróżnicowane wewnętrznie i informacyjne są neutralne do chwili
  weryfikacji ich podtypów, zamiast zmyślania jednej wagi dla wszystkich.
- Atrybuty powierzchni/długości już przeliczono w EPSG:2180; geometrie
  są zapisane w EPSG:3857. Nie licz powierzchni z ST_Area(geom 3857).
- Komórki na granicy powiatu są obcięte do jego zasięgu w agg_h3_r*.

PLIKI:
  MACIERZ_64_WSKAZNIKOW.csv       — do przeglądu (64 wiersze, średnik, UTF-8)
  app/python/iop_weights.json     — właściwa macierz ocen i priorytetów
  app/python/iop_passability.py  — analiza (domyślnie tylko dry-run)
  IOP_ENV_TEST.ps1                — sprawdzenie, backup i uruchomienie

URUCHOMIENIE:
  1) Rozpakuj ZIP do C:\Users\hello\PSIP_ms_L1.
  2) Otwórz PowerShell i przejdź do projektu:
       cd C:\Users\hello\PSIP_ms_L1
  3) Najpierw WYŁĄCZNIE sprawdź:
       .\IOP_ENV_TEST.ps1
     Powinno pokazać 64 klasy i 302/1885/12460 komórek.
  4) Jeśli dry-run zakończył się poprawnie i akceptujesz macierz:
       .\IOP_ENV_TEST.ps1 -Apply
     Skrypt sam zrobi świeżą kopię całej bazy na pulpicie.
  5) W QGIS, przez PostgreSQL env-test localhost:5444, dodaj:
       grid.iop_r7, grid.iop_r8, grid.iop_r9
     Styl: stopniowany, kolumna 'iop', czerwony = -1, biały = +1,
     obrys heksagonów cienki szary; CRS EPSG:3857.

EFEKT:
  grid.iop_weights — 64 klasy, oryginalny IVRF, priorytet, waga w_j,
                     źródło współczynnika, uwagi;
  grid.iop_r7/r8/r9 — 67 źródłowych pól z agg, 64 x norm_<kod>,
                      iop_raw i końcowy iop (skala mapy -1..+1).
  Tabele źródłowe BDOT i agg nie są zmieniane.

WAŻNE: skrypt SQL wykonuje zapis WYŁĄCZNIE po param. -Apply;
bez tego odczytuje metadane i maksima i nie modyfikuje bazy.

KONTROLA W PSQL PO -Apply:
  SELECT COUNT(*), MIN(iop), MAX(iop), MIN(iop_raw), MAX(iop_raw)
    FROM grid.iop_r9;
  SELECT layer, ivrf, priority, weight, source
    FROM grid.iop_weights ORDER BY layer;
