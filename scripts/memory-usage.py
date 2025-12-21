#!/usr/bin/env python3

import json
import re
from collections import OrderedDict
from typing import cast

import click
from dacite import Config, from_dict
from waybar import glyphs, util
from waybar.data import memory_usage

context_settings = dict(help_option_names=["-h", "--help"])


def generate_tooltip(memory_info: memory_usage.MemoryInfo) -> str:
    unit = "G"
    tooltip: list[str] = []
    tooltip.append("Memory")
    tooltip_od: OrderedDict[str, str | int] = OrderedDict()

    if memory_info.total >= 0:
        tooltip_od["Total"] = util.byte_converter(
            number=memory_info.total, unit=unit, use_int=False
        )

    if memory_info.used >= 0:
        tooltip_od["Used"] = util.byte_converter(
            number=memory_info.used, unit=unit, use_int=False
        )

    if memory_info.free >= 0:
        tooltip_od["Free"] = util.byte_converter(
            number=memory_info.free, unit=unit, use_int=False
        )

    if memory_info.shared >= 0:
        tooltip_od["Shared"] = util.byte_converter(
            number=memory_info.shared, unit=unit, use_int=False
        )

    if memory_info.buffers >= 0:
        tooltip_od["Buffers"] = util.byte_converter(
            number=memory_info.buffers, unit=unit, use_int=False
        )

    if memory_info.cached >= 0:
        tooltip_od["Cached"] = util.byte_converter(
            number=memory_info.cached, unit=unit, use_int=False
        )

    if memory_info.available >= 0:
        tooltip_od["Available"] = util.byte_converter(
            number=memory_info.available, unit=unit, use_int=False
        )

    max_key_length = 0
    for key in tooltip_od.keys():
        max_key_length = len(key) if len(key) > max_key_length else max_key_length

    for key, value in tooltip_od.items():
        tooltip.append(f"  {key:{max_key_length}} : {value}")

    if len(tooltip) > 0:
        tooltip.append("")

    tooltip.append("Swap")
    tooltip_od = OrderedDict()
    if memory_info.swap_total >= 0:
        tooltip_od["Total"] = util.byte_converter(
            number=memory_info.swap_total, unit=unit, use_int=False
        )

    if memory_info.swap_used >= 0:
        tooltip_od["Used"] = util.byte_converter(
            number=memory_info.swap_used, unit=unit, use_int=False
        )

    if memory_info.swap_free >= 0:
        tooltip_od["Free"] = util.byte_converter(
            number=memory_info.swap_free, unit=unit, use_int=False
        )

    max_key_length = 0
    for key in tooltip_od.keys():
        max_key_length = len(key) if len(key) > max_key_length else max_key_length

    for key, value in tooltip_od.items():
        tooltip.append(f"  {key:{max_key_length}} : {value}")

    if len(tooltip) > 0:
        tooltip.append("")

    if memory_info.dimms and type(memory_info.dimms) is list:
        for idx, dimm in enumerate(memory_info.dimms):
            if (
                dimm.values.size_raw
                and dimm.type
                and dimm.values.form_factor
                and dimm.values.speed
            ):
                tooltip.append(
                    f"DIMM {idx:02d} - {util.byte_converter(number=dimm.values.size_raw, unit=unit, use_int=False)} {dimm.type} {dimm.values.form_factor} @ {dimm.values.speed}"
                )

    if len(tooltip) > 0:
        tooltip.append("")
        tooltip.append(f"Last updated {memory_info.updated}")

    return "\n".join(tooltip)


def get_dimm_info() -> list[memory_usage.DimmInfo]:
    dimms: list[memory_usage.DimmInfo] = []
    command = "sudo dmidecode -t memory | jc --dmidecode"
    rc, stdout_raw, _ = util.run_piped_command(command)

    stdout = stdout_raw if isinstance(stdout_raw, str) else ""
    if rc == 0 and stdout != "":
        json_data = cast(list[dict[str, object]], json.loads(stdout))
        for device in json_data:
            if device["description"] == "Memory Device":
                dimm = from_dict(
                    data_class=memory_usage.DimmInfo,
                    data=device,
                    config=Config(cast=[int, str]),
                )
                match = re.search(r"(\d+)\s+([MmGg][Bb])$", dimm.values.size)
                if match:
                    raw = int(match.group(1))
                    if match.group(2).upper() == "MB":
                        dimm.values.size_raw = int(raw * (1000**2))
                    elif match.group(2).upper() == "GB":
                        dimm.values.size_raw = int(raw * (1000**3))

                dimms.append(dimm)

    return dimms


def get_memory_usage() -> memory_usage.MemoryInfo:
    memory_info: memory_usage.MemoryInfo = memory_usage.MemoryInfo()
    command = "cat /proc/meminfo | jc --pretty --proc-meminfo"
    rc, stdout_raw, stderr_raw = util.run_piped_command(command)

    stdout = stdout_raw if isinstance(stdout_raw, str) else ""
    stderr = stderr_raw if isinstance(stderr_raw, str) else ""
    if rc == 0 and stdout != "":
        json_data = cast(dict[str, int], json.loads(stdout))
        available = json_data.get("Available", 0) * 1024
        buffers = json_data.get("Buffers", 0) * 1024
        cached = json_data.get("Cached", 0) * 1024
        free = json_data.get("MemFree", 0) * 1024
        s_reclaimable = json_data.get("SReclaimable", 0) * 1024
        shared = json_data.get("Shmem", 0) * 1024
        total = json_data.get("MemTotal", 0) * 1024
        used = total - free - buffers - cached - s_reclaimable
        pct_total = 100
        pct_used = int(((total - available) / total) * 100)
        pct_free = pct_total - pct_used

        # Swap
        swap_total = json_data.get("SwapTotal", 0) * 1024
        swap_free = json_data.get("SwapFree", 0) * 1024
        swap_used = swap_total - swap_free
        swap_pct_total = 100
        swap_pct_used = int((swap_used / swap_total) * 100)
        swap_pct_free = swap_pct_total - swap_pct_used

        memory_info = memory_usage.MemoryInfo(
            success=True,
            available=available,
            buffers=buffers,
            buffers_cache=buffers + cached + s_reclaimable,
            cached=cached,
            dimms=get_dimm_info(),
            free=free,
            pct_free=pct_free,
            pct_total=pct_total,
            pct_used=pct_used,
            shared=shared,
            total=total,
            used=used,
            swap_total=swap_total,
            swap_free=swap_free,
            swap_used=swap_total - swap_free,
            swap_pct_total=swap_pct_total,
            swap_pct_used=swap_pct_used,
            swap_pct_free=swap_pct_free,
            updated=util.get_human_timestamp(),
        )
    else:
        memory_info = memory_usage.MemoryInfo(
            success=False,
            error=stderr or f'failed to execute "{command}"',
        )

    return memory_info


@click.command(
    help="Get memory usage from /proc/meminfo and dmidecode(8)",
    context_settings=context_settings,
)
@click.option(
    "-u",
    "--unit",
    required=False,
    type=click.Choice(util.get_valid_units()),
    help="The unit to use for output display",
)
def main(unit: str):
    output: dict[str, object] = {}
    output_class: str = ""
    memory_info = get_memory_usage()

    if memory_info.success:
        tooltip = generate_tooltip(memory_info)
        pct_free = memory_info.pct_free
        total = util.byte_converter(number=memory_info.total, unit=unit, use_int=False)
        used = util.byte_converter(number=memory_info.used, unit=unit, use_int=False)

        if pct_free < 20:
            output_class = "critical"
        elif pct_free >= 20 and pct_free < 50:
            output_class = "warning"
        elif pct_free >= 50:
            output_class = "good"

        output = {
            "text": f"{glyphs.md_memory}{glyphs.icon_spacer}{used} / {total}",
            "class": output_class,
            "tooltip": tooltip,
        }
    else:
        output = {
            "text": f"{glyphs.md_memory}{glyphs.icon_spacer}{memory_info.error if memory_info.error is not None else 'Unknown error'}",
            "class": "error",
            "tooltip": "System Memory",
        }

    print(json.dumps(output))


if __name__ == "__main__":
    main()
