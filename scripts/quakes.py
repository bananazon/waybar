#!/usr/bin/env python3

from dacite import from_dict, Config
from dataclasses import dataclass, field
from datetime import datetime
from typing import cast
from waybar import glyphs, http, util
import click
import json
import logging
import re
import signal
import sys
import threading
import time

update_event = threading.Event()
sys.stdout.reconfigure(line_buffering=True)  # type: ignore


@dataclass
class QuakeProperties:
    alert: str | None = None
    cdi: float | None = 0.0
    code: str | None = None
    detail: str | None = None
    dmin: float | None = 0.0
    felt: int = 0
    gap: int = 0
    ids: str | None = None
    mag: float | None = 0.0
    magType: str | None = None
    mmi: float | None = 0.0
    net: str | None = None
    nst: int = 0
    place: str | None = None
    rms: float | None = 0.0
    sig: int = 0
    sources: str | None = None
    status: str | None = None
    time: int = 0
    title: str | None = None
    tsunami: int = 0
    type: str | None = None
    types: str | None = None
    tz: str | None = None
    updated: int = 0
    url: str | None = None


@dataclass
class QuakeGeometry:
    type: str | None = None
    coordinates: list[float] = field(default_factory=list)


@dataclass
class Quake:
    geometry: QuakeGeometry = field(default_factory=QuakeGeometry)
    id: str | None = None
    properties: QuakeProperties = field(default_factory=QuakeProperties)
    type: str | None = None


@dataclass
class QuakeData:
    success: bool = False
    error: str | None = None
    quakes: list[Quake] = field(default_factory=list)
    updated: str | None = None


cache_dir = util.get_cache_directory()
context_settings = dict(help_option_names=["-h", "--help"])
loading = f"{glyphs.md_timer_outline}{glyphs.icon_spacer}Checking USGS..."
loading_dict = {"text": loading, "class": "loading", "tooltip": "Checking USGS..."}
logfile = cache_dir / "waybar-earthquakes.log"


def refresh_handler(_signum: int, _frame: object | None):
    logging.info("[refresh_handler] - received SIGHUP — re-fetching data")
    update_event.set()


_ = signal.signal(signal.SIGHUP, refresh_handler)


def generate_tooltip(quake_data: QuakeData) -> str:
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


def get_quake_data(radius: str, limit: int, magnitude: float) -> QuakeData:
    lat: str | None = ""
    lon: str | None = ""
    maxradiuskm: float = 0
    now = int(time.time())
    quake_data: QuakeData = QuakeData()
    quakes: list[Quake] = []

    ip = util.find_public_ip()
    if ip:
        location_data = util.ip_to_location(ip=ip)
        if location_data:
            print(location_data.loc)
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
                                        data_class=Quake,
                                        data=feature,
                                        config=Config(
                                            cast=[str, int, float],
                                            type_hooks={
                                                str: util.str_hook,
                                                int: util.int_hook,
                                            },
                                        ),
                                    )
                                    quakes.append(quake)
                            except Exception as e:
                                quake_data = QuakeData(
                                    success=False,
                                    error=f"Failed to parse quake data: {e}",
                                )

                            quake_data = QuakeData(
                                success=True,
                                quakes=quakes,
                                updated=util.get_human_timestamp(),
                            )
                        else:
                            quake_data = QuakeData(
                                success=False,
                                error="No data was received",
                            )
                    else:
                        quake_data = QuakeData(
                            success=False,
                            error="No data was received",
                        )
            else:
                quake_data = QuakeData(
                    success=False,
                    error="Unable to determine location data",
                )
    else:
        quake_data = QuakeData(
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
        if not util.waybar_is_running():
            logging.info("[worker] waybar not running")
            sys.exit(0)
        else:
            if util.network_is_reachable():
                print(json.dumps(loading_dict))

                quake_data = get_quake_data(
                    radius=radius, limit=limit, magnitude=magnitude
                )
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
        print(interval)
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
