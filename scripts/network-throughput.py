#!/usr/bin/env python3

import json
import logging
import os
import re
import signal
import sys
import threading
import time
from collections import OrderedDict
from typing import cast

import click
from dacite import Config, from_dict
from waybar import glyphs, util
from waybar.data import network_throughput as nt

sys.stdout.reconfigure(line_buffering=True)  # type: ignore


cache_dir = util.get_cache_directory()
condition = threading.Condition()
context_settings = dict(help_option_names=["-h", "--help"])
format_index: int = 0
logfile = cache_dir / "waybar-network-throughput.log"
needs_fetch = False
needs_redraw = False
network_throughput: list[nt.NetworkThroughput] | None = []

format: list[str] = []


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
    if network_throughput and type(network_throughput) is list:
        interface = network_throughput[format_index].interface
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


def generate_tooltip(network_throughput: nt.NetworkThroughput) -> str:
    logging.debug(
        f"[generate_tooltip] - entering with interface={network_throughput.interface}"
    )
    tooltip: list[str] = []
    tooltip_od: OrderedDict[str, str | int] = OrderedDict()

    if network_throughput.vendor and network_throughput.model:
        tooltip.append(f"{network_throughput.vendor} {network_throughput.model}")

    if network_throughput.mac_address:
        tooltip_od["MAC Address"] = network_throughput.mac_address

    if network_throughput.ip_public:
        tooltip_od["IP (Public)"] = network_throughput.ip_public

    if network_throughput.ip_private:
        tooltip_od["IP (Private)"] = network_throughput.ip_private

    if network_throughput.device_name:
        tooltip_od["Device Name"] = network_throughput.device_name

    if network_throughput.driver:
        tooltip_od["Driver"] = network_throughput.driver

    if network_throughput.alias:
        tooltip_od["Alias"] = network_throughput.alias

    max_key_length = 0
    for key in tooltip_od.keys():
        max_key_length = len(key) if len(key) > max_key_length else max_key_length

    for key, value in tooltip_od.items():
        tooltip.append(f"{key:{max_key_length}} : {value}")

    if len(tooltip) > 0:
        tooltip.append("")
        tooltip.append(f"Last updated {network_throughput.updated}")

    return "\n".join(tooltip)


def get_icon(interface: str) -> str:
    is_connected = util.interface_is_connected(interface=interface)
    if os.path.isdir(f"/sys/class/net/{interface}/wireless"):
        return (
            glyphs.md_wifi_strength_4
            if is_connected
            else glyphs.md_wifi_strength_alert_outline
        )
    else:
        return glyphs.md_network if is_connected else glyphs.md_network_off


def get_sample() -> list[nt.Sample] | None:
    entries: list[nt.Sample] = []
    command = "jc --pretty /proc/net/dev"
    rc, stdout_raw, _ = util.run_piped_command(command)

    stdout = stdout_raw if isinstance(stdout_raw, str) else ""
    if rc == 0 and stdout != "":
        json_data = cast(list[dict[str, object]], json.loads(stdout))
        for item in json_data:
            entry = from_dict(
                data_class=nt.Sample,
                data=item,
                config=Config(cast=[str, int]),
            )
            entries.append(entry)
        return entries
    return None


def get_network_throughput(interfaces: list[str]) -> list[nt.NetworkThroughput]:
    network_throughput: list[nt.NetworkThroughput] = []
    first_sample = get_sample()
    time.sleep(1)
    second_sample = get_sample()

    if not first_sample or not second_sample:
        return [nt.NetworkThroughput(success=False, error="failed to get network data")]

    for interface in interfaces:
        if util.interface_exists(interface=interface):
            if util.interface_is_connected(interface=interface):
                alias: str = ""
                device_name: str = ""
                driver: str = ""
                model: str = ""
                vendor: str = ""

                public_ip = util.find_public_ip()
                private_ip, mac_address = util.find_private_ip_and_mac(
                    interface=interface
                )

                command = f"udevadm info --query=all --path=/sys/class/net/{interface}"
                rc, stdout_raw, _ = util.run_piped_command(command)

                stdout = stdout_raw if isinstance(stdout_raw, str) else ""
                if rc == 0 and stdout != "":
                    match = re.search(r"SYSTEMD_ALIAS=(.*)", stdout, re.MULTILINE)
                    if match:
                        alias = match.group(1)

                    match = re.search(
                        r"ID_NET_LABEL_ONBOARD=(.*)", stdout, re.MULTILINE
                    )
                    if match:
                        device_name = match.group(1)

                    match = re.search(r"ID_NET_DRIVER=(.*)", stdout, re.MULTILINE)
                    if match:
                        driver = match.group(1)

                    match = re.search(
                        r"ID_MODEL_FROM_DATABASE=(.*)", stdout, re.MULTILINE
                    )
                    if match:
                        model = match.group(1)

                    match = re.search(
                        r"ID_VENDOR_FROM_DATABASE=(.*)", stdout, re.MULTILINE
                    )
                    if match:
                        vendor = match.group(1)

                first = [
                    entry for entry in first_sample if entry.interface == interface
                ][0]
                second = [
                    entry for entry in second_sample if entry.interface == interface
                ][0]

                network_throughput.append(
                    nt.NetworkThroughput(
                        success=True,
                        alias=alias,
                        device_name=device_name,
                        driver=driver,
                        interface=interface,
                        icon=get_icon(interface=interface),
                        ip_private=private_ip,
                        ip_public=public_ip,
                        mac_address=mac_address,
                        model=model,
                        received=util.network_speed(
                            number=second.r_bytes - first.r_bytes, bytes=False
                        ),
                        transmitted=util.network_speed(
                            number=second.t_bytes - first.t_bytes, bytes=False
                        ),
                        vendor=vendor,
                        updated=util.get_human_timestamp(),
                    )
                )
            else:
                network_throughput.append(
                    nt.NetworkThroughput(
                        success=False,
                        error="disconnected",
                        icon=get_icon(interface=interface),
                        interface=interface,
                    )
                )
        else:
            network_throughput.append(
                nt.NetworkThroughput(
                    success=False,
                    error="doesn't exist",
                    icon=get_icon(interface=interface),
                    interface=interface,
                )
            )
    return network_throughput


def render_output(
    network_throughput: nt.NetworkThroughput, icon: str | None
) -> tuple[str, str, str]:
    interface = network_throughput.interface
    logging.debug("[render_output] - entering function")
    if not icon:
        icon = (
            network_throughput.icon
            if not network_throughput.icon
            else get_icon(interface=interface)
        )
    if network_throughput.success:
        text = f"{icon}{glyphs.icon_spacer}{interface} {glyphs.cod_arrow_small_down}{network_throughput.received} {glyphs.cod_arrow_small_up}{network_throughput.transmitted}"
        output_class = "success"
        tooltip = generate_tooltip(network_throughput=network_throughput)
    else:
        text = f"{icon}{glyphs.icon_spacer}{interface} {network_throughput.error}"
        output_class = "error"
        tooltip = f"{network_throughput.interface} {network_throughput.error}"

    return text, output_class, tooltip


def worker(interfaces: list[str]):
    global network_throughput, needs_fetch, needs_redraw, format_index

    while True:
        with condition:
            while not (needs_fetch or needs_redraw):
                _ = condition.wait()

            fetch = needs_fetch
            redraw = needs_redraw
            needs_fetch = False
            needs_redraw = False

        if fetch:
            loading = f"{glyphs.md_timer_outline}{glyphs.icon_spacer}Gathering network data..."
            loading_dict = {
                "text": loading,
                "class": "loading",
                "tooltip": "Gathering network data...",
            }
            if network_throughput and type(network_throughput) is list:
                text, _, tooltip = render_output(
                    network_throughput=network_throughput[format_index],
                    icon=glyphs.md_timer_outline,
                )
                print(
                    json.dumps({"text": text, "class": "loading", "tooltip": tooltip})
                )
            else:
                print(json.dumps(loading_dict))

            network_throughput = get_network_throughput(interfaces=interfaces)

        if network_throughput is None:
            continue

        if network_throughput and len(network_throughput) > 0:
            if redraw:
                text, output_class, tooltip = render_output(
                    network_throughput=network_throughput[format_index], icon=None
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


@click.command(name="run", help="Get network throughput via /sys/class/net")
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
        network_throughput = get_network_throughput(interfaces=interface)
        text, output_class, tooltip = render_output(
            network_throughput=network_throughput[format_index],
            icon=None,
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
