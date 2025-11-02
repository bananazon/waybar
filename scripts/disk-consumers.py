#!/usr/bin/env python3

from collections import OrderedDict
from dataclasses import dataclass, field
from glob import glob
from pathlib import Path
from waybar import glyphs, util
import click
import json
import logging
import os
import re
import signal
import subprocess
import sys
import threading
import time

sys.stdout.reconfigure(line_buffering=True)


@dataclass
class PathEntry:
    success: bool = False
    error: str | None = None
    count: int = -1
    path: str | None = None
    usage: OrderedDict[str, float] = field(default_factory=OrderedDict)
    updated: str | None = None


cache_dir = util.get_cache_directory()
condition = threading.Condition()
context_settings = dict(help_option_names=["-h", "--help"])
disk_consumers: list[PathEntry] = []
format_index: int = 0
logfile = cache_dir / "waybar-filesystem-usage.log"
needs_fetch: bool = False
needs_redraw: bool = False

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
    if disk_consumers and type(disk_consumers) is list:
        path = disk_consumers[format_index].path
    else:
        path = format_index + 1
    logging.info(
        f"[toggle_format] - received SIGUSR1 - switching output format to {path}"
    )
    with condition:
        needs_redraw = True
        condition.notify()


_ = signal.signal(signal.SIGHUP, refresh_handler)
_ = signal.signal(signal.SIGUSR1, toggle_format)


def generate_tooltip(disk_consumers: PathEntry):
    tooltip: list[str] = []
    max_len = 0
    for key, _ in disk_consumers.usage.items():
        max_len = (
            len(os.path.basename(key))
            if len(os.path.basename(key)) > max_len
            else max_len
        )

    for key, value in disk_consumers.usage.items():
        icon = glyphs.md_folder if os.path.isdir(key) else glyphs.md_file
        tooltip.append(
            f"{icon}{glyphs.icon_spacer}{os.path.basename(key):{max_len}} {util.byte_converter(number=value, unit='auto', use_int=False)}"
        )

    tooltip.append("")
    tooltip.append(f"Last updated {disk_consumers.updated}")

    return "\n".join(tooltip)


def find_consumers(path: str):
    min_bytes = 1_048_576
    sorted_data_desc: dict[str, int] = {}

    if Path(path).exists():
        paths = glob(f"{path}/*")
        command = ["du", "-sb", *paths]
        try:
            result = subprocess.run(
                command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
            )
            stdout = result.stdout.lstrip().rstrip()
            if stdout != "":
                usage: dict[str, int] = {}
                for line in stdout.split("\n"):
                    match = re.search(r"^([\d]+)\s+(.*)$", line)
                    if match:
                        if int(match.group(1)) > min_bytes:
                            usage[match.group(2)] = int(match.group(1))
                sorted_data_desc = dict(
                    sorted(usage.items(), key=lambda x: x[1], reverse=True)
                )
                usage_od: OrderedDict[str, float] = OrderedDict()
                for item, size in sorted_data_desc.items():
                    usage_od[item] = size

                return PathEntry(
                    success=True,
                    path=path,
                    count=len(usage_od),
                    usage=usage_od,
                    updated=util.get_human_timestamp(),
                )
        except Exception:
            return PathEntry(
                success=False,
                path=path,
                error="failed to get usage",
            )
    else:
        return PathEntry(
            success=False,
            path=path,
            error="doesn't exist",
        )


def render_output(disk_consumers: PathEntry, icon: str) -> tuple[str, str, str]:
    if disk_consumers.success and disk_consumers.path:
        text = f"{icon}{glyphs.icon_spacer}{disk_consumers.path.replace('&', '&amp')}"
        output_class = "success"
        tooltip = generate_tooltip(disk_consumers=disk_consumers)
    else:
        text = f"{icon}{glyphs.icon_spacer}{disk_consumers.path} {disk_consumers.error}"
        output_class = "error"
        tooltip = f"{disk_consumers.path} error"

    return text, output_class, tooltip


def worker(paths: list[str]) -> list[PathEntry]:
    global disk_consumers, needs_fetch, needs_redraw, format_index

    while True:
        with condition:
            while not (needs_fetch or needs_redraw):
                _ = condition.wait()

            fetch = needs_fetch
            redraw = needs_redraw
            needs_fetch = False
            needs_redraw = False

        if fetch:
            disk_consumers = []
            for path in paths:
                print(
                    json.dumps(
                        {
                            "text": f"{glyphs.md_timer_outline}{glyphs.icon_spacer}Scanning {path}...",
                            "class": "loading",
                            "tooltip": f"Scanning {path}...",
                        }
                    )
                )
                path_usage = find_consumers(path=path)
                if path_usage:
                    disk_consumers.append(path_usage)

        if disk_consumers:
            continue

        if disk_consumers and len(disk_consumers) > 0:
            if redraw:
                text, output_class, tooltip = render_output(
                    disk_consumers=disk_consumers[format_index], icon=glyphs.md_folder
                )
                output = {
                    "text": text,
                    "class": output_class,
                    "tooltip": tooltip,
                }
                print(json.dumps(output))


@click.command(
    help="Show a list of disk consumers for one of more directories",
    context_settings=context_settings,
)
@click.option(
    "-p",
    "--path",
    required=True,
    multiple=True,
    default=["~"],
    help="The path to check",
)
@click.option(
    "-u",
    "--unit",
    required=False,
    default="auto",
    type=click.Choice(util.get_valid_units()),
    help="The unit to use for output display",
)
@click.option(
    "-i", "--interval", type=int, default=5, help="The update interval (in seconds)"
)
@click.option(
    "-t", "--test", default=False, is_flag=True, help="Print the output and exit"
)
@click.option("-d", "--debug", default=False, is_flag=True, help="Enable debug logging")
def main(path: str, unit: str, interval: int, test: bool, debug: bool):
    global formats, needs_fetch, needs_redraw

    configure_logging(debug=debug)
    formats = list(range(len(path)))
    paths = [os.path.expanduser(item).rstrip("/") for item in path]

    if test:
        print(interval)
        print(unit)
        disk_consumers = find_consumers(path=paths[0])
        if disk_consumers:
            text, output_class, tooltip = render_output(
                disk_consumers=disk_consumers, icon=glyphs.md_folder
            )
            print(text)
            print(output_class)
            print(tooltip)
        return

    logging.info("[main] - entering")

    threading.Thread(
        target=worker,
        args=(
            path,
            unit,
        ),
        daemon=True,
    ).start()

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
