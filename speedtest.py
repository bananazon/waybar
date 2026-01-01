#!/usr/bin/env python3

import json
import logging
import os
import re
import signal
import socket
import subprocess
import sys
import threading
import time
from collections import OrderedDict
from datetime import datetime, timezone
from typing import cast

import click
from dacite import Config, from_dict

from waybar import glyphs
from waybar.data import speedtest
from waybar.util import conversion, log, network, system, wtime

sys.stdout.reconfigure(line_buffering=True)  # type: ignore

cache_dir = system.get_cache_directory()
condition = threading.Condition()
context_settings = dict(help_option_names=["-h", "--help"])
logfile = cache_dir / "waybar-speedtest.log"
logger: logging.Logger
needs_fetch: bool = False
speedtest_data: speedtest.Results | None = speedtest.Results()


class SpeedTest:
    global logger

    def __init__(self, **kwargs) -> None:
        self.success: bool = True
        self.error: str | None = None

        self.avg_speed: int = 0

        self.results: speedtest.Results = speedtest.Results()

    def _parse_results(self):
        server_ip: str | None = None
        client_location: network.LocationData | None = None
        server_location: network.LocationData | None = None

        self.results.client.loggedin = (
            True if self.results.client.loggedin == "1" else False
        )
        if self.results.client.ispdlavg:
            self.results.client.ispdlavg = int(self.results.client.ispdlavg)

        if self.results.client.ispulavg:
            self.results.client.ispulavg = int(self.results.client.ispulavg)

        if self.results.client.isprating:
            self.results.client.isprating = float(self.results.client.isprating)

        if self.results.client.rating:
            self.results.client.rating = int(self.results.client.rating)

        if self.results.server.d:
            self.results.server.d = float(self.results.server.d)

        if self.results.server.id:
            self.results.server.id = int(self.results.server.id)

        if self.results.client.ip:
            client_location = network.ip_to_location(ip=self.results.client.ip)

        if self.results.server.host:
            hostname = self.results.server.host.split(":")[0]
            try:
                server_ip = socket.gethostbyname(hostname)
            except Exception:
                server_ip = None

        if server_ip:
            server_location = network.ip_to_location(ip=server_ip)
            self.results.server.ip = server_ip

        if client_location:
            self.results.client.city = client_location.city
            self.results.client.country = client_location.country
            self.results.client.region = client_location.region
            self.results.client.timezone = client_location.timezone
            if client_location.org:
                self.results.client.isp = client_location.org

        if server_location:
            self.results.server.city = (
                server_location.city
                if server_location.city
                else re.split(r"\s*,\s*", self.results.server.name)[0] or None
            )
            self.results.server.country = (
                server_location.country
                if server_location.country
                else self.results.server.country or None
            )
            self.results.server.region = (
                server_location.region
                if server_location.region
                else re.split(r"\s*,\s*", self.results.server.name)[1] or None
            )

            self.results.server.timezone = server_location.timezone

            self.results.speed_rx = round(self.results.download)
            self.results.speed_tx = round(self.results.upload)

            self.avg_speed = cast(
                int, (self.results.speed_rx + self.results.speed_tx) / 2
            )

            self._get_icon()
            self.results.success = True

    def _get_icon(self):
        if self.avg_speed < 100_000_000:
            self.results.icon = glyphs.md_speedometer_slow
        elif self.avg_speed < 500_000_000:
            self.results.icon = glyphs.md_speedometer_medium
        else:
            self.results.icon = glyphs.md_speedometer_fast

    def run_speedtest(self):
        stdout: str = ""
        stderr: str = ""

        command_list = ["speedtest-cli", "--secure", "--json"]
        command = " ".join(command_list)
        runtime = datetime.fromtimestamp(time.time(), tz=timezone.utc).isoformat()

        try:
            result = subprocess.run(
                command_list, capture_output=True, text=True, check=False
            )
            stdout = result.stdout.strip()
            stderr = result.stderr.strip()
            rc = result.returncode
        except Exception as e:
            return speedtest.Results(
                success=False,
                error=stderr or f'failed to execute "{command}": {e}',
                icon=glyphs.md_alert,
            )

        if rc == 0 and stdout != "":
            try:
                json_data = cast(dict[str, object], json.loads(stdout))
                # Speedtest timestamp (2025-12-30T16:44:17.640410+00:00Z) is
                # an invalid format so we fix it here
                if "timestamp" in json_data:
                    timestamp = cast(str, json_data["timestamp"])
                    logger.info(f"runtime = {runtime}")
                    logger.info(f"timstamp = {timestamp}")
                    match = re.search(
                        r"^(\d{4}\-\d{2}\-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?(\+\d{2}:\d{2})?)",
                        timestamp,
                    )
                    json_data["timestamp"] = match.group(1) if match else runtime

                self.results = from_dict(
                    data_class=speedtest.Results,
                    data=json_data,
                    config=Config(
                        cast=[int, float, str],
                        type_hooks={datetime: datetime.fromisoformat},
                    ),
                )
            except Exception as e:
                self.success = False
                self.error = str(e)
                return

        self._parse_results()


def refresh_handler(_signum: int, _frame: object | None):
    global needs_fetch, needs_redra
    logging.info("[refresh_handler] - received SIGHUP — triggering speedtest")
    with condition:
        needs_fetch = True
        condition.notify()


_ = signal.signal(signal.SIGHUP, refresh_handler)


def generate_tooltip(results: speedtest.Results) -> str:
    tooltip: list[str] = []
    tooltip_od: OrderedDict[str, str | int | float | None] = OrderedDict()

    if results.bytes_sent and results.bytes_received:
        tooltip_od["Bytes sent"] = conversion.byte_converter(
            number=results.bytes_sent, unit="auto", use_int=False
        )
        tooltip_od["Bytes received"] = conversion.byte_converter(
            number=results.bytes_received, unit="auto", use_int=False
        )

    if results.speed_tx and results.speed_rx:
        tooltip_od["Upload speed"] = network.network_speed(
            number=results.speed_tx, bytes=False
        )
        tooltip_od["Download speed"] = network.network_speed(
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


def parse_results(results: speedtest.Results) -> speedtest.Results:
    server_ip: str | None = None
    client_location: network.LocationData | None = None
    server_location: network.LocationData | None = None

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
        client_location = network.ip_to_location(ip=results.client.ip)

    if results.server.host:
        hostname = results.server.host.split(":")[0]
        try:
            server_ip = socket.gethostbyname(hostname)
        except Exception:
            server_ip = None

    if server_ip:
        server_location = network.ip_to_location(ip=server_ip)
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
        results.updated = wtime.get_human_timestamp()
        results.success = True

    return results


def run_speedtest() -> speedtest.Results:
    # speedtest_results: Results = Results()
    results: speedtest.Results = speedtest.Results()
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
        return speedtest.Results(
            success=False,
            error=stderr or f'failed to execute "{command}": {e}',
            icon=glyphs.md_alert,
        )

    if rc == 0 and stdout != "":
        json_data = cast(dict[str, object], json.loads(stdout))
        results = from_dict(
            data_class=speedtest.Results,
            data=json_data,
            config=Config(cast=[int, float, str]),
        )

    speedtest_results = parse_results(results=results)
    return speedtest_results


def render_output(speedtest_data: speedtest.Results, icon: str) -> tuple[str, str, str]:
    logging.info("[render_output] - entering function")
    text: str = ""
    output_class: str = ""
    tooltip: str = ""

    if speedtest_data.success:
        parts: list[str] = []
        if speedtest_data.speed_rx:
            parts.append(
                f"{glyphs.cod_arrow_small_down}{network.network_speed(number=speedtest_data.speed_rx, bytes=False)}"
            )
        if speedtest_data.speed_tx:
            parts.append(
                f"{glyphs.cod_arrow_small_up}{network.network_speed(number=speedtest_data.speed_tx, bytes=False)}"
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
    global speedtest_data, needs_fetch

    while True:
        with condition:
            while not needs_fetch:
                _ = condition.wait()

            fetch = needs_fetch
            needs_fetch = False

        if not network.network_is_reachable():
            print(
                json.dumps(
                    {
                        "text": f"{glyphs.md_alert}{glyphs.icon_spacer}the network is unreachable",
                        "class": "error",
                        "tooltip": "Speedtest error",
                    }
                )
            )
            continue

        if fetch:
            loading = (
                f"{glyphs.md_timer_outline}{glyphs.icon_spacer}Speedtest running..."
            )
            loading_dict = {
                "text": loading,
                "class": "loading",
                "tooltip": "Speedtest is running",
            }

            if (
                speedtest_data
                and type(speedtest_data) is speedtest.Results
                and speedtest_data.success
            ):
                text, _, tooltip = render_output(
                    speedtest_data=speedtest_data, icon=glyphs.md_timer_outline
                )
                print(
                    json.dumps({"text": text, "class": "loading", "tooltip": tooltip})
                )
            else:
                print(json.dumps(loading_dict))

            speedtest_data = run_speedtest()

        if speedtest_data is None:
            continue

        if speedtest_data and type(speedtest_data) is speedtest.Results:
            text, output_class, tooltip = render_output(
                speedtest_data=speedtest_data, icon=speedtest_data.icon
            )
            print(
                json.dumps(
                    {
                        "text": text,
                        "class": output_class,
                        "tooltip": tooltip,
                    }
                )
            )


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
@click.option("-d", "--debug", default=False, is_flag=True, help="Enable debug logging")
def main(interval: int, test: bool, debug: bool):
    global formats, logger, needs_fetch

    logger = log.configure(
        debug=debug, name=os.path.basename(__file__), logfile=logfile
    )

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

    with condition:
        needs_fetch = True
        condition.notify()

    while True:
        time.sleep(interval)
        with condition:
            needs_fetch = True
            condition.notify()


if __name__ == "__main__":
    main()
