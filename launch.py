#!/usr/bin/env python3


import getpass
import logging
import os
import signal
import subprocess
import sys
import time
from typing import cast, override

import click
import psutil

from waybar.util import system

cache_dir = system.get_cache_directory()
context_settings = dict(help_option_names=["-h", "--help"])
logfile = cache_dir / "waybar.log"


class RightPadFormatter(logging.Formatter):
    def __init__(self, levelnames: list[str]):
        self.max_len: int = 0
        self.max_len = max(len(name) for name in levelnames)
        fmt = "[%(levelname)s] %(pad)s%(message)s"
        super().__init__(fmt)

    @override
    def format(self, record: logging.LogRecord):
        # Spaces after the closing bracket
        pad_len = self.max_len - len(record.levelname)
        record.pad = " " * (pad_len + 1)  # +1 for spacing
        return super().format(record)


# ----------------------------
# Common helpers
# ----------------------------
def get_background_scripts() -> list[dict[str, str | list[str] | int | None]]:
    processes: list[dict[str, str | list[str] | int | None]] = []
    for proc in psutil.process_iter(
        attrs=["cmdline", "create_time", "name", "pid", "ppid", "username"]
    ):
        try:
            cmdline = cast(list[str], proc.info["cmdline"])
            cmd_short: str = ""
            if cmdline and len(cmdline) > 0:
                cmd_str = " ".join(cmdline)
                if len(cmdline) > 2:
                    cmd_short = " ".join(cmdline[:2])
                if (
                    cmd_str.startswith("python3")
                    and system.get_script_directory() in cmd_str
                    and proc.info.get("username") == getpass.getuser()
                ):
                    created = cast(int, proc.info.get("create_time"))
                    new_process = {
                        "cmd_short": cmd_short,
                        "created": created or 0,
                        "pid": proc.info.get("pid"),
                        "ppid": proc.info.get("ppid"),
                        "username": proc.info.get("username"),
                    }

                    processes.append(new_process)

        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue

    return processes


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
                        "duration": "",
                    }
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return None


# ----------------------------
# Setup and configuration
# ----------------------------
def configure_logging(debug: bool = False):
    """Set up the logging"""
    all_levels: list[str] = []
    for level in range(10, 50, 10):
        foo = logging.getLevelName(level)
        all_levels.append(foo)

    handler = logging.StreamHandler()
    handler.setFormatter(RightPadFormatter(all_levels))
    logger = logging.getLogger()
    logger.setLevel(logging.DEBUG) if debug else logger.setLevel(logging.INFO)
    logger.addHandler(handler)


def setup(debug: bool = False):
    """Run some quick checks"""
    for binary in ["waybar"]:
        if not system.which(binary):
            logging.error(f"{binary} is not installed")
            sys.exit(1)

    configure_logging(debug=debug)


# ----------------------------
# Start functions
# ----------------------------
def start_waybar() -> None:
    """A simple wrapper for starting waybar"""
    proc = waybar_is_running()
    if proc:
        print(
            f"waybar is running with PID {proc.get('pid')}; please use stop or restart"
        )
        sys.exit(0)

    print("starting waybar")
    # Get the env before starting so we can start via systemctl

    # Here we'll simulate what's done in launch.sh
    # Step 1: Append '---' to the log file
    # echo "---" | tee -a /tmp/waybar.log
    try:
        with open(logfile, "w") as f:
            _ = f.write("---\n")
    except Exception as e:
        logging.error(f"failed to write the log file {logfile}: {e}")
        sys.exit(1)

    # Step 2: Start waybar, redirect output, and run it in the background detached
    # /usr/bin/waybar 2>&1 | tee -a /tmp/waybar.log & disown
    command = [
        "waybar",
        "--log-level",
        "info",
    ]
    try:
        with open(logfile, "a") as f:
            proc = subprocess.Popen(
                command,
                stdout=f,
                stderr=subprocess.STDOUT,
                preexec_fn=os.setpgrp,  # Detach like 'disown'
                shell=True,
            )
            print(f"successfully launched waybar with PID {proc.pid}")
    except Exception as e:
        logging.error(f"failed to launch waybar: {str(e)}")
        sys.exit(1)


# ----------------------------
# Stop functions
# ----------------------------
def stop_waybar(pid: int = 0):
    """A simple wrapper for stopping waybar"""
    proc = waybar_is_running()
    if not proc:
        print("waybar isn't running")
        sys.exit(0)

    waybar_pid: int = cast(int, proc["pid"])
    pid = waybar_pid
    print("stopping waybar")
    try:
        os.kill(pid, signal.SIGTERM)
        for _ in range(5):
            try:
                os.kill(pid, 0)
            except ProcessLookupError:
                break
            time.sleep(1)
        else:
            os.kill(pid, signal.SIGKILL)
    except Exception:
        print("waybar isn't running!")


@click.group(context_settings=context_settings)
def cli():
    pass


@cli.command(name="start", help="Start waybar and its backgound modules")
@click.option("-d", "--debug", is_flag=True, help="Show debug logging")
def start(debug: bool):
    setup(debug=debug)
    start_waybar()


@cli.command(name="stop", help="Stop waybar and its backgound modules")
@click.option("-d", "--debug", is_flag=True, help="Show debug logging")
@click.option("-p", "--pid", help="Specify a pid")
def stop(debug: bool, pid: int):
    setup(debug=debug)
    stop_waybar(pid=pid)


@cli.command(name="restart", help="Restart waybar and its backgound modules")
@click.option("-d", "--debug", is_flag=True, help="Show debug logging")
@click.option("-p", "--pid", help="Specify a pid")
def restart(debug: bool, pid: int):
    setup(debug=debug)
    stop_waybar(pid=pid)
    time.sleep(0.5)
    start_waybar()


@cli.command(name="status", help="Get the status of waybar and its background modules")
@click.option("-d", "--debug", is_flag=True, help="Show debug logging")
def status(debug: bool):
    setup(debug=debug)
    proc = waybar_is_running()

    if proc:
        modules = get_background_scripts()
        message = f"waybar is running with PID {proc['pid']}"
        pids = [
            str(process["pid"]) for process in modules if process.get("pid") is not None
        ]
        if len(pids) > 0:
            message += f" and is managing {len(pids)} background {'module' if len(pids) == 1 else 'modules'}"
        print(message)

        longest_duration = 0
        longest_pid = 0
        now = int(time.time())
        for process in modules:
            created: int = cast(int, process["created"])
            # process["duration"] = waybar_time.get_duration(seconds=(now - created))
            # longest_duration = (
            #     len(process["duration"])
            #     if len(process["duration"]) > longest_duration
            #     else longest_duration
            # )

        for process in modules:
            print(
                f"{process['pid']:{longest_pid}} [{process['duration']:<{longest_duration}}] {process['cmd_short']}"
            )
    else:
        print("waybar isn't running")

    sys.exit(0)


if __name__ == "__main__":
    cli()
