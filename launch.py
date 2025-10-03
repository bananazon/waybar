#!/usr/bin/env python3

from pathlib import Path, PurePosixPath
from scripts.waybar import util
import click
import getpass
import glob
import logging
import os
import psutil
import signal
import subprocess
import sys
import time

cache_dir = util.get_cache_directory()
context_settings = dict(help_option_names=['-h', '--help'])
logfile = cache_dir / f'waybar.log'

class RightPadFormatter(logging.Formatter):
    def __init__(self, levelnames):
        self.max_len = max(len(name) for name in levelnames)
        fmt = '[%(levelname)s] %(pad)s%(message)s'
        super().__init__(fmt)

    def format(self, record):
        # Spaces after the closing bracket
        pad_len = self.max_len - len(record.levelname)
        record.pad = ' ' * (pad_len + 1)  # +1 for spacing
        return super().format(record)

#----------------------------
# Common helpers
#----------------------------
def get_background_scripts(waybar_pid: int=0):
    processes = []
    for proc in psutil.process_iter(attrs=['cmdline', 'create_time', 'name', 'pid', 'ppid', 'username']):
        try:
            if proc.info.get('cmdline') is not None and len(proc.info.get('cmdline')) > 0:
                cmdline = ' '.join(list(proc.info['cmdline']))
                if len(proc.info['cmdline']) > 2:
                    cmd_short = ' '.join(list(proc.info['cmdline'][:2]))
                if cmdline.startswith('python3') and util.get_script_directory() in cmdline and proc.info.get('username') == getpass.getuser():
                    new_process = {
                        'cmd_short': cmd_short,
                        'created'  : int(proc.info.get('create_time')) or 0,
                        'pid'      : proc.info.get('pid'),
                        'ppid'     : proc.info.get('ppid'),
                        'username' : proc.info.get('username'),
                    }

                    processes.append(new_process)

        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue

    return processes

def waybar_is_running():
    for proc in psutil.process_iter(attrs=['cmdline', 'create_time', 'name', 'pid', 'ppid', 'username']):
        try:
            if proc.info.get('cmdline') is not None:
                cmd = ' '.join(list(proc.info['cmdline']))
                if cmd == f'waybar' and proc.info.get('username') == getpass.getuser():
                    return {
                        'cmd'      : cmd,
                        'cmdline'  : list(proc.info.get('cmdline')) or [],
                        'created'  : int(proc.info.get('create_time')),
                        'pid'      : proc.info.get('pid'),
                        'ppid'     : proc.info.get('ppid'),
                        'username' : proc.info.get('username'),
                    }
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return None

#----------------------------
# Setup and configuration
#----------------------------
def configure_logging(debug: bool=False):
    """ Set up the logging """
    all_levels = [logging.getLevelName(lvl) for lvl in range(0, 60) if isinstance(logging.getLevelName(lvl), str)]
    handler = logging.StreamHandler()
    handler.setFormatter(RightPadFormatter(all_levels))
    logger = logging.getLogger()
    logger.setLevel(logging.DEBUG) if debug else logger.setLevel(logging.INFO)
    logger.addHandler(handler)

def setup(debug: bool=False):
    """ Run some quick checks  """
    for binary in ['waybar']:
        if not util.which(binary):
            logging.error(f'{binary} is not installed')
            sys.exit(1)

    configure_logging(debug=debug)

#----------------------------
# Start functions
#----------------------------
def setup_gui_env():
    env = os.environ.copy()

    uid = os.getuid()
    xdg_runtime = f'/run/user/{uid}'

    # Always set XDG_RUNTIME_DIR (critical for Wayland)
    env['XDG_RUNTIME_DIR'] = xdg_runtime

    # Detect session type
    display_server = os.environ.get('XDG_SESSION_TYPE', '').lower()

    if display_server == 'wayland':
        # Prefer existing WAYLAND_DISPLAY, fallback to wayland-0
        wayland_display = os.environ.get('WAYLAND_DISPLAY')
        if not wayland_display:
            wayland_display = 'wayland-0'
        env['WAYLAND_DISPLAY'] = wayland_display

        # DISPLAY may still be needed for XWayland apps (like some GTK apps)
        if 'DISPLAY' not in env:
            env['DISPLAY'] = ':0'

    elif display_server == 'x11':
        # X11 requires DISPLAY and XAUTHORITY
        if 'DISPLAY' not in env:
            env['DISPLAY'] = ':0'

        # Try to set XAUTHORITY
        if 'XAUTHORITY' in env and os.path.exists(env['XAUTHORITY']):
            pass  # Already set and valid
        else:
            # Fallback: ~/.Xauthority
            xauth_path = os.path.expanduser('~/.Xauthority')
            if os.path.exists(xauth_path):
                env['XAUTHORITY'] = xauth_path

    # Ensure DBUS_SESSION_BUS_ADDRESS is set (critical for many GUI apps)
    if 'DBUS_SESSION_BUS_ADDRESS' not in env:
        # Try to get it from the runtime environment
        dbus_address_path = os.path.join(xdg_runtime, 'bus')
        if os.path.exists(dbus_address_path):
            env['DBUS_SESSION_BUS_ADDRESS'] = f'unix:path={dbus_address_path}'

    return env

def start_waybar():
    """ A simple wrapper for starting waybar """
    proc = waybar_is_running()
    if proc:
        print(f'waybar is running with PID {proc.get("pid")}; please use stop or restart')
        sys.exit(0)

    print('starting waybar')
    # Get the env before starting so we can start via systemctl
    env = setup_gui_env()

    # Here we'll simulate what's done in launch.sh
    # Step 1: Append '---' to the log file
    # echo "---" | tee -a /tmp/waybar.log
    try:
        with open(logfile, 'a') as f:
            f.write('---\n')
    except Exception as e:
        logging.error(f'failed to append the log file {logfile}: {e}')
        sys.exit(1)

    # Step 2: Start waybar, redirect output, and run it in the background detached
    # /usr/bin/waybar 2>&1 | tee -a /tmp/waybar.log & disown
    command = [
        'waybar',
        '--log-level',
        'info',
    ]
    try:
        with open(logfile, 'a') as f:
            proc = subprocess.Popen(
                command,
                stdout     = f,
                stderr     = subprocess.STDOUT,
                preexec_fn = os.setpgrp,  # Detach like 'disown'
                shell      = True,
                env        = env,
            )
            print(f'successfully launched waybar with PID {proc.pid}')
            return proc.pid
    except Exception as e:
        logging.error(f'failed to launch waybar: {str(e)}')
        sys.exit(1)

#----------------------------
# Stop functions
#----------------------------
def stop_waybar(pid: str=None):
    """ A simple wrapper for stopping waybar """
    proc = waybar_is_running()
    if not proc:
        print('waybar isn\'t running')
        sys.exit(0)

    pid = proc.get('pid')
    print('stopping waybar')
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
    except:
        print('waybar isn\'t running!')

@click.group(context_settings=context_settings)
def cli():
    pass

@cli.command(name='start', help='Start waybar and its backgound modules')
@click.option('-d', '--debug', is_flag=True, help='Show debug logging')
def start(debug):
    setup(debug=debug)
    start_waybar()

@cli.command(name='stop', help='Stop waybar and its backgound modules')
@click.option('-d', '--debug', is_flag=True, help='Show debug logging')
@click.option('-p', '--pid', help='Specify a pid')
def stop(debug, pid):
    setup(debug=debug)
    stop_waybar(pid=pid)

@cli.command(name='restart', help='Restart waybar and its backgound modules')
@click.option('-d', '--debug', is_flag=True, help='Show debug logging')
@click.option('-p', '--pid', help='Specify a pid')
def restart(debug, pid):
    setup(debug=debug)
    stop_waybar(pid=pid)
    time.sleep(.5)
    start_waybar()

@cli.command(name='status', help='Get the status of waybar and its background modules')
@click.option('-d', '--debug', is_flag=True, help='Show debug logging')
def status(debug):
    setup(debug=debug)
    proc = waybar_is_running()

    if proc:
        modules = get_background_scripts(waybar_pid=proc['pid'])
        message = f'waybar is running with PID {proc["pid"]}'
        pids = [str(process['pid']) for process in modules if process.get('pid') is not None]
        if len(pids) > 0:
            message += f' and is managing {len(pids)} background {"module" if len(pids) == 1 else "modules"}'
        print(message)

        longest_duration = 0
        longest_pid = 0
        now = int(time.time())
        for process in modules:
            process['duration'] = util.get_duration(seconds=(now - process['created']))
            longest_duration = len(process['duration']) if len(process['duration']) > longest_duration else longest_duration

        for process in modules:
            print(f'{process["pid"]:{longest_pid}} [{process["duration"]:<{longest_duration}}] {process["cmd_short"]}')
    else:
        print('waybar isn\'t running')

    sys.exit(0)

if __name__ == '__main__':
    cli()
