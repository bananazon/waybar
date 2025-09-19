#!/usr/bin/env python3

from pathlib import Path
from polybar import glyphs, util
from typing import Optional, NamedTuple
import logging
import os
import signal
import subprocess
import sys
import time
import traceback

# Ensure required modules are present
util.validate_requirements(required=['click', 'speedtest'])
import click
import speedtest

# Named tuples for structured results
class SpeedtestResults(NamedTuple):
    success: Optional[bool] = False
    error: Optional[str] = None
    bits: Optional[int] = None

class SpeedtestOutput(NamedTuple):
    download: Optional[SpeedtestResults] = None
    upload: Optional[SpeedtestResults] = None
    icon: Optional[str] = None

# Paths and constants
CONTEXT_SETTINGS = dict(help_option_names=['-h', '--help'])
TMPFILE = Path.home() / '.polybar-speedtest-result.txt'
LOCKFILE = Path.home() / '.polybar-speedtest.lock'
LOGFILE = Path.home() / '.polybar-speedtest-result.log'
LOADING = f'{util.color_title(glyphs.md_timer_outline)} Speedtest running...'

# Logging configuration
logging.basicConfig(
    filename=LOGFILE,
    filemode='a',
    format='%(asctime)s [%(levelname)-5s] - %(message)s',
    level=logging.DEBUG
)

# Helpers
def get_icon(speed: int = 0) -> str:
    if speed < 100_000_000:
        return glyphs.md_speedometer_slow
    elif speed < 500_000_000:
        return glyphs.md_speedometer_medium
    else:
        return glyphs.md_speedometer_fast

def parse_speedtest_output(output=None, download: bool=False, upload: bool=False, bytes: bool=False) -> str:
    logging.info(f'[parse_speedtest_output] - output={output}, download={download}, upload={upload}, bytes={bytes}')
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
    logging.info(f'[run_speedtest] download={download}, upload={upload}, bytes={bytes}')
    download_results = None
    upload_results = None

    s = speedtest.Speedtest(secure=True)

    if download:
        try:
            s.download()
            download_results = SpeedtestResults(success=True, bits=int(s.results.download))
            logging.info('[run_speedtest] download test successful!')
        except Exception as e:
            download_results = SpeedtestResults(success=False, error=str(e))
            logging.error(f'[run_speedtest] download failed: {e}')
    if upload:
        try:
            s.upload()
            upload_results = SpeedtestResults(success=True, bits=int(s.results.upload))
            logging.info('[run_speedtest] upload test successful!')
        except Exception as e:
            upload_results = SpeedtestResults(success=False, error=str(e))
            logging.error(f'[run_speedtest] upload failed: {e}')

    output = SpeedtestOutput(download=download_results, upload=upload_results)

    try:
        module_output = parse_speedtest_output(output=output, download=download, upload=upload, bytes=bytes)
        TMPFILE.write_text(module_output)
        logging.info(f'[run_speedtest] success! output={module_output}')
    except Exception as e:
        logging.error(f'[run_speedtest] parse/write failed: {e}\n{traceback.format_exc()}')
        TMPFILE.write_text(f'{glyphs.oct_alert} {util.color_error(e)}')
    finally:
        # Notify Polybar
        subprocess.run(['polybar-msg', 'action', '#polybar-speedtest.hook.0'])

def cleanup_lockfile():
    if LOCKFILE.exists():
        LOCKFILE.unlink()
        logging.info(f'[worker] lockfile removed for {LOCKFILE.stem}')

def setup_signal_handlers():
    def handle_signal(signum, frame):
        logging.info(f'[worker] caught signal {signum}, exiting')
        cleanup_lockfile()
        sys.exit(0)

    for sig in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP):
        try:
            signal.signal(sig, handle_signal)
        except Exception as e:
            logging.error(f"[worker] failed to set signal handler: {e!r}")

# CLI
@click.group(context_settings=CONTEXT_SETTINGS)
def cli():
    """Polybar Speedtest CLI"""
    pass

@cli.command()
def show():
    """Display last speedtest result or loading message"""
    if TMPFILE.exists():
        logging.info('[show] TMPFILE exists')
        print(TMPFILE.read_text().strip())
    else:
        logging.info('[show] TMPFILE does not exist')
        print(LOADING)

@cli.command(help='Run a network speed test and return the results')
@click.option('-d', '--download', is_flag=True, default=False, help='Only run the download test')
@click.option('-u', '--upload', is_flag=True, default=False, help='Only run the upload test')
@click.option('-b', '--bytes', is_flag=True, default=False, help='Display output using bytes instead of bits')
@click.option('--background', is_flag=True, default=False, help='Run this script in the background')
@click.option('-i', '--interval', type=int, default=300, show_default=True, help='The update interval (in seconds)')
def run(download, upload, bytes, background, interval):
    util.network_is_reachable()
    TMPFILE.write_text(LOADING)

    if not upload and not download:
        upload = download = True

    logging.info(f'[run] download={download}, upload={upload}, bytes={bytes}, background={background}, interval={interval}')

    if background:
        if LOCKFILE.exists():
            logging.info('[worker] worker already running, exiting')
            return

        subprocess.run(['polybar-msg', 'action', f'#polybar-speedtest.send.{LOADING}'])
        logging.info('[run] launching background worker')
        subprocess.Popen(
            [__file__, 'worker', str(int(download)), str(int(upload)), str(int(bytes)), str(int(background)), str(interval)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            stdin=subprocess.DEVNULL,
            start_new_session=True
        )
        subprocess.run(['polybar-msg', 'action', '#polybar-speedtest.hook.0'])
    else:
        subprocess.run(['polybar-msg', 'action', f'#polybar-speedtest.send.{LOADING}'])
        logging.info('[run] running in foreground')
        run_speedtest(download=download, upload=upload, bytes=bytes)

@cli.command()
@click.argument('download', type=int, required=True)
@click.argument('upload', type=int, required=True)
@click.argument('bytes', type=int, required=True)
@click.argument('background', type=int, required=False)
@click.argument('interval', type=int, required=False)
def worker(download, upload, bytes, background=1, interval=300):
    logging.info('[worker] starting worker loop')
    setup_signal_handlers()
    LOCKFILE.write_text(str(os.getpid()))

    try:
        while True:
            subprocess.run(['polybar-msg', 'action', f'#polybar-speedtest.send.{LOADING}'])
            logging.info('[worker] entered main loop iteration')
            if not util.polybar_is_running():
                logging.info('[worker] polybar not running, shutting down')
                break

            run_speedtest(download=bool(download), upload=bool(upload), bytes=bool(bytes))
            logging.info('[worker] returned from run_speedtest')

            if interval > 0:
                logging.info(f'[worker] sleeping for {interval} seconds before next run')
                time.sleep(interval)
            else:
                logging.info('[worker] interval <= 0, exiting after one run')
                break
    except Exception as e:
        logging.error(f'[worker] unhandled exception: {e}\n{traceback.format_exc()}')
    finally:
        cleanup_lockfile()
        logging.info('[worker] exiting worker loop')

if __name__ == '__main__':
    cli()

