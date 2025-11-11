#!/usr/bin/env python3

import json
import logging
import re
import signal
import socket
import subprocess
import sys
import threading
import time
from collections import OrderedDict
from dataclasses import dataclass, field
from typing import cast

import click
from dacite import Config, from_dict
from waybar import glyphs, util

sys.stdout.reconfigure(line_buffering=True)  # type: ignore


@dataclass
class Server:
    cc: str | None = None
    city: str | None = None
    country: str | None = None
    d: str | None = None
    host: str | None = None
    id: str | int | None = None
    ip: str | None = None
    lat: str | None = None
    latency: float = 0.0
    lon: str | None = None
    name: str = ""
    region: str | None = None
    sponsor: str | None = None
    timezone: str | None = None
    url: str | None = None


@dataclass
class Client:
    city: str | None = None
    country: str | None = None
    ip: str | None = None
    isp: str | None = None
    ispdlavg: str | int | None = None
    isprating: str | float | None = None
    ispulavg: str | int | None = None
    lat: str | None = None
    loggedin: str | bool | None = None
    lon: str | None = None
    rating: str | int | None = None
    region: str | None = None
    timezone: str | None = None


@dataclass
class Results:
    success: bool = False
    error: str | None = None
    icon: str = ""
    bytes_received: float = 0.0
    bytes_sent: float = 0.0
    client: Client = field(default_factory=Client)
    download: float = 0.0
    ping: float = 0.0
    server: Server = field(default_factory=Server)
    share: str | None = None
    speed_rx: float = 0.0
    speed_tx: float = 0.0
    timestamp: str = ""
    updated: str | None = None
    upload: float = 0.0


cache_dir = util.get_cache_directory()
condition = threading.Condition()
context_settings = dict(help_option_names=["-h", "--help"])
loading = f"{glyphs.md_timer_outline}{glyphs.icon_spacer}Speedtest running..."
loading_dict = {"text": loading, "class": "loading", "tooltip": "Speedtest is running"}
logfile = cache_dir / "waybar-speedtest.log"
speedtest_data: Results = Results()

update_event = threading.Event()


def configure_logging(debug: bool = False):
    logging.basicConfig(
        filename=logfile,
        filemode="w",  # 'a' = append, 'w' = overwrite
        format="%(asctime)s [%(levelname)-5s] - %(message)s",
        level=logging.DEBUG if debug else logging.INFO,
    )


def refresh_handler(_signum: int, _frame: object | None):
    logging.info("[refresh_handler] - received SIGHUP — triggering speedtest")
    update_event.set()


_ = signal.signal(signal.SIGHUP, refresh_handler)


def generate_tooltip(results: Results) -> str:
    tooltip: list[str] = []
    tooltip_od: OrderedDict[str, str | int | float | None] = OrderedDict()

    if results.bytes_sent and results.bytes_received:
        tooltip_od["Bytes sent"] = util.byte_converter(
            number=results.bytes_sent, unit="auto", use_int=False
        )
        tooltip_od["Bytes received"] = util.byte_converter(
            number=results.bytes_received, unit="auto", use_int=False
        )

    if results.speed_tx and results.speed_rx:
        tooltip_od["Upload speed"] = util.network_speed(
            number=results.speed_tx, bytes=False
        )
        tooltip_od["Download speed"] = util.network_speed(
            number=results.speed_rx, bytes=False
        )

    if results.ping:
        tooltip_od["Ping"] = f"{results.ping} ms"

    max_key_length = 0
    for key in tooltip_od.keys():
        max_key_length = len(key) if len(key) > max_key_length else max_key_length

    for key, value in tooltip_od.items():
        tooltip.append(f"{key:{max_key_length}} : {value}")

    if len(tooltip) > 0:
        tooltip.append("")

    if results.server:
        tooltip.append("Server")
        tooltip_od = OrderedDict()
        if results.server.ip:
            tooltip_od["IP"] = results.server.ip

        if results.server.city and results.server.region and results.server.country:
            tooltip_od["Location"] = (
                f"{results.server.city}, {results.server.region}, {results.server.country}"
            )

        if results.server.host:
            tooltip_od["Hostname"] = results.server.host.split(":")[0]

        if results.server.sponsor:
            tooltip_od["Sponsor"] = results.server.sponsor

        max_key_length = 0
        for key in tooltip_od.keys():
            max_key_length = len(key) if len(key) > max_key_length else max_key_length

        for key, value in tooltip_od.items():
            tooltip.append(f"{key:{max_key_length}} : {value}")

        if len(tooltip) > 0:
            tooltip.append("")

    if results.client:
        tooltip.append("Client")
        tooltip_od = OrderedDict()
        if results.client.ip:
            tooltip_od["IP"] = results.client.ip

        if results.client.city and results.client.region and results.client.country:
            tooltip_od["Location"] = (
                f"{results.client.city}, {results.client.region}, {results.client.country}"
            )

        if results.client.isp:
            tooltip_od["ISP"] = results.client.isp

        max_key_length = 0
        for key in tooltip_od.keys():
            max_key_length = len(key) if len(key) > max_key_length else max_key_length

        for key, value in tooltip_od.items():
            tooltip.append(f"{key:{max_key_length}} : {value}")

    if len(tooltip) > 0:
        tooltip.append("")
        tooltip.append(f"Last updated {results.updated}")

    return "\n".join(tooltip)


def get_icon(speed: int) -> str:
    if speed < 100_000_000:
        return glyphs.md_speedometer_slow
    elif speed < 500_000_000:
        return glyphs.md_speedometer_medium
    else:
        return glyphs.md_speedometer_fast


def parse_results(results: Results) -> Results:
    server_ip: str | None = None
    client_location: util.LocationData | None = None
    server_location: util.LocationData | None = None

    results.client.loggedin = True if results.client.loggedin == "1" else False
    if results.client.ispdlavg:
        results.client.ispdlavg = int(results.client.ispdlavg)

    if results.client.ispulavg:
        results.client.ispulavg = int(results.client.ispulavg)

    if results.client.isprating:
        results.client.isprating = float(results.client.isprating)

    if results.client.rating:
        results.client.rating = int(results.client.rating)

    if results.server.id:
        results.server.id = int(results.server.id)

    if results.client.ip:
        client_location = util.ip_to_location(ip=results.client.ip)

    if results.server.host:
        hostname = results.server.host.split(":")[0]
        try:
            server_ip = socket.gethostbyname(hostname)
        except Exception:
            server_ip = None

    if server_ip:
        server_location = util.ip_to_location(ip=server_ip)
        results.server.ip = server_ip

    if client_location:
        results.client.city = client_location.city
        results.client.country = client_location.country
        results.client.region = client_location.region
        results.client.timezone = client_location.timezone
        if client_location.org:
            results.client.isp = client_location.org

    if server_location:
        results.server.city = (
            server_location.city
            if server_location.city
            else re.split(r"\s*,\s*", results.server.name)[0] or None
        )
        results.server.country = (
            server_location.country
            if server_location.country
            else results.server.country or None
        )
        results.server.region = (
            server_location.region
            if server_location.region
            else re.split(r"\s*,\s*", results.server.name)[1] or None
        )

        results.server.timezone = server_location.timezone

        results.speed_rx = round(results.download)
        results.speed_tx = round(results.upload)

        avg_speed = cast(int, (results.speed_rx + results.speed_tx) / 2)

        results.icon = get_icon(speed=avg_speed)
        results.updated = util.get_human_timestamp()
        results.success = True

    return results


def run_speedtest() -> Results:
    # speedtest_results: Results = Results()
    results: Results = Results()
    stdout: str = ""
    stderr: str = ""

    command_list = ["speedtest-cli", "--secure", "--json"]
    command = " ".join(command_list)

    try:
        result = subprocess.run(
            command_list, capture_output=True, text=True, check=False
        )
        stdout = result.stdout.strip()
        stderr = result.stderr.strip()
        rc = result.returncode
    except Exception as e:
        return Results(
            success=False,
            error=stderr or f'failed to execute "{command}": {e}',
            icon=glyphs.md_alert,
        )

    if rc == 0 and stdout != "":
        json_data = cast(dict[str, object], json.loads(stdout))
        results = from_dict(
            data_class=Results,
            data=json_data,
            config=Config(cast=[int, float, str]),
        )

    speedtest_results = parse_results(results=results)
    return speedtest_results


def render_output(speedtest_data: Results, icon: str) -> tuple[str, str, str]:
    logging.info("[render_output] - entering function")
    text: str = ""
    output_class: str = ""
    tooltip: str = ""

    if speedtest_data.success:
        parts: list[str] = []
        if speedtest_data.speed_rx:
            parts.append(
                f"{glyphs.cod_arrow_small_down}{util.network_speed(number=speedtest_data.speed_rx, bytes=False)}"
            )
        if speedtest_data.speed_tx:
            parts.append(
                f"{glyphs.cod_arrow_small_up}{util.network_speed(number=speedtest_data.speed_tx, bytes=False)}"
            )

        if len(parts) == 2:
            text = f"{icon}{glyphs.icon_spacer}Speedtest {' '.join(parts)}"
            output_class = "success"
            tooltip = generate_tooltip(results=speedtest_data)
        else:
            text = f"{icon}{glyphs.icon_spacer}all tests failed"
            output_class = "error"
            tooltip = "Speedtest error"
    else:
        text = f"{glyphs.md_alert}{glyphs.icon_spacer}{speedtest_data.error}"
        output_class = "error"
        tooltip = "Speedtest error"

    return text, output_class, tooltip


def worker():
    global speedtest_data

    while True:
        _ = update_event.wait()
        update_event.clear()

        if not util.waybar_is_running():
            logging.info("[worker] - waybar not running")
            sys.exit(0)
        else:
            if util.network_is_reachable():
                if speedtest_data:
                    if speedtest_data.success:
                        text, _, tooltip = render_output(
                            speedtest_data=speedtest_data, icon=glyphs.md_timer_outline
                        )
                        print(
                            json.dumps(
                                {"text": text, "class": "loading", "tooltip": tooltip}
                            )
                        )
                    else:
                        print(json.dumps(loading_dict))

                speedtest_data = run_speedtest()
                text, output_class, tooltip = render_output(
                    speedtest_data=speedtest_data, icon=speedtest_data.icon
                )
                output = {
                    "text": text,
                    "class": output_class,
                    "tooltip": tooltip,
                }
            else:
                output = {
                    "text": f"{glyphs.md_alert}{glyphs.icon_spacer}the network is unreachable",
                    "class": "error",
                    "tooltip": "Speedtest error",
                }

        print(json.dumps(output))


@click.command(
    help="Run a network speed test and return the results",
    context_settings=context_settings,
)
@click.option(
    "-i", "--interval", type=int, default=300, help="The update interval (in seconds)"
)
@click.option(
    "-t", "--test", default=False, is_flag=True, help="Print the output and exit"
)
def main(interval: int, test: bool):
    if test:
        speedtest_data = run_speedtest()
        text, output_class, tooltip = render_output(
            speedtest_data=speedtest_data, icon=speedtest_data.icon
        )
        print(text)
        print(output_class)
        print(tooltip)
        return

    logging.info("[main] - entering function")

    threading.Thread(target=worker, args=(), daemon=True).start()
    update_event.set()

    while True:
        time.sleep(interval)
        update_event.set()


if __name__ == "__main__":
    main()
