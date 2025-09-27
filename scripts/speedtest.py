#!/usr/bin/env python3

from collections import namedtuple
from pathlib import Path
from typing import Optional, NamedTuple
from waybar import glyphs, http, util
import json
import logging
import re
import signal
import socket
import subprocess
import sys
import threading
import time

util.validate_requirements(required=['click', 'speedtest'])
import click
import speedtest

CACHE_DIR = util.get_cache_directory()
CONTEXT_SETTINGS = dict(help_option_names=['-h', '--help'])
LOADING = f'{glyphs.md_timer_outline}{glyphs.icon_spacer}Speedtest running...'
LOADING_DICT = { 'text': LOADING, 'class': 'loading', 'tooltip': 'Speedtest is running'}
LOGFILE = CACHE_DIR / 'waybar-speedtest.log'

update_event = threading.Event()
sys.stdout.reconfigure(line_buffering=True)

class Client(NamedTuple):
    city      : Optional[str] = None
    country   : Optional[str] = None
    ip        : Optional[str] = None
    isp       : Optional[str] = None
    latitude  : Optional[str] = None
    longitude : Optional[str] = None
    region    : Optional[str] = None
    timezone  : Optional[str] = None

class Server(NamedTuple):
    city      : Optional[str]   = None
    country   : Optional[str]   = None
    hostname  : Optional[str]   = None
    ip        : Optional[str]   = None
    latency   : Optional[float] = 0.0
    latitude  : Optional[str]   = None
    name      : Optional[str]   = None
    longitude : Optional[str]   = None
    region    : Optional[str]   = None
    sponsor   : Optional[str]   = None

class SpeedtestResults(NamedTuple):
    success  : Optional[bool]   = False
    error    : Optional[str]    = None
    client   : Optional[Client] = None
    server   : Optional[Server] = None
    icon     : Optional[str]    = None
    bytes_rx : Optional[int]    = -1
    bytes_tx : Optional[int]    = -1
    ping     : Optional[float]  = -1
    speed_rx : Optional[int]    = -1
    speed_tx : Optional[int]    = -1

logging.basicConfig(
    filename=LOGFILE,
    filemode='a',  # 'a' = append, 'w' = overwrite
    format='%(asctime)s [%(levelname)-5s] - %(message)s',
    level=logging.INFO
)

def get_icon(speed: int = 0) -> str:
    if speed < 100_000_000:
        return glyphs.md_speedometer_slow
    elif speed < 500_000_000:
        return glyphs.md_speedometer_medium
    else:
        return glyphs.md_speedometer_fast

def generate_tooltip(data):
    tooltip = [
        f'Bytes sent     : {util.byte_converter(number=data.bytes_tx, unit='auto')}',
        f'Bytes received : {util.byte_converter(number=data.bytes_rx, unit='auto')}',
        f'Upload speed   : {util.network_speed(number=data.speed_tx)}',
        f'Download speed : {util.network_speed(number=data.speed_rx)}',
        f'Ping           : {data.ping} ms',
        '',
        'Server',
        f'IP       : {data.server.ip}',
        f'Location : {data.server.city}, {data.server.region}, {data.server.country}',
        f'Hostname : {data.server.hostname.split(':')[0]}',
        f'Sponsor  : {data.server.sponsor}',
        '',
        'Client',
        f'IP       : {data.client.ip}',
        f'Location : {data.client.city}, {data.client.region}, {data.client.country}',
        f'ISP      : {data.client.isp}',
    ]

    return '\n'.join(tooltip)

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

def parse_speedtest_data(json_data=None):
    speedtest_data = dict_to_namedtuple( name='SpeedtestData', obj=json_data)

    client_data = speedtest_data.client
    server_data = speedtest_data.server
    speed_rx    = round(speedtest_data.download)
    speed_tx    = round(speedtest_data.upload)
    icon        = get_icon((speed_rx + speed_tx) / 2)

    if client_data.ip:
        client_location = ip_to_location(ip=client_data.ip, name='ClientLocation')

    if server_data.host:
        hostname = server_data.host.split(':')[0]
        try:
            server_ip = socket.gethostbyname(hostname)
        except:
            server_ip = None
    
    if server_ip:
        server_location = ip_to_location(ip=server_ip, name='ServerLocation')
    
    if not client_data or not server_data or not client_location or not server_location:
        return SpeedtestResults(
            success = False,
            icon    = glyphs.md_alert,
            error   = 'Failed to parse the speedtest results',
        )

    return SpeedtestResults(
        success  = True,
        icon     = icon,
        client   = Client(
            city      = client_location.city,
            country   = client_location.country,
            ip        = client_data.ip,
            isp       = client_location.org or client_data.isp,
            latitude  = client_data.lat,
            longitude = client_data.lon,
            region    = client_location.region,
            timezone  = client_location.timezone,
        ),
        server = Server(
            city      = server_location.city or re.split(r'\s*,\s*', server_data.name)[0] or None,
            country   = server_location.country or server_data.country or None,
            hostname  = server_data.host,
            ip        = server_ip,
            latitude  = server_data.lat,
            longitude = server_data.lon,
            latency   = server_data.latency,
            name      = server_data.name,
            region    = server_location.region or re.split(r'\s*,\s*', server_data.name)[1] or None,
            sponsor   = server_data.sponsor,
        ),
        bytes_rx = round(speedtest_data.bytes_received) or -1,
        bytes_tx = round(speedtest_data.bytes_sent) or -1,
        ping     = speedtest_data.ping or -1,
        speed_rx = speed_rx,
        speed_tx = speed_tx,
    )

def run_speedtest():
    logging.info('[run_speedtest] running speedtest')
    location = None

    command_list = ['speedtest-cli', '--secure', '--json']
    command = ' '.join(command_list)
    try:
        result = subprocess.run(
            command_list,
            capture_output = True,
            text           = True,
            check          = False
        )
        stdout = result.stdout.strip()
        stderr = result.stderr.strip()
        rc = result.returncode
    except Exception as e:
        return SpeedtestResults(
            success = False,
            error   = stderr or f'failed to execute "{command}"',
            icon    = glyphs.md_alert,
        )

    if rc == 0:
        if stdout != '':
            json_data, err = util.parse_json_string(stdout)
            if err:
                return SpeedtestResults(
                    success = False,
                    error   = 'failed to parse the JSON data',
                    icon    = glyphs.md_alert,
                )
        else:
            return SpeedtestResults(
                success = False,
                error   = 'empty results received',
                icon    = glyphs.md_alert,
            )
    else:
        return SpeedtestResults(
            success = False,
            error   = stderr or f'failed to execute "{command}"',
            icon    = glyphs.md_alert,
        )
    
    speedtest_results = parse_speedtest_data(json_data)
    return speedtest_results

def worker():
    while True:
        update_event.wait()
        update_event.clear()

        if not util.waybar_is_running():
            logging.info('[main] waybar not running')
            sys.exit(0)
        else:
            if util.network_is_reachable():
                print(json.dumps(LOADING_DICT))

                speedtest_data = run_speedtest()

                if speedtest_data.success:
                    tooltip = generate_tooltip(speedtest_data)
                    parts = []
                    if speedtest_data.speed_rx:
                        parts.append(f'{glyphs.cod_arrow_small_down}{util.network_speed(number=speedtest_data.speed_rx)}')
                    if speedtest_data.speed_tx:
                        parts.append(f'{glyphs.cod_arrow_small_up}{util.network_speed(number=speedtest_data.speed_tx)}')

                    if len(parts) == 2:
                        output = {
                            'text'    : f'{speedtest_data.icon}{glyphs.icon_spacer}Speedtest {" ".join(parts)}',
                            'class'   : 'success',
                            'tooltip' : tooltip,
                        }
                    elif len(parts) == 0:
                        output = {
                            'text'  : f'{glyphs.md_alert}{glyphs.icon_spacer}all tests failed',
                            'class' : 'error',
                            'tooltip' : 'Speedtest error',
                        }
                else:
                    output = {
                        'text'  : f'{speedtest_data.icon}{glyphs.icon_spacer}{speedtest_data.error}',
                        'class' : 'error',
                        'tooltip' : 'Speedtest error',
                    }
            else:
                output = {
                    'text'    : f'{glyphs.md_alert}{glyphs.icon_spacer}the network is unreachable',
                    'class'   : 'error',
                    'tooltip' : 'Speedtest error',
                }

        print(json.dumps(output))

def refresh_handler(signum, frame):
    logging.info('Received SIGHUP — triggering speedtest')
    update_event.set()

signal.signal(signal.SIGHUP, refresh_handler)

@click.command(help='Run a network speed test and return the results', context_settings=CONTEXT_SETTINGS)
@click.option('-i', '--interval', type=int, default=300, help='The update interval (in seconds)')
@click.option('-t', '--test', default=False, is_flag=True, help='Print the output and exit')
def main(interval, test):
    if test:
        speedtest_data = run_speedtest()
        util.pprint(speedtest_data)
        sys.exit(0)

    logging.info('[main] entering')

    threading.Thread(target=worker, args=(), daemon=True).start()
    update_event.set()

    while True:
        time.sleep(interval)
        update_event.set()

if __name__ == '__main__':
    main()
