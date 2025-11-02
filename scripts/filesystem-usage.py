#!/usr/bin/env python3

from collections import OrderedDict
from dacite import from_dict, Config
from dataclasses import dataclass, field
from pathlib import Path
from typing import cast
from waybar import glyphs, util
import click
import json
import logging
import signal
import sys
import threading
import time

sys.stdout.reconfigure(line_buffering=True)


@dataclass
class DFEntry:
    available: int = 0
    blocks: int = 0
    filesystem: str = ""
    free: int = 0
    free_percent: int = 0
    mounted_on: str | None = None
    use_percent: int = 0
    used: int = 0


@dataclass
class KvOptions:
    discard: str | None = None
    space_cache: str | None = None
    subvolid: str | None = None
    subvol: str | None = None


@dataclass
class FindMount:
    target: str | None = None
    source: str | None = None
    fstype: str | None = None
    options: list[str] = field(default_factory=list)
    kv_options: KvOptions = field(default_factory=KvOptions)


@dataclass
class DiskStatsSample:
    device: str | None = None
    discarding_time_ms: int = 0
    discards_completed_successfully: int = 0
    discards_merged: int = 0
    flush_requests_completed_successfully: int = 0
    flushing_time_ms: int = 0
    io_in_progress: int = 0
    io_time_ms: int = 0
    maj: int = 0
    min: int = 0
    read_time_ms: int = 0
    reads_completed: int = 0
    reads_merged: int = 0
    sectors_discarded: int = 0
    sectors_read: int = 0
    sectors_written: int = 0
    weighted_io_time_ms: int = 0
    write_time_ms: int = 0
    writes_completed: int = 0
    writes_merged: int = 0


@dataclass
class BlockDevice:
    alignment: int = 0
    dax: bool = False
    disc_aln: int = 0
    disc_gran: str | None = None
    disc_max: str | None = None
    disc_zero: bool = False
    disk_seq: int = 0
    fsavail: str | None = None
    fsroots: list[str] = field(default_factory=list)
    fssize: str | None = None
    fstype: str | None = None
    fsuse_pct: str | None = None
    fsused: str | None = None
    fsver: str | None = None
    group: str | None = None
    hctl: str | None = None
    hotplug: bool = False
    id: str | None = None
    id_link: str | None = None
    kname: str | None = None
    label: str | None = None
    log_sec: int = 0
    maj: str | None = None
    maj_min: str | None = None
    min: str | None = None
    min_io: int = 0
    mode: str | None = None
    model: str | None = None
    mountpoint: str | None = None
    mountpoints: list[str] = field(default_factory=list)
    mq: str | None = None
    name: str | None = None
    opt_io: int = 0
    owner: str | None = None
    partflags: str | None = None
    partlabel: str | None = None
    partn: int = 0
    parttype: str | None = None
    parttypename: str | None = None
    partuuid: str | None = None
    path: str | None = None
    phy_sec: int = 0
    pkname: str | None = None
    pttype: str | None = None
    ptuuid: str | None = None
    ra: int = 0
    rand: bool = False
    rev: str | None = None
    rm: bool = False
    ro: bool = False
    rota: bool = False
    rq_size: int = 0
    sched: str | None = None
    serial: str | None = None
    size: str | None = None
    start: int = 0
    state: str | None = None
    subsystems: str | None = None
    tran: str | None = None
    type: str | None = None
    uuid: str | None = None
    vendor: str | None = None
    wsame: str | None = None
    wwn: str | None = None
    zone_amax: int = 0
    zone_app: str | None = None
    zone_nr: int = 0
    zone_omax: int = 0
    zone_sz: str | None = None
    zone_wgran: str | None = None
    zoned: str | None = None


@dataclass
class FilesystemInfo:
    success: bool = False
    error: str | None = None
    filesystem: str | None = None
    free: int = 0
    fsopts: str | None = None
    fstype: str | None = None
    lsblk: BlockDevice = field(default_factory=BlockDevice)
    mountpoint: str | None = None
    pct_free: int = 0
    pct_total: int = 0
    pct_used: int = 0
    total: int = 0
    used: int = 0
    sample1: DiskStatsSample = field(default_factory=DiskStatsSample)
    sample2: DiskStatsSample = field(default_factory=DiskStatsSample)
    updated: str | None = None


cache_dir = util.get_cache_directory()
condition = threading.Condition()
context_settings = dict(help_option_names=["-h", "--help"])
disk_info: list[FilesystemInfo] | None = []
format_index: int = 0
logfile: Path = cache_dir / "waybar-filesystem-usage.log"
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
    if disk_info and type(disk_info) is list:
        mountpoint = disk_info[format_index].mountpoint
    else:
        mountpoint = format_index + 1
    logging.info(
        f"[toggle_format] - received SIGUSR1 - switching output format to {mountpoint}"
    )
    with condition:
        needs_redraw = True
        condition.notify()


_ = signal.signal(signal.SIGHUP, refresh_handler)
_ = signal.signal(signal.SIGUSR1, toggle_format)


def generate_tooltip(disk_info: FilesystemInfo, show_stats: bool) -> str:
    logging.debug(
        f"[generate_tooltip] - entering with mountpoint={disk_info.mountpoint}"
    )
    tooltip: list[str] = []
    tooltip_od: OrderedDict[str, str | int] = OrderedDict()

    if disk_info.filesystem:
        tooltip_od["Filesystem"] = disk_info.filesystem

    if disk_info.mountpoint:
        tooltip_od["Mountpoint"] = disk_info.mountpoint

    if disk_info.fstype:
        tooltip_od["Type"] = disk_info.fstype

    if disk_info.lsblk:
        if disk_info.lsblk.kname:
            tooltip_od["Kernel Name"] = disk_info.lsblk.kname

        if disk_info.lsblk.rm in [True, False]:
            tooltip_od["Removable"] = "yes" if disk_info.lsblk.rm else "no"

        if disk_info.lsblk.ro in [True, False]:
            tooltip_od["Read-only"] = "yes" if disk_info.lsblk.ro else "no"

    if show_stats and (disk_info.sample1 and disk_info.sample2):
        tooltip_od["Reads/sec"] = (
            disk_info.sample2.reads_completed - disk_info.sample1.reads_completed
        )
        tooltip_od["Writes/sec"] = (
            disk_info.sample2.writes_completed - disk_info.sample1.writes_completed
        )
        tooltip_od["Read Time/sec"] = (
            disk_info.sample2.read_time_ms - disk_info.sample1.read_time_ms
        )
        tooltip_od["Write Time/sec"] = (
            disk_info.sample2.write_time_ms - disk_info.sample1.write_time_ms
        )

    max_key_length = 0
    for key in tooltip_od.keys():
        max_key_length = len(key) if len(key) > max_key_length else max_key_length

    for key, value in tooltip_od.items():
        tooltip.append(f"{key:{max_key_length}} : {value}")

    if len(tooltip) > 0:
        tooltip.append("")
        tooltip.append(f"Last updated {disk_info.updated}")

    return "\n".join(tooltip)


def filesystem_exists(mountpoint: str) -> bool:
    command = f"jc findmnt {mountpoint}"
    rc, _, _ = util.run_piped_command(command)
    return True if rc == 0 else False


def get_sample() -> list[DiskStatsSample]:
    logging.debug("[get_sample] - entering function")
    sample: list[DiskStatsSample] = []
    command = "cat /proc/diskstats | jc --pretty --proc-diskstats"
    rc, stdout_raw, _ = util.run_piped_command(command)

    stdout = stdout_raw if isinstance(stdout_raw, str) else ""

    if rc == 0 and stdout != "":
        json_data = cast(list[dict[str, object]], json.loads(stdout))
        for device in json_data:
            entry = from_dict(
                data_class=DiskStatsSample, data=device, config=Config(cast=[int, str])
            )
            sample.append(entry)

    return sample


def parse_lsblk(filesystem: str) -> BlockDevice:
    logging.debug(f"[parse_lsblk] - entering with filesystem={filesystem}")
    mapping: dict[str, str] = {
        "id-link": "id_link",
        "disc-aln": "disc_aln",
        "dik-seq": "disk_seq",
        "disc-gran": "disc_gran",
        "disc-max": "disc_max",
        "fsuse%": "fsuse_pct",
        "maj:min": "maj_min",
        "min-io": "min_io",
        "opt-io": "opt_io",
        "rq-size": "rq_size",
        "zone-sz": "zone_sz",
        "zone-wgran": "zone_wgran",
        "zone-app": "zone_app",
    }

    block_device: BlockDevice = BlockDevice()
    command = f"lsblk -O --json {filesystem}"
    rc, stdout_raw, _ = util.run_piped_command(command)

    stdout = stdout_raw if isinstance(stdout_raw, str) else ""
    if rc == 0 and stdout != "":
        json_data = cast(dict[str, list[dict[str, object]]], json.loads(stdout))
        bd = json_data["blockdevices"][0]
        for bad, good in mapping.items():
            if bad in bd:
                bd[good] = bd.pop(bad)

        block_device = from_dict(
            data_class=BlockDevice,
            data=bd,
            config=Config(
                cast=[int, float],
                type_hooks={str: util.str_hook, int: util.int_hook},
                strict=False,
            ),
        )
        return block_device

    return BlockDevice()


def get_disk_usage(mountpoints: list[str], show_stats: bool) -> list[FilesystemInfo]:
    logging.debug(f"[get_disk_usage] - entering with mountpoints={mountpoints}")
    disk_usage: list[FilesystemInfo] = []
    first: DiskStatsSample = DiskStatsSample()
    first_sample: list[DiskStatsSample] = []
    second: DiskStatsSample = DiskStatsSample()
    second_sample: list[DiskStatsSample] = []

    if show_stats:
        first_sample = get_sample()
        time.sleep(1)
        second_sample = get_sample()

    for mountpoint in mountpoints:
        stdout: str = ""
        stderr: str = ""

        if filesystem_exists(mountpoint=mountpoint):
            command = f"jc --pretty df {mountpoint}"
            try:
                rc, stdout_raw, stderr_raw = util.run_piped_command(command)

                stdout = stdout_raw if isinstance(stdout_raw, str) else ""
                stderr = stderr_raw if isinstance(stderr_raw, str) else ""
                if rc == 0 and stdout != "":
                    mapping: dict[str, str] = {"1k_blocks": "blocks"}
                    json_data = cast(list[dict[str, object]], json.loads(stdout))
                    item = json_data[0]
                    for bad, good in mapping.items():
                        if bad in item:
                            item[good] = item.pop(bad)

                    df_item = from_dict(
                        data_class=DFEntry,
                        data=item,
                        config=Config(
                            cast=[int, float],
                            type_hooks={str: util.str_hook, int: util.int_hook},
                            strict=False,
                        ),
                    )
                else:
                    error_item = FilesystemInfo(
                        success=False,
                        error=stderr or f"failed to execute {command}",
                    )
                    disk_usage.append(error_item)
                    return disk_usage
            except Exception as e:
                error_item = FilesystemInfo(
                    success=False,
                    error=stderr or f"failed to execute {command}: {e}",
                )
                disk_usage.append(error_item)
                return disk_usage

            if df_item:
                command = f"jc --pretty findmnt {mountpoint}"
                try:
                    rc, stdout_raw, stderr_raw = util.run_piped_command(command)

                    stdout = stdout_raw if isinstance(stdout_raw, str) else ""
                    stderr = stderr_raw if isinstance(stderr_raw, str) else ""
                    if rc == 0 and stdout != "":
                        json_data = cast(list[dict[str, object]], json.loads(stdout))
                        item = json_data[0]
                        findmnt_item = from_dict(
                            data_class=FindMount,
                            data=item,
                            config=Config(
                                cast=[int, float, dict],
                                type_hooks={str: util.str_hook, int: util.int_hook},
                                strict=False,
                            ),
                        )
                    else:
                        error_item = FilesystemInfo(
                            success=False,
                            error=stderr or f"failed to execute {command}",
                        )
                        disk_usage.append(error_item)
                        return disk_usage
                except Exception as e:
                    error_item = FilesystemInfo(
                        success=False,
                        error=stderr or f"failed to execute {command}: {e}",
                    )
                    disk_usage.append(error_item)
                    return disk_usage

                lsblk_data = parse_lsblk(filesystem=df_item.filesystem)
                if lsblk_data and show_stats:
                    first = [
                        entry
                        for entry in first_sample
                        if entry.device == lsblk_data.kname
                    ][0]

                    second = [
                        entry
                        for entry in second_sample
                        if entry.device == lsblk_data.kname
                    ][0]

                if df_item and findmnt_item:
                    disk_usage.append(
                        FilesystemInfo(
                            success=True,
                            filesystem=df_item.filesystem,
                            mountpoint=mountpoint,
                            total=df_item.blocks * 1024,
                            used=df_item.used * 1024,
                            free=df_item.free * 1024,
                            pct_total=100,
                            pct_used=df_item.use_percent,
                            pct_free=100 - df_item.use_percent,
                            fsopts=",".join(findmnt_item.options or []),
                            fstype=findmnt_item.fstype,
                            lsblk=lsblk_data,
                            sample1=first,
                            sample2=second,
                            updated=util.get_human_timestamp(),
                        )
                    )
            else:
                disk_usage.append(
                    FilesystemInfo(
                        success=False,
                        error="failed to find the data",
                        mountpoint=mountpoint,
                    )
                )
        else:
            disk_usage.append(
                FilesystemInfo(
                    success=False,
                    error="doesn't exist",
                    mountpoint=mountpoint,
                )
            )

    return disk_usage


def render_output(
    disk_info: FilesystemInfo, unit: str, icon: str, show_stats: bool
) -> tuple[str, str, str]:
    if disk_info.success:
        pct_free = disk_info.pct_free
        total = util.byte_converter(number=disk_info.total, unit=unit, use_int=False)
        used = util.byte_converter(number=disk_info.used, unit=unit, use_int=False)

        if pct_free < 20:
            output_class = "critical"
        elif pct_free < 50:
            output_class = "warning"
        else:
            output_class = "good"

        text = f"{icon}{glyphs.icon_spacer}{disk_info.mountpoint} {used} / {total}"
        output_class = output_class
        tooltip = generate_tooltip(disk_info=disk_info, show_stats=show_stats)
    else:
        text = f"{glyphs.md_alert}{glyphs.icon_spacer}{disk_info.mountpoint} {disk_info.error}"
        output_class = "error"
        tooltip = f"{disk_info.mountpoint} error"

    return text, output_class, tooltip


def worker(mountpoints: list[str], unit: str, show_stats: bool):
    global disk_info, needs_fetch, needs_redraw, format_index

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
                f"{glyphs.md_timer_outline}{glyphs.icon_spacer}Gathering disk data..."
            )
            loading_dict = {
                "text": loading,
                "class": "loading",
                "tooltip": "Gathering disk data...",
            }

            if disk_info and type(disk_info) is list:
                text, _, tooltip = render_output(
                    disk_info=disk_info[format_index],
                    unit=unit,
                    icon=glyphs.md_timer_outline,
                    show_stats=show_stats,
                )
                print(
                    json.dumps({"text": text, "class": "loading", "tooltip": tooltip})
                )

                disk_info = get_disk_usage(
                    mountpoints=mountpoints, show_stats=show_stats
                )
            else:
                print(json.dumps(loading_dict))

            disk_info = get_disk_usage(mountpoints=mountpoints, show_stats=show_stats)

        if disk_info is None:
            continue

        if disk_info and type(disk_info) is list:
            if redraw:
                text, output_class, tooltip = render_output(
                    disk_info=disk_info[format_index],
                    unit=unit,
                    icon=glyphs.md_harddisk,
                    show_stats=show_stats,
                )
                output = {
                    "text": text,
                    "class": output_class,
                    "tooltip": tooltip,
                }

                print(json.dumps(output))


@click.command(
    help="Get disk informatiopn from df(1)", context_settings=context_settings
)
@click.option(
    "-m", "--mountpoint", required=True, multiple=True, help="The mountpoint to check"
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
    "-s",
    "--show-stats",
    is_flag=True,
    help="Gather disk statistics and display them in the tooltip",
)
@click.option(
    "-i", "--interval", type=int, default=5, help="The update interval (in seconds)"
)
@click.option(
    "-t", "--test", default=False, is_flag=True, help="Print the output and exit"
)
@click.option("-d", "--debug", default=False, is_flag=True, help="Enable debug logging")
def main(
    mountpoint: list[str],
    unit: str,
    show_stats: bool,
    interval: int,
    test: bool,
    debug: bool,
):
    global formats, needs_fetch, needs_redraw

    configure_logging(debug=debug)
    formats = list(range(len(mountpoint)))

    if test:
        disk_info: list[FilesystemInfo] = get_disk_usage(
            mountpoints=mountpoint, show_stats=show_stats
        )

        text, output_class, tooltip = render_output(
            disk_info[0], unit=unit, icon=glyphs.md_harddisk, show_stats=show_stats
        )
        print(text)
        print(output_class)
        print(tooltip)
        return

    logging.info("[main] - entering")

    threading.Thread(
        target=worker, args=(mountpoint, unit, show_stats), daemon=True
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
