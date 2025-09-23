#!/usr/bin/env python3

from pathlib import Path
from typing import Any, Dict, List, Optional, NamedTuple
from waybar import glyphs, util
import json
import os
import re
import sys
import time

util.validate_requirements(required=['click'])
import click

CACHE_DIR = util.get_cache_directory()
CONTEXT_SETTINGS = dict(help_option_names=['-h', '--help'])

class NetworkSample(NamedTuple):
    interface   : Optional[str] = None
    rx_bytes    : Optional[int] = -1
    rx_packets  : Optional[int] = -1
    rx_errors   : Optional[int] = -1
    rx_dropped  : Optional[int] = -1
    rx_fifo     : Optional[int] = -1
    tx_bytes    : Optional[int] = -1
    tx_packets  : Optional[int] = -1
    tx_errors   : Optional[int] = -1
    tx_dropped  : Optional[int] = -1
    tx_fifo     : Optional[int] = -1

class NetworkThrouhput(NamedTuple):
    success     : Optional[bool] = False
    error       : Optional[str]  = None
    received    : Optional[str]  = None
    transmitted : Optional[str]  = None

def get_icon(interface: str=None, connected: bool=True):
    if os.path.isdir(f'/sys/class/net/{interface}/wireless'):
        return glyphs.md_wifi_strength_4 if connected else glyphs.md_wifi_strength_off
    else:
        return glyphs.md_network if connected else glyphs.md_network_off

def get_sample(interface: str=None):
    try:
        with open('/proc/net/dev', 'r') as f:
            content = f.read()
    except:
        return None
    
    pattern = rf'{interface}:\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)'
    match = re.search(pattern, content, re.MULTILINE)
    if match:
        # int   bytes       packes      errs  drop    fifo    frame      comp      multi  | bytes       packets    errs   drop   fifo   colls   carrier    compressed
        # wlo1: 77442682121 55683972    0     8633    0       0          0         0      | 18241197531 8222646    0      11     0      0       0          0
        return NetworkSample(
            interface  = interface,
            rx_bytes   = int(match.group(1)),  # bytes received
            rx_packets = int(match.group(2)),  # packets received
            rx_errors  = int(match.group(3)),  # total # of rx errors
            rx_dropped = int(match.group(4)),  # total # of rx packets dropped
            rx_fifo    = int(match.group(5)),  # number of FIFO rx errors
            tx_bytes   = int(match.group(9)),  # bytes sent
            tx_packets = int(match.group(10)), # packets sent
            tx_errors  = int(match.group(11)), # total # of tx errors
            tx_dropped = int(match.group(12)), # total # of tx packets dropped
            tx_fifo    = int(match.group(13)), # number of FIFO tx errors
        )
    
    return None

def get_network_throughput(interface: str=None):
    errors = []
    first = get_sample(interface=interface)
    time.sleep(1)
    second = get_sample(interface=interface)

    if not first or not second:
        return NetworkThrouhput(
            success = False,
            error   = 'failed to get data from /proc/net/dev'
        )

    return NetworkThrouhput(
        success     = True,
        received    = util.network_speed(second.rx_bytes - first.rx_bytes),
        transmitted = util.network_speed(second.tx_bytes - first.tx_bytes),
    )

@click.command(name='run', help='Get network throughput via /proc/net/dev')
@click.option('--interface', required=True, help='The interface to check')
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
                    'text'  : f'{get_icon(interface=interface)} {interface} {glyphs.cod_arrow_small_down}{network_throughput.received} {glyphs.cod_arrow_small_up}{network_throughput.transmitted}',
                    'class' : 'success',
                }
            else:
                output = {
                    'text'  : f'{get_icon(interface=interface)} {interface} {network_throughput.error}',
                    'class' : 'error',
                }
        else:
            output = {
                'text'  : f'{get_icon(interface=interface, connected=False)} {interface} disconnected',
                'class' : 'error'
            }

        print(json.dumps(output))

if __name__ == '__main__':
    main()
