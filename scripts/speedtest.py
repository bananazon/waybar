#!/usr/bin/env python3

from pathlib import Path
from waybar import glyphs, util
from typing import Optional, NamedTuple
from urllib.parse import quote, urlunparse
import json
import logging
import re
import signal
import socket
import sys
import threading
import time
import urllib.request

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

def ip_to_location(ip: str=None):
    url = f'https://ipinfo.io/{ip}/json'
    request = urllib.request.Request(url)
    with urllib.request.urlopen(request, timeout=3) as response:
        if response.status == 200:
            body = response.read().decode('utf-8').strip()
            try:
                json_data, err = util.parse_json_string(body)
                if not err:
                    return json_data
                return None
            except:
                return None
    return None

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

def run_speedtest():
    logging.info('[run_speedtest] running speedtest')
    location = None
    command = 'speedtest-cli --secure --json'
    rc, stdout, stderr = util.run_piped_command(command)
    logging.info('[run_speedtest] speedtest finished')
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
    
    client_data = json_data.get('client') or None
    server_data = json_data.get('server') or None
    speed_rx = round(json_data.get('download')) or 0
    speed_tx = round(json_data.get('upload')) or 0
    icon = get_icon((speed_rx + speed_tx) /2)

    if client_data.get('ip'):
        client_location = ip_to_location(ip=client_data.get('ip'))

    return SpeedtestResults(
        success  = True,
        icon     = icon,
        client   = Client(
            city      = client_location.get('city') or None,
            country   = client_location.get('country') or None,
            ip        = client_data.get('ip') or None,
            isp       = client_location.get('org') or client_data.get('isp') or None,
            latitude  = client_data.get('lat') or None,
            longitude = client_data.get('lon') or None,
            region    = client_location.get('region') or None,
            timezone  = client_location.get('timezone'),
        ),
        server = Server(
            city      = re.split(r'\s*,\s*', server_data.get('name'))[0] or None,
            country   = server_data.get('country') or None,
            hostname  = server_data.get('host') or None,
            ip        = socket.gethostbyname(server_data.get('host').split(':')[0]) or None,
            latitude  = server_data.get('lat') or None,
            longitude = server_data.get('lon') or None,
            latency   = server_data.get('latency') or None,
            name      = server_data.get('name') or None,
            region    = re.split(r'\s*,\s*', server_data.get('name'))[1] or None,
            sponsor   = server_data.get('sponsor') or None,
        ),
        bytes_rx = round(json_data.get('bytes_received')) or -1,
        bytes_tx = round(json_data.get('bytes_sent')) or -1,
        ping     = json_data.get('ping') or -1,
        speed_rx = speed_rx,
        speed_tx = speed_tx,
    )

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
                tooltip = generate_tooltip(speedtest_data)

                if speedtest_data.success:
                    parts = []
                    parts.append(f'{glyphs.cod_arrow_small_down}{util.network_speed(number=speedtest_data.speed_rx)}')
                    parts.append(f'{glyphs.cod_arrow_small_up}{util.network_speed(number=speedtest_data.speed_tx)}')
                    output = {
                        'text'    : f'{speedtest_data.icon}{glyphs.icon_spacer}Speedtest {" ".join(parts)}',
                        'class'   : 'success',
                        'tooltip' : tooltip,
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
def main(interval):
    logging.info('[main] entering')

    threading.Thread(target=worker, args=(), daemon=True).start()
    update_event.set()

    while True:
        time.sleep(interval)
        update_event.set()

if __name__ == '__main__':
    main()
