#!/usr/bin/env python3

from collections import OrderedDict
from dataclasses import dataclass, field
from waybar import glyphs, util
import click
import json
import logging
import os
import re
import signal
import sys
import threading
import time

sys.stdout.reconfigure(line_buffering=True)


@dataclass
class WifiStatus:
    success: bool = False
    error: str | None = None
    authenticated: bool = False
    authorized: bool = False
    bandwidth: int = 0
    channel: int = 0
    ciphers: list[str] = field(default_factory=list)
    connected_time: int = 0
    frequency: int = 0
    interface: str | None = None
    signal_strength: int = 0
    ssid_mac: str | None = None
    ssid_name: str | None = None
    updated: str | None = None


cache_dir = util.get_cache_directory()
condition = threading.Condition()
context_settings = dict(help_option_names=["-h", "--help"])
format_index: int = 0
logfile = cache_dir / "waybar-wifi-status.log"
needs_fetch: bool = False
needs_redraw: bool = False
wifi_status: list[WifiStatus] | None = []

formats: list[int] = []


def configure_logging(debug: bool = False):
    logging.basicConfig(
        filename=logfile,
        filemode="w",  # 'a' = append, 'w' = overwrite
        format="%(asctime)s [%(levelname)-5s] - %(message)s",
        level=logging.DEBUG if debug else logging.INFO,
    )


def refresh_handler(_signum: int, _frame: object | None):
    global needs_fetch, needs_redraw
    logging.info("[refresh_handler] - received SIGHUP — re-fetching data")
    with condition:
        needs_fetch = True
        needs_redraw = True
        condition.notify()


def toggle_format(_signum: int, _frame: object | None):
    global formats, format_index, needs_redraw
    format_index = (format_index + 1) % len(formats)
    if wifi_status and type(wifi_status) is list:
        interface = wifi_status[format_index].interface
    else:
        interface = format_index + 1
    logging.info(
        f"[toggle_format] - received SIGUSR1 - switching output format to {interface}"
    )
    with condition:
        needs_redraw = True
        condition.notify()


_ = signal.signal(signal.SIGHUP, refresh_handler)
_ = signal.signal(signal.SIGUSR1, toggle_format)


def generate_tooltip(wifi_status: WifiStatus) -> str:
    logging.debug(
        f"[generate_tooltip] - entering with interface={wifi_status.interface}"
    )
    tooltip: list[str] = []
    tooltip_od: OrderedDict[str, str | int | list[str]] = OrderedDict()

    if wifi_status.ssid_name and wifi_status.ssid_mac:
        tooltip_od["Connected To"] = f"{wifi_status.ssid_name} ({wifi_status.ssid_mac})"

    if wifi_status.connected_time:
        tooltip_od["Connection Time"] = util.get_duration(
            seconds=wifi_status.connected_time
        )

    if wifi_status.channel:
        channel_info: list[str] = []
        channel_info.append(f"{wifi_status.channel}")

        if wifi_status.frequency:
            channel_info.append(f"({wifi_status.frequency} MHz)")

        if wifi_status.bandwidth:
            channel_info.append(f"{wifi_status.bandwidth} MHz width")

        tooltip_od["Channel"] = " ".join(channel_info)

    if wifi_status.authenticated:
        tooltip_od["Authenticated"] = "Yes" if wifi_status.authorized else "No"

    if wifi_status.authorized:
        tooltip_od["Authorized"] = "Yes" if wifi_status.authorized else "No"

    if wifi_status.ciphers:
        tooltip_od["Available Ciphers"] = wifi_status.ciphers

    max_key_length = 0
    for key in tooltip_od.keys():
        max_key_length = len(key) if len(key) > max_key_length else max_key_length

    for key, value in tooltip_od.items():
        if key == "Available Ciphers":
            tooltip.append(f"{key:{max_key_length}} :")
            for cipher in wifi_status.ciphers:
                tooltip.append(f"  {cipher[0]}")
        else:
            tooltip.append(f"{key:{max_key_length}} : {value}")

    if len(tooltip) > 0:
        tooltip.append("")
        tooltip.append(f"Last updated {wifi_status.updated}")

    return "\n".join(tooltip)


def get_status_icon(signal: int) -> str:
    # -30 dBm to -50 dBm is considered excellent or very good
    # -50 dBm to -67 dBm is considered good and suitable for most applications, including streaming and video conferencing
    # -67 dBm to -70 dBm is the minimum recommended for reliable performance, with -70 dBm being the threshold for acceptable packet delivery
    # signals below -70 dBm, such as -80 dBm, are considered poor and may result in unreliable connectivity and slower speeds
    # signals below -90 dBm are typically unusable.

    if -50 <= signal <= -30:
        return glyphs.md_wifi_strength_4
    elif -67 <= signal < -50:
        return glyphs.md_wifi_strength_3
    elif -70 <= signal < -67:
        return glyphs.md_wifi_strength_2
    elif -80 < signal < -70:
        return glyphs.md_wifi_strength_1
    elif -90 < signal < -80:
        return glyphs.md_wifi_strength_outline
    else:  # signal_dbm <= -90
        return glyphs.md_wifi_strength_alert_outline


def get_wifi_status(interfaces: list[str]) -> list[WifiStatus]:
    authenticated: bool = False
    authorized: bool = False
    channel: int = 0
    channel_bandwidth: int = 0
    ciphers: list[str] = []
    connected_time: int = 0
    frequency: int = 0
    interface_status: WifiStatus = WifiStatus()
    signal_strength: int = 0
    ssid_mac: str = ""
    ssid_name: str = ""
    stderr: str = ""
    stdout: str = ""
    wifi_status: list[WifiStatus] = []

    for interface in interfaces:
        if util.interface_exists(interface=interface):
            if util.interface_is_connected(interface=interface):
                if os.path.isdir(f"/sys/class/net/{interface}/wireless"):
                    wiphy = -1

                    command = f"iw dev {interface} link"
                    rc, stdout_raw, stderr_raw = util.run_piped_command(command)

                    stdout = stdout_raw if isinstance(stdout_raw, str) else ""
                    stderr = stderr_raw if isinstance(stderr_raw, str) else ""
                    if rc == 0:
                        if stdout != "":
                            match = re.search(r"signal:\s+(-\d+)", stdout, re.MULTILINE)
                            if match:
                                signal_strength = int(match.group(1))
                        else:
                            interface_status = WifiStatus(
                                success=False,
                                interface=interface,
                                error=f'no output from "{command}"',
                            )
                    else:
                        interface_status = WifiStatus(
                            success=False,
                            interface=interface,
                            error=stderr or f'failed to execute "{command}"',
                        )

                    command = f"iw dev {interface} info"
                    rc, stdout_raw, stderr_raw = util.run_piped_command(command)

                    stdout = stdout_raw if isinstance(stdout_raw, str) else ""
                    stderr = stderr_raw if isinstance(stderr_raw, str) else ""
                    if rc == 0:
                        if stdout != "":
                            match = re.search(
                                r"channel\s+(\d+)\s+\((\d+)\s+MHz\),\s+width:\s+(\d+)\s+MHz",
                                stdout,
                                re.MULTILINE,
                            )
                            if match:
                                channel = int(match.group(1))
                                frequency = int(match.group(2))
                                channel_bandwidth = int(match.group(3))

                            match = re.search(r"ssid\s+(.*)$", stdout, re.MULTILINE)
                            if match:
                                ssid_name = match.group(1)

                            match = re.search(r"wiphy\s+([\d]+)", stdout, re.MULTILINE)
                            if match:
                                wiphy = int(match.group(1))
                        else:
                            interface_status = WifiStatus(
                                success=False,
                                interface=interface,
                                error=f'no output from "{command}"',
                            )
                    else:
                        interface_status = WifiStatus(
                            success=False,
                            interface=interface,
                            error=stderr or f'failed to execute "{command}"',
                        )

                    command = f"iw dev {interface} station dump"
                    rc, stdout_raw, stderr_raw = util.run_piped_command(command)

                    stdout = stdout_raw if isinstance(stdout_raw, str) else ""
                    stderr = stderr_raw if isinstance(stderr_raw, str) else ""
                    if rc == 0:
                        if stdout != "":
                            match = re.search(
                                r"Station\s+([a-z0-9:]+)\s+", stdout, re.MULTILINE
                            )
                            if match:
                                ssid_mac = match.group(1)

                            match = re.search(
                                r"\s+connected time:\s+([\d]+)\s+seconds",
                                stdout,
                                re.MULTILINE,
                            )
                            if match:
                                connected_time = int(match.group(1))

                            match = re.search(
                                r"\s+authenticated:\s+(yes|no)", stdout, re.MULTILINE
                            )
                            if match:
                                authenticated = (
                                    True if match.group(1) == "yes" else False
                                )

                            match = re.search(
                                r"\s+authorized:\s+(yes|no)", stdout, re.MULTILINE
                            )
                            if match:
                                authorized = True if match.group(1) == "yes" else False
                        else:
                            interface_status = WifiStatus(
                                success=False,
                                interface=interface,
                                error=f'no output from "{command}"',
                            )
                    else:
                        interface_status = WifiStatus(
                            success=False,
                            interface=interface,
                            error=stderr or f'failed to execute "{command}"',
                        )

                    if wiphy >= 0:
                        command = f"iw phy phy{wiphy} info"
                        rc, stdout_raw, stderr_raw = util.run_piped_command(command)

                        stdout = stdout_raw if isinstance(stdout_raw, str) else ""
                        stderr = stderr_raw if isinstance(stderr_raw, str) else ""
                        if rc == 0:
                            if stdout != "":
                                block_match = re.search(
                                    r"Supported Ciphers:\s*((?:\s+\*.*\n)+)", stdout
                                )
                                if block_match:
                                    block = block_match.group(1)
                                    ciphers = re.findall(
                                        r"\*\s+([A-Z0-9-]+)\s+\(([^)]+)\)", block
                                    )
                            else:
                                interface_status = WifiStatus(
                                    success=False,
                                    interface=interface,
                                    error=f'no output from "{command}"',
                                )
                        else:
                            interface_status = WifiStatus(
                                success=False,
                                interface=interface,
                                error=stderr or f'failed to execute "{command}"',
                            )

                    interface_status = WifiStatus(
                        success=True,
                        authenticated=authenticated,
                        authorized=authorized,
                        bandwidth=channel_bandwidth,
                        channel=channel,
                        ciphers=sorted(ciphers),
                        connected_time=connected_time,
                        frequency=frequency,
                        interface=interface,
                        signal_strength=signal_strength,
                        ssid_mac=ssid_mac,
                        ssid_name=ssid_name,
                        updated=util.get_human_timestamp(),
                    )
        wifi_status.append(interface_status)

    return wifi_status


def render_output(wifi_status: WifiStatus, icon: str | None) -> tuple[str, str, str]:
    interface = wifi_status.interface
    logging.debug("[render_output] - entering function")
    if wifi_status.success:
        icon = icon if icon else get_status_icon(signal=wifi_status.signal_strength)
        text = (
            f"{icon}{glyphs.icon_spacer}{interface} {wifi_status.signal_strength} dBm"
        )
        output_class = "success"
        tooltip = generate_tooltip(wifi_status=wifi_status)
    else:
        text = f"{glyphs.md_wifi_strength_alert_outline}{glyphs.icon_spacer}{interface} {wifi_status.error}"
        output_class = "error"
        tooltip = f"{wifi_status.interface} error"

    logging.debug(
        f"[render_output] - exiting with text={text}, output_class={output_class}, tooltip={tooltip}"
    )
    return text, output_class, tooltip


def worker(interfaces: list[str]):
    global wifi_status, needs_fetch, needs_redraw, format_index

    while True:
        with condition:
            while not (needs_fetch or needs_redraw):
                _ = condition.wait()

            fetch = needs_fetch
            redraw = needs_redraw
            needs_fetch = False
            needs_redraw = False

        if fetch:
            loading = (
                f"{glyphs.md_timer_outline}{glyphs.icon_spacer}Gathering WiFi status..."
            )
            loading_dict = {
                "text": loading,
                "class": "loading",
                "tooltip": "Gathering WiFi status...",
            }
            if wifi_status and type(wifi_status) is list:
                text, _, tooltip = render_output(
                    wifi_status=wifi_status[format_index], icon=glyphs.md_timer_outline
                )
                print(
                    json.dumps({"text": text, "class": "loading", "tooltip": tooltip})
                )
            else:
                print(json.dumps(loading_dict))

            logging.debug("[worker] - passing to get_network_throughput")
            wifi_status = get_wifi_status(interfaces=interfaces)

        if wifi_status is None:
            continue

        if wifi_status and len(wifi_status) > 0:
            if redraw:
                text, output_class, tooltip = render_output(
                    wifi_status=wifi_status[format_index], icon=None
                )
                output = {
                    "text": text,
                    "class": output_class,
                    "tooltip": tooltip,
                }
                print(json.dumps(output))


@click.command(help="Get WiFi status using iw(8)", context_settings=context_settings)
@click.option(
    "-i", "--interface", required=True, multiple=True, help="The interface to check"
)
@click.option(
    "--interval", type=int, default=5, help="The update interval (in seconds)"
)
@click.option(
    "-t", "--test", default=False, is_flag=True, help="Print the output and exit"
)
@click.option("-d", "--debug", default=False, is_flag=True, help="Enable debug logging")
def main(interface: list[str], interval: int, test: bool, debug: bool):
    global formats, needs_fetch, needs_redraw

    configure_logging(debug=debug)
    formats = list(range(len(interface)))

    if test:
        print(interval)

        wifi_status = get_wifi_status(interfaces=interface)
        text, output_class, tooltip = render_output(
            wifi_status=wifi_status[0], icon=None
        )
        print(text)
        print(output_class)
        print(tooltip)
        return

    logging.info("[main] - entering")

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


if __name__ == "__main__":
    main()
