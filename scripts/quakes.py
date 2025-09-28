#!/usr/bin/env python3

from collections import namedtuple
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, NamedTuple
from waybar import glyphs, http, util
import json
import re
import time

util.validate_requirements(required=['click'])
import click

CONTEXT_SETTINGS = dict(help_option_names=['-h', '--help'])

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

def miles_to_kilometers(miles: int=0) -> float:
    """ Convert miles to kilometers """
    return miles * 1.609344

# Start duplicated
def dict_to_namedtuple(name: str=None, obj: dict=None):
    """
    Recursively convert a dict (possibly nested) into a namedtuple.
    """
    if isinstance(obj, dict):
        fields = {k: dict_to_namedtuple(k.capitalize(), v) for k, v in obj.items()}
        NT = namedtuple(name, fields.keys())
        return NT(**fields)
    elif isinstance(obj, list):
        return [dict_to_namedtuple(name, i) for i in obj]
    else:
        return obj

def ip_to_location(ip: str=None, name: str=None):
    url = f'https://ipinfo.io/{ip}/json'
    response = http.request(url=url)
    if response.status == 200:
        return dict_to_namedtuple(name=name, obj=response.body)

    return None

def find_public_ip():
    url = 'https://ifconfig.io'
    headers = {'User-Agent': 'curl/7.54.1'}
    response = http.request(url=url, headers=headers)
    if response.status == 200:
        return response.body
    return None
# End duplicated

def get_quake_data(location_data: namedtuple=None, radius: str=None, limit: int=None, magnitude: float=None):
    now = int(time.time())
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
                    quakes.append(dict_to_namedtuple(name='Quake', obj=feature['properties']))

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

def format_time(timestamp: int=0) -> str:
    ts = timestamp / 1000
    dt = datetime.fromtimestamp(ts)
    return dt.strftime("%Y-%m-%d %H:%M")

def generate_tooltip(quakes):
    tooltip = []
    max_header_len = 0
    for quake in quakes:
        header = f'{format_time(timestamp=quake.time)} - mag {quake.mag}'
        max_header_len = len(header) if len(header) > max_header_len else max_header_len
    
    for quake in quakes:
        header = f'{format_time(timestamp=quake.time)} - mag {quake.mag}'
        tooltip.append(f'{header:{max_header_len}} {quake.place}')
    
    return '\n'.join(tooltip)

@click.command(help='Show recent earthquakes near you', context_settings=CONTEXT_SETTINGS)
@click.option('-r', '--radius', default='50m', help='The radius, e.g., 50m (or 50km)')
@click.option('-l', '--limit', type=int, default=10, show_default=True, help='Maximum number of results to display')
@click.option('-m', '--magnitude', type=float, default=0.1, show_default=True, help='Minimum magnitude')
def main(radius, limit, magnitude):
    ip = find_public_ip()
    if ip:
        location_data = ip_to_location(ip=ip, name='Location')
    
    quake_data = get_quake_data(location_data=location_data, radius=radius, limit=limit, magnitude=magnitude)
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
            'tooltip': 'Earthquakes; Error',
        }       

    print(json.dumps(output))

if __name__ == "__main__":
    main()
