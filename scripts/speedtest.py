#!/usr/bin/env python3

from collections import namedtuple, OrderedDict
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

util.validate_requirements(modules=['click', 'speedtest'])
import click
import speedtest

cache_dir        = util.get_cache_directory()
context_settings = dict(help_option_names=['-h', '--help'])
loading          = f'{glyphs.md_timer_outline}{glyphs.icon_spacer}Speedtest running...'
loading_dict     = { 'text': loading, 'class': 'loading', 'tooltip': 'Speedtest is running'}
logfile          = cache_dir / 'waybar-speedtest.log'
speedtest_data   = None

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
    filename = logfile,
    filemode = 'w',  # 'a' = append, 'w' = overwrite
    format   = '%(asctime)s [%(levelname)-5s] - %(message)s',
    level    = logging.INFO
)

def generate_tooltip(data: namedtuple=None):
    logging.info('[generate_tooltip] - entering function')
    tooltip = []

    tooltip_od = OrderedDict()
    if data.bytes_tx and data.bytes_rx:
        tooltip_od['Bytes sent'] = util.byte_converter(number=data.bytes_tx, unit='auto')
        tooltip_od['Bytes receives'] = util.byte_converter(number=data.bytes_rx, unit='auto')

    if data.speed_tx and data.speed_rx:
        tooltip_od['Upload speed'] = util.network_speed(number=data.speed_tx)
        tooltip_od['Download speed'] = util.network_speed(number=data.speed_rx)

    if data.ping:
        tooltip_od['Ping'] = f'{data.ping} ms'

    max_key_length = 0
    for key in tooltip_od.keys():
        max_key_length = len(key) if len(key) > max_key_length else max_key_length

    for key, value in tooltip_od.items():
        tooltip.append(f'{key:{max_key_length}} : {value}')

    if len(tooltip) > 0:
        tooltip.append('')

    if data.server:
        tooltip.append('Server')
        tooltip_od = OrderedDict()
        if data.server.ip:
            tooltip_od['IP'] = data.server.ip

        if data.server.city and data.server.region and data.server.country:
            tooltip_od['Location'] = f'{data.server.city}, {data.server.region}, {data.server.country}'

        if data.server.hostname:
            tooltip_od['Hostname'] = data.server.hostname.split(':')[0]

        if data.server.sponsor:
            tooltip_od['Sponsor'] = data.server.sponsor

        max_key_length = 0
        for key in tooltip_od.keys():
            max_key_length = len(key) if len(key) > max_key_length else max_key_length

        for key, value in tooltip_od.items():
            tooltip.append(f'{key:{max_key_length}} : {value}')

        if len(tooltip) > 0:
            tooltip.append('')

    if data.client:
        tooltip.append('Client')
        tooltip_od = OrderedDict()
        if data.client.ip:
            tooltip_od['IP'] = data.client.ip

        if data.client.city and data.client.region and data.client.country:
            tooltip_od['Location'] = f'{data.client.city}, {data.client.region}, {data.client.country}'

        if data.client.isp:
            tooltip_od['ISP'] = data.client.isp

        max_key_length = 0
        for key in tooltip_od.keys():
            max_key_length = len(key) if len(key) > max_key_length else max_key_length

        for key, value in tooltip_od.items():
            tooltip.append(f'{key:{max_key_length}} : {value}')

    if len(tooltip) > 0:
        tooltip.append('')
        tooltip.append(f'Last updated {util.get_human_timestamp()}')

    return '\n'.join(tooltip)

def get_icon(speed: int = 0) -> str:
    if speed < 100_000_000:
        return glyphs.md_speedometer_slow
    elif speed < 500_000_000:
        return glyphs.md_speedometer_medium
    else:
        return glyphs.md_speedometer_fast

def parse_speedtest_data(json_data=None):
    logging.info('[parse_speedtest_data] - entering function')
    speedtest_data = util.dict_to_namedtuple( name='SpeedtestData', obj=json_data)

    client_data = speedtest_data.client
    server_data = speedtest_data.server
    speed_rx    = round(speedtest_data.download)
    speed_tx    = round(speedtest_data.upload)
    avg_speed   = (speed_rx + speed_tx) / 2
    icon        = get_icon(avg_speed)

    logging.info(f'[parse_speedtest_data] - speed_rx={speed_rx}, speed_tx={speed_tx}')
    logging.info(f'[parse_speedtest_data] - avg_speed={avg_speed}')
    logging.info(f'[parse_speedtest_data] - icon={icon}')

    if client_data.ip:
        client_location = util.ip_to_location(ip=client_data.ip, name='ClientLocation')

    if server_data.host:
        hostname = server_data.host.split(':')[0]
        try:
            server_ip = socket.gethostbyname(hostname)
        except:
            server_ip = None
    
    if server_ip:
        server_location = util.ip_to_location(ip=server_ip, name='ServerLocation')
    
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
    logging.info('[run_speedtest] - running speedtest')
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

def render_output(speedtest_data: namedtuple=None, icon: str=None):
    logging.info('[render_output] - entering function')
    if speedtest_data.success:
        parts = []
        if speedtest_data.speed_rx:
            parts.append(f'{glyphs.cod_arrow_small_down}{util.network_speed(number=speedtest_data.speed_rx)}')
        if speedtest_data.speed_tx:
            parts.append(f'{glyphs.cod_arrow_small_up}{util.network_speed(number=speedtest_data.speed_tx)}')

        if len(parts) == 2:
            text = f'{icon}{glyphs.icon_spacer}Speedtest {" ".join(parts)}'
            output_class = 'success'
            tooltip = generate_tooltip(data=speedtest_data)
        else:
            text = f'{icon}{glyphs.icon_spacer}all tests failed'
            output_class = 'error'
            tooltip = 'Speedtest error'
    else:
        text = f'{glyphs.md_alert}{glyphs.icon_spacer}{speedtest_data.error}'
        output_class = 'error'
        tooltip = 'Speedtest error'
    
    return text, output_class, tooltip

def worker():
    global speedtest_data

    while True:
        update_event.wait()
        update_event.clear()

        if not util.waybar_is_running():
            logging.info('[worker] - waybar not running')
            sys.exit(0)
        else:
            if util.network_is_reachable():
                if speedtest_data:
                    if speedtest_data.success:
                        text, _, tooltip = render_output(speedtest_data=speedtest_data, icon=glyphs.md_timer_outline)
                        print(json.dumps({'text': text, 'class': 'loading', 'tooltip': tooltip}))
                    else:
                        print(json.dumps(loading_dict))
                else:
                    print(json.dumps(loading_dict))

                speedtest_data = run_speedtest()
                text, output_class, tooltip = render_output(speedtest_data=speedtest_data, icon=speedtest_data.icon)
                output = {
                    'text'    : text,
                    'class'   : output_class,
                    'tooltip' : tooltip,
                }
            else:
                output = {
                    'text'    : f'{glyphs.md_alert}{glyphs.icon_spacer}the network is unreachable',
                    'class'   : 'error',
                    'tooltip' : 'Speedtest error',
                }

        print(json.dumps(output))

def refresh_handler(signum, frame):
    logging.info('[refresh_handler] - received SIGHUP — triggering speedtest')
    update_event.set()

signal.signal(signal.SIGHUP, refresh_handler)

@click.command(help='Run a network speed test and return the results', context_settings=context_settings)
@click.option('-i', '--interval', type=int, default=300, help='The update interval (in seconds)')
@click.option('-t', '--test', default=False, is_flag=True, help='Print the output and exit')
def main(interval, test):
    if test:
        speedtest_data = run_speedtest()
        util.pprint(speedtest_data)
        print()
        print(generate_tooltip(speedtest_data))
        return

    logging.info('[main] - entering function')

    threading.Thread(target=worker, args=(), daemon=True).start()
    update_event.set()

    while True:
        time.sleep(interval)
        update_event.set()

if __name__ == '__main__':
    main()
