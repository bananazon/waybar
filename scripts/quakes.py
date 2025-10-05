#!/usr/bin/env python3

from collections import namedtuple
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, NamedTuple
from waybar import glyphs, http, util
import json
import logging
import re
import signal
import sys
import threading
import time

util.validate_requirements(modules=['click'])
import click

cache_dir = util.get_cache_directory()
context_settings = dict(help_option_names=['-h', '--help'])
loading = f'{glyphs.md_timer_outline}{glyphs.icon_spacer}Checking USGS...'
loading_dict = { 'text': loading, 'class': 'loading', 'tooltip': 'Checking USGS...'}
logfile = cache_dir / 'waybar-earthquakes.log'

update_event = threading.Event()
sys.stdout.reconfigure(line_buffering=True)

# class Quake(NamedTuple):
#     alert        : Optional[str]   = None   # Alert level (e.g. “green”, “yellow”, “red”) in USGS’s alerting system
#     cdi          : Optional[float] = 0      # Community Determined Intensity (a measure of felt intensity)
#     detail       : Optional[str]   = None   # Link to the detailed GeoJSON / full record for this event
#     dmin         : Optional[float] = 0      # Horizontal distance from epicenter to nearest station / data point (in degrees)
#     gap          : Optional[int]   = 0      # Maximum azimuthal gap (in degrees) in the station distribution around the epicenter
#     mag_type     : Optional[str]   = None   # Type of magnitude measurement (e.g. “Mw”, “mb”, “Ml”)
#     magnitude    : Optional[float] = 0      # Magnitude of the earthquake (e.g. 5.2)
#     mmi          : Optional[float] = 0      # Modified Mercalli Intensity (instrumental estimate)
#     net          : Optional[str]   = None   # Network code (e.g. “us”, “ci”, etc.)
#     place        : Optional[str]   = None   # A human-readable description of location relative to known places (e.g. “5 km S of X, Country”)
#     significance : Optional[int]   = 0      # Significance — a non-linear number indicating how noteworthy the event is
#     status       : Optional[str]   = None   # Status of the event (e.g. “reviewed”, “automatic”)
#     time         : Optional[int]   = 0      # Origin time of the event in UTC
#     tsunami      : Optional[bool]  = False  # 1 if tsunami warning is associated, 0 otherwise
#     updated      : Optional[float] = 0      # Last update time by the catalog / system

class QuakeData(NamedTuple):
    success : Optional[bool] = False
    error   : Optional[str]  = None
    quakes  : Optional[list] = None

def generate_tooltip(quakes):
    tooltip = []
    max_header_len = 0
    for quake in quakes:
        header = f'{format_time(timestamp=quake.time)} - mag {quake.mag}'
        max_header_len = len(header) if len(header) > max_header_len else max_header_len

    for quake in quakes:
        header = f'{format_time(timestamp=quake.time)} - mag {quake.mag}'
        tooltip.append(f'{header:{max_header_len}} {quake.place}')

    if len(tooltip) > 0:
        tooltip.append('')
        tooltip.append(f'Last updated {util.get_human_timestamp()}')

    return '\n'.join(tooltip)

def miles_to_kilometers(miles: int=0) -> float:
    """ Convert miles to kilometers """
    return miles * 1.609344

def format_time(timestamp: int=0) -> str:
    ts = timestamp / 1000
    dt = datetime.fromtimestamp(ts)
    return dt.strftime("%Y-%m-%d %H:%M")

def get_quake_data(radius: str=None, limit: int=None, magnitude: float=None):
    now = int(time.time())
    ip = util.find_public_ip()
    if ip:
        location_data = util.ip_to_location(ip=ip, name='Location')
        if location_data:
            lat, lon = re.split(r'\s*,\s*', location_data.loc)
            maxradiuskm = 0

            match = re.search(r'^([\d]+)(m|km)$', radius)
            if match:
                if match.group(2) == 'km':
                    maxradiuskm = match.group(1)
                elif match.group(2) == 'm':
                    maxradiuskm = miles_to_kilometers(miles=int(match.group(1)))

                response = http.request(
                    url    = 'https://earthquake.usgs.gov/fdsnws/event/1/query',
                    params = {
                        'format'       : 'geojson',
                        'starttime'    : datetime.fromtimestamp(now - 86400).isoformat('T', 'seconds'),
                        'endtime'      : datetime.fromtimestamp(now).isoformat('T', 'seconds'),
                        'latitude'     : lat,
                        'longitude'    : lon,
                        'limit'        : limit,
                        'maxradiuskm'  : maxradiuskm,
                        'minmagnitude' : magnitude,
                        'offset'       : 1,
                        'orderby'      : 'time',
                    }
                )

                if response.status == 200:
                    quakes = []
                    if 'features' in response.body:
                        for feature in response.body['features']:
                            quakes.append(util.dict_to_namedtuple(name='Quake', obj=feature['properties']))

                        return QuakeData(
                            success = True,
                            quakes  = quakes,
                        )
                    else:
                        return QuakeData(
                            success = False,
                            error   = f'No data was received',
                        )
                else:
                    return QuakeData(
                        success = False,
                        error   = f'A non-200 {response.status} was received',
                    )
        else:
            return QuakeData(
                success = False,
                error  = 'failed to geolocate'
            )
    else:
        return QuakeData(
            success = False,
            error   = 'failed to determine IP',
        )

def worker(radius: str=None, limit: int=None, magnitude: float=None):
    while True:
        update_event.wait()
        update_event.clear()

        logging.info('[worker] entering main loop')
        if not util.waybar_is_running():
            logging.info('[worker] waybar not running')
            sys.exit(0)
        else:
            if util.network_is_reachable():
                print(json.dumps(loading_dict))

                quake_data = get_quake_data(radius=radius, limit=limit, magnitude=magnitude)
                if quake_data.success:
                    output = {
                        'text': f'Earthquakes: {len(quake_data.quakes)}',
                        'class': 'success',
                        'tooltip': generate_tooltip(quake_data.quakes),
                    }
                else:
                    output = {
                        'text': f'Earthquakes: {quake_data.error}',
                        'class': 'error',
                        'tooltip': 'Earthquakes error',
                    }
            else:
                output = {
                    'text'    : f'the network is unreachable',
                    'class'   : 'error',
                    'tooltip' : 'Earthquakes error',
                }

        print(json.dumps(output))

def refresh_handler(signum, frame):
    logging.info('Received SIGHUP — triggering speedtest')
    update_event.set()

signal.signal(signal.SIGHUP, refresh_handler)

@click.command(help='Show recent earthquakes near you', context_settings=context_settings)
@click.option('-r', '--radius', default='100m', help='The radius, e.g., 50m (or 50km)')
@click.option('-l', '--limit', type=int, default=20, show_default=True, help='Maximum number of results to display')
@click.option('-m', '--magnitude', type=float, default=0.1, show_default=True, help='Minimum magnitude')
@click.option('-i', '--interval', type=int, default=900, help='The update interval (in seconds)')
@click.option('-t', '--test', default=False, is_flag=True, help='Print the output and exit')
def main(radius, limit, magnitude, interval, test):
    if test:
        quake_data = get_quake_data(radius=radius, limit=limit, magnitude=magnitude)
        util.pprint(quake_data)
        print()
        print(generate_tooltip(quake_data.quakes))
        return
    
    threading.Thread(target=worker, args=(radius, limit, magnitude,), daemon=True).start()
    update_event.set()

    while True:
        time.sleep(interval)
        update_event.set()

    print(json.dumps(output))

if __name__ == "__main__":
    main()
