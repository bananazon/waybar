#!/usr/bin/env python3

from waybar import glyphs, http, util
import json

# util.validate_requirements(modules=["click"])
import click

context_settings = dict(help_option_names=["-h", "--help"])


def get_plex_status(ip: str, port: int, token: str) -> tuple[bool, bool]:
    response = http.request(
        method="GET",
        url=f"http://localhost:{port}/identity",
    )
    process = True if response and response.status == 200 else False

    response = http.request(
        method="GET",
        url="https://api.plex.tv/api/resources",
        params={
            "includeHttps": 1,
            "X-Plex-Token": token,
        },
    )
    available = True if response and response.status == 200 else False

    return process, available


@click.command(
    help="Show the status of your Plex Media Server", context_settings=context_settings
)
@click.option(
    "-i",
    "--ip",
    required=False,
    default=util.find_public_ip(),
    show_default=True,
    help="The public IP of the Plex media server",
)
@click.option(
    "-p",
    "--port",
    required=False,
    default=32400,
    show_default=True,
    help="The port of the Plex media server",
)
@click.option(
    "-t",
    "--token",
    required=True,
    help='Plex Server API token; stored in "/var/lib/plexmediaserver/Library/Application Support/Plex Media Server/Preferences.xml"',
)
def main(ip: str, port: int, token: str):
    if util.network_is_reachable():
        if not ip:
            output = {
                "text": f"{glyphs.md_alert}{glyphs.icon_spacer}unable to determine the public IP address",
                "class": "error",
                "tooltip": "Plex error",
            }
        else:
            process, available = get_plex_status(ip=ip, port=port, token=token)
            process_color = "green" if process else "red"
            availability_color = "green" if available else "red"
            process_ok = "OK" if process else "Not OK"
            availability_ok = "OK" if available else "Not OK"
            tooltip = [
                "Plex Media Server",
                f"IP: {ip}",
                f"Port: {port}",
                f'Process: <span foreground="{process_color}">{process_ok}</span>',
                f'Availability: <span foreground="{availability_color}">{availability_ok}</span>',
            ]

            if process and available:
                output = {
                    "text": f'{glyphs.md_plex}{glyphs.icon_spacer}<span foreground="{process_color}">●</span> <span foreground="{availability_color}">●</span>',
                    "class": "success",
                    "markup": "pango",
                    "tooltip": "\n".join(tooltip),
                }
            else:
                output = {
                    "text": f'{glyphs.md_plex}{glyphs.icon_spacer}<span foreground="{process_color}">●</span> <span foreground="{availability_color}">●</span>',
                    "class": "error",
                    "markup": "pango",
                    "tooltip": "\n".join(tooltip),
                }
    else:
        output = {
            "text": f"{glyphs.md_alert}{glyphs.icon_spacer}the network is unreachable",
            "class": "error",
        }

    print(json.dumps(output))


if __name__ == "__main__":
    main()
