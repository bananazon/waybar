#!/usr/bin/env python3

from pathlib import Path
from waybar import glyphs, util
from typing import Optional, NamedTuple
import json
import logging
import os
import signal
import sys
import threading
import time

util.validate_requirements(required=['click', 'speedtest'])
import click
import speedtest

CACHE_DIR = util.get_cache_directory()
CONTEXT_SETTINGS = dict(help_option_names=['-h', '--help'])
LOADING = f'{glyphs.md_timer_outline} Speedtest running...'
LOADING_DICT = { 'text': LOADING, 'class': 'loading', 'tooltip': 'Speedtest is running'}
LOGFILE = CACHE_DIR / 'waybar-speedtest.log'

update_event = threading.Event()
sys.stdout.reconfigure(line_buffering=True)

class SpeedtestResults(NamedTuple):
    success    : Optional[bool]  = False
    error      : Optional[str]   = None
    icon       : Optional[str]   = None
    bytes_rx   : Optional[int]   = -1
    bytes_tx   : Optional[int]   = -1
    ping       : Optional[float] = -1
    server     : Optional[str]   = None
    speed_rx   : Optional[int]   = -1
    speed_tx   : Optional[int]   = -1

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

def run_speedtest():
    logging.info('[run_speedtest] running speedtest')
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
    
    speed_rx = round(json_data.get('download')) or 0
    speed_tx = round(json_data.get('upload')) or 0
    icon = get_icon((speed_rx + speed_tx) /2)

    return SpeedtestResults(
        success  = True,
        icon     = icon,
        bytes_rx = round(json_data.get('bytes_received')) or -1,
        bytes_tx = round(json_data.get('bytes_sent')) or -1,
        ping     = json_data.get('ping') or -1,
        server   = json_data.get('server').get('host') or 'Unknown',
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

                if speedtest_data.success:
                    parts = []
                    parts.append(f'{glyphs.cod_arrow_small_down}{util.network_speed(number=speedtest_data.speed_rx)}')
                    parts.append(f'{glyphs.cod_arrow_small_up}{util.network_speed(number=speedtest_data.speed_tx)}')
                    output = {
                        'text'    : f'{speedtest_data.icon} Speedtest {" ".join(parts)}',
                        'class'   : 'success',
                        'tooltip' : 'Speedtest results',
                    }
                else:
                    output = {
                        'text'  : f'{speedtest_data.icon} {speedtest_data.error}',
                        'class' : 'error',
                        'tooltip' : 'Speedtest error',
                    }
            else:
                output = {
                    'text'    : f'{glyphs.md_alert} the network is unreachable',
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
