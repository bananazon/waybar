#!/usr/bin/env python3

from pathlib import Path
from typing import Any, Dict, List, Optional, NamedTuple
from waybar import glyphs, state, util
import json
import os
import re
import sys
import time

# Ensure required modules are present
util.validate_requirements(required=['click'])
import click

class WifiStatus(NamedTuple):
    success   : Optional[bool] = False
    error     : Optional[str]  = None
    bandwidth : Optional[int]  = 0
    channel   : Optional[str]  = None
    connected : Optional[bool] = False
    frequency : Optional[int]  = 0
    interface : Optional[str]  = None
    signal    : Optional[int]  = 0
    ssid      : Optional[str]  = None

# Paths and constants
CONTEXT_SETTINGS = dict(help_option_names=['-h', '--help'])

# Globals
INTERFACE_LABEL : str | None = None

def get_statefile() -> str:
    """
    Return the statefile as a Path object
    """
    global INTERFACE_LABEL

    statefile = os.path.basename(__file__)
    statefile_no_ext = os.path.splitext(statefile)[0]

    return Path.home() / f'.waybar-{statefile_no_ext}-{INTERFACE_LABEL}-state'

def get_status_icon(signal):
    """
    Return a wifi icon based on signal strength
    """

    # -30 dBm to -50 dBm is considered excellent or very good 
    # -50 dBm to -67 dBm is considered good and suitable for most applications, including streaming and video conferencing 
    # -67 dBm to -70 dBm is the minimum recommended for reliable performance, with -70 dBm being the threshold for acceptable packet delivery 
    # signals below -70 dBm, such as -80 dBm, are considered poor and may result in unreliable connectivity and slower speeds 
    # signals below -90 dBm are typically unusable.

    if -50 <= signal <= -30:
        return glyphs.md_wifi_strength_4
    elif -67 <= signal < -50:
        return glyphs.md_wifi_strength_3
    elif -70 <= signal < -67:
        return glyphs.md_wifi_strength_2
    elif -80 < signal < -70:
        return glyphs.md_wifi_strength_1
    elif -90 < signal < -80:
        return glyphs.md_wifi_strength_outline
    else:  # signal_dbm <= -90
        return glyphs.md_wifi_strength_alert_outline

def get_signal(interface: str=None) -> int:
    command = f'iwconfig {interface}'
    rc, stdout, stderr = util.run_piped_command(command)
    if rc == 0:
        if stdout != '':
            match = re.search(r"Signal level=(-?\d+)\s*dBm", stdout)
            if match:
                return match.group(1)

    return None

def get_ssid():
    command = f'iwgetid -r'
    rc, stdout, stderr = util.run_piped_command(command)
    if rc == 0 and stdout != '':
        return stdout
    
    return None

def get_wifi_status(interface: str=None):
    output_dict = {}
    command = f'iw dev {interface} link'
    rc, stdout, stderr = util.run_piped_command(command)
    
    if rc == 0:
        if stdout != '':
            connected = False if stdout.startswith('Not connected') else True

            match = re.search(r'signal:\s+(-\d+)', stdout, re.MULTILINE)
            if match:
                signal = int(match.group(1))
        else:
            wifi_status = WifiStatus(
                success   = False,
                interface = interface,
                error     = f'no output from "{command}"',
            )
    else:
        wifi_status = WifiStatus(
            success   = False,
            interface = interface,
            error     = stderr if stderr != '' else f'failed to execute "{command}"',
        )

    command = f'iw dev {interface} info'
    rc, stdout, stderr = util.run_piped_command(command)
    if rc == 0:
        if stdout != '':
            # channel 48 (5240 MHz), width: 160 MHz, center1: 5250 MHz
            match = re.search(r'channel\s+(\d+)\s+\((\d+)\s+MHz\),\s+width:\s+(\d+)\s+MHz', stdout, re.MULTILINE)
            if match:
                channel = int(match.group(1))
                frequency = int(match.group(2))
                channel_bandwidth = int(match.group(3))
            
            match = re.search(r'ssid\s+(.*)$', stdout, re.MULTILINE)
            if match:
                ssid = match.group(1)
        else:
            wifi_status = WifiStatus(
                success   = False,
                interface = interface,
                error     = f'no output from "{command}"',
            )
    else:
        wifi_status = WifiStatus(
            success   = False,
            interface = interface,
            error     = stderr if stderr != '' else f'failed to execute "{command}"',
        )
    
    wifi_status = WifiStatus(
        success   = True,
        bandwidth = channel_bandwidth,
        channel   = channel,
        connected = connected,
        frequency = frequency,
        interface = interface,
        signal    = signal,
        ssid      = ssid,
    )

    return wifi_status

@click.group(context_settings=CONTEXT_SETTINGS)
def cli():
    """
    WiFi Status script
    """
    pass

@cli.command(name='run', help='Get WiFi status using iw(8)')
@click.option('--interface', required=True, help='The interface to check')
@click.option('--toggle', is_flag=True, help='Toggle the output format')
def run(interface, toggle):
    global INTERFACE_LABEL

    output = {}
    mode_count = 2
    INTERFACE_LABEL = interface

    if toggle:
        mode = state.next_state(statefile=get_statefile(), mode_count=mode_count)
    else:
        mode = state.read_state(statefile=get_statefile())
    
    wifi_status = get_wifi_status(interface=interface)

    if wifi_status.success:
        if wifi_status.connected:
            wifi_icon = get_status_icon(wifi_status.signal)
            if mode == 0:
                output = {
                    'text'   : f'{wifi_icon} {wifi_status.interface} {wifi_status.signal} dBm',
                    # 'tooltip': interface,
                    'class'  : 'connected',
                }
            elif mode == 1:
                output = {
                    'text'   : f'{wifi_icon} {wifi_status.interface} channel {wifi_status.channel} ({wifi_status.frequency} MHz) {wifi_status.bandwidth} MHz width',
                    # 'tooltip': interface,
                    'class'  : 'connected',
                }
        else:
            wifi_icon = glyphs.md_wifi_strength_alert_outline
            output = {
                'text'   : f'{wifi_icon} {wifi_status.interface} disconnected',
                # 'tooltip': interface,
                'class'  : 'disconnected',
            }
    else:
        wifi_icon = glyphs.md_wifi_strength_alert_outline
        output = {
            'text'   : f'{wifi_icon} {wifi_status.interface} {wifi_status.error if wifi_status.error is not None else "Unknown error"}',
            # 'tooltip': interface,
            'class'  : 'error',
        }

    print(json.dumps(output))

if __name__ == '__main__':
    cli()
