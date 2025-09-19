#!/usr/bin/env python3

from pathlib import Path
from waybar import glyphs, state, util
from typing import Any, Dict, List, Optional, NamedTuple
import argparse
import json
import os
import platform
import re
import sys
import time

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

def get_statefile() -> str:
    statefile = os.path.basename(__file__)
    statefile_no_ext = os.path.splitext(statefile)[0]
    return Path.home() / f'.waybar-{statefile_no_ext}-state'

def get_icon():
    if platform.machine() == 'x86':
        return glyphs.md_cpu_32_bit
    elif platform.machine() == 'x86_64':
        return glyphs.md_cpu_64_bit
    else:
        return glyphs.oct_cpu

def get_cpu_type():
    command = 'grep -m 1 "model name" /proc/cpuinfo'
    rc, stdout, _ = util.run_piped_command(command)
    if rc == 0:
        return re.split(r'\s*:\s*', stdout)[1]
    else:
        return 'Unknown CPU model'

def get_cpu_freq():
    rc, stdout, _ = util.run_piped_command('cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_cur_freq')
    freq_cur = stdout if (rc == 0 and stdout and stdout != '') else -1

    rc, stdout, _ = util.run_piped_command('cat /sys/devices/system/cpu/cpu0/cpufreq/cpuinfo_min_freq')
    freq_min = stdout if (rc == 0 and stdout and stdout != '') else -1

    rc, stdout, _ = util.run_piped_command('cat /sys/devices/system/cpu/cpu0/cpufreq/cpuinfo_max_freq')
    freq_max = stdout if (rc == 0 and stdout and stdout != '') else -1

    return int(freq_cur) * 1000, int(freq_min) * 1000, int(freq_max) * 1000

def get_logical_cpu_cores():
    command = 'grep -c ^processor /proc/cpuinfo'
    rc, stdout, _ = util.run_piped_command(command)
    if rc == 0 and stdout != '':
        return int(stdout)

    return -1

def get_physical_cpu_cores():
    command = 'grep -m 1 "cpu cores" /proc/cpuinfo'
    rc, stdout, _ = util.run_piped_command(command)
    if rc == 0 and stdout != '':
        physical_cores = re.split(r'\s+:\s+', stdout)[1]
        return int(physical_cores)

    return -1

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

def get_cpu_info() -> CpuInfo:
    """
    Gather information about the CPU and return it to main()
    """

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
                model              = get_cpu_type(),
                cores_logical      = get_logical_cpu_cores(),
                cores_physical     = get_physical_cpu_cores(),
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
            error     = stderr if stderr != '' else f'failed to execute "{command}"',
        )

    return cpu_info

def main():
    mode_count = 4
    parser = argparse.ArgumentParser(description='Get CPU usage from mpstat(1)')
    parser.add_argument('-t', '--toggle', action='store_true', help='Toggle the output format', required=False)
    parser.add_argument('-i', '--interval', help='The update interval (in seconds)', required=False, default=2, type=int)
    parser.add_argument('-b', '--background', action='store_true', help='Run this script in the background', required=False)
    args = parser.parse_args()

    if args.toggle:
        mode = state.next_state(statefile=get_statefile(), mode_count=mode_count)
    else:
        mode = state.read_state(statefile=get_statefile())

    cpu_info = get_cpu_info()

    if float(cpu_info.idle) < 40:
        output_class = 'critical'
    elif float(cpu_info.idle) >= 40 and float(cpu_info.idle) < 60:
        output_class = 'warning'
    elif float(cpu_info.idle) >= 60:
        output_class = 'good'

    if cpu_info.success:
        if mode == 0:
            output = {
                'text'    : f'{get_icon()} user {cpu_info.user}%, sys {cpu_info.system}%, idle {cpu_info.idle}%',
                'tooltip' : 'CPU user%, system%, and idle%',
                'class'   : output_class,
            }
        elif mode == 1:
            output = {
                'text'    : f'{get_icon()} load {cpu_info.load1},  {cpu_info.load5},  {cpu_info.load15}',
                'tooltip' : 'Load averages',
                'class'   : output_class,
            }
        elif mode == 2:
            output = {
                'text'    : f'{get_icon()} {cpu_info.cores_physical}C/{cpu_info.cores_logical}T x {cpu_info.model}',
                'tooltip' : 'core count/thread count x CPU model',
                'class'   : output_class,
            }
        elif mode == 3:
            output = {
                'text'    : f'{get_icon()} current: {util.processor_speed(cpu_info.freq_cur)}, min: {util.processor_speed(cpu_info.freq_min)}, max: {util.processor_speed(cpu_info.freq_max)}',
                'tooltip' : 'CPU frequency (current, min, max)',
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
