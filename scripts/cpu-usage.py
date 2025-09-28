#!/usr/bin/env python3

from pathlib import Path
from waybar import glyphs, state, util
from typing import Any, Dict, List, Optional, NamedTuple
import json
import platform
import re
import sys

util.validate_requirements(required=['click'])
import click

CACHE_DIR = util.get_cache_directory()
CONTEXT_SETTINGS = dict(help_option_names=['-h', '--help'])

CPU_INFO : dict | None=None

class CpuInfo(NamedTuple):
    success        : Optional[bool]  = False
    error          : Optional[str]   = None
    cores_logical  : Optional[int]   = 0
    cores_physical : Optional[int]   = 0
    cpu_load       : Optional[dict]  = None
    freq_cur       : Optional[int]   = 0
    freq_max       : Optional[int]   = 0
    freq_min       : Optional[str]   = 0
    model          : Optional[str]   = None

def get_icon():
    if platform.machine() == 'x86':
        return glyphs.md_cpu_32_bit
    elif platform.machine() == 'x86_64':
        return glyphs.md_cpu_64_bit
    else:
        return glyphs.oct_cpu

def get_cpu_freq():
    rc, stdout, _ = util.run_piped_command('cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_cur_freq')
    freq_cur = stdout if (rc == 0 and stdout and stdout != '') else -1

    rc, stdout, _ = util.run_piped_command('cat /sys/devices/system/cpu/cpu0/cpufreq/cpuinfo_min_freq')
    freq_min = stdout if (rc == 0 and stdout and stdout != '') else -1

    rc, stdout, _ = util.run_piped_command('cat /sys/devices/system/cpu/cpu0/cpufreq/cpuinfo_max_freq')
    freq_max = stdout if (rc == 0 and stdout and stdout != '') else -1

    return int(freq_cur) * 1000, int(freq_min) * 1000, int(freq_max) * 1000

def parse_proc_cpuinfo(path='/proc/cpuinfo'):
    """
    Read /proc/cpuinfo and return a list of CPU blocks as dicts
    """
    global CPU_INFO

    text = Path(path).read_text()
    blocks = re.split(r'\n\s*\n', text.strip())

    def parse_block(block: str):
        data = {}
        for line in block.splitlines():
            if ":" in line:
                key, value = line.split(":", 1)
                data[util.to_snake_case(key.strip())] = util.convert_value(value)
        return data

    CPU_INFO = [parse_block(block) for block in blocks]

def get_cpu_info() -> CpuInfo:
    """
    Gather information about the CPU and return it to main()
    """
    global CPU_INFO

    # make sure mpstat is installed
    rc, stdout, stderr = util.run_piped_command(f'mpstat -A -o JSON')
    if rc == 0:
        if stdout != '':
            json_data, err = util.parse_json_string(stdout)
            if not err:
                try:
                    freq_cur, freq_min, freq_max = get_cpu_freq()
                    cpu_load = []
                    for cpu in json_data['sysstat']['hosts'][0]['statistics'][0]['cpu-load']:
                        cpu_load.append(util.dict_to_namedtuple(name='CPU', obj=cpu))

                    cpu_info = CpuInfo(
                        success        = True,
                        cores_logical  = len(CPU_INFO) or -1,
                        cores_physical = CPU_INFO[0].get('cpu_cores') or -1,
                        cpu_load       = cpu_load,
                        freq_cur       = freq_cur,
                        freq_max       = freq_max,
                        freq_min       = freq_min,
                        model          = CPU_INFO[0].get('model_name') or 'Unknown',
                    )
                except Exception as e:
                    cpu_info = CpuInfo(
                        success = False,
                        error   = f'failed to parse mpstat data: {str(e)}',
                    )
            else:
                cpu_info = CpuInfo(
                    success = False,
                    error   = f'failed to parse mpstat data: {str(e)}',
                )
        else:
            cpu_info = CpuInfo(
                success   = False,
                error     = f'no output from mpstat',
            )
    else:
        cpu_info = CpuInfo(
            success   = False,
            error     = stderr or f'failed to execute "{command}"',
        )

    return cpu_info

def generate_tooltip(cpu_info):
    global CPU_INFO

    pc = cpu_info.cores_physical
    lc = cpu_info.cores_logical
    tpc = int(lc / pc)

    tooltip = [
        cpu_info.model,
        f'Physical cores: {pc}, Threads/core: {tpc}, Logical cores: {lc}',
        f'Frequency: {util.processor_speed(cpu_info.freq_min)} > {util.processor_speed(cpu_info.freq_max)}'
    ]

    for core in cpu_info.cpu_load:
        if core.cpu != 'all':
            tooltip.append(
                f'core {int(core.cpu):02} user {util.pad_float(core.usr)}%, sys {util.pad_float(core.sys)}%, idle {util.pad_float(core.idle)}%'

            )

    return '\n'.join(tooltip)

@click.command(help='Get CPU usage from using mpstat(1) and /proc/cpuinfo', context_settings=CONTEXT_SETTINGS)
def main():
    global CPU_INFO

    parse_proc_cpuinfo()
    cpu_info = get_cpu_info()
    if cpu_info.success:
        for core in cpu_info.cpu_load:
            if core.cpu == 'all':
                output = {
                    'text'    : f'{get_icon()}{glyphs.icon_spacer}user {core.usr}%, sys {core.sys}%, idle {core.idle}%',
                    'tooltip' : generate_tooltip(cpu_info),
                    'class'   : 'success',
                }
    else:
        output = {
            'text'    : f'{get_icon()} {cpu_info.error if cpu_info.error is not None else "Unknown error"}',
            'tooltip' : 'CPU error',
            'class'   : 'error',
        }

    print(json.dumps(output))

if __name__ == '__main__':
    main()
