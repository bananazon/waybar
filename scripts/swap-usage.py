#!/usr/bin/env python3

from pathlib import Path
from typing import Any, Dict, List, Optional, NamedTuple
from waybar import glyphs, state, util
import json
import re

util.validate_requirements(modules=['click'])
import click

cache_dir = util.get_cache_directory()
context_settings = dict(help_option_names=['-h', '--help'])

class SwapInfo(NamedTuple):
    success   : Optional[bool]  = False
    error     : Optional[str]   = None
    total     : Optional[int]   = 0
    used      : Optional[int]   = 0
    free      : Optional[int]   = 0
    pct_total : Optional[int]   = 0
    pct_used  : Optional[int]   = 0
    pct_free  : Optional[int]   = 0

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
            error     = stderr or f'failed to execute "{command}"',
        )

    return swap_info

@click.command(help='Get swap usage from free(1)', context_settings=context_settings)
@click.option('-u', '--unit', required=False, type=click.Choice(util.get_valid_units()), help=f'The unit to use for output display')
@click.option('-t', '--toggle', default=False, is_flag=True, help='Toggle the output format')
def main(unit, toggle):
    mode_count = 3
    statefile = Path(cache_dir) / f'waybar-{util.called_by() or "swap-usage"}-state'

    if toggle:
        mode = state.next_state(statefile=statefile, mode_count=mode_count)
    else:
        mode = state.current_state(statefile=statefile)

    swap_info = get_swap_usage()

    if swap_info.success:
        pct_total = swap_info.pct_total
        pct_used  = swap_info.pct_used
        pct_free  = swap_info.pct_free
        total     = util.byte_converter(number=swap_info.total, unit=unit)
        used      = util.byte_converter(number=swap_info.used, unit=unit)
        free      = util.byte_converter(number=swap_info.free, unit=unit)

        if pct_free < 20:
            output_class = 'critical'
        elif pct_free >= 20 and pct_free < 50:
            output_class = 'warning'
        elif pct_free >= 50:
            output_class = 'good'

        if mode == 0:
            output = {
                'text'    : f'{glyphs.cod_arrow_swap}{glyphs.icon_spacer}{used} / {total}',
                'class'   : output_class,
                'tooltip' : 'Swap Usage',
            }
        elif mode == 1:
            output = {
                'text'    : f'{glyphs.cod_arrow_swap}{glyphs.icon_spacer}{pct_used}% used',
                'class'   : output_class,
                'tooltip' : 'Swap Usage',
            }
        elif mode == 2:
            output = {
                'text'    : f'{glyphs.cod_arrow_swap}{glyphs.icon_spacer}{used}% used / {free}% free',
                'class'   : output_class,
                'tooltip' : 'Swap Usage',
            }
    else:
        output = {
            'text'    : f'{glyphs.cod_arrow_swap}{glyphs.icon_spacer}{swap_info.error if swap_info.error is not None else "Unknown error"}',
            'class'   : 'error',
            'tooltip' : 'Swap Usage',
        }

    print(json.dumps(output))

if __name__ == "__main__":
    main()
