#!/usr/bin/env python3

from collections import OrderedDict
from pathlib import Path
from typing import Any, Dict, List, Optional, NamedTuple
from waybar import glyphs, state, util
import json
import logging
import os
import re
import signal
import sys
import threading
import time

util.validate_requirements(modules=['click'])
import click

util.validate_requirements(binaries=['iw'])

sys.stdout.reconfigure(line_buffering=True)

cache_dir        = util.get_cache_directory()
condition        = threading.Condition()
context_settings = dict(help_option_names=['-h', '--help'])
format_index     = 0
logfile          = cache_dir / f'waybar-wifi-status.log'
needs_fetch      = False
needs_redraw     = False
wifi_status      = None

formats : list | None=None

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
    updated        : Optional[str]  = None

def configure_logging(debug: bool=False):
    logging.basicConfig(
        filename = logfile,
        filemode = 'w',  # 'a' = append, 'w' = overwrite
        format   = '%(asctime)s [%(levelname)-5s] - %(message)s',
        level    = logging.DEBUG if debug else logging.INFO
    )

def refresh_handler(signum, frame):
    global needs_fetch, needs_redraw
    logging.info(f'[refresh_handler] - received SIGHUP — re-fetching data')
    with condition:
        needs_fetch = True
        needs_redraw = True
        condition.notify()

def toggle_format(signum, frame):
    global formats, format_index, needs_redraw
    format_index = (format_index + 1) % len(formats)
    if wifi_status and type(wifi_status) == list:
        interface = wifi_status[format_index].interface
    else:
        interface = format_index + 1
    logging.info(f'[toggle_format] - received SIGUSR1 - switching output format to {interface}')
    with condition:
        needs_redraw = True
        condition.notify()

signal.signal(signal.SIGHUP, refresh_handler)
signal.signal(signal.SIGUSR1, toggle_format)

def generate_tooltip(wifi_status: NamedTuple=None):
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
                tooltip.append(f'  {cipher[0]}')
        else:
            tooltip.append(f'{key:{max_key_length}} : {value}')

    if len(tooltip) > 0:
        tooltip.append('')
        tooltip.append(f'Last updated {wifi_status.updated}')

    return '\n'.join(tooltip)

def get_status_icon(signal: int=None):
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

def get_wifi_status(interfaces: str=None):
    wifi_status = []

    for interface in interfaces:
        if util.interface_exists(interface=interface):
            if util.interface_is_connected(interface=interface):
                if os.path.isdir(f'/sys/class/net/{interface}/wireless'):
                    wiphy = -1

                    command = f'iw dev {interface} link'
                    rc, stdout, stderr = util.run_piped_command(command)
                    if rc == 0:
                        if stdout != '':
                            match = re.search(r'signal:\s+(-\d+)', stdout, re.MULTILINE)
                            if match:
                                signal = int(match.group(1))
                        else:
                            interface_status = WifiStatus(
                                success   = False,
                                interface = interface,
                                error     = f'no output from "{command}"',
                            )
                    else:
                        interface_status = WifiStatus(
                            success   = False,
                            interface = interface,
                            error     = stderr or f'failed to execute "{command}"',
                        )

                    command = f'iw dev {interface} info'
                    rc, stdout, stderr = util.run_piped_command(command)
                    if rc == 0:
                        if stdout != '':
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
                            interface_status = WifiStatus(
                                success   = False,
                                interface = interface,
                                error     = f'no output from "{command}"',
                            )
                    else:
                        interface_status = WifiStatus(
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

                    interface_status = WifiStatus(
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
                        updated        = util.get_human_timestamp(),
                    )
                else:
                    interface_status = WifiStatus(
                        success   = False,
                        error     = 'isn\'t wireless',
                        interface = interface,
                    )
            else:
                interface_status = WifiStatus(
                    success   = False,
                    error     = 'disconnected',
                    interface = interface,
                )
        else:
            interface_status = WifiStatus(
                success   = False,
                error     = 'doesn\'t exist',
                interface = interface,
            )

        wifi_status.append(interface_status)
        
    return wifi_status

def render_output(wifi_status: NamedTuple=None, icon: str=None):
    interface = wifi_status.interface
    logging.debug('[render_output] - entering function')
    if wifi_status.success:
        icon = icon if icon else get_status_icon(signal=wifi_status.signal)
        text = f'{icon}{glyphs.icon_spacer}{interface} {wifi_status.signal} dBm'
        output_class = 'success'
        tooltip = generate_tooltip(wifi_status=wifi_status)
    else:
        text = f'{glyphs.md_wifi_strength_alert_outline}{glyphs.icon_spacer}{interface} {wifi_status.error}'
        output_class = 'error'
        tooltip = f'{wifi_status.interface} error'

    logging.debug(f'[render_output] - exiting with text={text}, output_class={output_class}, tooltip={tooltip}')
    return text, output_class, tooltip

def worker(interfaces: list=None):
    global wifi_status, needs_fetch, needs_redraw, format_index

    while True:
        with condition:
            while not (needs_fetch or needs_redraw):
                condition.wait()

            fetch        = needs_fetch
            redraw       = needs_redraw
            needs_fetch  = False
            needs_redraw = False

        if fetch:
            loading      = f'{glyphs.md_timer_outline}{glyphs.icon_spacer}Gathering WiFi status...'
            loading_dict = { 'text': loading, 'class': 'loading', 'tooltip': 'Gathering WiFi status...'}
            if wifi_status and type(wifi_status) == list:
                text, _, tooltip = render_output(wifi_status=wifi_status[format_index], icon=glyphs.md_timer_outline)
                print(json.dumps({'text': text, 'class': 'loading', 'tooltip': tooltip}))
            else:
                print(json.dumps(loading_dict))

            logging.debug('[worker] - passing to get_network_throughput')
            wifi_status = get_wifi_status(interfaces=interfaces)

        if wifi_status is None:
            continue

        if wifi_status and type(wifi_status) == list:
            if redraw:
                text, output_class, tooltip = render_output(wifi_status=wifi_status[format_index])
                output = {
                    'text'    : text,
                    'class'   : output_class,
                    'tooltip' : tooltip,
                }
                print(json.dumps(output))

@click.command(help='Get WiFi status using iw(8)', context_settings=context_settings)
@click.option('-i', '--interface', required=True, multiple=True, help='The interface to check')
@click.option('--interval', type=int, default=5, help='The update interval (in seconds)')
@click.option('-t', '--test', default=False, is_flag=True, help='Print the output and exit')
@click.option('-d', '--debug', default=False, is_flag=True, help='Enable debug logging')
def main(interface, interval, test, debug):
    global formats, needs_fetch, needs_redraw

    configure_logging(debug=debug)
    formats = list(range(len(interface)))

    if test:
        wifi_status = get_wifi_status(interfaces=interface)
        util.pprint(wifi_status[0])
        print()
        print(generate_tooltip(wifi_status=wifi_status[0]))
        return

    logging.info('[main] - entering')

    threading.Thread(target=worker, args=(interface,), daemon=True).start()

    with condition:
        needs_fetch = True
        needs_redraw = True
        condition.notify()

    while True:
        time.sleep(interval)
        with condition:
            needs_fetch = True
            needs_redraw = True
            condition.notify()

if __name__ == '__main__':
    main()
