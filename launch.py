#!/usr/bin/env python3

from pathlib import Path, PurePosixPath
from pprint import pprint
from scripts.waybar import util
import click
import getpass
import json
import json5
import logging
import os
import psutil
import re
import signal
import subprocess
import sys
import time

# Constants
CONFIG_FILE = Path(PurePosixPath(util.get_config_directory())) / 'config.jsonc'
CONTEXT_SETTINGS = dict(help_option_names=['-h', '--help'])
LOGFILE = Path.home() / f'waybar.log'
STATEFILE = Path.home() / '.waybar-launch-state.json'

# Globals
CONFIG       : dict | None = None
IPC_ENABLED  : bool | None = None
PROCESS_NAME : str  | None = None

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
def get_duration(created: int=0) -> str:
    d, h, m, s = util.duration(int(time.time()) - created)
    if d > 0:
        return f'[{d:02d}d {h:02d}h {m:02d}m {s:02d}s]'
    else:
        return f'[{h:02d}h {m:02d}m {s:02d}s]'

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
                        'modules'  : get_background_scripts(waybar_pid=proc.info.get('pid')),
                        'pid'      : proc.info.get('pid'),
                        'ppid'     : proc.info.get('ppid'),
                        'username' : proc.info.get('username'),
                    }
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return None

def parse_statefile():
    if STATEFILE.exists():
        try:
            return json.loads(STATEFILE.read_text())
        except:
            return None
    return None

def compare_statefile_with_proc(state=None, proc=None):
    if not state:
        state = parse_statefile()
    if not proc:
        proc = waybar_is_running()

    # Hack
    return True

    return (
        state.get('pid') == proc.get('pid') and
        state.get('cmdline') == proc.get('cmdline') and
        state.get('username') == proc.get('username') and
        state.get('created') == proc.get('created')
    )

def show_module_differences(state=None, proc=None):
    if not state:
        state = parse_statefile()
    if not proc:
        proc = waybar_is_running()

    differences = []
    for i, (left, right) in enumerate(zip(state, proc)):
        for k in set(left) | set(right):
            if left.get(k) != right.get(k):
                differences.append({
                    'item'  : json.dumps(left),
                    'state' : left.get(k),
                    'proc'  : right.get(k)
                })

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

def parse_config():
    """ Parse config.jsonc and return it as a dictionary """
    try:
        with open(CONFIG_FILE, 'r') as f:
            config = json5.load(f)
    except Exception as e:
        logging.error(f'failed to parse the config file {CONFIG_FILE}: {e}')
        sys.exit(1)

    return config

def setup(debug: bool=False):
    """ Run some quick checks and return relevant bits """
    global CONFIG, PROCESS_NAME

    for binary in ['waybar']:
        if not util.is_binary_installed(binary):
            logging.error(f'{binary} is not installed')
            sys.exit(1)

    configure_logging(debug=debug)


    PROCESS_NAME = 'waybar'
    CONFIG = parse_config()

#----------------------------
# Start functions
#----------------------------
def start_waybar():
    """ A simple wrapper for starting waybar """
    proc = waybar_is_running()
    if proc:
        print(f'waybar is running with PID {proc.get("pid")}; please use stop or restart')

        state = parse_statefile()
        if not compare_statefile_with_proc(proc=proc, state=state):
            print(f'the statefile doesn\'t align with the current process; rewriting the file')
            write_launch_state(pid=proc.get('pid'))
        sys.exit(0)

    print('starting waybar')
    pid = launch_waybar()
    time.sleep(2)
    write_launch_state(pid=pid)

def launch_waybar():
    """ Attempt to launch waybar """
    # Here we'll simulate what's done in launch.sh
    # Step 1: Append '---' to the log file
    # echo "---" | tee -a /tmp/waybar.log
    try:
        with open(LOGFILE, 'a') as f:
            f.write('---\n')
    except Exception as e:
        logging.error(f'failed to append the log file {LOGFILE}: {e}')
        sys.exit(1)

    # Step 2: Start waybar, redirect output, and run it in the background detached
    # /usr/bin/waybar 2>&1 | tee -a /tmp/waybar.log & disown
    command = [
        'waybar',
        '--log-level',
        'info',
    ]
    try:
        with open(LOGFILE, 'a') as f:
            proc = subprocess.Popen(command,
                stdout     = f,
                stderr     = subprocess.STDOUT,
                preexec_fn = os.setpgrp,  # Detach like 'disown'
                shell      = True,
            )
            print(f'successfully launched waybar with PID {proc.pid}')
            return proc.pid
    except Exception as e:
        logging.error(f'failed to launch waybar: {str(e)}')
        sys.exit(1)

def write_launch_state(pid: int=0):
    try:
        proc = psutil.Process(pid)
        proc_info = proc.as_dict(attrs=['cmdline', 'create_time', 'name', 'pid', 'ppid', 'username'])
    except:
        logging.error(f'hmmmm PID {pid} doesn\'t seem to exist')
        sys.exit(1)

    launch_state = {
        'cmd'      : ' '.join(list(proc_info.get('cmdline'))) or None,
        'cmdline'  : list(proc_info.get('cmdline')) or [],
        'created'  : int(proc_info.get('create_time')),
        'modules'  : get_background_scripts(waybar_pid=proc_info.get('pid')),
        'pid'      : proc_info.get('pid'),
        'ppid'     : proc_info.get('ppid'),
        'username' : proc_info.get('username'),
    }
    STATEFILE.write_text(json.dumps(launch_state, indent=4))

#----------------------------
# Stop functions
#----------------------------
def stop_waybar(pid: str=None):
    """ A simple wrapper for stopping waybar """
    proc = waybar_is_running()
    if not proc:
        print('waybar isn\'t running')
        sys.exit(0)

    print('stopping waybar')
    kill_waybar_if_running(pid=proc.get('pid'))
    time.sleep(.5)

def kill_waybar_if_running(pid: str=None):
    """ Kill waybar if it's running """
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

@click.group(context_settings=CONTEXT_SETTINGS)
def cli():
    pass

@cli.command(name='start', help='Start waybar and its backgound modules')
@click.option('-d', '--debug', is_flag=True, help='Show debug logging')
@click.option('-p', '--pid', help='Specify a pid')
def start(debug, pid):
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
    stop_waybar()
    time.sleep(.5)
    start_waybar()

@cli.command(name='status', help='Get the status of waybar and its background modules')
@click.option('-d', '--debug', is_flag=True, help='Show debug logging')
@click.option('-p', '--pid', help='Specify a pid')
@click.option('--detail', is_flag=True, help='Show detailed information about any running background modules')
def status(debug, pid, detail):
    setup(debug=debug)
    proc = waybar_is_running()
    state = parse_statefile()

    if proc:
        message = f'waybar is running with PID {proc["pid"]}'
        # Rewerite the state file if the two mismatch, eventually compare module differences as well
        if not compare_statefile_with_proc(state=state, proc=proc):
            print(f'the state file "{STATEFILE}" doesn\'t match the current state; rewriting')
            write_launch_state(pid = proc.get('pid'))

        pids = [str(process['pid']) for process in proc.get('modules') if process.get('pid') is not None]
        if len(pids) > 0:
            message += f' and is managing {len(pids)} background {"module" if len(pids) == 1 else "modules"}'
        print(message)

        if detail:
            longest_duration = 0
            longest_pid = 0
            for process in proc.get('modules'):
                process['duration'] = get_duration(created=process['created'])
                longest_duration = len(process['duration']) if len(process['duration']) > longest_duration else longest_duration

            for process in proc.get('modules'):
                print(f'{process["pid"]:{longest_pid}} {process["duration"]:<{longest_duration}} {process["cmd_short"]}')
    else:
        print('waybar isn\'t running')

    sys.exit(0)

@cli.command(name='dummy', help='I am a dummy', hidden=(getpass.getuser() != 'gdanko'))
@click.option('-d', '--debug', is_flag=True, help='Show debug logging')
@click.option('-p', '--pid', help='Specify a pid')
def dummy(debug, pid):
    setup(debug=debug)
    print('i do nothing')
    proc = waybar_is_running()
    if proc:
        util.pprint(get_background_scripts(proc.get('pid')))

if __name__ == '__main__':
    cli()
