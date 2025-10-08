#!/usr/bin/env python3

from collections import namedtuple, OrderedDict
from pathlib import Path
from waybar import glyphs, state, util
from typing import Any, Dict, List, Optional, NamedTuple
import json
import logging
import re
import signal
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
disk_info        = None
format_index     = 0
logfile          = cache_dir / f'waybar-filesystem-usage.log'
needs_fetch      = False
needs_redraw     = False

formats : list | None=None

class FilesystemInfo(NamedTuple):
    success    : Optional[bool] = False
    error      : Optional[str]  = None
    device     : Optional[str]  = None
    filesystem : Optional[str]  = None
    free       : Optional[int]  = 0
    fsopts     : Optional[str]  = None
    fstype     : Optional[str]  = None
    lsblk      : Optional[dict] = None
    mountpoint : Optional[str]  = None
    pct_free   : Optional[int]  = 0
    pct_total  : Optional[int]  = 0
    pct_used   : Optional[int]  = 0
    total      : Optional[int]  = 0
    used       : Optional[int]  = 0
    sample1    : Optional[namedtuple] = None
    sample2    : Optional[namedtuple] = None
    updated    : Optional[str]  = None

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
    if disk_info and type(disk_info) == list:
        mountpoint = disk_info[format_index].mountpoint
    else:
        mountpoint = format_index + 1
    logging.info(f'[toggle_format] - received SIGUSR1 - switching output format to {mountpoint}')
    with condition:
        needs_redraw = True
        condition.notify()

signal.signal(signal.SIGHUP, refresh_handler)
signal.signal(signal.SIGUSR1, toggle_format)

def generate_tooltip(disk_info: namedtuple=None, show_stats: bool=False):
    logging.debug(f'[generate_tooltip] - entering with mountpoint={disk_info.mountpoint}')
    tooltip = []
    tooltip_od = OrderedDict()
    if disk_info.filesystem:
        tooltip_od['Filesystem'] = disk_info.filesystem

    if disk_info.mountpoint:
        tooltip_od['Mountpoint'] = disk_info.mountpoint

    if disk_info.fstype:
        tooltip_od['Type'] = disk_info.fstype

    if disk_info.lsblk:
        if disk_info.lsblk.kname:
            tooltip_od['Kernel Name'] = disk_info.lsblk.kname

        if disk_info.lsblk.rm in [True, False]:
            tooltip_od['Removable'] = 'yes' if disk_info.lsblk.rm else 'no'

        if disk_info.lsblk.ro in [True, False]:
            tooltip_od['Read-only'] = 'yes' if disk_info.lsblk.ro else 'no'

    if show_stats and (disk_info.sample1 and disk_info.sample2):
        tooltip_od['Reads/sec'] = (disk_info.sample2.reads_completed - disk_info.sample1.reads_completed)
        tooltip_od['Writes/sec'] = (disk_info.sample2.writes_completed - disk_info.sample1.writes_completed)
        tooltip_od['Read Time/sec'] = (disk_info.sample2.read_time_ms - disk_info.sample1.read_time_ms)
        tooltip_od['Write Time/sec'] = (disk_info.sample2.write_time_ms - disk_info.sample1.write_time_ms)

    max_key_length = 0
    for key in tooltip_od.keys():
        max_key_length = len(key) if len(key) > max_key_length else max_key_length

    for key, value in tooltip_od.items():
        tooltip.append(f'{key:{max_key_length}} : {value}')

    if len(tooltip) > 0:
        tooltip.append('')
        tooltip.append(f'Last updated {disk_info.updated}')

    return '\n'.join(tooltip)

def filesystem_exists(mountpoint: str = None):
    command = f'jc findmnt {mountpoint}'
    rc, _, _ = util.run_piped_command(command)
    return True if rc == 0 else False

def get_sample():
    logging.debug(f'[get_sample] - entering function')
    command = f'cat /proc/diskstats| jc --pretty --proc-diskstats'
    rc, stdout, stderr = util.run_piped_command(command)
    if rc == 0 and stdout != '':
        json_data, err = util.parse_json_string(stdout)
        if not err:
            entries = []
            for entry in json_data:
                sample = util.dict_to_namedtuple(name='DiskStatsSample', obj=entry)
                entries.append(sample)
            return entries

    return None

def parse_lsblk(filesystem: str=None):
    logging.debug(f'[parse_lsblk] - entering with filesystem={filesystem}')
    if filesystem:
        command = f'lsblk -O --json {filesystem}'
        rc, stdout, stderr = util.run_piped_command(command)
        if rc == 0 and stdout != '':
            json_data, err = util.parse_json_string(stdout)
            if not err:
                lsblk_data = util.dict_to_namedtuple(name='BlockDeviceData', obj=json_data.get('blockdevices')[0])
                return lsblk_data

    return None

def get_disk_usage(mountpoints: list=None, show_stats: bool=False):
    logging.debug(f'[get_disk_usage] - entering with mountpoints={mountpoints}')
    disk_usage = []

    if show_stats:
        first_sample = get_sample()
        time.sleep(1)
        second_sample = get_sample()

    for mountpoint in mountpoints:
        if filesystem_exists(mountpoint=mountpoint):
            df_item = None
            findmnt_item = None
            first = None
            second = None

            command = f'jc --pretty df {mountpoint}'
            try:
                rc, stdout, stderr = util.run_piped_command(command)
                if rc == 0 and stdout != '':
                    df_data, err = util.parse_json_string(stdout)
                    if len(df_data) == 1:
                        df_item = df_data[0]
                else:
                    return FilesystemInfo(success = False, error = stderr or f'failed to execute {command}')
            except:
                return FilesystemInfo(success = False, error = stderr or f'failed to execute {command}')

            if df_item:
                command = f'jc --pretty findmnt {mountpoint}'
                try:
                    rc, stdout, stderr = util.run_piped_command(command)
                    if rc == 0 and stdout != '':
                        findmnt_data, err = util.parse_json_string(stdout)
                        if len(findmnt_data) == 1:
                            findmnt_item = findmnt_data[0]
                    else:
                        return FilesystemInfo(success = False, error = stderr or f'failed to execute {command}')
                except:
                    return FilesystemInfo(success = False, error   = stderr or f'failed to execute {command}')

                lsblk_data = parse_lsblk(filesystem=df_item['filesystem'])
                if lsblk_data and show_stats:
                    first = [entry for entry in first_sample if entry.device == lsblk_data.kname][0]
                    second = [entry for entry in second_sample if entry.device == lsblk_data.kname][0]

            if df_item and findmnt_item:
                disk_usage.append(FilesystemInfo(
                    success    = True,
                    filesystem = df_item['filesystem'],
                    mountpoint = mountpoint,
                    total      = df_item['1k_blocks'] * 1024,
                    used       = df_item['used'] * 1024,
                    free       = df_item['available'] * 1024,
                    pct_total  = 100,
                    pct_used   = df_item['use_percent'],
                    pct_free   = 100 - df_item['use_percent'],
                    fsopts     = findmnt_item.get('options') or None,
                    fstype     = findmnt_item.get('fstype') or None,
                    lsblk      = lsblk_data,
                    sample1    = first or None,
                    sample2    = second or None,
                    updated    = util.get_human_timestamp(),
                ))
        else:
            disk_usage.append(FilesystemInfo(
                success    = False,
                error      = 'doesn\'t exist',
                mountpoint = mountpoint,
            ))

    return disk_usage

def render_output(disk_info: namedtuple=None, unit: str=None, icon: str=None, show_stats: bool=False):
    if disk_info.success:
        pct_total = disk_info.pct_total
        pct_used  = disk_info.pct_used
        pct_free  = disk_info.pct_free
        total     = util.byte_converter(number=disk_info.total, unit=unit)
        used      = util.byte_converter(number=disk_info.used, unit=unit)
        free      = util.byte_converter(number=disk_info.free, unit=unit)

        if pct_free < 20:
            output_class = 'critical'
        elif pct_free < 50:
            output_class = 'warning'
        else:
            output_class = 'good'

        text = f'{icon}{glyphs.icon_spacer}{disk_info.mountpoint} {used} / {total}'
        output_class = output_class
        tooltip = generate_tooltip(disk_info=disk_info, show_stats=show_stats)
    else:
        text = f'{glyphs.md_alert}{glyphs.icon_spacer}{disk_info.mountpoint} {disk_info.error}'
        output_class = 'error'
        tooltip = f'{disk_info.mountpoint} error'

    return text, output_class, tooltip

def worker(mountpoints: list=None, unit: str=None, show_stats: bool=False):
    global disk_info, needs_fetch, needs_redraw, format_index

    while True:
        with condition:
            while not (needs_fetch or needs_redraw):
                condition.wait()

            fetch        = needs_fetch
            redraw       = needs_redraw
            needs_fetch  = False
            needs_redraw = False

        if fetch:
            loading      = f'{glyphs.md_timer_outline}{glyphs.icon_spacer}Gathering disk data...'
            loading_dict = { 'text': loading, 'class': 'loading', 'tooltip': 'Gathering disk data...'}
            if disk_info and type(disk_info) == list:
                text, _, tooltip = render_output(disk_info=disk_info[format_index], unit=unit, icon=glyphs.md_timer_outline)
                print(json.dumps({'text': text, 'class': 'loading', 'tooltip': tooltip}))
            else:
                print(json.dumps(loading_dict))

            disk_info = get_disk_usage(mountpoints=mountpoints, show_stats=show_stats)

        if disk_info is None:
            continue

        if disk_info and type(disk_info) == list:
            if redraw:
                text, output_class, tooltip = render_output(disk_info=disk_info[format_index], unit=unit, icon=glyphs.md_harddisk, show_stats=show_stats)

                output = {
                    'text'    : text,
                    'class'   : output_class,
                    'tooltip' : tooltip,
                }

                print(json.dumps(output))

@click.command(help='Get disk informatiopn from df(1)', context_settings=context_settings)
@click.option('-m', '--mountpoint', required=True, multiple=True, help=f'The mountpoint to check')
@click.option('-u', '--unit', required=False, default='auto', type=click.Choice(util.get_valid_units()), help=f'The unit to use for output display')
@click.option('-s', '--show-stats', is_flag=True, help=f'Gather disk statistics and display them in the tooltip')
@click.option('-i', '--interval', type=int, default=5, help='The update interval (in seconds)')
@click.option('-t', '--test', default=False, is_flag=True, help='Print the output and exit')
@click.option('-d', '--debug', default=False, is_flag=True, help='Enable debug logging')
def main(mountpoint, unit, show_stats, interval, test, debug):
    global formats, needs_fetch, needs_redraw

    configure_logging(debug=debug)
    formats = list(range(len(mountpoint)))

    if test:
        disk_info = get_disk_usage(mountpoints=mountpoint, show_stats=show_stats)
        util.pprint(disk_info[0])
        print()
        print(generate_tooltip(disk_info=disk_info[0], show_stats=show_stats))
        return

    logging.info('[main] - entering')

    threading.Thread(target=worker, args=(mountpoint, unit, show_stats), daemon=True).start()

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
