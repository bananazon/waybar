#!/usr/bin/env python3

import json
import logging
import re
import signal
import sys
import threading
import time
from datetime import datetime
from typing import cast

import click
from dacite import Config, from_dict
from waybar import glyphs, http
from waybar.data import quakes
from waybar.util import misc, network, system
from waybar.util import time as waybar_time

update_event = threading.Event()
sys.stdout.reconfigure(line_buffering=True)  # type: ignore


cache_dir = system.get_cache_directory()
context_settings = dict(help_option_names=["-h", "--help"])
loading = f"{glyphs.md_timer_outline}{glyphs.icon_spacer}Checking USGS..."
loading_dict = {"text": loading, "class": "loading", "tooltip": "Checking USGS..."}
logfile = cache_dir / "waybar-earthquakes.log"


def refresh_handler(_signum: int, _frame: object | None):
    logging.info("[refresh_handler] - received SIGHUP — re-fetching data")
    update_event.set()


_ = signal.signal(signal.SIGHUP, refresh_handler)


def generate_tooltip(quake_data: quakes.QuakeData) -> str:
    tooltip: list[str] = []
    max_header_len = 0
    for quake in quake_data.quakes:
        header = f"{format_time(timestamp=quake.properties.time)} - mag {quake.properties.mag}"
        max_header_len = len(header) if len(header) > max_header_len else max_header_len

    for quake in quake_data.quakes:
        header = f"{format_time(timestamp=quake.properties.time)} - mag {quake.properties.mag}"
        tooltip.append(f"{header:{max_header_len}} {quake.properties.place}")

    if len(tooltip) > 0:
        tooltip.append("")
        tooltip.append(f"Last updated {quake_data.updated}")

    return "\n".join(tooltip)


def miles_to_kilometers(miles: int) -> float:
    """Convert miles to kilometers"""
    return miles * 1.609344


def format_time(timestamp: int) -> str:
    ts = timestamp / 1000
    dt = datetime.fromtimestamp(ts)
    return dt.strftime("%Y-%m-%d %H:%M")


def get_quake_data(radius: str, limit: int, magnitude: float) -> quakes.QuakeData:
    lat: str | None = ""
    lon: str | None = ""
    maxradiuskm: float = 0
    now = int(time.time())
    quake_data: quakes.QuakeData = quakes.QuakeData()
    quakes_list: list[quakes.Quake] = []

    ip = network.get_public_ip()
    if ip:
        location_data = network.ip_to_location(ip=ip)
        if location_data:
            if location_data.loc:
                lat, lon = re.split(r"\s*,\s*", location_data.loc)

                match = re.search(r"^([\d]+)(m|km)$", radius)
                if match:
                    if match.group(2) == "km":
                        maxradiuskm = float(match.group(1))
                    elif match.group(2) == "m":
                        maxradiuskm = miles_to_kilometers(miles=int(match.group(1)))

                    response = http.request(
                        method="GET",
                        url="https://earthquake.usgs.gov/fdsnws/event/1/query",
                        params={
                            "format": "geojson",
                            "starttime": datetime.fromtimestamp(now - 86400).isoformat(
                                "T", "seconds"
                            ),
                            "endtime": datetime.fromtimestamp(now).isoformat(
                                "T", "seconds"
                            ),
                            "latitude": lat,
                            "longitude": lon,
                            "limit": limit,
                            "maxradiuskm": maxradiuskm,
                            "minmagnitude": magnitude,
                            "offset": 1,
                            "orderby": "time",
                        },
                    )

                    if response and response.status and response.status == 200:
                        if response.body:
                            json_data = cast(
                                dict[str, object], json.loads(response.body)
                            )
                            features = cast(
                                list[dict[str, object]], json_data["features"]
                            )

                            try:
                                for feature in features:
                                    quake = from_dict(
                                        data_class=quakes.Quake,
                                        data=feature,
                                        config=Config(
                                            cast=[str, int, float],
                                            type_hooks={
                                                str: misc.str_hook,
                                                int: misc.int_hook,
                                            },
                                        ),
                                    )
                                    quakes_list.append(quake)
                            except Exception as e:
                                quake_data = quakes.QuakeData(
                                    success=False,
                                    error=f"Failed to parse quake data: {e}",
                                )

                            quake_data = quakes.QuakeData(
                                success=True,
                                quakes=quakes_list,
                                updated=waybar_time.get_human_timestamp(),
                            )
                        else:
                            quake_data = quakes.QuakeData(
                                success=False,
                                error="No data was received",
                            )
                    else:
                        quake_data = quakes.QuakeData(
                            success=False,
                            error="No data was received",
                        )
            else:
                quake_data = quakes.QuakeData(
                    success=False,
                    error="Unable to determine location data",
                )
    else:
        quake_data = quakes.QuakeData(
            success=False,
            error="Unable to determine IP address",
        )

    return quake_data


def worker(radius: str, limit: int, magnitude: float):
    output: dict[str, str] = {}
    while True:
        _ = update_event.wait()
        update_event.clear()

        logging.info("[worker] entering main loop")
        if network.network_is_reachable():
            print(json.dumps(loading_dict))

            quake_data = get_quake_data(radius=radius, limit=limit, magnitude=magnitude)
            if quake_data.success:
                output = {
                    "text": f"Earthquakes: {len(quake_data.quakes)}",
                    "class": "success",
                    "tooltip": generate_tooltip(quake_data=quake_data),
                }
            else:
                output = {
                    "text": f"Earthquakes: {quake_data.error}",
                    "class": "error",
                    "tooltip": "Earthquakes error",
                }
        else:
            output = {
                "text": "the network is unreachable",
                "class": "error",
                "tooltip": "Earthquakes error",
            }

        print(json.dumps(output))


@click.command(
    help="Show recent earthquakes near you", context_settings=context_settings
)
@click.option("-r", "--radius", default="100m", help="The radius, e.g., 50m (or 50km)")
@click.option(
    "-l",
    "--limit",
    type=int,
    default=20,
    show_default=True,
    help="Maximum number of results to display",
)
@click.option(
    "-m",
    "--magnitude",
    type=float,
    default=0.1,
    show_default=True,
    help="Minimum magnitude",
)
@click.option(
    "-i", "--interval", type=int, default=900, help="The update interval (in seconds)"
)
@click.option(
    "-t", "--test", default=False, is_flag=True, help="Print the output and exit"
)
def main(radius: str, limit: int, magnitude: float, interval: int, test: bool):
    if test:
        quake_data = get_quake_data(radius=radius, limit=limit, magnitude=magnitude)
        print(generate_tooltip(quake_data=quake_data))
        return

    threading.Thread(
        target=worker,
        args=(
            radius,
            limit,
            magnitude,
        ),
        daemon=True,
    ).start()
    update_event.set()

    while True:
        time.sleep(interval)
        update_event.set()


if __name__ == "__main__":
    main()
