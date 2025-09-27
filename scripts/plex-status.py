#!/usr/bin/env python3

from urllib.parse import quote, urlunparse
from waybar import glyphs, util
import json
import urllib.request
import xml.etree.ElementTree as ET

util.validate_requirements(required=['click'])
import click

CONTEXT_SETTINGS = dict(help_option_names=['-h', '--help'])

def find_public_ip():
    url = 'https://ifconfig.io'
    headers = {'User-Agent': 'curl/7.54.1'}
    request = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(request) as response:
        body = response.read().decode('utf-8').strip()
        if response.status == 200:
            return body
    return None

def get_plex_status(ip: str=None, port: int=0, token: str=None):
    url = f'http://localhost:{port}/identity'
    request = urllib.request.Request(url)
    with urllib.request.urlopen(request) as response:
        body = response.read().decode('utf-8').strip()
        process = True if response.status == 200 else False
    
    url = f'https://api.plex.tv/api/resources?includeHttps=1&X-Plex-Token={token}'
    request = urllib.request.Request(url)
    with urllib.request.urlopen(request, timeout=3) as response:
        body = response.read().decode('utf-8').strip()
        available = True if response.status == 200 else False

    return process, available

@click.command(help='Show the status of your Plex Media Server', context_settings=CONTEXT_SETTINGS)
@click.option('-i', '--ip', required=False, default=find_public_ip(), show_default=True, help=f'The public IP of the Plex media server')
@click.option('-p', '--port', required=False, default=32400, show_default=True, help=f'The port of the Plex media server')
@click.option('-t', '--token', required=True, help=f'Plex Server API token; stored in \"/var/lib/plexmediaserver/Library/Application Support/Plex Media Server/Preferences.xml\"')
def main(ip, port, token):
    if util.network_is_reachable():
        if not ip:
            output = {
                'text'    : f'{glyphs.md_alert}{glyphs.icon_spacer}unable to determine the public IP address',
                'class'   : 'error',
                'tooltip' : f'{location} error',
            }
        else:
            process, available = plex_status = get_plex_status(ip=ip, port=port, token=token)
            process_color = 'green' if process else 'red'
            availability_color = 'green' if available else 'red'
            process_ok = 'OK' if process else 'Not OK'
            availability_ok = 'OK' if available else 'Not OK'
            tooltip = [
                'Plex Media Server',
                f'IP: {ip}',
                f'Port: {port}',
                f'Process: <span foreground="{process_color}">{process_ok}</span>',
                f'Availability: <span foreground="{availability_color}">{availability_ok}</span>',
            ]

            if process and available:
                output = {
                    'text'    : f'{glyphs.md_plex}{glyphs.icon_spacer}<span foreground="{process_color}">●</span> <span foreground="{availability_color}">●</span>',
                    'class'   : 'success',
                    'markup'  : 'pango',
                    'tooltip' : '\n'.join(tooltip),
                }
            else:
                output = {
                    'text'    : f'{glyphs.md_plex}{glyphs.icon_spacer}<span foreground="{process_color}">●</span> <span foreground="{availability_color}">●</span>',
                    'class'   : 'error',
                    'markup'  : 'pango',
                    'tooltip' : '\n'.join(tooltip),
                }
    else:
        output = {
            'text'    : f'{glyphs.md_alert}{glyphs.icon_spacer}the network is unreachable',
            'class'   : 'error',
        }

    print(json.dumps(output)) 

if __name__ == '__main__':
    main()
