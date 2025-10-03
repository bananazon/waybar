#!/usr/bin/env python3

from pathlib import Path
from waybar import glyphs, state, util
from typing import Any, Dict, List, Optional, NamedTuple
import json
import platform
import re

util.validate_requirements(modules=['click'])
import click

util.validate_requirements(binaries=['dmidecode', 'jc', 'mpstat'])

cache_dir = util.get_cache_directory()
context_settings = dict(help_option_names=['-h', '--help'])

CPU_INFO : list | None=None

class CpuInfo(NamedTuple):
    success        : Optional[bool]  = False
    error          : Optional[str]   = None
    caches         : Optional[list]  = None
    cores_logical  : Optional[int]   = 0
    cores_physical : Optional[int]   = 0
    cpu_load       : Optional[dict]  = None
    freq_cur       : Optional[int]   = 0
    freq_max       : Optional[int]   = 0
    freq_min       : Optional[str]   = 0
    model          : Optional[str]   = None

def generate_tooltip(cpu_info):
    global CPU_INFO
    tooltip = []

    if cpu_info.model:
        tooltip.append(cpu_info.model)

    if cpu_info.cores_physical and cpu_info.cores_logical:
        pc = cpu_info.cores_physical
        lc = cpu_info.cores_logical
        tpc = int(lc / pc)
        tooltip.append(f'Physical cores: {pc}, Threads/core: {tpc}, Logical cores: {lc}')

    if cpu_info.freq_min and cpu_info.freq_max:
        tooltip.append(f'Frequency: {util.processor_speed(cpu_info.freq_min)} > {util.processor_speed(cpu_info.freq_max)}')

    if cpu_info.cpu_load and type(cpu_info.cpu_load) == list:
        tooltip.append('CPU Load:')
        for core in cpu_info.cpu_load:
            if core.cpu != 'all':
                core_number = int(core.cpu)
                core_freq = CPU_INFO[core_number].cpu_frequency
                tooltip.append(
                    f'  core {int(core.cpu):02} user {util.pad_float(core.usr, False)}%, sys {util.pad_float(core.sys, False)}%, idle {util.pad_float(core.idle, False)}% ({util.processor_speed(core_freq)})'
                )
    
    if cpu_info.caches and type(cpu_info.caches) == list and len(cpu_info.caches) > 0:
        tooltip.append('Caches:')
        max_key_length = 0
        for cache in cpu_info.caches:
            max_key_length = len(cache.installed_size) if len(cache.installed_size) > max_key_length else max_key_length
        
        for cache in cpu_info.caches:
            if cache.socket_designation and cache.installed_size and cache.speed:
                tooltip.append(f'  {cache.socket_designation} - {cache.installed_size:{max_key_length}} @ {cache.speed}')

    return '\n'.join(tooltip)

def get_icon():
    if platform.machine() == 'x86':
        return glyphs.md_cpu_32_bit
    elif platform.machine() == 'x86_64':
        return glyphs.md_cpu_64_bit
    else:
        return glyphs.oct_cpu


def get_cache_info():
    command = 'sudo dmidecode -t cache | jc --dmidecode'
    rc, stdout, stderr = util.run_piped_command(command)
    if rc == 0 and stdout != '':
        json_data, err = util.parse_json_string(stdout)
        if not err:
            caches = []
            for cache in json_data:
                caches.append(util.dict_to_namedtuple(name='CpuCache', obj=cache['values']))

            return caches if len(caches) > 0 else None

    return None

def get_cpu_freq():
    rc, stdout, _ = util.run_piped_command('cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_cur_freq')
    freq_cur = stdout if (rc == 0 and stdout and stdout != '') else -1

    rc, stdout, _ = util.run_piped_command('cat /sys/devices/system/cpu/cpu0/cpufreq/cpuinfo_min_freq')
    freq_min = stdout if (rc == 0 and stdout and stdout != '') else -1

    rc, stdout, _ = util.run_piped_command('cat /sys/devices/system/cpu/cpu0/cpufreq/cpuinfo_max_freq')
    freq_max = stdout if (rc == 0 and stdout and stdout != '') else -1

    return int(freq_cur) * 1000, int(freq_min) * 1000, int(freq_max) * 1000

def parse_proc_cpuinfo():
    """
    Read /proc/cpuinfo and return a list of CPU blocks as dicts
    """
    global CPU_INFO
    command = f'jc --pretty /proc/cpuinfo'
    rc, stdout, stderr = util.run_piped_command(command)
    if rc == 0 and stdout != '':
        json_data, err = util.parse_json_string(stdout)
        cores = []
        for core in json_data:
            core['cpu_frequency'] = core.get('cpu MHz') * 1000000
            core.pop('cpu MHz')
            core_tuple = util.dict_to_namedtuple(name='Core', obj=core)
            cores.append(core_tuple)

    CPU_INFO = cores

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
                        caches         = get_cache_info(),
                        cores_logical  = len(CPU_INFO) or -1,
                        cores_physical = CPU_INFO[0].cpu_cores or -1,
                        cpu_load       = cpu_load,
                        freq_cur       = freq_cur,
                        freq_max       = freq_max,
                        freq_min       = freq_min,
                        model          = CPU_INFO[0].model_name or 'Unknown',
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

@click.command(help='Get CPU usage from using mpstat(1) and /proc/cpuinfo', context_settings=context_settings)
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
