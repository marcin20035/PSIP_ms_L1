PSIP / ZADANIE 2 – BDOT10K POWIAT MIŃSKI (TERYT 1412)
==================================================

STATUS: SKRYPTY PRZYGOTOWANE I SPRAWDZONE SKŁADNIOWO, ALE NIE WYKONANE
NA TWOIM KOMPUTERZE. W TYM ŚRODOWISKU NIE UDAŁO SIĘ POBRAĆ PACZKI BDOT10K
Z SERWERA GUGiK, WIĘC POBIERANIE WYMAGA TESTU W TWOIM DOCKERZE.

OFICJALNE DANE: https://www.geoportal.gov.pl/pl/dane/baza-danych-obiektow-topograficznych-bdot10k/
Bezpośredni ZIP: https://opendata.geoportal.gov.pl/bdot10k/schemat2021/GPKG/14/1412_GPKG.zip
Adres ustalony z kodu wtyczki QGIS marylaGIS/bdot10k (task_dwnl_bdot.py).

CO ZAWIERA PACZKA:
- app/python/bdot_download.py – pobiera bezpośrednio paczkę GPKG powiatu 1412
  z oficjalnego adresu GUGiK i rozpakowuje ZIP do data/bdot10k.
- app/python/bdot_import.py – importuje wszystkie rozpoznane klasy
  przestrzenne SHP/GPKG do schematu bdot w env-test (EPSG:2180).
- app/python/bdot_aggregate.py – dla każdego poziomu H3 oblicza
  w osobnych kolumnach powierzchnie [m2], długości [m] i liczbę punktów.
  Wyniki: grid.agg_h3_r7, grid.agg_h3_r8, grid.agg_h3_r9.
- run_bdot_env_test.ps1 – łączy etapy (zdalna baza port 5444).

JAK UŻYĆ (bez usuwania obecnych baz):
1. Rozpakuj tę paczkę do C:\Users\hello\PSIP_ms_L1, zachowując strukturę
   katalogów. Nowe pliki mają zostać dodane, a istniejące nie są zmieniane.
2. Uruchom Docker Desktop; w PowerShell sprawdź: docker ps
3. Wejdź do repo: cd C:\Users\hello\PSIP_ms_L1
4. Uruchom:
   powershell -ExecutionPolicy Bypass -File .\run_bdot_env_test.ps1
5. Jeżeli automatyczne pobieranie się nie uda (Geoportal może zmienić adres paczki),
   pobierz paczkę *powiatową* GPKG/SHP dla powiatu mińskiego (1412) z mapy
   Geoportalu, zapisz w data\bdot10k\ i rozpakuj do
   data\bdot10k\extracted\. Wykonaj ponownie polecenie z pkt 4.

UWAGA:
- Skrypt importer używa operacji -overwrite wyłącznie na tabelach bdot,
  które importuje. Agregator odtwarza wyłącznie grid.agg_h3_r7/r8/r9.
  Nie modyfikuje istniejących grid.h3_r7/r8/r9 ani public.powiat.
- Dockerowy python używa domyślnie psip/psip. Jeśli env-test ma inne
  hasło, przed uruchomieniem dostosuj bezpiecznie konfigurację połączenia.
- W repozytorium dodaj do .gitignore linię: data/bdot10k/
  Surowe dane BDOT10K mogą być duże; nie dodawaj ich przez git add .
- Paczka dotyczy etapu pobrania/importu/agregacji na środowisku env-test.
  Automatyczne uruchamianie load.py na env-qa i main przez Actions
  wymaga osobnej rozbudowy workflow i oddzielnych ustawień środowisk.
- Geometryczne granice H3 w grid.agg_h3_* są obcięte do granicy powiatu.
- Agregacja punktów zlicza geometrie punktowe w komórce; punkty na
  wspólnej granicy sąsiadujących komórek mogą zostać naliczone obu.
- Źródło danych: Główny Urząd Geodezji i Kartografii / Geoportal.gov.pl.
