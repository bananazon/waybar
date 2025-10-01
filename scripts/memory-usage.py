#!/usr/bin/env python3

from collections import OrderedDict
from pathlib import Path
from typing import Any, Dict, List, Optional, NamedTuple
from waybar import glyphs, state, util
import json
import re

util.validate_requirements(required=['click'])
import click

CACHE_DIR = util.get_cache_directory()
CONTEXT_SETTINGS = dict(help_option_names=['-h', '--help'])

class MemoryInfo(NamedTuple):
    success   : Optional[bool] = False
    error     : Optional[str]  = None
    available : Optional[int]  = 0
    buffers   : Optional[int]  = 0
    cache     : Optional[int]  = 0
    dimms     : Optional[list] = None
    free      : Optional[int]  = 0
    pct_free  : Optional[int]  = 0
    pct_total : Optional[int]  = 0
    pct_used  : Optional[int]  = 0
    shared    : Optional[int]  = 0
    total     : Optional[int]  = 0
    used      : Optional[int]  = 0

def generate_tooltip(memory_info):
    unit = 'G'
    tooltip = []
    tooltip_od = OrderedDict()

    if memory_info.total:
        tooltip_od['Total'] = util.byte_converter(number=memory_info.total, unit=unit)

    if memory_info.used:
        tooltip_od['Used'] = util.byte_converter(number=memory_info.used, unit=unit)

    if memory_info.free:
        tooltip_od['Free'] = util.byte_converter(number=memory_info.free, unit=unit)

    if memory_info.shared:
        tooltip_od['Shared'] = util.byte_converter(number=memory_info.shared, unit=unit)

    if memory_info.buffers:
        tooltip_od['Buffers'] = util.byte_converter(number=memory_info.buffers, unit=unit)

    if memory_info.cache:
        tooltip_od['Cache'] = util.byte_converter(number=memory_info.total, unit=unit)

    if memory_info.total:
        tooltip_od['Availale'] = util.byte_converter(number=memory_info.cache, unit=unit)

    max_key_length = 0
    for key in tooltip_od.keys():
        max_key_length = len(key) if len(key) > max_key_length else max_key_length

    for key, value in tooltip_od.items():
        tooltip.append(f'{key:{max_key_length}} : {value}')

    if len(tooltip) > 0:
        tooltip.append('')

    if memory_info.dimms and type(memory_info.dimms) == list:
        for idx, dimm in enumerate(memory_info.dimms):
            if dimm.size and dimm.type and dimm.form_factor and dimm.speed:
                tooltip.append(f'DIMM {idx:02d} - {util.byte_converter(number=dimm.size, unit='G')} {dimm.type} {dimm.form_factor} @ {dimm.speed}')

    return '\n'.join(tooltip)

def get_dimm_info():
    command = 'sudo dmidecode -t memory | jc --dmidecode'
    rc, stdout, stderr = util.run_piped_command(command)
    if rc == 0 and stdout != '':
        json_data, err = util.parse_json_string(stdout)
        if not err:
            dimms = []
            for memory_device in json_data:
                if memory_device['description'] == 'Memory Device':
                    try:
                        bits = re.split(r'\s+', memory_device['values']['size'])
                        if len(bits) == 2:
                            raw = int(bits[0])
                            if bits[1] == 'MB':
                                memory_device['values']['size'] = int(raw * (1000**2))
                            if bits[1] == 'GB':
                                memory_device['values']['size'] = int(raw * (1000**3))
                    except:
                        pass

                    dimms.append(util.dict_to_namedtuple(name='DimmInfo', obj=memory_device['values']))

            return dimms if len(dimms) > 0 else None

    return None

def get_memory_usage():
    """
    Execute free -b -w and return a namedtuple with its values
    """

    command = 'free -b -w | sed -n "2p"'
    rc, stdout, stderr = util.run_piped_command(command)
    if rc == 0:
        if stdout != '':
            values    = re.split(r'\s+', stdout)
            total     = int(values[1])
            shared    = int(values[4])
            buffers   = int(values[5])
            cache     = int(values[6])
            available = int(values[7])
            used      = total - available
            free      = total - used
            pct_total = 100
            pct_used  = int(((total - available) / total) * 100)
            pct_free  = pct_total - pct_used

            mem_info = MemoryInfo(
                success   = True,
                total     = total,
                available = available,
                buffers   = buffers,
                cache     = cache,
                dimms     = get_dimm_info(),
                free      = free,
                pct_free  = pct_free,
                pct_total = 100,
                pct_used  = pct_used,
                shared    = shared,
                used      = used,
            )
        else:
            mem_info = MemoryInfo(
                success = False,
                error   = 'no output from free',
            )
    else:
        mem_info = MemInfo(
            success   = False,
            error     = stderr or f'failed to execute "{command}"',
        )

    return mem_info

@click.command(help='Get memory usage from free(1) and dmidecode(8)', context_settings=CONTEXT_SETTINGS)
@click.option('-u', '--unit', required=False, type=click.Choice(util.get_valid_units()), help=f'The unit to use for output display')
@click.option('-t', '--toggle', default=False, is_flag=True, help='Toggle the output format')
def main(unit, toggle):
    mode_count = 3
    statefile = Path(CACHE_DIR) / f'waybar-{util.called_by() or "memory-usage"}-state'

    if toggle:
        mode = state.next_state(statefile=statefile, mode_count=mode_count)
    else:
        mode = state.current_state(statefile=statefile)

    memory_info = get_memory_usage()

    if memory_info.success:
        tooltip   = generate_tooltip(memory_info)
        pct_total = memory_info.pct_total
        pct_used  = memory_info.pct_used
        pct_free  = memory_info.pct_free
        total     = util.byte_converter(number=memory_info.total, unit=unit)
        used      = util.byte_converter(number=memory_info.used, unit=unit)
        free      = util.byte_converter(number=memory_info.free, unit=unit)

        if pct_free < 20:
            output_class = 'critical'
        elif pct_free >= 20 and pct_free < 50:
            output_class = 'warning'
        elif pct_free >= 50:
            output_class = 'good'

        if mode == 0:
            output = {
                'text'    : f'{glyphs.md_memory}{glyphs.icon_spacer}{used} / {total}',
                'class'   : output_class,
                'tooltip' : tooltip,
            }
        elif mode == 1:
            output = {
                'text'    : f'{glyphs.md_memory}{glyphs.icon_spacer}{pct_used}% used',
                'class'   : output_class,
                'tooltip' : tooltip,
            }
        elif mode == 2:
            output = {
                'text'    : f'{glyphs.md_memory}{glyphs.icon_spacer}{used}% used / {free}% free',
                'class'   : output_class,
                'tooltip' : tooltip,
            }
    else:
        output = {
            'text'    : f'{glyphs.md_memory}{glyphs.icon_spacer}{memory_info.error if memory_info.error is not None else "Unknown error"}',
            'class'   : 'error',
            'tooltip' : 'System Memory',
        }

    print(json.dumps(output))

if __name__ == "__main__":
    main()
