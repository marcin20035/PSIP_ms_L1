# IOP v2 — powiat miński, env-test

Wynik jest scenariuszowym wskaźnikiem warunków pozadrogowych, a nie procentem przejezdności ani trasą przejazdu. Współczynniki wymagają walidacji dla pojazdu, pogody, gruntu i nachylenia. Nie przedstawiamy v2 jako wiernej implementacji publikacji.

## Zmiana modelu

W v1 19/64 klas miało wagę niezerową. Raport z pulpitu zawiera 192 rekordy, po 64 dla R7/R8/R9. Średni dodatni wkład dróg przewyższał bezwzględny wkład budynków 4,85 / 6,71 / 8,81 razy. PTZB było pomijane, mimo występowania w 281 / 1468 / 5909 komórkach. Normalizacja do maksimum klasy, a potem rozciąganie wyniku do [-1,+1], utrudniały interpretację między siatkami.

V2 liczy `IOP = suma(udział powierzchni rozłącznej grupy × współczynnik grupy)`. Powierzchnie i przecięcia liczone są w EPSG:2180, geometria wynikowa pozostaje w EPSG:3857. Nie ma normalizacji do maksimum ani dopasowywania kolorów. Każdy metr kwadratowy trafia tylko do jednej grupy. Priorytet przestrzenny jest jawny, ale scenariuszowy: hard → wet → urban → forest → excavation → waste → shrub → orchard → square → grass → unused → other_open. Pierwsza grupa zajmująca dany fragment wygrywa. To usuwa podwójne liczenie również wewnątrz grup (unia geometrii).

Współczynniki: budynki/wody/zbiorniki −1; mokradła/szuwary −0,9; pozostała zabudowa −0,65; las −0,8; wyrobiska −0,75; składowiska −0,7; krzewy −0,55; uprawy trwałe −0,45; place +0,45; trawy/uprawy +0,25; grunty nieużytkowane +0,2; inne niezabudowane +0,15. Nieznane pokrycie wnosi 0 i jest pokazane osobno jako `unknown_fraction`; zero nie jest dowodem dobrych warunków.

`iop` i `iop_offroad` są identycznym wynikiem pozadrogowym. `fraction_*` ujawniają skład wyniku. `road_km_km2` i `has_road` pokazują sieć drogową osobno, bez dodatniego wpływu na IOP. Nie wyznaczono przejezdności tras: wymaga to połączeń sieci, szerokości, ograniczeń, nośności mostów i rodzaju pojazdu. Dużo dróg nie oznacza łatwego przejazdu poza nimi.

`barrier_present` i `barrier_km_km2` są ostrzeżeniem przestrzennym, nie karą w IOP ani dowodem braku przejazdu. Obejmują perony, budowle hydrotechniczne, umocnienia, budowle ziemne, tory, kanały, rowy, rzeki. Długości mogą się pokrywać, więc nie są unikatową długością przeszkód. Nie odejmujemy ich ponownie od udziału wód. Potrzebna jest dalsza analiza przejść, mostów, wysokości i szerokości. W danych BIUB oznacza tutaj 25 peronów kolejowych, BUUO zawiera 237 ścian oporowych i 9 umocnień brzegu; BUZM zawiera wały/groble, nasypy i wykopy. BUIN miesza mosty, kładki, tunele i przejścia, dlatego nie otrzymuje jednej wagi.

## Wszystkie 64 klasy

`IOP_V2_ANALIZA_64.csv` zawiera decyzję dla każdej klasy, współczynnik, uzasadnienie, liczbę obiektów i rzeczywiste podtypy `rodzaj`. Kolumna `name_v1` zachowuje nazwy poprzednika, które nie zawsze są precyzyjne; podtypy pochodzą bezpośrednio z danych. Klasy opisowe, administracyjne, kompleksy funkcjonalne, duplikaty sieci i punkty bez powierzchni nie powinny automatycznie otrzymywać niezerowej wagi. Włączenie wszystkich 64 do sumy byłoby błędem.

## Uruchomienie i kontrola

Kod w projekcie: `app/python/iop_v2.py`; uruchomienie PowerShell: `C:\Users\hello\PSIP_ms_L1\IOP_V2_ENV_TEST.ps1`. Wymaga Python 3 i psycopg2 oraz działającego Docker. Skrypt sprawdza nazwę kontenera, wolumen env-test, port 5444 i TERYT 1412. Tworzy wyłącznie `grid.iop_v2_r7/r8/r9` w jednej transakcji. Istniejąca tabela v2 powoduje błąd zamiast nadpisania. Błąd przed zatwierdzeniem wycofuje wszystkie trzy tabele. Tabele tymczasowe znikają po rozłączeniu. Nie modyfikuje v1, agregacji, BDOT, env-qa ani main.

`KONTROLA_SQL.sql`: porównanie v1/v2 we wszystkich komórkach i sprawdzenie różnicy geometrycznej z całym powiatem. `POROWNANIE_R7_R8_R9.csv`: pełnopowiatowe statystyki, średnie ważone powierzchnią, korelacja, zabudowa, bariery i udział nieznanego pokrycia. Średnie v1 i v2 nie mają identycznej interpretacji — v1 jest względnie rozciągnięte. R7/R8/R9 nie są traktowane jako idealnie zagnieżdżone; każda siatka liczona jest osobno z tych samych geometrii i współczynników.

W QGIS dodaj przez localhost:5444 tabele `grid.iop_v2_r7`, `grid.iop_v2_r8`, `grid.iop_v2_r9`. Wybierz `iop_offroad`; użyj tych samych stałych granic [-1,+1] we wszystkich siatkach, bez automatycznego rozciągania do lokalnego minimum i maksimum. Osobno wyświetl `road_km_km2` i `barrier_present`.

Kod v1 zachowano jako punkt odniesienia. Kod v2, konfiguracja, styl i raporty są wersjonowane wspólnie na gałęziach env-test, env-qa i main. Pozostałe lokalne pliki interfejsu nie należą do tej zmiany.


## Późniejsze wdrożenie na polecenie użytkownika

Po obliczeniu w env-test użytkownik zlecił kolejno test → qa → main. Trzy tabele iop_v2_r7/r8/r9 skopiowano do env-qa (5446) i main (5447). We wszystkich trzech bazach zapisano domyślny styl QGIS w public.layer_styles: czerwony → biały → zielony. Liczby wierszy i sumy kontrolne całych rekordów zgadzają się między środowiskami. Wcześniejsze informacje o nietkniętym qa/main opisują etap obliczeń, przed tym wdrożeniem. Raport opisuje wdrożenie danych; publikacja kodu w Git jest osobnym krokiem. Wyniki kontroli: WDROZENIE_TEST_QA_MAIN.json.


## Styl i GitHub

Gotowy styl: `styles/IOP_V2_R7_R8_R9.qml`. Wartości ujemne są czerwone, zakres -0,05 do +0,05 biały, dodatnie zielone. Wczytaj go w QGIS przez Właściwości → Styl → Wczytaj styl. Nie interpretuj kolorów jako gwarancji przejazdu.

Raporty znajdują się w `reports/iop_v2/`. Uruchom `py -m pip install psycopg2-binary`, jeżeli lokalny Python nie ma tego pakietu. Skrypt v2 jest przeznaczony do lokalnego PowerShell/Docker, nie do uruchomienia wewnątrz obrazu loadera. Wymaga istniejących danych BDOT, agregacji i wyników v1. Odmawia nadpisania istniejących tabel v2.

Push na env-test, env-qa i main uruchamia dotychczasowy workflow sprawdzający PostGIS i H3. Workflow nie oblicza ani nie kopiuje IOP v2. Wyniki v2 i domyślne style zostały już wdrożone do wszystkich trzech baz; ich zgodność dokumentuje raport wdrożenia.
