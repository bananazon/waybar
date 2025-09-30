#!/usr/bin/env python3

from collections import OrderedDict
from pathlib import Path
from typing import Any, Dict, List, Optional, NamedTuple
from waybar import glyphs, util
import glob
import json
import os
import re
import time

util.validate_requirements(required=['click'])
import click

CACHE_DIR = util.get_cache_directory()
CONTEXT_SETTINGS = dict(help_option_names=['-h', '--help'])

class NetworkThroughput(NamedTuple):
    success     : Optional[bool] = False
    error       : Optional[str]  = None
    alias       : Optional[str]  = None
    device_name : Optional[str]  = None
    driver      : Optional[str]  = None
    ip_private  : Optional[str]  = None
    ip_public   : Optional[str]  = None
    mac_address : Optional[str]  = None
    model       : Optional[str]  = None
    received    : Optional[str]  = None
    transmitted : Optional[str]  = None
    vendor      : Optional[str]  = None

def generate_tooltip(data):
    tooltip = []
    tooltip_od = OrderedDict()

    if data.vendor and data.model:
        tooltip.append(f'{data.vendor} data.{data.model}')

    if data.mac_address:
        tooltip_od['MAC Address'] = data.mac_address

    if data.ip_public:
        tooltip_od['IP (Public)'] = data.ip_public

    if data.ip_private:
        tooltip_od['IP (Private)'] = data.ip_private

    if data.device_name:
        tooltip_od['Device Name'] = data.device_name

    if data.driver:
        tooltip_od['Driver'] = data.driver

    if data.alias:
        tooltip_od['Alias'] = data.alias

    max_key_length = 0
    for key in tooltip_od.keys():
        max_key_length = len(key) if len(key) > max_key_length else max_key_length

    for key, value in tooltip_od.items():
        tooltip.append(f'{key:{max_key_length}} : {value}')
    
    return '\n'.join(tooltip)

def get_icon(interface: str=None, connected: bool=True):
    if os.path.isdir(f'/sys/class/net/{interface}/wireless'):
        return glyphs.md_wifi_strength_4 if connected else glyphs.md_wifi_strength_off
    else:
        return glyphs.md_network if connected else glyphs.md_network_off

def get_sample(interface: str=None):
    statistics = {'interface': interface}
    base_dir = f'/sys/class/net/{interface}/statistics'
    wanted = glob.glob(f'{base_dir}/tx_*') + glob.glob(f'{base_dir}/rx_*')
    for filename in wanted:
        statistics[os.path.basename(filename)] = util.convert_value(Path(filename).read_text().strip())

    return util.dict_to_namedtuple(name='NetworkSample', obj=statistics)

def get_network_throughput(interface: str=None):
    first = get_sample(interface=interface)
    time.sleep(1)
    second = get_sample(interface=interface)

    if not first or not second:
        return NetworkThroughput(
            success = False,
            error   = 'failed to get network data'
        )

    public_ip = util.find_public_ip()
    private_ip, mac_address = util.find_private_ip_and_mac(interface=interface)
    alias       = None
    device_name = None
    driver      = None
    model       = None
    vendor      = None

    rc, stdout, stderr = util.run_piped_command(f'udevadm info --query=all --path=/sys/class/net/{interface}')
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

    return NetworkThroughput(
        success     = True,
        alias       = alias,
        device_name = device_name,
        driver      = driver,
        ip_private  = private_ip,
        ip_public   = public_ip,
        mac_address = mac_address,
        model       = model,
        received    = util.network_speed(second.rx_bytes - first.rx_bytes),
        transmitted = util.network_speed(second.tx_bytes - first.tx_bytes),
        vendor      = vendor,
    )

@click.command(name='run', help='Get network throughput via /sys/class/net')
@click.option('-i', '--interface', required=True, help='The interface to check')
def main(interface):
    if not util.interface_exists(interface=interface):
        print(json.dumps({
            'text'  : f'{glyphs.md_alert} {interface} does not exist',
            'class' : 'error',
        }))
    else:
        if util.interface_is_connected(interface=interface):
            network_throughput = get_network_throughput(interface=interface)
            if network_throughput.success:
                output = {
                    'text'    : f'{get_icon(interface=interface)}{glyphs.icon_spacer}{interface} {glyphs.cod_arrow_small_down}{network_throughput.received} {glyphs.cod_arrow_small_up}{network_throughput.transmitted}',
                    'class'   : 'success',
                    'tooltip' : generate_tooltip(network_throughput),
                }
            else:
                output = {
                    'text'  : f'{get_icon(interface=interface)}{glyphs.icon_spacer}{interface} {network_throughput.error}',
                    'class' : 'error',
                }
        else:
            output = {
                'text'  : f'{get_icon(interface=interface, connected=False)}{glyphs.icon_spacer}{interface} disconnected',
                'class' : 'error'
            }

        print(json.dumps(output))

if __name__ == '__main__':
    main()
