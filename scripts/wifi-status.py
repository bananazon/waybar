#!/usr/bin/env python3

from collections import OrderedDict
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
    success        : Optional[bool] = False
    error          : Optional[str]  = None
    authenticated  : Optional[bool] = False
    authorized     : Optional[bool] = False
    bandwidth      : Optional[int]  = 0
    channel        : Optional[str]  = None
    ciphers        : Optional[list] = None
    connected_time : Optional[int]  = 0
    frequency      : Optional[int]  = 0
    interface      : Optional[str]  = None
    signal         : Optional[int]  = 0
    ssid_mac       : Optional[str]  = None
    ssid_name      : Optional[str]  = None

def generate_tooltip(wifi_status):
    tooltip = []
    tooltip_od = OrderedDict()

    if wifi_status.ssid_name and wifi_status.ssid_mac:
        tooltip_od['Connected To'] = f'{wifi_status.ssid_name} ({wifi_status.ssid_mac})'

    if wifi_status.connected_time:
        tooltip_od['Connection Time'] = util.get_duration(seconds=wifi_status.connected_time)

    if wifi_status.channel:
        channel_info = []
        channel_info.append(f'{wifi_status.channel}')

        if wifi_status.frequency:
            channel_info.append(f'({wifi_status.frequency} MHz)')

        if wifi_status.bandwidth:
            channel_info.append(f'{wifi_status.bandwidth} MHz width')

        tooltip_od['Channel'] = ' '.join(channel_info)

    if wifi_status.authenticated:
        tooltip_od['Authenticated'] = 'Yes' if wifi_status.authorized else 'No'

    if wifi_status.authorized:
        tooltip_od['Authorized'] = 'Yes' if wifi_status.authorized else 'No'

    if wifi_status.ciphers:
        tooltip_od['Available Ciphers'] = wifi_status.ciphers

    max_key_length = 0
    for key in tooltip_od.keys():
        max_key_length = len(key) if len(key) > max_key_length else max_key_length

    for key, value in tooltip_od.items():
        if key == 'Available Ciphers':
            tooltip.append(f'{key:{max_key_length}} :')
            for cipher in wifi_status.ciphers:
                tooltip.append(f'   {cipher[0]}')
        else:
            tooltip.append(f'{key:{max_key_length}} : {value}')

    return '\n'.join(tooltip)

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

def get_wifi_status(interface: str=None):
    wiphy = -1
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
                ssid_name = match.group(1)
            
            match = re.search(r'wiphy\s+([\d]+)', stdout, re.MULTILINE)
            if match:
                wiphy = int(match.group(1))
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

    command = f'iw dev {interface} station dump'
    rc, stdout, stderr = util.run_piped_command(command)
    if rc == 0:
        if stdout != '':
            match = re.search(r'Station\s+([a-z0-9:]+)\s+', stdout, re.MULTILINE)
            if match:
                ssid_mac = match.group(1)

            match = re.search(r'\s+connected time:\s+([\d]+)\s+seconds', stdout, re.MULTILINE)
            if match:
                connected_time = match.group(1)

            match = re.search(r'\s+authenticated:\s+(yes|no)', stdout, re.MULTILINE)
            if match:
                authenticated = True if match.group(1) == 'yes' else False

            match = re.search(r'\s+authorized:\s+(yes|no)', stdout, re.MULTILINE)
            if match:
                authorized = True if match.group(1) == 'yes' else False
    
    if wiphy >= 0:
        ciphers = None
        command = f'iw phy phy{wiphy} info'
        rc, stdout, stderr = util.run_piped_command(command)
        if rc == 0:
            block_match = re.search(r'Supported Ciphers:\s*((?:\s+\*.*\n)+)', stdout)
            if block_match:
                block = block_match.group(1)
                ciphers = re.findall(r"\*\s+([A-Z0-9-]+)\s+\(([^)]+)\)", block)

    wifi_status = WifiStatus(
        success        = True,
        authenticated  = authenticated,
        authorized     = authorized,
        bandwidth      = channel_bandwidth,
        channel        = channel,
        ciphers        = sorted(ciphers),
        connected_time = int(connected_time),
        frequency      = frequency,
        interface      = interface,
        signal         = signal,
        ssid_mac       = ssid_mac,
        ssid_name      = ssid_name,
    )

    return wifi_status

@click.command(help='Get WiFi status using iw(8)')
@click.option('-i', '--interface', required=True, help='The interface to check')
def main(interface):
    if not util.interface_exists(interface=interface):
        print(json.dumps({
            'text'  : f'{glyphs.md_alert} {interface} does not exist',
            'class' : 'error',
        }))
    else:
        if util.interface_is_connected(interface=interface):
            wifi_status = get_wifi_status(interface=interface)
            if wifi_status.success:
                wifi_icon = get_status_icon(wifi_status.signal)
                output = {
                    'text'    : f'{wifi_icon}{glyphs.icon_spacer}{wifi_status.interface} {wifi_status.signal} dBm',
                    'class'   : 'success',
                    'tooltip' : generate_tooltip(wifi_status)
                }
            else:
                wifi_icon = glyphs.md_wifi_strength_alert_outline
                output = {
                    'text'  : f'{wifi_icon}{glyphs.icon_spacer}{wifi_status.interface} {wifi_status.error if wifi_status.error is not None else "Unknown error"}',
                    'class' : 'error',
                }
        else:
            wifi_icon = glyphs.md_wifi_strength_alert_outline
            output = {
                'text'  : f'{wifi_icon}{glyphs.icon_spacer}{interface} disconnected',
                'class' : 'error'
            }

        print(json.dumps(output))

if __name__ == '__main__':
    main()
