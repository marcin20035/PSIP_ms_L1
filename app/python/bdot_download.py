"""Download the official BDOT10k GeoPackage county archive from GUGiK.

County Miński (TERYT 1412). URL pattern comes from the published source
of QGIS plugin marylaGIS/bdot10k, task_dwnl_bdot.py (2026).
"""
import argparse
import shutil
import sys
import zipfile
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import Request, urlopen

COUNTY_TERYT = '1412'
BDOT_URL = (
    'https://opendata.geoportal.gov.pl/bdot10k/schemat2021/'
    'GPKG/14/1412_GPKG.zip'
)
UA = 'Mozilla/5.0 (compatible; PSIP-education/1.0)'


def safely_extract_zip(path, target):
    target = target.resolve()
    with zipfile.ZipFile(path) as archive:
        for member in archive.infolist():
            item_path = (target / member.filename).resolve()
            if not item_path.is_relative_to(target):
                raise ValueError('Niebezpieczna sciezka w ZIP: ' + member.filename)
            if member.file_size > 2_000_000_000:
                raise ValueError('Archiwum zawiera zbyt duzy pojedynczy plik.')
        archive.extractall(target)


def download(url, filepath):
    # This script downloads only from the official GUGiK open data host.
    hostname = (urlparse(url).hostname or '').lower()
    if hostname != 'opendata.geoportal.gov.pl':
        raise ValueError('Dopuszczalna tylko domena opendata.geoportal.gov.pl')
    print('Pobieram oficjalny BDOT10k GPKG dla powiatu mińskiego (1412):', url, flush=True)
    req = Request(url, headers={'User-Agent': UA})
    partial = filepath.with_suffix(filepath.suffix + '.part')
    try:
        with urlopen(req, timeout=180) as response, partial.open('wb') as out:
            shutil.copyfileobj(response, out, length=1024 * 1024)
        if not zipfile.is_zipfile(partial):
            raise ValueError('Serwer nie zwrocil poprawnego ZIP (np. blad HTTP).')
        partial.replace(filepath)
    finally:
        partial.unlink(missing_ok=True)
    print('Pobrano:', filepath, 'bajtow:', filepath.stat().st_size, flush=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--out', default='/data/bdot10k', help='Katalog wyjsciowy')
    parser.add_argument('--zip', dest='existing_zip', help='Gotowy pobrany ZIP')
    args = parser.parse_args()
    output = Path(args.out)
    output.mkdir(parents=True, exist_ok=True)
    zip_path = Path(args.existing_zip) if args.existing_zip else output / '1412_GPKG.zip'
    if not zip_path.is_file():
        download(BDOT_URL, zip_path)
    elif not zipfile.is_zipfile(zip_path):
        raise ValueError('Istniejacy plik nie jest poprawnym ZIP: ' + str(zip_path))
    dest = output / 'extracted'
    dest.mkdir(parents=True, exist_ok=True)
    safely_extract_zip(zip_path, dest)
    gpkg_files = sorted(dest.rglob('*.gpkg'))
    if not gpkg_files:
        raise RuntimeError('W archiwum brakuje plikow GPKG. Sprawdz pobrana paczke.')
    print('WYPakowano GeoPackage:')
    for path in gpkg_files:
        print('-', path, flush=True)
    print('Przygotowano dane BDOT10K do importu.', flush=True)


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        print('BLAD POBIERANIA:', exc, file=sys.stderr)
        raise SystemExit(1)
