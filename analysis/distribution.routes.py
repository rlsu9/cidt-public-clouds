#!/usr/bin/env python3

import argparse
from collections import Counter
import io
import logging
import sys
from typing import Any, Optional

import pandas as pd

from common import RouteMetric, calculate_route_metric, get_routes_from_file, init_logging

def export_routes_distribution(routes: list[list], metrics:list[RouteMetric],
                               output: Optional[io.TextIOWrapper] = None):
    logging.info('Exporting routes distribution ...')

    columns = ['count'] + [metric for metric in metrics] + ['route']

    routes_as_str = [ '|'.join([str(e) for e in route]) for route in routes ]
    rows = []
    for route_str, count in sorted(Counter(routes_as_str).items(), key=lambda x: x[1], reverse=True):
        row: list[Any] = [count]
        for metric in metrics:
            value = calculate_route_metric(route_str, metric)
            row.append(value)
        row.append(route_str)
        rows.append(row)

    df = pd.DataFrame(rows, columns=columns)
    df.to_csv(output if output else sys.stdout, sep='\t', index=False)

    logging.info('Done')

def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument('--routes_file', type=str, required=True, help='The routes file, each line contains a list of (lat, long) coordinates and represents a route.')
    parser.add_argument('--export-routes-distribution', required=True, action='store_true',
                        help='Export the routes distribution.')
    parser.add_argument('--include', nargs='*', type=RouteMetric, choices=list(RouteMetric),
                        help='The additional metrics to include.')
    parser.add_argument('-o', '--output-tsv', type=argparse.FileType('w'), help='The output TSV file.')
    args = parser.parse_args()

    if not args.include:
        args.include = []

    return args

def main():
    init_logging(level=logging.INFO)
    args = parse_args()

    if args.export_routes_distribution:
        routes = get_routes_from_file(args.routes_file)
        export_routes_distribution(routes, args.include, args.output_tsv)
    else:
        raise ValueError('No action specified')

if __name__ == '__main__':
    main()
