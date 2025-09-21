#!/usr/bin/env python3

from pathlib import Path
from waybar import glyphs, state, util
from typing import Any, Dict, List, Optional, NamedTuple
import argparse
import json
import os
import re
import sys
import time

DISK_IDENTIFIER : str | None = None
DISK_LABEL      : str | None = None

class FilesystemInfo(NamedTuple):
    success    : Optional[bool]  = False
    error      : Optional[str]   = None
    mountpoint : Optional[str]   = None
    filesystem : Optional[str]   = None
    pct_total  : Optional[int]   = 0
    pct_used   : Optional[int]   = 0
    pct_free   : Optional[int]   = 0
    total      : Optional[int]   = 0
    used       : Optional[int]   = 0
    free       : Optional[int]   = 0

def get_uuid(mountpoint: str='') -> str:
    rc, device, _ = util.run_piped_command(f'findmnt -n -o SOURCE {mountpoint}')
    if rc == 0 and device != '':
        rc, uuid, _ = util.run_piped_command(f'blkid -s UUID -o value "{device}"')
        if rc == 0 and uuid != '':
            return uuid
    else:
        util.error_exit(icon=glyphs.md_alert, message=f'{mountpoint} is an invalid mountpoint')
    
    return None

def set_label(label: str=None):
    """
    Set the global label variable
    """
    global DISK_LABEL
    DISK_LABEL = label

def set_disk_identifier(mountpoint: str=None):
    """
    Set the disk UUID
    """
    global DISK_IDENTIFIER, DISK_LABEL

    uuid = get_uuid(mountpoint=mountpoint)

    DISK_IDENTIFIER = uuid if uuid else DISK_LABEL
    
def get_statefile() -> str:
    global DISK_IDENTIFIER

    statefile = os.path.basename(__file__)
    statefile_no_ext = os.path.splitext(statefile)[0]

    return Path.home() / f'.waybar-{statefile_no_ext}-{DISK_IDENTIFIER}-state'

def get_disk_usage(mountpoint: str) -> list:
    """
    Execute df -B 1 against a mount point and return a namedtuple with its values
    """

    rc, stdout, stderr = util.run_piped_command(f'findmnt {mountpoint}')
    if rc != 0:
        return FilesystemInfo(
            success    = False,
            mountpoint = mountpoint,
            error      = f'{mountpoint} does not exist'
        )

    command = f'df -B 1 {mountpoint} | sed -n "2p"'
    rc, stdout, stderr = util.run_piped_command(command)
    if rc == 0:
        if stdout != '':
            values = re.split(r'\s+', stdout)

            filesystem = values[0]
            total      = int(values[1])
            used       = int(values[2])
            free       = int(values[3])
            pct_total  = 100
            pct_used   = round((used / (used + free)) * 100)
            pct_free   = pct_total - pct_used

            filesystem_info = FilesystemInfo(
                success    = True,
                mountpoint = mountpoint,
                filesystem = filesystem,
                total      = total,
                used       = used,
                free       = free,
                pct_total  = pct_total,
                pct_used   = pct_used,
                pct_free   = pct_free,
            )
        else:
            filesystem_info = FilesystemInfo(
                success    = False,
                mountpoint = mountpoint,
                error      = f'{mountpoint} no output from {command}',
            )
    else:
        filesystem_info = FilesystemInfo(
            success   = False,
            interface = interface,
            error     = f'{mountpoint} {stderr}' if stderr != '' else f'{mountpoint} failed to execute {command}',
        )

    return filesystem_info

def main():
    mode_count = 3
    parser = argparse.ArgumentParser(description='Get disk info from df(1)')
    parser.add_argument('-m', '--mountpoint', help='The mountpoint to check', required=False)
    parser.add_argument('-u', '--unit', help='The unit to use for display', choices=util.get_valid_units(), required=False)
    parser.add_argument('-l', '--label', help='For now we need to pass a friendly mountpoint label', required=False)
    parser.add_argument('-t', '--toggle', action='store_true', help='Toggle the output format', required=False)
    args = parser.parse_args()

    set_label(label=args.label)
    set_disk_identifier(mountpoint=args.mountpoint)

    if args.toggle:
        mode = state.next_state(statefile=get_statefile(), mode_count=mode_count)
    else:
        mode = state.current_state(statefile=get_statefile())

    disk_info = get_disk_usage(args.mountpoint)

    if disk_info.success:
        pct_total = disk_info.pct_total
        pct_used  = disk_info.pct_used
        pct_free  = disk_info.pct_free
        total     = util.byte_converter(number=disk_info.total, unit=args.unit)
        used      = util.byte_converter(number=disk_info.used, unit=args.unit)
        free      = util.byte_converter(number=disk_info.free, unit=args.unit)

        if pct_free < 20:
            output_class = 'critical'
        elif pct_free >= 20 and pct_free < 50:
            output_class = 'warning'
        elif pct_free >= 50:
            output_class = 'good'

        if mode == 0:
            output = {
                'text'    : f'{glyphs.md_harddisk} {args.mountpoint} {used} / {total}',
                'class'   : output_class,
                'tooltip' : 'Filesystem Usage',
            }
        elif mode == 1:
            output = {
                'text'    : f'{glyphs.md_harddisk} {args.mountpoint} {pct_used}% used',
                'class'   : output_class,
                'tooltip' : 'Filesystem Usage',
            }
        elif mode == 2:
            output = {
                'text'    : f'{glyphs.md_harddisk} {args.mountpoint} {used}% used / {free}% free',
                'class'   : output_class,
                'tooltip' : 'Filesystem Usage',
            }
    else:
        output = {
            'text'    : f'{glyphs.md_harddisk} {args.mountpoint} {disk_info.error if disk_info.error is not None else "Unknown error"}',
            'class'   : 'error',
            'tooltip' : 'Filesystem Usage',
        }
    
    print(json.dumps(output))

if __name__ == "__main__":
    main()
