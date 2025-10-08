#!/usr/bin/env python3

from pathlib import Path
from typing import Dict, List, NamedTuple, Optional, Tuple, Union
from waybar import glyphs, util
import json
import logging
import os
import re
import signal
import subprocess
import sys
import threading
import time

util.validate_requirements(modules=['click'])
import click

util.validate_requirements(binaries=['jc'])

update_event = threading.Event()
sys.stdout.reconfigure(line_buffering=True)

cache_dir        = util.get_cache_directory()
condition        = threading.Condition()
context_settings = dict(help_option_names=['-h', '--help'])
format_index     = 0
logfile          = cache_dir / f'waybar-software-updates.log'
needs_fetch      = False
needs_redraw     = False
update_data      = None
update_data      = None
valid_types      = ['apk', 'apt', 'brew', 'dnf', 'emerge', 'flatpak', 'mintupdate', 'pacman', 'snap', 'xbps', 'yay', 'yay-aur', 'yum']

formats : list | None=None

class Package(NamedTuple):
    name    : Optional[str]  = None
    version : Optional[str]  = None

class SystemUpdates(NamedTuple):
    success      : Optional[bool] = False
    error        : Optional[str]  = None
    count        : Optional[int]  = 0
    package_type : Optional[str]  = None
    packages     : Optional[List[str]] = None
    updated      : Optional[str]  = None

def configure_logging(debug: bool=False):
    logging.basicConfig(
        filename = logfile,
        filemode = 'w',  # 'a' = append, 'w' = overwrite
        format   = '%(asctime)s [%(levelname)-5s] - %(message)s',
        level    = logging.DEBUG if debug else logging.INFO
    )

def refresh_handler(signum, frame):
    global needs_fetch, needs_redraw
    logging.info(f'[refresh_handler] - received SIGHUP — re-fetching data')
    with condition:
        needs_fetch = True
        needs_redraw = True
        condition.notify()

def toggle_format(signum, frame):
    global formats, format_index, needs_redraw
    format_index = (format_index + 1) % len(formats)
    if update_data and type(update_data) == list:
        package_type = update_data[format_index].package_type
    else:
        package_type = format_index + 1

    logging.info(f'[toggle_format] - received SIGUSR1 - switching output format to {package_type}')
    with condition:
        needs_redraw = True
        condition.notify()

signal.signal(signal.SIGHUP, refresh_handler)
signal.signal(signal.SIGUSR1, toggle_format)  

def generate_tooltip(update_data: NamedTuple=None):
    tooltip = []
    count = len(update_data.packages)
    max_shown = 20 if count > 20 else count
    max_name_len = 0
    max_version_len = 0

    if update_data.packages and len(update_data.packages) > 0:
        for item in update_data.packages[:max_shown]:
            # I'm trying to remember why I split on '.'
            # package_name = item.name.split('.')[0]
            # if len(item.name.split('.')[0]) > max_name_len:
            #     max_name_len = len(item.name.split('.')[0])
            if len(item.name) > max_name_len:
                max_name_len = len(item.name)
            if len(item.version) > max_version_len:
                max_version_len = len(item.version)

        max_name_len = max_name_len if max_name_len <=30 else 30
        max_version_len = max_version_len if max_version_len <=30 else 30

        for item in update_data.packages[:max_shown]:
            # line = f'{item.name.split('.')[0][:max_name_len]:{max_name_len}} => {item.version[:max_version_len]:{max_version_len}}'
            line = f'{item.name[:max_name_len]:{max_name_len}} => {item.version[:max_version_len]:{max_version_len}}'
            tooltip.append(line)

        if count > max_shown:
            tooltip.append(f'and {count - max_shown} more...')
    else:
        tooltip.append(f'Hooray! No outdated {update_data.package_type} packages.'),

    if len(tooltip) > 0:
        tooltip.append('')
        tooltip.append(f'Last updated {update_data.updated}')

    return '\n'.join(tooltip)

def execute_command(command: list=None, cwd: str=None, shell: bool=False):
    try:
        result = subprocess.run(
            command,
            cwd            = cwd,
            capture_output = True,
            text           = True,
            check          = False,
            shell          = shell,
        )
        return result.returncode, result.stdout.lstrip().rstrip(), result.stderr.lstrip().rstrip()
    except Exception as e:
        return -1, None, str(e)

def success(package_type: str=None, packages: list=None):
    logging.info(f'[find_{package_type}_updates] - returning data')
    return SystemUpdates(
        success      = True,
        count        = len(packages),
        packages     = packages,
        package_type = package_type,
        updated      = util.get_human_timestamp(),
    )

def error(package_type: str=None, command: list=None, error: str=None):
    error = error or 'unknown error'
    if type(command) == list:
        joined = ' '.join(command)
    elif type(command) == str:
        joined = command

    logging.error(f'[find_{package_type}_updates] - failed to execute command "{joined}": {error}')
    return SystemUpdates(
        success      = False,
        error        = f'Failed to execute "{joined}": {error}',
        package_type = package_type
    )

def find_apk_updates(package_type: str = None):
    logging.info(f'[find_{package_type}_updates] - entering fcunction')

    packages = []
    command = ['sudo', 'apk', 'update']
    rc, _, stderr = execute_command(command)
    if rc != 0:
        return error(package_type=package_type, command=command, error=stderr)

    command = ['sudo', 'apk', '--simulate', 'upgrade']
    rc, stdout, stderr = execute_command(command)
    if rc == 0:
        for line in stdout.split('\n'):
            match = re.search(r'^\(\d+/\d+\)\s+Upgrading\s+([^\s]+)\s+\(([^\s]+)\s+->\s+([^\)]+)', line)
            if match:
                packages.append(Package(
                    name    = match.group(1),
                    version = match.group(3),
                ))
    else:
        return error(package_type=package_type, command=command, error=stderr)

    return success(package_type=package_type, packages=packages)

def find_apt_updates(package_type: str = None):
    logging.info(f'[find_{package_type}_updates] - entering function')

    packages = []
    command = ['sudo', 'apt', 'update']
    rc, _, stderr = execute_command(command=command)
    if rc != 0:
        return error(package_type=package_type, command=command, error=stderr)

    command = ['sudo', 'apt', 'upgrade', '--simulate', '--quiet']
    rc, stdout, _ = execute_command(command=command)
    if rc == 0:
        lines = [line for line in stdout.split('\n') if line.startswith('Inst')]
        for line in lines:
            match = re.search(r'^Inst\s+(\S+)\s+\[([^\]]+)\]\s+\(([^\s]+)', line)
            if match:
                packages.append(Package(name=match.group(1), version=match.group(3)))
    else:
        return error(package_type=package_type, command=command, error=stderr)

    return success(package_type=package_type, packages=packages)

def find_brew_updates(package_type: str = None):
    logging.info(f'[find_{package_type}_updates] - entering function')

    packages = []
    # This should prevent this message
    # To restore the stashed changes to /home/linuxbrew/.linuxbrew/Homebrew,
    #   run: cd /home/linuxbrew/.linuxbrew/Homebrew && git stash pop
    logging.info(f'[find_{package_type}_updates] - safe brew update')
    rc, _, stderr = execute_command(
        command = 'git stash push -m "automation backup" --quiet || true',
        cwd     = os.environ['HOMEBREW_DIR'] or '/home/linuxbrew/.linuxbrew/Homebrew',
        shell   = True,
    )
    if rc != 0:
        return error(package_type=package_type, command=command, error=stderr)

    logging.info(f'[find_{package_type}_updates] - brew outdated')
    command = ['brew', 'outdated', '--json']
    rc, stdout, stderr = execute_command(command=command)
    if rc == 0:
        brew_data, stderr = util.parse_json_string(stdout)
        if stderr:
            joined = stdout.replace('\n', '')
            logging.error(f'[find_{package_type}_updates] - JSON parse error - stdout="{joined}", stderr="{stderr}"')
            return error(package_type=package_type, command=command, error=stderr)
    else:
        return error(package_type=package_type, command=command, error=stderr)

    for item_type in ['formulae', 'casks']:
        for package in brew_data[item_type]:
            if 'name' in package and 'current_version' in package:
                packages.append(Package(name=package['name'], version=package['current_version']))

    return success(package_type=package_type, packages=packages)

def find_dnf_updates(package_type: str=None):
    logging.info(f'[find_{package_type}_updates] - entering function')

    packages = []
    command = ['sudo', 'dnf', 'check-upgrade']
    rc, stdout, stderr = execute_command(command)
    if rc == 0:
        return success(package_type=package_type, packages=packages)
    elif rc == 100:
        for line in stdout.split('\n'):
            bits = re.split(r'\s+', line)
            if len(bits) == 3:
                packages.append(Package(name=bits[0], version=bits[1]))
    else:
        return error(package_type=package_type, command=command, error=stderr)

    return success(package_type=package_type, packages=packages)

def find_emerge_updates(package_type: str=None):
    logging.info(f'[find_{package_type}_updates] - entering function')

    packages = []
    command = ['emerge', '--sync']
    rc, _, stderr = execute_command(command)
    if rc != 0:
        return error(package_type=package_type, command=command, error=stderr)
    
    command = ['emerge', '-puD', '@world']
    rc, stdout, stderr = execute_command(command)
    if rc == 0:
        lines = [line for line in stdout.split('\n') if line.startswith('[ebuild') or line.startswith('[binary')]
        for line in lines:
            match = re.search(r'\] ([\w\-+/]+)-([^\s]+)', line)
            if match:
                packages.append(Package(
                    name    = match.group(1),
                    version = match.group(2),
                ))
    else:
        return error(package_type=package_type, command=command, error=stderr)

    return success(package_type=package_type, packages=packages)

def find_flatpak_updates(package_type: str=None):
    logging.info(f'[find_{package_type}_updates] - entering function')

    packages = []
    command = ['flatpak', 'update', '--appstream']
    rc, stdout, stderr = execute_command(command)
    if rc != 0:
        return error(package_type=package_type, command=command, error=stderr)

    command = ['flatpak', 'remote-ls', '--updates', '--columns=name,version']
    rc, stdout, stderr = execute_command(command)
    if rc == 0:
        for line in stdout.split('\n'):
            bits = re.split(r'\s+', line)
            if len(bits) == 2:
                packages.append(Package(name=bits[0], version = bits[1]))
    else:
        return error(package_type=package_type, command=command, error=stderr)

    return success(package_type=package_type, packages=packages)

def find_mint_updates(package_type: str=None):
    logging.info(f'[find_{package_type}_updates] - entering function')

    packages = []
    command = ['sudo', 'mintupdate-cli', 'list', '-r']
    rc, stdout, stderr = execute_command(command)
    if rc == 0:
        for line in stdout.split('\n'):
            bits = re.split(r'\s+', line)
            if len(bits) == 3:
                packages.append(Package(name=bits[1], version = bits[2]))
    else:
        return error(package_type=package_type, command=command, error=stderr)

    return success(package_type=package_type, packages=packages)

def find_pacman_updates(package_type: str=None):
    logging.info(f'[find_{package_type}_updates] - entering function')

    packages = []
    command = ['sudo', 'pacman', '-Sy']
    rc, _, stderr = execute_command(command)
    if rc != 0:
        return error(package_type=package_type, command=command, error=stderr)

    command = ['sudo', 'pacman', '-Qu']
    rc, stdout, stderr = execute_command(command)
    if rc == 0:
        for line in stdout.split('\n'):
            match = re.search(r'^([^\s]+)\s+([^\s]+)\s+->\s+([^\s]+)', line)
            if match:
                packages.append(Package(name=match.group(1), version=match.group(3)))
    else:
        return error(package_type=package_type, command=command, error=stderr)

    return success(package_type=package_type, packages=packages)

def find_snap_updates(package_type: str=None):
    logging.info(f'[find_{package_type}_updates] - entering function')

    packages = []
    command = ['sudo', 'snap', 'refresh', '--list']
    rc, stdout, stderr = execute_command(command)
    if rc == 0:
        if stdout !='All snaps up to date':
            lines = stdout.lstrip().strip().split('\n')
            for line in lines[1:]:
                bits = re.split(r'\s+', line)
                packages.append(Package(name=bits[0], version=bits[1]))
    else:
        return error(package_type=package_type, command=command, error=stderr)

    return success(package_type=package_type, packages=packages)

def find_xbps_updates(package_type: str=None):
    logging.info(f'[find_{package_type}_updates] - entering function')

    packages = []
    command = ['sudo', 'xbps-install', '-Snu']
    rc, stdout, stderr = execute_command(command)
    if rc == 0:
        for line in stdout.split('\n'):
            bits = re.split(r'\s+', line)
            if len(bits) == 6:
                match = re.match(r'^(.*)-(.*)$', bits[0])
                if match:
                    packages.append(Package(name=match.group(1), version=match.group(2)))
    else:
        return error(package_type=package_type, command=command, error=stderr)

    return success(package_type=package_type, packages=packages)

def find_yay_updates(package_type: str=None, aur: bool=False):
    logging.info(f'[find_{package_type}_updates] - entering function, aur={aur}')

    packages = []
    command = ['yay', '-Sy']
    rc, _, stderr = execute_command(command)
    if rc != 0:
        return error(package_type=package_type, command=command, error=stderr)

    command = ['yay', '-Qu']
    rc, stdout, stderr = execute_command(command)
    if rc == 0:
        for line in stdout.split('\n'):
            if aur:
                pattern = r'^([^\s]+)\s+([^\s]+)\s+->\s+([^\s]+)\s+\(AUR\)$'
            else:
                pattern = r'^([^\s]+)\s+([^\s]+)\s+->\s+([^\s]+)$'
            match = re.search(pattern, line)
            if match:
                packages.append(Package(name=match.group(1), version=match.group(3)))
    else:
        return error(package_type=package_type, command=command, error=stderr)

    return success(package_type=package_type, packages=packages)

def find_updates(package_type: str = ''):
    """
    Determine which function is required to get the updates
    """
    logging.info(f'[find_updates] - entering with package_type={package_type}')

    dispatch = {
        'apk'        : find_apk_updates,
        'apt'        : find_apt_updates,
        'brew'       : find_brew_updates,
        'dnf'        : find_dnf_updates,
        'emerge'     : find_emerge_updates,
        'flatpak'    : find_flatpak_updates,
        'mintupdate' : find_mint_updates,
        'pacman'     : find_pacman_updates,
        'snap'       : find_snap_updates,
        'xbps'       : find_xbps_updates,
        'yay-aur'    : lambda package_type: find_yay_updates(package_type=package_type, aur=True),
        'yay'        : lambda package_type: find_yay_updates(package_type=package_type, aur=False),
        'yum'        : find_dnf_updates,
    }

    func = dispatch.get(package_type)
    data = func(package_type=package_type) if func else None

    return data

def render_output(update_data: NamedTuple=None, icon: str=None):
    if update_data.success:
        packages = 'package' if update_data.count == 1 else 'packages'
        text = f'{icon}{glyphs.icon_spacer}{update_data.package_type} {update_data.count} outdated {packages}'
        output_class = 'success'
        tooltip = generate_tooltip(update_data=update_data)
    else:
        text = f'{glyphs.md_alert}{glyphs.icon_spacer}{update_data.package_type} failed to find updates'
        output_class = 'error'
        tooltip = f'{update_data.package_type} update error'

    return text, output_class, tooltip

def worker(package_types: list=None):
    global update_data, needs_fetch, needs_redraw, format_index

    while True:
        with condition:
            while not (needs_fetch or needs_redraw):
                condition.wait()

            fetch        = needs_fetch
            redraw       = needs_redraw
            needs_fetch  = False
            needs_redraw = False

        logging.info('[worker] - entering worker loop')
        if not util.waybar_is_running():
            logging.info('[worker] - waybar not running')
            sys.exit(0)
        else:
            if not util.network_is_reachable():
                output= {
                    'text'    : f'{glyphs.md_alert}{glyphs.icon_spacer}the network is unreachable',
                    'class'   : 'error',
                    'tooltip' : f'Software update error',
                }
                print(json.dumps(output))
                update_data = None
                continue

            if fetch:
                update_data = []
                for package_type in package_types:
                    print(json.dumps({
                        'text'    : f'{glyphs.md_timer_outline}{glyphs.icon_spacer}Checking {package_type} updates...',
                        'class'   : 'loading',
                        'tooltip' : f'Checking {package_type} updates...',
                    }))
                    package_data = find_updates(package_type=package_type)
                    update_data.append(package_data)
                
            if update_data and type(update_data) == list:
                if redraw:
                    count = sum(item.count for item in update_data)
                    icon = glyphs.md_alert if count > 0 else util.get_distro_icon()
                    text, output_class, tooltip = render_output(update_data=update_data[format_index], icon=icon)
                    output = {
                        'text'    : text,
                        'class'   : output_class,
                        'tooltip' : tooltip,
                    }
            
            print(json.dumps(output))

@click.command(help='Check available system updates from different sources', context_settings=context_settings)
@click.option('-p', '--package-type', required=True, multiple=True, help=f'The type of update to query; valid choices are: {", ".join(valid_types)}')
@click.option('-i', '--interval', type=int, default=1800, help='The update interval (in seconds)')
@click.option('-t', '--test', default=False, is_flag=True, help='Print the output and exit')
@click.option('-d', '--debug', default=False, is_flag=True, help='Enable debug logging')
def main(package_type, interval, test, debug):
    global formats, needs_fetch, needs_redraw

    configure_logging(debug=debug)
    formats = list(range(len(package_type)))

    logging.info('[main] - entering function')

    if test:
        update_data = find_updates(package_type=package_type[0])
        util.pprint(update_data)
        print()
        print(generate_tooltip(update_data=update_data[0]))
        return

    threading.Thread(target=worker, args=(package_type,), daemon=True).start()

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

if __name__ == '__main__':
    main()
