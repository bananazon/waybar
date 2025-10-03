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

cache_dir        = util.get_cache_directory()
condition        = threading.Condition()
context_settings = dict(help_option_names=['-h', '--help'])
disk_info        = None
format_index     = 0
formats          = [0, 1, 2]
loading          = f'{glyphs.md_timer_outline}{glyphs.icon_spacer}Working...'
loading_dict     = { 'text': loading, 'class': 'loading', 'tooltip': 'Gathering disk statistics'}
logfile          = cache_dir / 'waybar-filesystem-usage.log'
needs_fetch      = False
needs_redraw     = False

sys.stdout.reconfigure(line_buffering=True)

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

logging.basicConfig(
    filename=logfile,
    filemode='a',  # 'a' = append, 'w' = overwrite
    format='%(asctime)s [%(levelname)-5s] - %(message)s',
    level=logging.INFO
)

def refresh_handler(signum, frame):
    global needs_fetch, needs_redraw
    logging.info('[refresh_handler] - received SIGHUP — re-fetching data')
    with condition:
        needs_fetch = True
        needs_redraw = True
        condition.notify()

def toggle_format(signum, frame):
    global format_index, needs_redraw
    format_index = (format_index + 1) % len(formats)
    logging.info(f'[toggle_format] - received SIGUSR1 - switching output format to {format_index + 1}')
    with condition:
        needs_redraw = True
        condition.notify()

signal.signal(signal.SIGHUP, refresh_handler)
signal.signal(signal.SIGUSR1, toggle_format)  

def generate_tooltip(disk_info: namedtuple=None, show_stats: bool=False):
    logging.info(f'[generate_tooltip] - entering with mountpoint={disk_info.mountpoint}')
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

    return '\n'.join(tooltip)

def filesystem_exists(mountpoint: str = None):
    command = f'jc findmnt {mountpoint}'
    rc, _, _ = util.run_piped_command(command)
    return True if rc == 0 else False

def get_sample(filesystem: str=None):
    logging.info(f'[get_sample] - entering with filesystem={filesystem}')
    command = f'cat /proc/diskstats| jc --pretty --proc-diskstats'
    rc, stdout, stderr = util.run_piped_command(command)
    if rc == 0 and stdout != '':
        json_data, err = util.parse_json_string(stdout)
        if not err:
            for entry in json_data:
                if entry['device'] == filesystem:
                    sample = util.dict_to_namedtuple(name='DiskStatsSample', obj=entry)
                    return sample

    return None

def get_disk_stats(filesystem: str=None):
    logging.info(f'[get_disk_stats] - entering with filesystem={filesystem}')
    first = get_sample(filesystem=filesystem)
    time.sleep(1)
    second = get_sample(filesystem=filesystem)

    if not first or not second:
        return DiskStats(
            success = False,
            error   = 'failed to get disk stats'
        )

    return DiskStats(
        success        = True,
        reads_per_sec  = (second.reads_completed - first.reads_completed),
        writes_per_sec = (second.writes_completed - first.writes_completed),
    )

def parse_lsblk(filesystem: str=None):
    logging.info(f'[parse_lsblk] - entering with filesystem={filesystem}')
    if filesystem:
        command = f'lsblk -O --json {filesystem}'
        rc, stdout, stderr = util.run_piped_command(command)
        if rc == 0 and stdout != '':
            json_data, err = util.parse_json_string(stdout)
            if not err:
                lsblk_data = util.dict_to_namedtuple(name='BlockDeviceData', obj=json_data.get('blockdevices')[0])
                return lsblk_data

    return None

def get_disk_usage(mountpoint: str, show_stats: bool=False) -> list:
    """
    Execute df -B 1 against a mount point and return a namedtuple with its values
    """
    logging.info(f'[get_disk_usage] - entering with mountpoint={mountpoint}')
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
            first = get_sample(filesystem=lsblk_data.kname)
            time.sleep(1)
            second = get_sample(filesystem=lsblk_data.kname)

    if df_item and findmnt_item:
        return FilesystemInfo(
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
            sample1    = first,
            sample2    = second,
        )

def worker(mountpoint: str=None, unit: str=None, show_stats: bool=False):
    global disk_info, needs_fetch, needs_redraw, format_index

    while True:
        with condition:
            while not (needs_fetch or needs_redraw):
                condition.wait()

            fetch        = needs_fetch
            redraw       = needs_redraw
            needs_fetch  = False
            needs_redraw = False

        if not filesystem_exists(mountpoint=mountpoint):
            output = {
                'text'    : f'{glyphs.md_harddisk}{glyphs.icon_spacer}{mountpoint} doesn\'t exist',
                'class'   : 'error',
                'tooltip' : 'Filesystem error',
            }
            print(json.dumps(output))
            disk_info = None
            continue    

        if fetch:
            print(json.dumps(loading_dict))
            disk_info = get_disk_usage(mountpoint=mountpoint, show_stats=show_stats)

        if disk_info is None:
            continue

        if disk_info.success:
            if redraw:
                logging.info(f'[worker] - successfully retrieved data for mountpoint {mountpoint}')
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

                if format_index == 0:
                    text = f'{glyphs.md_harddisk}{glyphs.icon_spacer}{mountpoint} {used} / {total}'
                elif format_index == 1:
                    text = f'{glyphs.md_harddisk}{glyphs.icon_spacer}{mountpoint} {pct_used}% used'
                elif format_index == 2:
                    text = f'{glyphs.md_harddisk}{glyphs.icon_spacer}{mountpoint} {used}% used / {free}% free'

                output = {
                    'text'    : text,
                    'class'   : output_class,
                    'tooltip' : generate_tooltip(disk_info=disk_info, show_stats=show_stats),
                }
        else:
            output = {
                'text'    : f'{glyphs.md_harddisk}{glyphs.icon_spacer}{mountpoint} {disk_info.error}',
                'class'   : 'error',
                'tooltip' : generate_tooltip(disk_info=disk_info, show_stats=show_stats),
            }

        print(json.dumps(output))

@click.command(help='Get disk informatiopn from df(1)', context_settings=context_settings)
@click.option('-m', '--mountpoint', required=True, help=f'The mountpoint to check')
@click.option('-u', '--unit', required=False, default='auto', type=click.Choice(util.get_valid_units()), help=f'The unit to use for output display')
@click.option('-l', '--label', required=True, help=f'A unique label to use')
@click.option('-s', '--show-stats', is_flag=True, help=f'Gather disk statistics and display them in the tooltip')
@click.option('-i', '--interval', type=int, default=5, help='The update interval (in seconds)')
@click.option('-t', '--test', default=False, is_flag=True, help='Print the output and exit')
def main(mountpoint, unit, label, show_stats, interval, test):
    global needs_fetch, needs_redraw

    if test:
        disk_info = get_disk_usage(mountpoint=mountpoint, show_stats=show_stats)
        util.pprint(disk_info)
        print()
        print(generate_tooltip(disk_info=disk_info, show_stats=show_stats))
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
