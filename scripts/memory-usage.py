#!/usr/bin/env python3

from collections import OrderedDict
from pathlib import Path
from typing import Any, Dict, List, Optional, NamedTuple
from waybar import glyphs, state, util
import json
import re

util.validate_requirements(modules=['click'])
import click

util.validate_requirements(binaries=['dmidecode', 'jc'])

context_settings = dict(help_option_names=['-h', '--help'])

class MemoryInfo(NamedTuple):
    success        : Optional[bool] = False
    error          : Optional[str]  = None
    available      : Optional[int]  = 0
    buffers        : Optional[int]  = 0
    buffers_cache  : Optional[int]  = 0
    cached         : Optional[int]  = 0
    dimms          : Optional[list] = None
    free           : Optional[int]  = 0
    pct_free       : Optional[int]  = 0
    pct_total      : Optional[int]  = 0
    pct_used       : Optional[int]  = 0
    shared         : Optional[int]  = 0
    total          : Optional[int]  = 0
    used           : Optional[int]  = 0
    swap_pct_total : Optional[int]  = 0
    swap_pct_used  : Optional[int]  = 0
    swap_pct_free  : Optional[int]  = 0
    swap_total     : Optional[int]  = 0
    swap_used      : Optional[int]  = 0
    swap_free      : Optional[int]  = 0
    updated        : Optional[str]  = None

def generate_tooltip(memory_info):
    unit = 'G'
    tooltip = []

    tooltip.append('Memory')
    tooltip_od = OrderedDict()
    if  memory_info.total >= 0:
        tooltip_od['Total'] = util.byte_converter(number=memory_info.total, unit=unit)

    if memory_info.used >= 0:
        tooltip_od['Used'] = util.byte_converter(number=memory_info.used, unit=unit)

    if memory_info.free >= 0:
        tooltip_od['Free'] = util.byte_converter(number=memory_info.free, unit=unit)

    if memory_info.shared >= 0:
        tooltip_od['Shared'] = util.byte_converter(number=memory_info.shared, unit=unit)

    if memory_info.buffers >= 0:
        tooltip_od['Buffers'] = util.byte_converter(number=memory_info.buffers, unit=unit)

    if memory_info.cached >= 0:
        tooltip_od['Cached'] = util.byte_converter(number=memory_info.cached, unit=unit)

    if memory_info.available >= 0:
        tooltip_od['Available'] = util.byte_converter(number=memory_info.available, unit=unit)

    max_key_length = 0
    for key in tooltip_od.keys():
        max_key_length = len(key) if len(key) > max_key_length else max_key_length

    for key, value in tooltip_od.items():
        tooltip.append(f'  {key:{max_key_length}} : {value}')

    if len(tooltip) > 0:
        tooltip.append('')

    tooltip.append('Swap')
    tooltip_od = OrderedDict()
    if memory_info.swap_total >= 0:
        tooltip_od['Total'] = util.byte_converter(number=memory_info.swap_total, unit=unit)

    if memory_info.swap_used >= 0:
        tooltip_od['Used'] = util.byte_converter(number=memory_info.swap_used, unit=unit)

    if memory_info.swap_free >= 0:
        tooltip_od['Free'] = util.byte_converter(number=memory_info.swap_free, unit=unit)

    max_key_length = 0
    for key in tooltip_od.keys():
        max_key_length = len(key) if len(key) > max_key_length else max_key_length

    for key, value in tooltip_od.items():
        tooltip.append(f'  {key:{max_key_length}} : {value}')

    if len(tooltip) > 0:
        tooltip.append('')

    if memory_info.dimms and type(memory_info.dimms) == list:
        for idx, dimm in enumerate(memory_info.dimms):
            if dimm.size and dimm.type and dimm.form_factor and dimm.speed:
                tooltip.append(f'DIMM {idx:02d} - {util.byte_converter(number=dimm.size, unit='G')} {dimm.type} {dimm.form_factor} @ {dimm.speed}')

    if len(tooltip) > 0:
        tooltip.append('')
        tooltip.append(f'Last updated {memory_info.updated}')

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
    Read /proc/meminfo and return a namedtuple with some of its values
    """
    command = 'cat /proc/meminfo | jc --pretty --proc-meminfo'
    rc, stdout, stderr = util.run_piped_command(command)
    if rc == 0 and stdout != '':
        json_data, err = util.parse_json_string(stdout)
        if not err:
            available     = json_data['MemAvailable'] * 1024
            buffers       = json_data['Buffers'] * 1024
            cached        = json_data['Cached'] * 1024
            free          = json_data['MemFree'] * 1024
            s_reclaimable = json_data['SReclaimable'] * 1024
            shared        = json_data['Shmem'] * 1024
            total         = json_data['MemTotal'] * 1024
            used          = total - free - buffers - cached - s_reclaimable
            pct_total     = 100
            pct_used      = int(((total - available) / total) * 100)
            pct_free      = pct_total - pct_used

            # Swap
            swap_total     = json_data['SwapTotal'] * 1024
            swap_free      = json_data['SwapFree'] * 1024
            swap_used      = swap_total - swap_free
            swap_pct_total = 100
            swap_pct_used  = int((swap_used / swap_total) * 100)
            swap_pct_free  = swap_pct_total - swap_pct_used

            mem_info = MemoryInfo(
                success        = True,
                available      = available,
                buffers        = buffers,
                buffers_cache  = buffers + cached + s_reclaimable,
                cached         = cached,
                dimms          = get_dimm_info(),
                free           = free,
                pct_free       = pct_free,
                pct_total      = pct_total,
                pct_used       = pct_used,
                shared         = shared,
                total          = total,
                used           = used,
                swap_total     = swap_total,
                swap_free      = swap_free,
                swap_used      = swap_total - swap_free,
                swap_pct_total = swap_pct_total,
                swap_pct_used  = swap_pct_used,
                swap_pct_free  = swap_pct_free,
                updated        = util.get_human_timestamp(),
            )
        else:
            mem_info = MemoryInfo(
                success = False,
                error   = 'no output from /proc/meminfo',
            )
    else:
        mem_info = MemInfo(
            success   = False,
            error     = stderr or f'failed to execute "{command}"',
        )

    return mem_info

@click.command(help='Get memory usage from /proc/meminfo and dmidecode(8)', context_settings=context_settings)
@click.option('-u', '--unit', required=False, type=click.Choice(util.get_valid_units()), help=f'The unit to use for output display')
@click.option('-t', '--toggle', default=False, is_flag=True, help='Toggle the output format')
def main(unit, toggle):
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

        output = {
            'text'    : f'{glyphs.md_memory}{glyphs.icon_spacer}{used} / {total}',
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
