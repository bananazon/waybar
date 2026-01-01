import getpass
import json
import logging
import os
import platform
import re
import shlex
import shutil
import signal
import subprocess
from collections import namedtuple
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Tuple, cast

from waybar import glyphs


class LevelPadFormatter(logging.Formatter):
    LEVEL_WIDTH = len("WARNING")

    def format(self, record):
        level = record.levelname
        pad = " " * (self.LEVEL_WIDTH - len(level))
        record.padded = f"[{level}]{pad}"
        record.unpadded = f"[{level}]"
        return super().format(record)


@dataclass
class Mountpoint:
    device: str = ""
    mountpoint: str = ""
    fstype: str = ""
    opts: list[str] = field(default_factory=list)


def configure_logger(debug: bool, name: str, logfile: Path) -> logging.Logger:
    level = logging.DEBUG if debug else logging.INFO

    logger = logging.getLogger(name)
    logger.setLevel(level)

    # Logs go only to your file
    # No interference from pytest / SwiftBar / root handlers
    # First log line is written immediately
    logger.propagate = False

    # Do not add handlers twice
    if any(isinstance(h, logging.FileHandler) for h in logger.handlers):
        return logger

    handler = logging.FileHandler(logfile, mode="a", encoding="utf-8")
    handler.setLevel(level)
    formatter = LevelPadFormatter(
        # f"%(asctime)s %(padded)s {self.plugin_basename_no_suffix}.%(funcName)s - %(message)s"
        f"%(asctime)s %(unpadded)s {name}.%(funcName)s - %(message)s"
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)

    return logger


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


def parse_version(version_string: str):
    """
    Parse a version string and return a namedtuple containing all of the bits.
    """
    fields = [f"part{i + 1}" for i in range(len(version_string.split(".")))]
    version = namedtuple("version", fields)
    parts = map(int, version_string.split("."))
    return version(*parts)


def get_signal_map() -> dict[str, signal.Signals]:
    """
    Return a dict containing all valid signals.
    """
    return {
        "SIHGUP": signal.SIGHUP,
        "SIGINT": signal.SIGINT,
        "SIGQUIT": signal.SIGQUIT,
        "SIGILL": signal.SIGILL,
        "SIGTRAP": signal.SIGTRAP,
        "SIGABRT": signal.SIGABRT,
        "SIGEMT": signal.SIGEMT,
        "SIGFPE": signal.SIGFPE,
        "SIGKILL": signal.SIGKILL,
        "SIGBUS": signal.SIGBUS,
        "SIGSEGV": signal.SIGSEGV,
        "SIGSYS": signal.SIGSYS,
        "SIGPIPE": signal.SIGPIPE,
        "SIGALRM": signal.SIGALRM,
        "SIGTERM": signal.SIGTERM,
        "SIGURG": signal.SIGURG,
        "SIGSTOP": signal.SIGSTOP,
        "SIGTSTP": signal.SIGTSTP,
        "SIGCONT": signal.SIGCONT,
        "SIGCHLD": signal.SIGCHLD,
        "SIGTTIN": signal.SIGTTIN,
        "SIGTTOU": signal.SIGTTOU,
        "SIGIO": signal.SIGIO,
        "SIGXCPU": signal.SIGXCPU,
        "SIGXFSZ": signal.SIGXFSZ,
        "SIGVTALRM": signal.SIGVTALRM,
        "SIGPROF": signal.SIGPROF,
        "SIGWINCH": signal.SIGWINCH,
        "SIGINFO": signal.SIGINFO,
        "SIGUSR1": signal.SIGUSR1,
        "SIGUSR2": signal.SIGUSR2,
    }


def get_macos_version() -> str:
    """
    Determine the current OS version and return it as the full OS string.
    """
    version_string: str = ""
    os_version = parse_version(platform.mac_ver()[0])
    macos_families = {
        "10.0": "Cheetah",
        "10.1": "Puma",
        "10.2": "Jaguar",
        "10.3": "Panther",
        "10.4": "Tiger",
        "10.5": "Leopard",
        "10.6": "Snow Leopard",
        "10.7": "Lion",
        "10.8": "Mountain Lion",
        "10.9": "Mavericks",
        "10.10": "Yosemite",
        "10.11": "El Capitan",
        "10.12": "Sierra",
        "10.13": "High Sierra",
        "10.14": "Mojave",
        "10.15": "Catalina",
        "11": "Big Sur",
        "12": "Monterey",
        "13": "Ventura",
        "14": "Sonoma",
        "15": "Sequoia",
        "26": "Tacoma",
    }
    if os_version.part1 == 10:
        version_string = f"{os_version.part1}.{os_version.part2}"
    elif os_version.part1 > 10:
        version_string = f"{os_version.part1}"
    return (
        f"macOS {macos_families[version_string]} {os_version.part1}.{os_version.part2}"
    )


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


# Need to combine with run_piped_command
def execute_command(command: str, input: Any) -> tuple[int, str, str]:
    """
    Execute a system command, returning exit code, stdout, and stderr.
    """
    rc: int = 0
    stdout: str | bytes = ""
    stderr: str | bytes = ""
    for command in re.split(r"\s*\|\s*", command):
        p = subprocess.Popen(
            command,
            shell=True,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        stdout, stderr = p.communicate(input=input.encode("utf-8") if input else None)
        stdout = stdout.decode("utf-8").strip()
        stderr = stderr.decode("utf-8").strip()
        if stdout:
            input = stdout
        rc = p.returncode
    return rc, stdout, stderr


def get_sysctl(metric: str) -> str | None:
    """
    Execute sysctl via execute_command() and return the results or None.
    """
    command = f"sysctl -n {metric}"
    rc, stdout_raw, _ = run_piped_command(command)

    stdout = stdout_raw if isinstance(stdout_raw, str) else ""
    return stdout if rc == 0 else None


def get_theme() -> str:
    # defaults read -g AppleInterfaceStyle
    rc, _, _ = run_piped_command("defaults read -g AppleInterfaceStyle")
    return "dark" if rc == 0 else "light"


def brew_package_installed(package: str) -> bool:
    """
    Check if thes upplied homebrew package is installed.
    """
    returncode, stdout, stderr = run_piped_command(f"brew list {package}")
    return True if returncode == 0 else False


def find_partitions() -> list[Mountpoint]:
    """
    Find and return a list of all valid partitions.
    """
    partitions: list[Mountpoint] = []
    rc, stdout_raw, _ = run_piped_command("mount")

    stdout = stdout_raw if isinstance(stdout_raw, str) else ""
    if rc == 0:
        entries = stdout.split("\n")
        for entry in entries:
            match = re.search(r"^(/dev/disk[s0-9]+)\s+on\s+([^(]+)\s+\((.*)\)", entry)
            if match:
                device = match.group(1)
                mountpoint = match.group(2)
                opts_string = match.group(3)
                opts_list = re.split(r"\s*,\s*", opts_string)
                fstype = opts_list[0]
                opts = opts_list[1:]
                partitions.append(
                    Mountpoint(
                        device=device, mountpoint=mountpoint, fstype=fstype, opts=opts
                    )
                )
    return partitions


def which(binary_name: str) -> str | None:
    return shutil.which(binary_name)


def get_process_icon(
    theme: str, process_owner: str, click_to_kill: bool = False
) -> Tuple[str, str]:
    """
    Return a skull icon if a process can be killed or a no entry sign icon if it cannot.
    """
    if click_to_kill:
        if process_owner == getpass.getuser():
            return (glyphs.fa_skull_crossbones, "")
        else:
            return (
                glyphs.oct_circle_dash,
                "#808080" if theme == "light" else "#C0C0C0",
            )
    else:
        return "", "#808080" if theme == "light" else "#C0C0C0"


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
