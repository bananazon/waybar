#!/usr/bin/env python3

from pathlib import Path
from typing import Any, Dict, List, Optional, NamedTuple
from waybar import glyphs, state, util
import json
import os
import re
import sys
import time

util.validate_requirements(required=['click'])
import click

CACHE_DIR = util.get_cache_directory()
CONTEXT_SETTINGS = dict(help_option_names=['-h', '--help'])

class WifiStatus(NamedTuple):
    success   : Optional[bool] = False
    error     : Optional[str]  = None
    bandwidth : Optional[int]  = 0
    channel   : Optional[str]  = None
    frequency : Optional[int]  = 0
    interface : Optional[str]  = None
    signal    : Optional[int]  = 0
    ssid      : Optional[str]  = None

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

def get_ssid():
    command = f'iwgetid -r'
    rc, stdout, stderr = util.run_piped_command(command)
    if rc == 0 and stdout != '':
        return stdout
    
    return None

def get_wifi_status(interface: str=None):
    command = f'iw dev {interface} link'
    rc, stdout, stderr = util.run_piped_command(command)
    
    if rc == 0:
        if stdout != '':
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
            error     = stderr or f'failed to execute "{command}"',
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
            error     = stderr or f'failed to execute "{command}"',
        )

    wifi_status = WifiStatus(
        success   = True,
        bandwidth = channel_bandwidth,
        channel   = channel,
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
    if not util.interface_exists(interface=interface):
        print(json.dumps({
            'text'  : f'{glyphs.md_alert} {interface} does not exist',
            'class' : 'error',
        }))
    else:
        if util.interface_is_connected(interface=interface):
            mode_count = 2
            statefile = CACHE_DIR / f'waybar-{util.called_by() or "wifi-status"}-{interface}-state'

            if toggle:
                mode = state.next_state(statefile=statefile, mode_count=mode_count)
            else:
                mode = state.current_state(statefile=statefile)

            wifi_status = get_wifi_status(interface=interface)

            if wifi_status.success:
                wifi_icon = get_status_icon(wifi_status.signal)
                if mode == 0:
                    output = {
                        'text'  : f'{wifi_icon} {wifi_status.interface} {wifi_status.signal} dBm',
                        'class' : 'success',
                    }
                elif mode == 1:
                    output = {
                        'text'  : f'{wifi_icon} {wifi_status.interface} channel {wifi_status.channel} ({wifi_status.frequency} MHz) {wifi_status.bandwidth} MHz width',
                        'class' : 'success',
                    }
            else:
                wifi_icon = glyphs.md_wifi_strength_alert_outline
                output = {
                    'text'  : f'{wifi_icon} {wifi_status.interface} {wifi_status.error if wifi_status.error is not None else "Unknown error"}',
                    'class' : 'error',
                }
        else:
            wifi_icon = glyphs.md_wifi_strength_alert_outline
            output = {
                'text'  : f'{wifi_icon} {interface} disconnected',
                'class' : 'error'
            }

        print(json.dumps(output))

if __name__ == '__main__':
    cli()
