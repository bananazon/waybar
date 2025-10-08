#!/usr/bin/env python3

from collections import OrderedDict
from pathlib import Path
from typing import Any, Dict, List, Optional, NamedTuple
from waybar import glyphs, util
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

util.validate_requirements(binaries=['jc', 'udevadm'])

sys.stdout.reconfigure(line_buffering=True)

cache_dir          = util.get_cache_directory()
condition          = threading.Condition()
context_settings   = dict(help_option_names=['-h', '--help'])
format_index       = 0
logfile            = cache_dir / f'waybar-network-throughput.log'
needs_fetch        = False
needs_redraw       = False
network_throughput = None

formats : list | None=None

class NetworkThroughput(NamedTuple):
    success     : Optional[bool] = False
    error       : Optional[str]  = None
    alias       : Optional[str]  = None
    device_name : Optional[str]  = None
    driver      : Optional[str]  = None
    interface   : Optional[str]  = None
    ip_private  : Optional[str]  = None
    ip_public   : Optional[str]  = None
    mac_address : Optional[str]  = None
    model       : Optional[str]  = None
    received    : Optional[str]  = None
    transmitted : Optional[str]  = None
    vendor      : Optional[str]  = None
    updated     : Optional[str]  = None

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
    if network_throughput and type(network_throughput) == list:
        interface = network_throughput[format_index].interface
    else:
        interface = format_index + 1
    logging.info(f'[toggle_format] - received SIGUSR1 - switching output format to {interface}')
    with condition:
        needs_redraw = True
        condition.notify()

signal.signal(signal.SIGHUP, refresh_handler)
signal.signal(signal.SIGUSR1, toggle_format)

def generate_tooltip(network_throughput: NamedTuple=None):
    tooltip = []
    tooltip_od = OrderedDict()

    if network_throughput.vendor and network_throughput.model:
        tooltip.append(f'{network_throughput.vendor} {network_throughput.model}')

    if network_throughput.mac_address:
        tooltip_od['MAC Address'] = network_throughput.mac_address

    if network_throughput.ip_public:
        tooltip_od['IP (Public)'] = network_throughput.ip_public

    if network_throughput.ip_private:
        tooltip_od['IP (Private)'] = network_throughput.ip_private

    if network_throughput.device_name:
        tooltip_od['Device Name'] = network_throughput.device_name

    if network_throughput.driver:
        tooltip_od['Driver'] = network_throughput.driver

    if network_throughput.alias:
        tooltip_od['Alias'] = network_throughput.alias

    max_key_length = 0
    for key in tooltip_od.keys():
        max_key_length = len(key) if len(key) > max_key_length else max_key_length

    for key, value in tooltip_od.items():
        tooltip.append(f'{key:{max_key_length}} : {value}')

    if len(tooltip) > 0:
        tooltip.append('')
        tooltip.append(f'Last updated {network_throughput.updated}')

    return '\n'.join(tooltip)

def get_icon(interface: str=None, connected: bool=True):
    if os.path.isdir(f'/sys/class/net/{interface}/wireless'):
        return glyphs.md_wifi_strength_4 if connected else glyphs.md_wifi_strength_alert_outline
    else:
        return glyphs.md_network if connected else glyphs.md_network_off

def get_sample(interface: str=None):
    command = f'jc --pretty /proc/net/dev'
    rc, stdout, stderr = util.run_piped_command(command)
    if rc == 0 and stdout != '':
        json_data, err = util.parse_json_string(stdout)
        if not err:
            entries = []
            for entry in json_data:
                sample = util.dict_to_namedtuple(name='NetworkSample', obj=entry)
                entries.append(sample)
            return entries

    return None

def get_network_throughput(interfaces: list=None):
    network_throughput = []
    first_sample = get_sample()
    time.sleep(1)
    second_sample = get_sample()

    if not first_sample or not second_sample:
        return [NetworkThroughput(
            success = False,
            error   = 'failed to get network data'
        )]

    for interface in interfaces:
        if util.interface_exists(interface=interface):
            if util.interface_is_connected(interface=interface):
                public_ip = util.find_public_ip()
                private_ip, mac_address = util.find_private_ip_and_mac(interface=interface)
                alias       = None
                device_name = None
                driver      = None
                model       = None
                vendor      = None

                command = f'udevadm info --query=all --path=/sys/class/net/{interface}'
                rc, stdout, stderr = util.run_piped_command(command)
                if rc == 0 and stdout != '':
                    match = re.search(r'SYSTEMD_ALIAS=(.*)', stdout, re.MULTILINE)
                    if match:
                        alias = match.group(1)

                    match = re.search(r'ID_NET_LABEL_ONBOARD=(.*)', stdout, re.MULTILINE)
                    if match:
                        device_name = match.group(1)

                    match = re.search(r'ID_NET_DRIVER=(.*)', stdout, re.MULTILINE)
                    if match:
                        driver = match.group(1)

                    match = re.search(r'ID_MODEL_FROM_DATABASE=(.*)', stdout, re.MULTILINE)
                    if match:
                        model = match.group(1)

                    match = re.search(r'ID_VENDOR_FROM_DATABASE=(.*)', stdout, re.MULTILINE)
                    if match:
                        vendor = match.group(1)
                
                first = [entry for entry in first_sample if entry.interface == interface][0]
                second = [entry for entry in second_sample if entry.interface == interface][0]

                network_throughput.append(NetworkThroughput(
                    success     = True,
                    alias       = alias,
                    device_name = device_name,
                    driver      = driver,
                    interface   = interface,
                    ip_private  = private_ip,
                    ip_public   = public_ip,
                    mac_address = mac_address,
                    model       = model,
                    received    = util.network_speed(second.r_bytes - first.r_bytes),
                    transmitted = util.network_speed(second.t_bytes - first.t_bytes),
                    vendor      = vendor,
                    updated     = util.get_human_timestamp(),
                ))
            else:
                network_throughput.append(NetworkThroughput(
                    success   = False,
                    error     = 'disconnected',
                    interface = interface,
                ))
        else:
            network_throughput.append(NetworkThroughput(
                success   = False,
                error     = 'doesn\'t exist',
                interface = interface,
            ))

    return network_throughput

def render_output(network_throughput: NamedTuple=None, icon: str=None):
    interface = network_throughput.interface
    logging.debug('[render_output] - entering function')
    icon = icon if icon else get_icon(interface=interface)
    if network_throughput.success:
        text = f'{icon}{glyphs.icon_spacer}{interface} {glyphs.cod_arrow_small_down}{network_throughput.received} {glyphs.cod_arrow_small_up}{network_throughput.transmitted}'
        output_class = 'success'
        tooltip = generate_tooltip(network_throughput=network_throughput)
    else:
        text = f'{glyphs.md_alert}{glyphs.icon_spacer}{interface} {network_throughput.error}'
        output_class = 'error'
        tooltip = f'{network_throughput.interface} error'

    logging.debug(f'[render_output] - exiting with text={text}, output_class={output_class}, tooltip={tooltip}')
    return text, output_class, tooltip

def worker(interfaces: list=None):
    global network_throughput, needs_fetch, needs_redraw, format_index

    while True:
        with condition:
            while not (needs_fetch or needs_redraw):
                condition.wait()

            fetch        = needs_fetch
            redraw       = needs_redraw
            needs_fetch  = False
            needs_redraw = False

        if fetch:
            loading      = f'{glyphs.md_timer_outline}{glyphs.icon_spacer}Gathering network data...'
            loading_dict = { 'text': loading, 'class': 'loading', 'tooltip': 'Gathering network data...'}
            if network_throughput and type(network_throughput) == list:
                text, _, tooltip = render_output(network_throughput=network_throughput[format_index], icon=glyphs.md_timer_outline)
                print(json.dumps({'text': text, 'class': 'loading', 'tooltip': tooltip}))
            else:
                print(json.dumps(loading_dict))

            logging.debug('[worker] - passing to get_network_throughput')
            network_throughput = get_network_throughput(interfaces=interfaces)

        if network_throughput is None:
            continue

        if network_throughput and type(network_throughput) == list:
            if redraw:
                text, output_class, tooltip = render_output(network_throughput=network_throughput[format_index])
                output = {
                    'text'    : text,
                    'class'   : output_class,
                    'tooltip' : tooltip,
                }
                print(json.dumps(output))

@click.command(name='run', help='Get network throughput via /sys/class/net')
@click.option('-i', '--interface', required=True, multiple=True, help='The interface to check')
@click.option('--interval', type=int, default=5, help='The update interval (in seconds)')
@click.option('-t', '--test', default=False, is_flag=True, help='Print the output and exit')
@click.option('-d', '--debug', default=False, is_flag=True, help='Enable debug logging')
def main(interface, interval, test, debug):
    global formats, needs_fetch, needs_redraw

    configure_logging(debug=debug)
    formats = list(range(len(interface)))

    if test:
        network_throughput = get_network_throughput(interfaces=interface)
        util.pprint(network_throughput[0])
        print()
        print(generate_tooltip(network_throughput=network_throughput[0]))
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
