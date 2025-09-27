#!/usr/bin/env python3

from pathlib import Path
from typing import Any, Dict, List, Optional, NamedTuple
from waybar import glyphs, state, util
import json
import re

util.validate_requirements(required=['click'])
import click

CACHE_DIR = util.get_cache_directory()
CONTEXT_SETTINGS = dict(help_option_names=['-h', '--help'])

class DIMMInfo(NamedTuple):
    configured_voltage : Optional[str] = None
    data_width         : Optional[int] = 0
    form_factor        : Optional[str] = None
    locator            : Optional[str] = None
    maximum_voltage    : Optional[str] = None
    minimum_voltage    : Optional[str] = None
    part_number        : Optional[str] = None
    serial_number      : Optional[str] = None
    size               : Optional[int] = 0
    speed              : Optional[str] = None
    technology         : Optional[str] = None
    total_width        : Optional[int] = 0
    type               : Optional[str] = None
    volatile_size      : Optional[int] = 0

class MemoryType(NamedTuple):
    success : Optional[bool] = False
    error   : Optional[str] = None
    info    : Optional[List[DIMMInfo]] = None

class MemoryInfo(NamedTuple):
    success     : Optional[bool] = False
    error       : Optional[str]  = None
    total       : Optional[int]  = 0
    used        : Optional[int]  = 0
    free        : Optional[int]  = 0
    shared      : Optional[int]  = 0
    buffers     : Optional[int]  = 0
    cache       : Optional[int]  = 0
    available   : Optional[int]  = 0
    pct_total   : Optional[int]  = 0
    pct_used    : Optional[int]  = 0
    pct_free    : Optional[int]  = 0
    memory_type : Optional[List[MemoryType]] = None

def get_memory_type():
    command = 'sudo dmidecode -t memory'
    rc, stdout, stderr = util.run_piped_command(command)
    if rc == 0 and stdout != '':
        stanzas = re.split(r'^Handle.*', stdout, flags=re.MULTILINE)
        stanzas = [stanza.lstrip().rstrip() for stanza in stanzas if stanza.lstrip().rstrip().startswith('Memory Device')]
        if len(stanzas) > 0:
            dimms = []
            for stanza in stanzas:
                memory_block = {}
                for line in stanza.splitlines():
                    line = line.lstrip().rstrip()
                    if line.startswith('Handle'):
                        continue
                    bits = re.split(r'\s*:\s*', line)
                    if len(bits) == 2:
                        memory_block[util.to_snake_case(bits[0])] = bits[1]
                if len(memory_block.keys()) > 0:
                    data_width = -1
                    size = -1
                    total_width = -1
                    volatile_size = -1

                    if 'data_width' in memory_block and memory_block['data_width'] != '':
                        bits = re.split(r'\s+', memory_block['data_width'])
                        if len(bits) == 2:
                            try:
                                data_width = int(bits[0])
                            except:
                                data_width = -1

                    if 'total_width' in memory_block and memory_block['total_width'] != '':
                        bits = re.split(r'\s+', memory_block['total_width'])
                        if len(bits) == 2:
                            try:
                                total_width = int(bits[0])
                            except:
                                total_width = -1

                    if 'size' in memory_block and memory_block['size'] != '':
                        bits = re.split(r'\s+', memory_block['size'])
                        if len(bits) == 2:
                            try:
                                raw = int(bits[0])
                                if bits[1] == 'MB':
                                    size = int(raw * (1000**2))
                                if bits[1] == 'GB':
                                    size = int(raw * (1000**3))
                            except:
                                size = -1

                    if 'volatile_size' in memory_block and memory_block['volatile_size'] != '':
                        bits = re.split(r'\s+', memory_block['volatile_size'])
                        if len(bits) == 2:
                            try:
                                raw = int(bits[0])
                                if bits[1] == 'MB':
                                    volatile_size = int(raw * (1000**2))
                                if bits[1] == 'GB':
                                    volatile_size = int(raw * (1000**3))
                            except:
                                volatile_size = -1

                    dimms.append(DIMMInfo(
                        configured_voltage = memory_block['configured_voltage'] if 'configured_voltage' in memory_block else 'Unknown',
                        data_width         = data_width,
                        form_factor        = memory_block['form_factor'] if 'form_factor' in memory_block else 'Unknown',
                        locator            = memory_block['locator'] if 'locator' in memory_block else 'Unknown',
                        maximum_voltage    = memory_block['maximum_voltage'] if 'maximum_voltage' in memory_block else 'Unknown',
                        minimum_voltage    = memory_block['minimum_voltage'] if 'minimum_voltage' in memory_block else 'Unknown',
                        part_number        = memory_block['part_number'] if 'part_number' in memory_block else 'Unknown',
                        serial_number      = memory_block['serial_number'] if 'serial_number' in memory_block else 'Unknown',
                        size               = size,
                        speed              = memory_block['speed'] if 'speed' in memory_block else 'Unknown',
                        technology         = memory_block['memory_technology'] if 'memory_technology' in memory_block else 'Unknown',
                        total_width        = total_width,
                        type               = memory_block['type'] if 'type' in memory_block else 'Unknown',
                        volatile_size      = volatile_size,
                    ))
                memory_type = MemoryType(
                    success = True,
                    info    = dimms,
                )
        else:
            memory_type = MemoryType(
                success = False,
                error   = 'no information found about installed memory',
            )
    else:
        memory_type = MemoryType(
            success = False,
            error   = stderr or f'failed to execute {command}',
        )

    return memory_type

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
                success     = True,
                total       = total,
                shared      = shared,
                buffers     = buffers,
                cache       = cache,
                available   = available,
                pct_total   = 100,
                pct_used    = pct_used,
                pct_free    = pct_free,
                used        = used,
                free        = free,
                memory_type = get_memory_type()
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

def generate_tooltip(memory_info):
    unit = 'G'

    tooltip = [
        f'Total     = {util.byte_converter(number=memory_info.total, unit=unit)}',
        f'Used      = {util.byte_converter(number=memory_info.used, unit=unit)}',
        f'Free      = {util.byte_converter(number=memory_info.free, unit=unit)}',
        f'Shared    = {util.byte_converter(number=memory_info.shared, unit=unit)}',
        f'Buffers   = {util.byte_converter(number=memory_info.buffers, unit=unit)}',
        f'Cache     = {util.byte_converter(number=memory_info.cache, unit=unit)}',
        f'Available = {util.byte_converter(number=memory_info.available, unit=unit)}',
        '',
    ]

    for idx, dimm in enumerate(memory_info.memory_type.info):
        tooltip.append(f'DIMM {idx:02d} - {util.byte_converter(number=dimm.size, unit='G')} {dimm.type} {dimm.form_factor} @ {dimm.speed}')

    return '\n'.join(tooltip)

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
    tooltip = generate_tooltip(memory_info)

    if memory_info.success:
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
