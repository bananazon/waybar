#!/usr/bin/env python3

from dacite import from_dict, Config
from dataclasses import dataclass, field
from typing import cast
from waybar import glyphs, util
import click
import json
import platform


@dataclass
class CacheValues:
    associativity: str | None = None
    configuration: str | None = None
    error_correction_type: str | None = None
    install_sram_type: str | None = None
    installed_size: str = ""
    location: str | None = None
    maximum_size: str | None = None
    operational_mode: str | None = None
    socket_designation: str | None = None
    supported_sram_types: list[str] = field(default_factory=list)
    speed: str | None = None
    system_type: str | None = None


@dataclass
class CpuCache:
    handle: str | None = None
    type: int = 0
    bytes: int = 0
    description: str | None = None
    values: CacheValues = field(default_factory=CacheValues)


@dataclass
class CoreInfo:
    tlb_size: str | None = None
    address_sizes: str | None = None
    address_size_physical: str | None = None
    address_size_virtual: str | None = None
    apicid: int = 0
    bogomips: float = 0.0
    bugs: list[str] = field(default_factory=list)
    cache_size: str | None = None
    cache_alignment: int = 0
    cache_size_num: int = 0
    cache_size_unit: str | None = None
    clfush_size: int = 0
    core_id: int = 0
    cpu_cores: int = 0
    cpu_family: int = 0
    cpu_frequency: float = 0.0
    cpuid_level: int = 0
    flags: list[str] = field(default_factory=list)
    fpu: bool = False
    fpu_exception: bool = False
    initial_apicid: int = 0
    microcode: str | None = None
    model_name: str | None = None
    model: int = 0
    physical_id: int = 0
    power_management: str | None = None
    processor: int = 0
    siblings: int = 0
    stepping: int = 0
    vendor_id: str | None = None
    wp: bool = False


@dataclass
class CorePercent:
    cpu: str | None = None
    percent_usr: float = 0.0
    percent_nice: float = 0.0
    percent_sys: float = 0.0
    percent_iowait: float = 0.0
    percent_irq: float = 0.0
    percent_soft: float = 0.0
    percent_steal: float = 0.0
    percent_guest: float = 0.0
    percent_gnice: float = 0.0
    percent_idle: float = 0.0
    type: str | None = None
    timestamp: str | None = None


@dataclass
class CpuInfo:
    success: bool = False
    error: str | None = None
    caches: list[CpuCache] = field(default_factory=list)
    cores_logical: int = 0
    cores_physical: int = 0
    cpu_load: list[CorePercent] = field(default_factory=list)
    freq_cur: float = 0.0
    freq_max: float = 0.0
    freq_min: float = 0.0
    model: str | None = None
    updated: str | None = None


context_settings = dict(help_option_names=["-h", "--help"])
CORE_INFO: list[CoreInfo] = []


def generate_tooltip(cpu_info: CpuInfo) -> str:
    tooltip: list[str] = []

    if cpu_info.model:
        tooltip.append(cpu_info.model)

    if cpu_info.cores_physical and cpu_info.cores_logical:
        pc = cpu_info.cores_physical
        lc = cpu_info.cores_logical
        tpc = int(lc / pc)
        tooltip.append(
            f"Physical cores: {pc}, Threads/core: {tpc}, Logical cores: {lc}"
        )

    if cpu_info.freq_min and cpu_info.freq_max:
        tooltip.append(
            f"Frequency: {util.processor_speed(cpu_info.freq_min)} > {util.processor_speed(cpu_info.freq_max)}"
        )

    if cpu_info.cpu_load and type(cpu_info.cpu_load) is list:
        tooltip.append("CPU Load:")
        for core in cpu_info.cpu_load:
            if core.cpu and core.cpu != "all":
                core_number = int(core.cpu)
                core_freq = CORE_INFO[core_number].cpu_frequency
                tooltip.append(
                    f"  core {int(core.cpu):02} user {util.pad_float(core.percent_usr, False)}%, sys {util.pad_float(core.percent_sys, False)}%, idle {util.pad_float(core.percent_idle, False)}% ({util.processor_speed(core_freq)})"
                )

    if cpu_info.caches and type(cpu_info.caches) is list and len(cpu_info.caches) > 0:
        tooltip.append("Caches:")
        max_key_length = 0
        for cache in cpu_info.caches:
            max_key_length = (
                len(cache.values.installed_size)
                if len(cache.values.installed_size) > max_key_length
                else max_key_length
            )

        for cache in cpu_info.caches:
            if (
                cache.values.socket_designation
                and cache.values.installed_size
                and cache.values.speed
            ):
                tooltip.append(
                    f"  {cache.values.socket_designation} - {cache.values.installed_size:{max_key_length}} @ {cache.values.speed}"
                )

    if len(tooltip) > 0:
        tooltip.append("")
        tooltip.append(f"Last updated {cpu_info.updated}")

    return "\n".join(tooltip)


def get_icon():
    if platform.machine() == "x86":
        return glyphs.md_cpu_32_bit
    elif platform.machine() == "x86_64":
        return glyphs.md_cpu_64_bit
    else:
        return glyphs.oct_cpu


def get_cache_info() -> list[CpuCache]:
    caches: list[CpuCache] = []
    command = "sudo dmidecode -t cache | jc --dmidecode"
    rc, stdout_raw, _ = util.run_piped_command(command)

    stdout = stdout_raw if isinstance(stdout_raw, str) else ""
    if rc == 0 and stdout != "":
        json_data = cast(list[dict[str, object]], json.loads(stdout))
        for item in json_data:
            cache_item = from_dict(
                data_class=CpuCache,
                data=item,
                config=Config(
                    cast=[int, float],
                    type_hooks={str: util.str_hook, int: util.int_hook},
                    strict=False,
                ),
            )
            caches.append(cache_item)

    return caches


def get_cpu_freq() -> tuple[float, float, float]:
    rc, stdout_raw, _ = util.run_piped_command(
        "cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_cur_freq"
    )
    freq_cur_raw = stdout_raw if (rc == 0 and isinstance(stdout_raw, str)) else "-1"

    rc, stdout_raw, _ = util.run_piped_command(
        "cat /sys/devices/system/cpu/cpu0/cpufreq/cpuinfo_min_freq"
    )
    freq_min_raw = stdout_raw if (rc == 0 and isinstance(stdout_raw, str)) else "-1"

    rc, stdout_raw, _ = util.run_piped_command(
        "cat /sys/devices/system/cpu/cpu0/cpufreq/cpuinfo_max_freq"
    )
    freq_max_raw = stdout_raw if (rc == 0 and isinstance(stdout_raw, str)) else "-1"

    return (
        float(freq_cur_raw) * 1000,
        float(freq_min_raw) * 1000,
        float(freq_max_raw) * 1000,
    )


def parse_proc_cpuinfo():
    global CORE_INFO

    mapping: dict[str, str] = {
        "TLB size": "tlb_size",
        "address sizes": "address_sizes",
        "cache size": "cache_size",
        "clflush size": "clflush_size",
        "core id": "core_id",
        "cpu MHz": "cpu_frequency",
        "cpu cores": "cpu_cores",
        "cpu family": "cpu_family",
        "cpuid level": "cpuid_level",
        "initial apicid": "initial_apicid",
        "model name": "model_name",
        "physical id": "physical_id",
        "power management": "power_management",
    }

    command = "jc --pretty /proc/cpuinfo"
    rc, stdout_raw, _ = util.run_piped_command(command)

    stdout = stdout_raw if isinstance(stdout_raw, str) else ""
    if rc == 0 and stdout != "":
        json_data = cast(list[dict[str, object]], json.loads(stdout))
        for core in json_data:
            for bad, good in mapping.items():
                if bad in core:
                    core[good] = core.pop(bad)

            core_item = from_dict(
                data_class=CoreInfo,
                data=core,
                config=Config(
                    cast=[int, float],
                    type_hooks={str: util.str_hook, int: util.int_hook},
                    strict=False,
                ),
            )
            CORE_INFO.append(core_item)


def get_cpu_info() -> CpuInfo:
    global CORE_INFO

    mapping: dict[str, str] = {
        "time": "timestamp",
    }

    cpu_info: CpuInfo = CpuInfo()
    cpu_load: list[CorePercent] = []

    command = "mpstat -A | jc --pretty --mpstat"
    rc, stdout_raw, stderr_raw = util.run_piped_command(command)

    stdout = stdout_raw if isinstance(stdout_raw, str) else ""
    stderr = stderr_raw if isinstance(stderr_raw, str) else ""
    if rc == 0 and stdout != "":
        freq_cur, freq_min, freq_max = get_cpu_freq()
        json_data = cast(list[dict[str, object]], json.loads(stdout))
        for stanza in json_data:
            if stanza["type"] == "cpu" and "cpu" in stanza:
                for bad, good in mapping.items():
                    if bad in stanza:
                        stanza[good] = stanza.pop(bad)

                        core_percent = from_dict(
                            data_class=CorePercent,
                            data=stanza,
                            config=Config(
                                cast=[int, float],
                                type_hooks={str: util.str_hook, int: util.int_hook},
                                strict=False,
                            ),
                        )
                        cpu_load.append(core_percent)

        cpu_info = CpuInfo(
            success=True,
            caches=get_cache_info(),
            cores_logical=len(CORE_INFO) or -1,
            cores_physical=CORE_INFO[0].cpu_cores or -1,
            cpu_load=cpu_load,
            freq_cur=freq_cur,
            freq_min=freq_min,
            freq_max=freq_max,
            model=CORE_INFO[0].model_name or "Unknown",
            updated=util.get_human_timestamp(),
        )
    else:
        cpu_info = CpuInfo(
            success=False,
            error=stderr or f'failed to execute "{command}"',
        )

    return cpu_info


@click.command(
    help="Get CPU usage from using mpstat(1) and /proc/cpuinfo",
    context_settings=context_settings,
)
def main():
    output: dict[str, object] = {}
    parse_proc_cpuinfo()
    cpu_info = get_cpu_info()
    if cpu_info.success:
        for core in cpu_info.cpu_load:
            if core.cpu == "all":
                output = {
                    "text": f"{get_icon()}{glyphs.icon_spacer}user {core.percent_usr}%, sys {core.percent_sys}%, idle {core.percent_idle}%",
                    "tooltip": generate_tooltip(cpu_info),
                    "class": "success",
                }
    else:
        output = {
            "text": f"{get_icon()} {cpu_info.error if cpu_info.error is not None else 'Unknown error'}",
            "tooltip": "CPU error",
            "class": "error",
        }

    print(json.dumps(output))


if __name__ == "__main__":
    main()
