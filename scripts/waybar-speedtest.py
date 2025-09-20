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

update_event = threading.Event()

# ---- Unbuffered stdout ----
sys.stdout.reconfigure(line_buffering=True)

class SpeedtestResults(NamedTuple):
    success: Optional[bool] = False
    error: Optional[str] = None
    bits: Optional[int] = None

class SpeedtestOutput(NamedTuple):
    download: Optional[SpeedtestResults] = None
    upload: Optional[SpeedtestResults] = None
    icon: Optional[str] = None

CONTEXT_SETTINGS = dict(help_option_names=['-h', '--help'])
LOADING = f'{glyphs.md_timer_outline} Speedtest running...'
LOADING_DICT = { 'text': LOADING, 'class': 'loading', 'tooltip': 'Speedtest is running'}
LOGFILE = Path.home() / '.waybar-speedtest-results.log'

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

def parse_speedtest_output(output=None, download: bool=False, upload: bool=False, bytes: bool=False) -> str:
    download_speed = output.download.bits if download and output.download and output.download.bits else None
    upload_speed = output.upload.bits if upload and output.upload and output.upload.bits else None

    icon = get_icon(int((download_speed + upload_speed) / 2) if download_speed and upload_speed else download_speed or upload_speed or 0)

    parts = []
    if download_speed:
        parts.append(f'{glyphs.cod_arrow_small_down}{util.network_speed(number=download_speed, bytes=bytes)}')
    if upload_speed:
        parts.append(f'{glyphs.cod_arrow_small_up}{util.network_speed(number=upload_speed, bytes=bytes)}')

    if parts:
        return f'{util.color_title(icon)} Speedtest {" ".join(parts)}'
    else:
        return f'{util.color_title(icon)} Speedtest {util.color_error("All tests failed")}'

def run_speedtest(download: bool=True, upload: bool=True, bytes: bool=False):
    download_results = None
    upload_results = None

    s = speedtest.Speedtest(secure=True)

    if download:
        try:
            s.download()
            download_results = SpeedtestResults(success=True, bits=int(s.results.download))
        except Exception as e:
            download_results = SpeedtestResults(success=False, error=str(e))
    if upload:
        try:
            s.upload()
            upload_results = SpeedtestResults(success=True, bits=int(s.results.upload))
        except Exception as e:
            upload_results = SpeedtestResults(success=False, error=str(e))

    speedtest_data = SpeedtestOutput(download=download_results, upload=upload_results)

    return speedtest_data

def worker(download: bool=False, upload: bool=False, bytes: bool=False, interval: int=300):
    while True:
        update_event.wait()
        update_event.clear()

        logging.info('[main] entering main loop')
        if not util.waybar_is_running():
            logging.info('[main] waybar not running')
            sys.exit(0)
        else:
            if util.network_is_reachable():
                if not upload and not download:
                    upload = download = True

                print(json.dumps(LOADING_DICT))

                download_speed = 0
                upload_speed = 0

                speedtest_data = run_speedtest(download=download, upload=upload, bytes=bytes)
                if download:
                    if speedtest_data.download:
                        if speedtest_data.download.bits is not None:
                            download_speed = speedtest_data.download.bits
                
                if upload:
                    if speedtest_data.upload:
                        if speedtest_data.upload.bits is not None:
                            upload_speed = speedtest_data.upload.bits
                
                icon = get_icon(int((download_speed + upload_speed) / 2) if download_speed and upload_speed else download_speed or upload_speed or 0)

                parts = []
                if download_speed:
                    parts.append(f'{glyphs.cod_arrow_small_down}{util.network_speed(number=download_speed, bytes=bytes)}')
                if upload_speed:
                    parts.append(f'{glyphs.cod_arrow_small_up}{util.network_speed(number=upload_speed, bytes=bytes)}')

                if parts:
                    output = {
                        'text'    : f'{icon} Speedtest {" ".join(parts)}',
                        'class'   : 'success',
                        'tooltip' : 'Speedtest results',
                    }
                else:
                    output = {
                        'text'    : f'{icon} Speedtest {util.color_error("All tests failed")}',
                        'class'   : 'failure',
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
@click.option('-d', '--download', is_flag=True, default=False, help='Only run the download test')
@click.option('-u', '--upload', is_flag=True, default=False, help='Only run the upload test')
@click.option('-b', '--bytes', is_flag=True, default=False, help='Display output using bytes instead of bits')
@click.option('-i', '--interval', type=int, help='The update interval (in seconds)')
def main(download, upload, bytes, interval):
    logging.info('[main] entering')

    threading.Thread(target=worker, args=(download, upload, bytes, interval), daemon=True).start()
    update_event.set()

    while True:
        time.sleep(interval)
        update.event(set)

if __name__ == '__main__':
    main()
