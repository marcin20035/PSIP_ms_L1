import json
from pathlib import Path

import h3
from osgeo import ogr, osr
from shapely.geometry import shape, mapping, Polygon
from shapely.ops import unary_union

SOURCE = Path("/data/powiat_minski.shp")
OUTPUT = Path("/tmp/h3_grids")
RESOLUTIONS = (7, 8, 9)


def read_boundary():
    ogr.UseExceptions()
    dataset = ogr.Open(str(SOURCE))

    if dataset is None:
        raise RuntimeError(f"Nie mozna otworzyc: {SOURCE}")

    layer = dataset.GetLayer()
    source_crs = layer.GetSpatialRef()

    if source_crs is None:
        raise RuntimeError("Brak ukladu wspolrzednych pliku.")

    source_crs = source_crs.Clone()
    source_crs.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)

    target_crs = osr.SpatialReference()
    target_crs.ImportFromEPSG(4326)
    target_crs.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)

    transform = osr.CoordinateTransformation(source_crs, target_crs)
    polygons = []

    for feature in layer:
        geometry = feature.GetGeometryRef()
        if geometry is None:
            continue

        geometry = geometry.Clone()
        geometry.Transform(transform)
        polygons.append(shape(json.loads(geometry.ExportToJson())))

    if not polygons:
        raise RuntimeError("Plik nie zawiera geometrii.")

    boundary = unary_union(polygons)

    if not boundary.is_valid:
        raise RuntimeError("Granica ma bledna geometrie.")

    if boundary.geom_type not in ("Polygon", "MultiPolygon"):
        raise RuntimeError("Granica musi byc poligonem.")

    return boundary


def generate_grid(boundary, resolution):
    h3_shape = h3.geo_to_h3shape(mapping(boundary))
    cells = h3.h3shape_to_cells_experimental(
        h3_shape, resolution, contain="overlap"
    )

    features = []

    for cell in sorted(cells):
        coordinates = [
            (longitude, latitude)
            for latitude, longitude in h3.cell_to_boundary(cell)
        ]
        polygon = Polygon(coordinates)

        features.append({
            "type": "Feature",
            "properties": {
                "h3_id": cell,
                "resolution": resolution,
            },
            "geometry": mapping(polygon),
        })

    return {
        "type": "FeatureCollection",
        "features": features,
    }


def main():
    boundary = read_boundary()
    OUTPUT.mkdir(parents=True, exist_ok=True)

    for resolution in RESOLUTIONS:
        grid = generate_grid(boundary, resolution)
        destination = OUTPUT / f"h3_r{resolution}.geojson"

        destination.write_text(
            json.dumps(grid),
            encoding="utf-8",
        )

        print(
            f"H3 r{resolution}: {len(grid['features'])} komorek"
            f" -> {destination}",
            flush=True,
        )


if __name__ == "__main__":
    main()