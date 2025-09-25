#!/usr/bin/env python3

from urllib.parse import quote, urlunparse
from waybar import glyphs, util
import argparse
import json
import urllib.request

def find_public_ip():
    url = 'https://ifconfig.io'
    headers = {'User-Agent': 'curl/7.54.1'}
    request = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(request) as response:
        body = response.read().decode('utf-8').strip()
        if response.status == 200:
            return body
    return None

def get_plex_status(ip: str=None, port: int=0):
    url = f'http://localhost:{port}/identity'
    request = urllib.request.Request(url)
    with urllib.request.urlopen(request) as response:
        body = response.read().decode('utf-8').strip()
        process = True if response.status == 200 else False
    
    url = f'http://{ip}:{port}/identity'
    request = urllib.request.Request(url)
    with urllib.request.urlopen(request, timeout=3) as response:
        body = response.read().decode('utf-8').strip()
        available = True if response.status == 200 else False

    return process, available

def main():
    mode_count = 4
    parser = argparse.ArgumentParser(description='Show the status of your Plex Media Server')
    parser.add_argument('-i', '--ip', default=find_public_ip(), help='The public IP of the Plex media server', required=False)
    parser.add_argument('-p', '--port', default=32400, help='The port of the Plex media server', required=False)
    args = parser.parse_args()

    process, available = plex_status = get_plex_status(ip=args.ip, port=args.port)
    process_color = 'green' if process else 'red'
    availability_color = 'green' if available else 'red'
    tooltip = f'Plex Media Server\nIP: {args.ip}\nPort: {args.port}\nProcess: {"OK" if process else "Not OK"}\nAvailability: {"OK" if available else "Not OK"}'
    if process and available:
        output = {
            'text'    : f'{glyphs.md_plex}{glyphs.icon_spacer}<span foreground="{process_color}">●</span> <span foreground="{availability_color}">●</span>',
            'class'   : 'success',
            'markup'  : 'pango',
            'tooltip' : tooltip,
        }
    else:
        output = {
            'text'    : f'{glyphs.md_plex}{glyphs.icon_spacer}<span foreground="{process_color}">●</span> <span foreground="{availability_color}">●</span>',
            'class'   : 'error',
            'markup'  : 'pango',
            'tooltip' : tooltip,
        }

    print(json.dumps(output)) 

if __name__ == '__main__':
    main()
