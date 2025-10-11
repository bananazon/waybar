#!/usr/bin/env python3

from collections import namedtuple, OrderedDict
from glob import glob
from pathlib import Path
from waybar import glyphs, state, util
from typing import Any, Dict, List, Optional, NamedTuple
import json
import logging
import os
import re
import signal
import subprocess
import sys
import threading
import time

util.validate_requirements(modules=['click'])
import click

util.validate_requirements(binaries=['jc'])

sys.stdout.reconfigure(line_buffering=True)

cache_dir        = util.get_cache_directory()
condition        = threading.Condition()
context_settings = dict(help_option_names=['-h', '--help'])
disk_consumers   = None
format_index     = 0
logfile          = cache_dir / f'waybar-filesystem-usage.log'
needs_fetch      = False
needs_redraw     = False

formats : list | None=None

class PathEntry(NamedTuple):
    success : Optional[bool] = False
    error   : Optional[str]  = None
    count   : Optional[int]  = -1
    path    : Optional[str]  = None
    usage   : Optional[OrderedDict] = None
    updated : Optional[str]  = None

def configure_logging(debug: bool=False):
    logging.basicConfig(
        filename = logfile,
        filemode = 'w',  # 'a' = append, 'w' = overwrite
        format   = '%(asctime)s [%(levelname)-5s] - %(message)s',
        level    = logging.DEBUG if debug else logging.INFO
    )

def refresh_handler(signum, frame):
    global needs_fetch, needs_redraw
    logging.info(f'[refresh_handler] - received SIGHUP — re-fetching data')
    with condition:
        needs_fetch = True
        needs_redraw = True
        condition.notify()

def toggle_format(signum, frame):
    global formats, format_index, needs_redraw
    format_index = (format_index + 1) % len(formats)
    if disk_consumers and type(disk_consumers) == list:
        path = disk_consumers[format_index].path
    else:
        path = format_index + 1
    logging.info(f'[toggle_format] - received SIGUSR1 - switching output format to {path}')
    with condition:
        needs_redraw = True
        condition.notify()

signal.signal(signal.SIGHUP, refresh_handler)
signal.signal(signal.SIGUSR1, toggle_format)

def generate_tooltip(disk_consumers: namedtuple=None, show_stats: bool=False):
    tooltip = []
    max_len = 0
    for key, _ in disk_consumers.usage.items():
        max_len = len(os.path.basename(key)) if len(os.path.basename(key)) > max_len else max_len
    
    for key, value in disk_consumers.usage.items():
        icon = glyphs.md_folder if os.path.isdir(key) else glyphs.md_file
        tooltip.append(f'{icon}{glyphs.icon_spacer}{os.path.basename(key):{max_len}} {util.byte_converter(number=value, unit="auto")}')
    
    tooltip.append('')
    tooltip.append(f'Last updated {disk_consumers.updated}')

    return '\n'.join(tooltip)

def find_consumers(path: str=None):
    min_bytes = 1_048_576
    if Path(path).exists():
        paths = glob(f'{path}/*')
        command = ['du', '-sb', *paths]
        try:
            result = subprocess.run(
                command,
                stdout = subprocess.PIPE,
                stderr = subprocess.PIPE,
                text   = True
            )
            rc = result.returncode
            stdout = result.stdout.lstrip().rstrip()
            if stdout != '':
                usage = {}
                for line in stdout.split('\n'):
                    match = re.search(r'^([\d]+)\s+(.*)$', line)
                    if match:
                        if int(match.group(1)) > min_bytes:
                            usage[match.group(2)] = int(match.group(1))
                sorted_data_desc = dict(sorted(usage.items(), key=lambda x: x[1], reverse=True))
                usage_od = OrderedDict()
                for item, size in sorted_data_desc.items():
                    usage_od[item] = size

                return PathEntry(
                    success = True,
                    path    = path,
                    count   = len(usage_od),
                    usage   = usage_od,
                    updated = util.get_human_timestamp(),
                )
        except Exception as e:
            return PathEntry(
                success = False,
                path    = path,
                usage   = f'failed to get usage',
            )
    else:
        return PathEntry(
            success = False,
            path    = path,
            usage   = 'doesn\'t exist',
        )

def render_output(disk_consumers: namedtuple=None, unit: str=None, icon: str=None, show_stats: bool=False):
    if disk_consumers.success:
        text = f'{icon}{glyphs.icon_spacer}{disk_consumers.path.replace('&', '&amp')}'
        output_class = 'success'
        tooltip = generate_tooltip(disk_consumers=disk_consumers)
    else:
        text = f'{icon}{glyphs.icon_spacer}{disk_consumers.path} {disk_consumers.error}'
        output_class = 'error'
        tooltip = f'{disk_consumers.path} error'
    
    return text, output_class, tooltip

def worker(paths: list=None, unit: str=None):
    global disk_consumers, needs_fetch, needs_redraw, format_index

    while True:
        with condition:
            while not (needs_fetch or needs_redraw):
                condition.wait()

            fetch        = needs_fetch
            redraw       = needs_redraw
            needs_fetch  = False
            needs_redraw = False
        
        if fetch:
            disk_consumers = []
            for path in paths:
                print(json.dumps({
                    'text'    : f'{glyphs.md_timer_outline}{glyphs.icon_spacer}Scanning {path}...',
                    'class'   : 'loading',
                    'tooltip' : f'Scanning {path}...',
                }))
                path_usage = find_consumers(path=path)
                disk_consumers.append(path_usage)

        if disk_consumers is None:
            continue

        if disk_consumers and type(disk_consumers) == list:
            if redraw:
                text, output_class, tooltip = render_output(disk_consumers=disk_consumers[format_index], icon=glyphs.md_folder)
                output = {
                    'text'    : text,
                    'class'   : output_class,
                    'tooltip' : tooltip,
                }
                print(json.dumps(output))

@click.command(help='Show a list of disk consumers for one of more directories', context_settings=context_settings)
@click.option('-p', '--path', required=True, multiple=True, default=['~'], help=f'The path to check')
@click.option('-u', '--unit', required=False, default='auto', type=click.Choice(util.get_valid_units()), help=f'The unit to use for output display')
@click.option('-i', '--interval', type=int, default=5, help='The update interval (in seconds)')
@click.option('-t', '--test', default=False, is_flag=True, help='Print the output and exit')
@click.option('-d', '--debug', default=False, is_flag=True, help='Enable debug logging')
def main(path, unit, interval, test, debug):
    global formats, needs_fetch, needs_redraw

    configure_logging(debug=debug)
    formats = list(range(len(path)))
    paths = [os.path.expanduser(item).rstrip('/') for item in path]

    if test:
        disk_consumers = find_consumers(path=paths[0])
        util.pprint(disk_consumers)
        print()
        print(generate_tooltip(disk_consumers=disk_consumers))
        return

    logging.info('[main] - entering')

    threading.Thread(target=worker, args=(path, unit,), daemon=True).start()

    with condition:
        needs_fetch = True
        needs_redraw = True
        condition.notify()

    while True:
        time.sleep(interval)
        with condition:
            needs_fetch = True
            needs_redraw = True
            condition.notify()

if __name__ == "__main__":
    main()
