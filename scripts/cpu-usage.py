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
STATEFILE = Path(CACHE_DIR) / f'waybar-{util.called_by() or "cpu-usage"}-state'

CPU_INFO : dict | None=None

class CpuInfo(NamedTuple):
    success        : Optional[bool]  = False
    error          : Optional[str]   = None
    cores_logical  : Optional[int]   = 0
    cores_physical : Optional[int]   = 0
    freq_cur       : Optional[int]   = 0
    freq_max       : Optional[int]   = 0
    freq_min       : Optional[str]   = 0
    guest          : Optional[float] = 0.0
    guestnice      : Optional[float] = 0.0
    idle           : Optional[float] = 0.0
    iowait         : Optional[float] = 0.0
    irq            : Optional[float] = 0.0
    load1          : Optional[float] = 0.0
    load15         : Optional[float] = 0.0
    load5          : Optional[float] = 0.0
    model          : Optional[str]   = None
    nice           : Optional[float] = 0.0
    softirq        : Optional[float] = 0.0
    steal          : Optional[float] = 0.0
    system         : Optional[float] = 0.0
    user           : Optional[float] = 0.0

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

def get_load_averages():
    """
    Execute uptime and return the load averages
    """
    rc, stdout, stderr = util.run_piped_command('uptime')
    if rc == 0:
        if stdout != '':
            match = re.search(r"load average:\s*([\d.]+),\s*([\d.]+),\s*([\d.]+)", stdout)
            if match:
                return [float(avg) for avg in list(match.groups())]

    return [-1.0, -1.0, -1.0]

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

    if platform.machine() == 'x86':
        icon = glyphs.md_cpu_32_bit
    elif platform.machine() == 'x86_64':
        icon = glyphs.md_cpu_64_bit
    else:
        icon = glyphs.oct_cpu

    # make sure mpstat is installed
    load_averages = get_load_averages()
    rc, stdout, stderr = util.run_piped_command(f'mpstat | tail -n 1')
    if rc == 0:
        if stdout != '':
            freq_cur, freq_min, freq_max = get_cpu_freq()
            values = re.split(r'\s+', stdout)
            cpu_info = CpuInfo(
                success            = True,
                model              = CPU_INFO[0].get('model_name') or 'Unknown',
                cores_logical      = len(CPU_INFO) or -1,
                cores_physical     = CPU_INFO[0].get('cpu_cores') or -1,
                freq_cur           = freq_cur,
                freq_max           = freq_max,
                freq_min           = freq_min,
                idle               = util.pad_float(values[12]),
                nice               = util.pad_float(values[4]),
                system             = util.pad_float(values[5]),
                user               = util.pad_float(values[3]),
                iowait             = util.pad_float(values[6]),
                irq                = util.pad_float(values[7]),
                softirq            = util.pad_float(values[7]),
                steal              = util.pad_float(values[9]),
                guest              = util.pad_float(values[10]),
                guestnice          = util.pad_float(values[11]),
                load1              = util.pad_float(load_averages[0]),
                load5              = util.pad_float(load_averages[1]),
                load15             = util.pad_float(load_averages[2]),
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
    for idx, core in enumerate(CPU_INFO):
        speed = util.processor_speed(round(core.get('cpu_mhz')) * 1000000)
        tooltip.append(
            f'Logical core {idx:02d} - {speed}'
        )

    return '\n'.join(tooltip)

@click.command(help='Get CPU usage from using mpstat(1) and /proc/cpuinfo', context_settings=CONTEXT_SETTINGS)
@click.option('-t', '--toggle', default=False, is_flag=True, help='Toggle the output format')
def main(toggle):
    mode_count = 2
    global CPU_INFO

    parse_proc_cpuinfo()

    if toggle:
        mode = state.next_state(statefile=STATEFILE, mode_count=mode_count)
    else:
        mode = state.current_state(statefile=STATEFILE)

    cpu_info = get_cpu_info()
    tooltip = generate_tooltip(cpu_info)

    if float(cpu_info.idle) < 40:
        output_class = 'critical'
    elif float(cpu_info.idle) >= 40 and float(cpu_info.idle) < 60:
        output_class = 'warning'
    elif float(cpu_info.idle) >= 60:
        output_class = 'good'

    if cpu_info.success:
        if mode == 0:
            output = {
                'text'    : f'{get_icon()}{glyphs.icon_spacer}user {cpu_info.user}%, sys {cpu_info.system}%, idle {cpu_info.idle}%',
                'tooltip' : tooltip,
                'class'   : output_class,
            }
        elif mode == 1:
            output = {
                'text'    : f'{get_icon()}{glyphs.icon_spacer}load {cpu_info.load1},  {cpu_info.load5},  {cpu_info.load15}',
                'tooltip' : tooltip,
                'class'   : output_class,
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
