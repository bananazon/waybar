#!/usr/bin/env python3

from collections import OrderedDict
from pathlib import Path
from waybar import glyphs, state, util
from typing import Any, Dict, List, Optional, NamedTuple
import json

util.validate_requirements(modules=['click'])
import click

util.validate_requirements(binaries=['jc'])

CACHE_DIR = util.get_cache_directory()
CONTEXT_SETTINGS = dict(help_option_names=['-h', '--help'])

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

def generate_tooltip(disk_info):
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

def parse_lsblk(filesystem: str=None):
    if filesystem:
        command = f'lsblk -O --json {filesystem}'
        rc, stdout, stderr = util.run_piped_command(command)
        if rc == 0 and stdout != '':
            json_data, err = util.parse_json_string(stdout)
            if not err:
                lsblk_data = util.dict_to_namedtuple(name='BlockDeviceData', obj=json_data.get('blockdevices')[0])
                return lsblk_data

    return None

def get_disk_usage(mountpoint: str) -> list:
    """
    Execute df -B 1 against a mount point and return a namedtuple with its values
    """
    df_item = None
    findmnt_item = None

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
            lsblk      = parse_lsblk(filesystem=df_item['filesystem']),
        )

@click.command(help='Get disk informatiopn from df(1)', context_settings=CONTEXT_SETTINGS)
@click.option('-m', '--mountpoint', required=True, help=f'The mountpoint to check')
@click.option('-u', '--unit', required=False, type=click.Choice(util.get_valid_units()), help=f'The unit to use for output display')
@click.option('-l', '--label', required=True, help=f'A unique label to use')
@click.option('-t', '--toggle', default=False, is_flag=True, help='Toggle the output format')
def main(mountpoint, unit, label, toggle):
    mode_count = 3
    statefile = CACHE_DIR / f'waybar-{util.called_by() or "filesystem-usage"}-{label}-state'

    if filesystem_exists(mountpoint=mountpoint):
        if toggle:
            mode = state.next_state(statefile=statefile, mode_count=mode_count)
        else:
            mode = state.current_state(statefile=statefile)

        disk_info = get_disk_usage(mountpoint)
        if disk_info.success:
            tooltip   = generate_tooltip(disk_info)
            pct_total = disk_info.pct_total
            pct_used  = disk_info.pct_used
            pct_free  = disk_info.pct_free
            total     = util.byte_converter(number=disk_info.total, unit=unit)
            used      = util.byte_converter(number=disk_info.used, unit=unit)
            free      = util.byte_converter(number=disk_info.free, unit=unit)

            if pct_free < 20:
                output_class = 'critical'
            elif pct_free >= 20 and pct_free < 50:
                output_class = 'warning'
            elif pct_free >= 50:
                output_class = 'good'

            if mode == 0:
                output = {
                    'text'    : f'{glyphs.md_harddisk}{glyphs.icon_spacer}{mountpoint} {used} / {total}',
                    'class'   : output_class,
                    'tooltip' : tooltip,
                }
            elif mode == 1:
                output = {
                    'text'    : f'{glyphs.md_harddisk}{glyphs.icon_spacer}{mountpoint} {pct_used}% used',
                    'class'   : output_class,
                    'tooltip' : tooltip,
                }
            elif mode == 2:
                output = {
                    'text'    : f'{glyphs.md_harddisk}{glyphs.icon_spacer}{mountpoint} {used}% used / {free}% free',
                    'class'   : output_class,
                    'tooltip' : tooltip,
                }
        else:
            output = {
                'text'    : f'{glyphs.md_harddisk}{glyphs.icon_spacer}{mountpoint} {disk_info.error or "Unknown error"}',
                'class'   : 'error',
                'tooltip' : 'Filesystem Usage',
            }
    else:
        output = {
            'text'    : f'{glyphs.md_harddisk}{glyphs.icon_spacer}{mountpoint} doesn\'t exist',
            'class'   : 'error',
            'tooltip' : 'Filesystem Usage',
        }
    
    print(json.dumps(output))

if __name__ == "__main__":
    main()
