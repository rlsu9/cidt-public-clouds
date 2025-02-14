#!/usr/bin/env python3

import logging
import os
import sys
import pandas as pd
import argparse

from common import init_logging, detect_cloud_regions_from_filename

REQUIRED_COLUMNS = ['count', 'hop_count', 'distance_km', 'route']

def combine_tsv_files_and_add_regions(input_files: list[str], output_file: str) -> None:
    """Combine the TSV files into a single TSV file with added src/dst region information based on the file name."""
    combined_df = pd.DataFrame()
    for input_file in input_files:
        logging.info(f'Processing {input_file} ...')
        cloud_regions = detect_cloud_regions_from_filename(os.path.basename(input_file))
        assert cloud_regions is not None, f"Cannot detect cloud regions from filename '{input_file}'"
        (src_cloud, src_region, dst_cloud, dst_region) = cloud_regions

        df = pd.read_csv(input_file, delimiter='\t')
        for column in REQUIRED_COLUMNS:
            assert column in df.columns, f"Required column '{column}' is missing in '{input_file}'"

        df['src_cloud'] = src_cloud
        df['src_region'] = src_region
        df['dst_cloud'] = dst_cloud
        df['dst_region'] = dst_region

        combined_df = pd.concat([combined_df, df], ignore_index=True)

    # Reorder columns with the new ones at the beginning
    new_columns = ['src_cloud', 'src_region', 'dst_cloud', 'dst_region'] + REQUIRED_COLUMNS
    combined_df = combined_df[new_columns]

    logging.info(f'Writing to {output_file} ...')
    combined_df.to_csv(output_file if output_file else sys.stdout, sep='\t', index=False)

def parse_args():
    parser = argparse.ArgumentParser(description='Process TSV files and add columns.')
    parser.add_argument('-i', '--input-tsvs', type=str, required=True, nargs='+', help='The TSV files for each region, must be named in the format of *.src_cloud.src_region.dst_cloud.dst_region.*')
    parser.add_argument('-o', '--output-tsv', type=str, help='The output TSV file.')
    args = parser.parse_args()

    return args

def main():
    init_logging()
    args = parse_args()
    combine_tsv_files_and_add_regions(args.input_tsvs, args.output_tsv)

if __name__ == '__main__':
    main()
