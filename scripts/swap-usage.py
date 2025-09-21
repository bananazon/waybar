#!/usr/bin/env python3

from pathlib import Path
from typing import Any, Dict, List, Optional, NamedTuple
from waybar import glyphs, state, util
import argparse
import json
import os
import re
import sys
import time

class SwapInfo(NamedTuple):
    success   : Optional[bool]  = False
    error     : Optional[str]   = None
    total     : Optional[int]   = 0
    used      : Optional[int]   = 0
    free      : Optional[int]   = 0
    pct_total : Optional[int]   = 0
    pct_used  : Optional[int]   = 0
    pct_free  : Optional[int]   = 0

def get_statefile() -> str:
    statefile = os.path.basename(__file__)
    statefile_no_ext = os.path.splitext(statefile)[0]
    return Path.home() / f'.waybar-{statefile_no_ext}-state'

def get_swap_usage():
    """
    Execute free -b -w and return a namedtuple with its values
    """

    command = 'free -b -w | sed -n "3p"'
    rc, stdout, stderr = util.run_piped_command(command)
    if rc == 0:
        if stdout != '':
            values    = re.split(r'\s+', stdout)
            total     = int(values[1])
            used      = int(values[2])
            free      = int(values[3])
            pct_total = 100
            pct_used  = int(used / total) * 100
            pct_free  = pct_total - pct_used

            swap_info = SwapInfo(
                success   = True,
                total     = total,
                used      = used,
                free      = free,
                pct_total = 100,
                pct_used  = pct_used,
                pct_free  = pct_free,

            )
        else:
            swap_info = SwapInfo(
                success = False,
                error   = 'no output from free',
            )
    else:
        swap_info = SwapInfo(
            success   = False,
            error     = stderr if stderr != '' else f'failed to execute "{command}"',
        )

    return swap_info

def main():
    mode_count = 3
    parser = argparse.ArgumentParser(description='Get swap usage from free(1)')
    parser.add_argument('-u', '--unit', help='The unit to use for display', choices=util.get_valid_units(), required=False)
    parser.add_argument('-t', '--toggle', action='store_true', help='Toggle the output format', required=False)
    args = parser.parse_args()

    if args.toggle:
        mode = state.next_state(statefile=get_statefile(), mode_count=mode_count)
    else:
        mode = state.current_state(statefile=get_statefile())

    swap_info = get_swap_usage()

    if swap_info.success:
        pct_total = swap_info.pct_total
        pct_used  = swap_info.pct_used
        pct_free  = swap_info.pct_free
        total     = util.byte_converter(number=swap_info.total, unit=args.unit)
        used      = util.byte_converter(number=swap_info.used, unit=args.unit)
        free      = util.byte_converter(number=swap_info.free, unit=args.unit)

        if pct_free < 20:
            output_class = 'critical'
        elif pct_free >= 20 and pct_free < 50:
            output_class = 'warning'
        elif pct_free >= 50:
            output_class = 'good'

        if mode == 0:
            output = {
                'text'    : f'{glyphs.cod_arrow_swap} {used} / {total}',
                'class'   : output_class,
                'tooltip' : 'Swap Usage',
            }
        elif mode == 1:
            output = {
                'text'    : f'{glyphs.cod_arrow_swap} {pct_used}% used',
                'class'   : output_class,
                'tooltip' : 'Swap Usage',
            }
        elif mode == 2:
            output = {
                'text'    : f'{glyphs.cod_arrow_swap} {used}% used / {free}% free',
                'class'   : output_class,
                'tooltip' : 'Swap Usage',
            }
    else:
        output = {
            'text'    : f'{glyphs.cod_arrow_swap} {swap_info.error if swap_info.error is not None else "Unknown error"}',
            'class'   : 'error',
            'tooltip' : 'Swap Usage',
        }

    print(json.dumps(output))

if __name__ == "__main__":
    main()
