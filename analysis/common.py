#!/usr/bin/env python3

import argparse
import ast
from enum import Enum
import functools
import json
import os
import re
import sys
import time
import logging
from typing import Optional
from geopy.distance import geodesic

CARBON_API_URL = 'http://yak-03.sysnet.ucsd.edu'
MATCHED_NODES_FILENAME_AWS = 'matched_nodes.aws.by_region.txt'
MATCHED_NODES_FILENAME_GCLOUD = 'matched_nodes.gcloud.by_region.txt'

Coordinate = tuple[float, float]
RouteInCoordinate = list[Coordinate]
RouteInIP = list[str]
RouteInISO = list[str]

class RouteMetric(str, Enum):
    HopCount = 'hop_count'
    DistanceKM = 'distance_km'

    def __str__(self) -> str:
        return self.value

def init_logging(level=logging.DEBUG):
    logging.basicConfig(level=level,
                        stream=sys.stderr,
                        format='%(asctime)s %(levelname)-8s %(message)s',
                        datefmt='%Y-%m-%d %H:%M:%S')

def load_aws_ip_ranges(region):
    # Load the JSON data from the file
    with open('../data/cloud/ip-ranges.aws.json', 'r') as file:
        data = json.load(file)
    # Iterate through the prefixes and populate the mapping
    ip_ranges = []
    for item in data['prefixes']:
        if region and item['region'] != region:
            continue
        ip_prefix = item['ip_prefix']
        ip_ranges.append((ip_prefix, 'aws', item['region']))
    return ip_ranges

def load_gcloud_ip_ranges(region):
    with open('../data/cloud/ip-ranges.gcloud.json', 'r') as file:
        data = json.load(file)
    # Iterate through the prefixes and populate the mapping
    ip_ranges = []
    for item in data['prefixes']:
        if region and item['region'] != region:
            continue
        if 'ipv4Prefix' not in item:
            continue
        ip_prefix = item['ipv4Prefix']
        ip_ranges.append((ip_prefix, 'gcloud', item['scope']))
    return ip_ranges

def load_cloud_ip_ranges(cloud, region):
    if cloud == 'aws':
        return load_aws_ip_ranges(region)
    if cloud == 'gcloud':
        return load_gcloud_ip_ranges(region)
    raise ValueError(f'Unsupported cloud {cloud}')

def load_itdk_mapping_internal(node_file, reverse=False) -> dict:
    logging.info('Loading ITDK nodes ...')
    start_time = time.time()
    mapping_id_to_ips = {}
    mapping_ip_to_id = {}
    node_count = 0
    with open(node_file, 'r') as file:
        for line in file:
            if line.startswith('#'):
                continue

            if not line.startswith('node N'):
                logging.error('Cannot process line:', line)
                continue

            arr = line.split(':', 1)
            node_id = arr[0].split()[1]
            ips = arr[1].split()
            if reverse:
                for ip in ips:
                    mapping_ip_to_id[ip] = node_id
            else:
                mapping_id_to_ips[node_id] = ips

            node_count += 1
            if node_count % 1000000 == 0:
                elapsed_time = time.time() - start_time
                logging.debug(f'Elapsed: {elapsed_time:.2f}s, node count: {node_count}')
                # break   # _debug_
    elapsed_time = time.time() - start_time
    logging.info(f'Elapsed: {elapsed_time:.2f}s, total node count: {node_count}')
    if reverse:
        return mapping_ip_to_id
    else:
        return mapping_id_to_ips

def load_itdk_node_id_to_ips_mapping(node_file='../data/caida-itdk/midar-iff.nodes') -> dict[str, list]:
    return load_itdk_mapping_internal(node_file, False)

def load_itdk_node_ip_to_id_mapping(node_file='../data/caida-itdk/midar-iff.nodes') -> dict[str, str]:
    return load_itdk_mapping_internal(node_file, True)

def get_routes_from_file(filename) -> list[list]:
    logging.info(f'Loading routes from {filename} ...')
    with open(filename, 'r') as file:
        lines = file.readlines()
        routes = [ ast.literal_eval(line) for line in lines ]
    logging.info(f'Loaded {len(routes)} routes')
    return routes

def write_routes_to_file(routes: list[list], output_file: Optional[str] = None) -> None:
    if output_file:
        output = open(output_file, 'x')
        logging.info(f'Writing (lat, lon) routes to {output_file} ...')
    else:
        output = None

    for route in routes:
        print(route, file=output if output else sys.stdout)

    if output:
        output.close()
        logging.info('Done')

def detect_cloud_regions_from_filename(filename: str) -> Optional[tuple[str, str, str, str]]:
    """Parse the filename and return a 4-item tuple (src_cloud, src_region, dst_cloud, dst_region)."""
    # filename example: routes.aws.af-south-1.aws.ap-northeast-1.by_geo
    regex_4_tuple = re.compile(r'.*\.(aws|gcloud|gcp)\.([\w-]+)\.(aws|gcloud|gcp)\.([\w-]+)\.by_.*')
    m = regex_4_tuple.match(filename)
    if m:
        (src_cloud, src_region, dst_cloud, dst_region) = m.groups()
        return (src_cloud, src_region, dst_cloud, dst_region)
    # filename example: routes.aws.af-south-1.ap-northeast-1.by_geo
    # Assume both regions belong to the same cloud if the filename does not contain a second cloud name
    regex_3_tuple = re.compile(r'.*\.(aws|gcloud|gcp)\.([\w-]+)\.([\w-]+)\.by_.*')
    m = regex_3_tuple.match(filename)
    if m:
        (src_cloud, src_region, dst_region) = m.groups()
        dst_cloud = src_cloud
        return (src_cloud, src_region, dst_cloud, dst_region)
    # Cannot match with any regex
    return None

def DirType(path: str):
    if os.path.isdir(path):
        return path
    else:
        raise argparse.ArgumentTypeError(f'{path} is not a valid directory path')

def calculate_total_distance_km(hops: RouteInCoordinate) -> float:
    """Calculate the total distance across all hops, by summing the pairwise distances.
    """
    if len(hops) <= 1:
        return 0.

    @functools.cache
    def calculate_pairwise_distance_km(hop1: Coordinate, hop2: Coordinate) -> float:
        return geodesic(hop1, hop2).km

    total_distance = 0.
    for i in range(len(hops) - 1):
        total_distance += calculate_pairwise_distance_km(hops[i], hops[i + 1])
    return total_distance

def calculate_route_metric(route: str, metric: RouteMetric) -> float:
    match metric:
        case RouteMetric.HopCount:
            return len(route.split('|'))
        case RouteMetric.DistanceKM:
            return round(calculate_total_distance_km([ast.literal_eval(e) for e in route.split('|')]), 2)
        case _:
            raise ValueError(f'Unknown metric {metric}')
