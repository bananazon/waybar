import getpass
import json
import os
import re
import shlex
import shutil
import socket
import subprocess
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import cast

import psutil
from dacite import Config, from_dict

from . import glyphs, http


@dataclass
class LocationData:
    city: str | None = None
    country: str | None = None
    hostname: str | None = None
    ip: str | None = None
    loc: str | None = None
    org: str | None = None
    postal: str | None = None
    readme: str | None = None
    region: str | None = None
    timezone: str | None = None


def run_piped_command(
    command: str = "", background: bool = False
) -> (
    tuple[int, str, str]
    | list[subprocess.Popen[bytes]]
    | tuple[int, None, FileNotFoundError]
):
    """
    Run a shell-like command with pipes using subprocess.

    Args:
        command (str): The pipeline command, e.g. "echo hi | grep h".
        background (bool): If True, run in background (detached).

    Returns:
        - If background=False: (return_code, stdout, stderr)
        - If background=True : list of Popen objects (pipeline)
    """
    # Split pipeline into stages
    parts = [shlex.split(cmd.strip()) for cmd in command.split("|")]
    processes: list[subprocess.Popen[bytes]] = []
    prev_stdout = None

    for i, part in enumerate(parts):
        try:
            proc = subprocess.Popen(
                part,
                stdin=prev_stdout,
                stdout=subprocess.PIPE if not background else subprocess.DEVNULL,
                stderr=subprocess.PIPE
                if not background and i == len(parts) - 1
                else subprocess.DEVNULL,
                preexec_fn=os.setpgrp if background else None,
            )

            if prev_stdout:
                prev_stdout.close()
            prev_stdout = proc.stdout
            processes.append(proc)
        except FileNotFoundError as e:
            return 1, None, e

    if background:
        # Don't wait; return process list so caller can manage if needed
        return processes

    # Foreground (blocking) mode
    stdout, stderr = processes[-1].communicate()
    for p in processes[:-1]:
        _ = p.wait()

    return processes[-1].returncode, stdout.decode().strip(), stderr.decode().strip()


def get_valid_units() -> list[str]:
    """
    Return a list of valid storage units
    """
    return [
        "K",
        "Ki",
        "M",
        "Mi",
        "G",
        "Gi",
        "T",
        "Ti",
        "P",
        "Pi",
        "E",
        "Ei",
        "Z",
        "Zi",
        "auto",
    ]


def error_exit(icon: str, message: str):
    print(
        json.dumps(
            {
                "text": f"{icon} {message}",
                "class": "error",
            }
        )
    )


def get_cache_directory() -> Path:
    xdg_cache = os.environ.get("XDG_CACHE_HOME")
    if xdg_cache:
        cache_dir = Path(xdg_cache) / "waybar"
    else:
        cache_dir = Path.home() / ".cache/waybar"

    if not os.path.exists(cache_dir):
        try:
            os.mkdir(cache_dir, mode=0o700)
        except Exception:
            error_exit(icon=glyphs.md_alert, message=f'Couldn\'t create "{cache_dir}"')

    return cache_dir


def str_hook(v: str | None):
    if v is None:
        return None
    return str(v)


def int_hook(v: int | None):
    if v is None:
        return 0  # or None if your field is Optional[int]
    return int(v)


def get_human_timestamp() -> str:
    now = int(time.time())
    dt = datetime.fromtimestamp(now)
    return dt.strftime("%Y-%m-%d %H:%M:%S")


def byte_converter(number: float, unit: str | None, use_int: bool) -> str:
    """
    Convert bytes to the given unit.
    """
    if unit is None:
        unit = "auto"
    suffix = "B"

    if unit == "auto":
        for unit_prefix in ["", "Ki", "Mi", "Gi", "Ti", "Pi", "Ei", "Zi", "Yi"]:
            if abs(number) < 1024.0:
                return (
                    f"{pad_float(number=number, round_int=False)} {unit_prefix}{suffix}"
                )
            number /= 1024
        return f"{pad_float(number=number, round_int=False)} Yi{suffix}"
    else:
        divisor: int = 1000
        if len(unit) == 2 and unit.endswith("i"):
            divisor = 1024

        prefix_map: dict[str, int] = {
            "K": 1,
            "Ki": 1,
            "M": 2,
            "Mi": 2,
            "G": 3,
            "Gi": 3,
            "T": 4,
            "Ti": 4,
            "P": 5,
            "Pi": 5,
            "E": 6,
            "Ei": 6,
            "Z": 7,
            "Zi": 7,
            "Y": 8,
            "Yi": 8,
        }

        if unit in prefix_map:
            power: int = prefix_map[unit]
            value = cast(float, number / (divisor**power))
            if use_int:
                return f"{int(value)} {unit}{suffix}"
            else:
                return f"{pad_float(value, round_int=False)} {unit}{suffix}"
        else:
            return f"{number} {suffix}"


def pad_float(number: float | str, round_int: bool) -> str:
    """
    Pad a float to two decimal places.
    """
    if type(number) is str:
        number = float(number)

    if isinstance(number, int) and round_int:
        return str(int(number))
    else:
        return f"{number:.2f}"


def processor_speed(number: float) -> str | None:
    """
    Intelligently determine processor speed
    """
    suffix = "Hz"

    for unit in ["", "K", "M", "G", "T"]:
        if abs(number) < 1000.0:
            return f"{pad_float(number=number, round_int=False)} {unit}{suffix}"
        number = number / 1000


def to_unix_time(input: str | None) -> int:
    if input:
        pattern = r"^(0[1-9]|1[0-2]):[0-5][0-9] (AM|PM)$"
        if re.match(pattern, input):
            try:
                # Parse as 12-hour format
                dt = datetime.strptime(input, "%I:%M %p")

                # Replace today's date with the parsed time
                now = datetime.now()
                dt = dt.replace(year=now.year, month=now.month, day=now.day)

                # Convert to Unix timestamp (local time)
                return int(time.mktime(dt.timetuple()))
            except Exception:
                return 0
        else:
            return 0
    return 0


def to_24hour_time(input: int) -> str | None:
    try:
        # Convert to datetime (local time)
        dt = datetime.fromtimestamp(input)

        # Format as 24-hour time (HH:MM)
        return dt.strftime("%H:%M")
    except Exception:
        return None


def waybar_is_running() -> dict[str, str | list[str] | int | None] | None:
    for proc in psutil.process_iter(
        attrs=["cmdline", "create_time", "name", "pid", "ppid", "username"]
    ):
        try:
            if proc.info.get("cmdline") is not None:
                cmdline = cast(list[str], proc.info["cmdline"])
                cmd = " ".join(cmdline)
                if cmd == "waybar" and proc.info.get("username") == getpass.getuser():
                    created = cast(int, proc.info.get("create_time"))
                    return {
                        "cmd": cmd,
                        "cmdline": cmdline or [],
                        "created": created,
                        "pid": proc.info.get("pid"),
                        "ppid": proc.info.get("ppid"),
                        "username": proc.info.get("username"),
                    }
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return None


def network_is_reachable():
    host = "8.8.8.8"
    port = 53
    timeout = 3
    try:
        socket.setdefaulttimeout(timeout)
        with socket.create_connection((host, port)):
            return True
    except OSError:
        return False


def ip_to_location(ip: str) -> LocationData | None:
    location_data: LocationData = LocationData()
    response = http.request(
        method="GET",
        url=f"https://ipinfo.io/{ip}/json",
        params={},
    )
    if response and response.status == 200 and response.body:
        json_data = cast(dict[str, str], json.loads(response.body))
        location_data = from_dict(
            data_class=LocationData, data=json_data, config=Config(cast=[str])
        )
        return location_data
    return None


def network_speed(number: float, bytes: bool) -> str | None:
    """
    Intelligently determine network speed
    """
    # test this with dummy numbers
    suffix = "iB/s" if bytes else "bit/s"

    for unit in ["", "K", "M", "G", "T", "P"]:
        if abs(number) < 1024.0:
            if bytes:
                return f"{pad_float(number=number / 8, round_int=False)} {unit}{suffix}"
            return f"{pad_float(number=number, round_int=False)} {unit}{suffix}"
        number = number / 1024


def get_config_directory() -> str:
    return os.path.join(
        Path.home(),
        ".config",
        "waybar",
    )


def get_script_directory() -> str:
    return os.path.join(
        get_config_directory(),
        "scripts",
    )


def which(binary_name: str) -> str | None:
    return shutil.which(binary_name)


def duration(seconds: int = 0) -> tuple[int, int, int, int]:
    seconds = int(seconds)
    days = int(seconds / 86400)
    hours = int(((seconds - (days * 86400)) / 3600))
    minutes = int(((seconds - days * 86400 - hours * 3600) / 60))
    secs = int((seconds - (days * 86400) - (hours * 3600) - (minutes * 60)))

    return days, hours, minutes, secs


def get_duration(seconds: int = 0) -> str:
    d, h, m, s = duration(seconds)
    if d > 0:
        return f"{d:02d}d {h:02d}h {m:02d}m {s:02d}s"
    else:
        return f"{h:02d}h {m:02d}m {s:02d}s"


def interface_exists(interface: str) -> bool:
    try:
        return os.path.isdir(f"/sys/class/net/{interface}")
    except Exception:
        return False


def interface_is_connected(interface: str) -> bool:
    try:
        with open(f"/sys/class/net/{interface}/carrier", "r") as f:
            contents = f.read()
        return True if int(contents) == 1 else False
    except Exception:
        return False


def find_public_ip() -> str | None:
    headers = {"User-Agent": "curl/7.54.1"}
    response = http.request(method="GET", url="https://ifconfig.io", headers=headers)
    if response and response.status == 200 and response.body:
        return response.body

    return None


def find_private_ip_and_mac(interface: str) -> tuple[str, str]:
    ip: str = ""
    mac: str = ""
    command = f"ip -4 addr show dev {interface}"
    rc, stdout_raw, _ = run_piped_command(command)

    stdout = stdout_raw if isinstance(stdout_raw, str) else ""
    if rc == 0 and stdout != "":
        match = re.search(r"inet\s+(\d+\.\d+\.\d+\.\d+)", stdout)
        if match:
            ip = match.group(1)

    command = f"ip -4 link show dev {interface}"
    rc, stdout_raw, _ = run_piped_command(command)
    stdout = stdout_raw if isinstance(stdout_raw, str) else ""
    if rc == 0 and stdout != "":
        match = re.search(r"ether\s+([a-z0-9:]+)", stdout)
        if match:
            mac = match.group(1)

    return ip, mac


def get_distro_icon() -> str:
    command = "cat /etc/os-release | jc --pretty --os-release"
    rc, stdout_raw, _ = run_piped_command(command)

    stdout = stdout_raw if isinstance(stdout_raw, str) else ""

    if rc == 0 and stdout:
        json_data = cast(dict[str, str], json.loads(stdout))
        if "ID" in json_data:
            distro_id = json_data["ID"]
            if distro_id in glyphs.distro_map:
                return glyphs.distro_map[distro_id]

    return glyphs.md_linux
