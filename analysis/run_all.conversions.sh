#!/bin/bash

# This script runs all the conversion of IP addresses to geo coordinates and then to carbon regions / ISOs.

cd "$(dirname "$0")"

set -e

# IP-to-geo conversion
./itdk_geo.py --convert-ip-to-latlon --filter-geo-coordinate-by-ground-truth --geo-coordinate-ground-truth-csv ./results/geo_distributions/geo_distribution.all.csv --routes_file region_pair.by_ip/routes.*.by_ip --outputs
chmod 440 routes.*.by_geo

for file in routes.*.by_geo; do
    echo "Processing $file ..."
    name="$(basename "$file" ".by_geo")"

    # Geo distribution
    ./distribution.routes.py --export-routes-distribution --include hop_count distance_km --remove-duplicate-consecutive-hops --routes_file "$name.by_geo" > "$name.by_geo.distribution"

    # Geo-to-ISO conversion
    ./carbon_client.py --convert-latlon-to-carbon-region --routes_file "$file" > "$name".by_iso
    # It is not necessary to filter again as we've filtered earlier. See notes at the end of "Clean up noisy routes" section.
    # src_cloud="$(echo "$name" | awk -F. '{print $2}')"
    # src_region="$(echo "$name" | awk -F. '{print $3}')"
    # dst_cloud="$(echo "$name" | awk -F. '{print $4}')"
    # dst_region="$(echo "$name" | awk -F. '{print $5}')"
    # ./carbon_client.py --convert-latlon-to-carbon-region --filter-iso-by-ground-truth --iso-ground-truth-csv ./results/iso_distributions/iso_distribution.all.csv --src-cloud "$src_cloud" --src-region "$src_region" --dst-cloud "$dst_cloud" --dst-region "$dst_region" --routes_file "$file" > "$name".by_iso

    # ISO distribution
    ./distribution.routes.py --export-routes-distribution --routes_file "$name.by_iso" > "$name.by_iso.distribution"

    chmod 440 "$name.by_geo.distribution" $name.by_iso $name.by_iso.distribution
done

mkdir region_pair.by_geo region_pair.by_geo.distribution region_pair.by_iso region_pair.by_iso.distribution
mv routes.*.by_geo region_pair.by_geo/
mv routes.*.by_geo.distribution region_pair.by_geo.distribution/
mv routes.*.by_iso region_pair.by_iso/
mv routes.*.by_iso.distribution region_pair.by_iso.distribution/

# Consolidate all the geo distributions TSV files into one, for batch import into SQL
./combine_per_region_pair_tsvs.py -i region_pair.by_geo.distribution/routes.*.by_geo.distribution -o ./routes.all.by_geo.distribution.tsv
chmod 440 ./routes.all.by_geo.distribution.tsv
# import this later into SQL.
