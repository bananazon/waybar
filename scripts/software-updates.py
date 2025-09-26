#!/usr/bin/env python3

from pathlib import Path
from typing import Dict, List, NamedTuple, Optional, Tuple, Union
from waybar import glyphs, util
import json
import logging
import os
import re
import signal
import sys
import threading
import time

util.validate_requirements(required=['click'])
import click

update_event = threading.Event()
sys.stdout.reconfigure(line_buffering=True)

CACHE_DIR = util.get_cache_directory()
CONTEXT_SETTINGS = dict(help_option_names=['-h', '--help'])
LOGFILE = CACHE_DIR / 'waybar-software-updates.log'
VALID_TYPES = ['apt', 'brew', 'dnf', 'flatpak', 'mintupdate', 'pacman', 'snap', 'yay', 'yay-aur', 'yum']

class Package(NamedTuple):
    available_version : Optional[str]  = None
    installed_version : Optional[str]  = None
    name              : Optional[str]  = None

class SystemUpdates(NamedTuple):
    success      : Optional[bool] = False
    error        : Optional[str]  = None
    package_type : Optional[str]  = None
    count        : Optional[int]  = 0
    packages     : Optional[List[str]] = None

logging.basicConfig(
    filename=LOGFILE,
    filemode='a',  # 'a' = append, 'w' = overwrite
    format='%(asctime)s [%(levelname)-5s] - %(message)s',
    level=logging.INFO
)

def generate_tooltip(data):
    tooltip = [
    ]
    count = len(data.packages)
    max_shown = 20
    max_name_len = 0
    max_version_len = 0

    for item in data.packages:
        package_name = item.name.split('.')[0]
        if len(item.name.split('.')[0]) > max_name_len:
            max_name_len = len(item.name.split('.')[0])
        
        if len(item.installed_version) > max_version_len:
            max_version_len = len(item.installed_version)

    for item in data.packages[:max_shown]:
        tooltip.append(f'{item.name.split('.')[0][:max_name_len]:{max_name_len}} {item.installed_version:{max_version_len}} => {item.available_version}')
    
    if count > max_shown:
        tooltip.append(f'and {count - max_shown} more...')

    return '\n'.join(tooltip)

def find_apt_updates(package_type: str = None):
    """
    Execute apt to search for new updates
    """
    logging.info(f'[find_apt_updates] entering function, type={package_type}')

    command = f'sudo apt update'
    rc, stdout, stderr = util.run_piped_command(command)
    if rc != 0:
        return SystemUpdates(success=False, error=f'Failed to execute "{command}"')

    # command = 'sudo apt list --upgradable'
    command = 'sudo apt upgrade --simulate --quiet'
    rc, stdout, stderr = util.run_piped_command(command)
    if rc == 0:
        packages = []
        # We don't want to count deferred packages as they can't be installed
        try:
            _, after = stdout.split('The following packages will be upgraded:', 1)
            lines = after.lstrip().strip().split('\n')
        except:
            logging.info(f'[find_apt_updates] regex not found, please run "{command}" manually to verify')
            lines = []

        for line in lines:
            pattern = re.compile(
                r'(\d+)\s+upgraded,\s+(\d+)\s+newly installed,\s+(\d+)\s+to remove and\s+(\d+)\s+not upgraded\.'
            )
            match = pattern.search(line)
            if match:
                break
            else:
                for name in re.split(r'\s+', line):
                    if len(name) > 0:
                        packages.append(name)
    else:
        return SystemUpdates(success=False, error=f'Failed to execute "{command}"')

    logging.info(f'[find_apt_updates] returning data, package_type={package_type}')
    return SystemUpdates(success=True, count=len(packages), packages=packages)

def find_brew_updates(package_type: str = None):
    """
    Execute brew to search for new updates
    """
    logging.info(f'[find_brew_updates] entering function, type={package_type}')

    command = f'brew update'
    rc, _, stderr = util.run_piped_command(command)
    if rc != 0:
        return SystemUpdates(success=False, error=f'Failed to execute "{command}"')

    command = f'brew list --installed-on-request'
    rc, stdout, _ = util.run_piped_command(command)
    if rc != 0:
        return SystemUpdates(success=False, error=f'Failed to execute "{command}"')

    manually_installed = {line for line in stdout.splitlines()}

    command = f'brew outdated --json'
    rc, stdout, _ = util.run_piped_command(command)
    if rc != 0:
        return SystemUpdates(success=False, error=f'Failed to execute "{command}"')

    try:
        brew_data = json.loads(stdout)
    except Exception as e:
        return SystemUpdates(success=False, error=f'failed to parse JSON from {command}: {e}')

    packages = []
    for obj in brew_data['formulae']:
        packages.append(Package(
            name              = obj.get('name'),
            available_version = obj.get('current_version'),
            installed_version = obj.get('installed_versions')[0],
        ))

    for obj in brew_data['casks']:
        packages.append(Package(
            name              = obj.get('name'),
            available_version = obj.get('current_version'),
            installed_version = obj.get('installed_versions')[0],
        ))

    logging.info(f'[find_brew_updates] returning data, package_type={package_type}')
    return SystemUpdates(success=True, count=len(packages), packages=packages, package_type=package_type)

def find_dnf_updates(package_type: str=None):
    """
    Execute dnf to search for new updates
    """
    logging.info(f'[find_dnf_updates] entering function, type={package_type}')

    packages = []
    available_map = {}
    installed_map = {}

    command = f'sudo dnf check-upgrade'
    rc, stdout, stderr = util.run_piped_command(command)
    if rc == 0:
        return SystemUpdates(success=True, packages=[], package_type=package_type)
    elif rc == 1:
        return SystemUpdates(success=False, error=f'Failed to execute "{command}"', package_type=package_type)
    elif rc == 100:
        for line in stdout.split('\n'):
            bits = re.split(r'\s+', line)
            if len(bits) == 3:
                available_map[bits[0]] = {
                    'available_version': bits[1]
                }

    command = f'sudo dnf list --installed'
    rc, stdout, stderr = util.run_piped_command(command)
    if rc == 0:
        match = re.search(r"Installed packages\n([\s\S]*)", stdout)
        if match:
            for line in match.group(1).split('\n'):
                bits = re.split(r'\s+', line)
                if len(bits) == 3:
                    installed_map[bits[0]] = {
                        'installed_version': bits[1]
                    }
    else:
        return SystemUpdates(success=False, error=f'Failed to execute "{command}"', package_type=package_type)
    
    for key, value in available_map.items():
        if key in installed_map:
            available_map[key]['installed_version'] = installed_map[key]['installed_version']

    for key, value in available_map.items():
        packages.append(Package(
            name              = key,
            available_version = value.get('available_version'),
            installed_version = value.get('installed_version'),
        ))

    return SystemUpdates(success=True, count=len(packages), packages=packages, package_type=package_type)

def find_flatpak_updates(package_type: str=None):
    """
    Execute flatpak to search for new updates
    """
    logging.info(f'[find_flatpak_updates] entering function, type={package_type}')

    command = f'sudo flatpak update --appstream'
    rc, stdout, stderr = util.run_piped_command(command)
    if rc != 0:
        data['success'] = False
        data['error'] = f'failed to execute {command}'
        return data

    command = f'sudo flatpak remote-ls --updates --columns=name,version'
    rc, stdout, stderr = util.run_piped_command(command)
    if rc == 0:
        packages = []
        if stdout == '':
            logging.info(f'[find_flatpak_updates] returning data, package_type={package_type}')
            return SystemUpdates(success=True, count=len(packages), packages=packages)
        else:
            lines = stdout.split('\n')
            for line in lines:
                bits = re.split(r'\s+', line)
                packages.append(bits[0])
    else:
        return SystemUpdates(success=False, error=f'Failed to execute "{command}"')

    logging.info(f'[find_flatpak_updates] returning data, package_type={package_type}')
    return SystemUpdates(success=True, count=len(packages), packages=packages)

def find_mint_updates(package_type: str=None):
    """
    Execute mintupdate-cli to search for new updates
    """

    logging.info(f'[find_mint_updates] entering function, type={package_type}')

    command = f'sudo mintupdate-cli list -r'
    rc, stdout, stderr = util.run_piped_command(command)
    if rc == 0:
        packages = []
        lines = stdout.split('\n')
        for line in lines:
            bits = re.split(r'\s+', line)
            packages.append(bits[1])
    else:
        return SystemUpdates(success=False, error=f'Failed to execute "{command}"')

    logging.info(f'[find_mint_updates] returning data, package_type={package_type}')
    return SystemUpdates(success=True, count=len(packages), packages=packages)

def find_pacman_updates(package_type: str=None):
    """
    Execute pacman to search for new updates
    """
    logging.info(f'[find_pacman_updates] entering function, type={package_type}')

    command = f'sudo pacman -Qu'
    rc, stdout, stderr = util.run_piped_command(command)
    if rc == 0:
        packages = []
        try:
            _, after = stdout.split(':: Checking for updates...', 1)
            lines = after.lstrip().strip().split('\n')
        except:
            logging.info(f'[find_pacman_updates] regex not found, please run "{command}" manually to verify')
            lines = []

        for line in lines:
            bits = re.split(r'\s+', line)
            packages.append(bits[0])
    else:
        return SystemUpdates(success=False, error=f'Failed to execute "{command}"')

    # This is here to test locally as I don't have pacman
    # with open(os.path.join(util.get_script_directory(), 'pacman-output.txt'), 'r', encoding='utf-8') as f:
    #     stdout = f.read()
    #     packages = []
    #     _, after = stdout.split(':: Checking for updates...', 1)
    #     lines = after.lstrip().strip().split('\n')
    #     for line in lines:
    #         bits = re.split(r'\s+', line)
    #         packages.append(bits[0])

    logging.info(f'[find_pacman_updates] returning data, package_type={package_type}')
    return SystemUpdates(success=True, count=len(packages), packages=packages)

def find_snap_updates(package_type: str=None):
    """
    Execute snap to search for new updates
    """
    logging.info(f'[find_snap_updates] entering function, type={package_type}')

    command = f'sudo snap refresh --list'
    rc, stdout, stderr = util.run_piped_command(command)
    if rc == 0:
        packages = []
        if stdout !='All snaps up to date':
            lines = stdout.lstrip().strip().split('\n')
            for line in lines[1:]:
                bits = re.split(r'\s+', line)
                packages.append(bits[0])
    else:
        return SystemUpdates(success=False, error=f'Failed to execute "{command}"')

    logging.info(f'[find_snap_updates] returning data, package_type={package_type}')
    return SystemUpdates(success=True, count=len(packages), packages=packages)

def find_yay_updates(package_type: str=None, aur: bool=False):
    """
    Execute yay to search for new updates
    """
    logging.info(f'[find_yay_updates] entering function, type={package_type}, aur={aur}')

    command = f'sudo yay -Qua'
    rc, stdout, stderr = util.run_piped_command(command)
    if rc == 0:
        packages = []
        try:
            _, after = stdout.split(':: Checking for updates...', 1)
            lines = after.lstrip().strip().split('\n')
        except:
            logging.info(f'[find_pacman_updates] regex not found, please run "{command}" manually to verify')
            lines = []

        if aur:
            lines = [line for line in lines if line.endswith('(AUR)')]
        else:
            lines = [line for line in lines if not line.endswith('(AUR)')]

        for line in lines:
            bits = re.split(r'\s+', line)
            packages.append(bits[0])
    else:
        return SystemUpdates(success=False, error=f'Failed to execute "{command}"')

    # This is here to test locally as I don't have yay
    # with open(os.path.join(util.get_script_directory(), 'yay-output.txt'), 'r', encoding='utf-8') as f:
    #     stdout = f.read()
    #     packages = []
    #     _, after = stdout.split(':: Checking for updates...', 1)
    #     lines = after.lstrip().strip().split('\n')

    #     if aur:
    #         lines = [line for line in lines if line.endswith('(AUR)')]
    #     else:
    #         lines = [line for line in lines if not line.endswith('(AUR)')]

    #     for line in lines:
    #         bits = re.split(r'\s+', line)
    #         packages.append(bits[0])

    logging.info(f'[find_yay_updates] returning data, package_type={package_type}')
    return SystemUpdates(success=True, count=len(packages), packages=packages)

def find_yum_updates(package_type: str=None):
    """
    Execute yum to search for new updates
    """
    logging.info(f'[find_yum_updates] entering function, type={package_type}')

    command = f'sudo yum update -y'
    rc, stdout, stderr = util.run_piped_command(command)
    if rc != 0:
        return SystemUpdates(success=False, error=f'Failed to execute "{command}"')

    command = f'sudo {binary} check-update'
    rc, stdout, stderr = util.run_piped_command(command)
    if rc == 0:
        packages = []
        try:
            _, after = stdout.split('Repositories loaded.', 1)
            lines = after.lstrip().strip().split('\n')
        except:
            logging.info(f'[find_yum_updates] regex not found, please run "{command}" manually to verify')
            lines = []

        for line in lines:
            bits = re.split(r'\s+', line)
            packages.append(bits[0])
    else:
        return SystemUpdates(success=False, error=f'Failed to execute "{command}"')

    logging.info(f'[find_yum_updates] returning data, package_type={package_type}')
    return SystemUpdates(success=True, count=len(packages), packages=packages)

def find_updates(package_type: str = ''):
    """
    Determine which function is required to get the updates
    """
    logging.info(f'[find_updates] type={package_type}')

    dispatch = {
        'apt'        : find_apt_updates,
        'brew'       : find_brew_updates,
        'dnf'        : find_dnf_updates,
        'flatpak'    : find_flatpak_updates,
        'pacman'     : find_pacman_updates,
        'snap'       : find_snap_updates,
        'yay-aur'    : lambda package_type: find_yay_updates(package_type=package_type, aur=True),
        'yay'        : lambda package_type: find_yay_updates(package_type=package_type, aur=False),
        'yum'        : find_yum_updates,
    }

    func = dispatch.get(package_type)
    data = func(package_type=package_type) if func else None

    return data

def worker(package_type: str=None):
    while True:
        update_event.wait()
        update_event.clear()

        logging.info('[main] entering main loop')
        if not util.waybar_is_running():
            logging.info('[main] waybar not running')
            sys.exit(0)
        else:
            if util.network_is_reachable():
                logging.info(f'[run] Starting - package_type={package_type}')


                loading_dict = {
                    'text'    : f'{glyphs.md_timer_outline}{glyphs.icon_spacer}Checking {package_type}...',
                    'class'   : 'loading',
                    'tooltip' : f'Checking {package_type}',
                }
                print(json.dumps(loading_dict))

                data = find_updates(package_type=package_type)

                if data.success:
                    tooltip = generate_tooltip(data)
                    packages = 'package' if data.count == 1 else 'packages'
                    output = {
                        'text'    : f'{glyphs.md_package_variant}{glyphs.icon_spacer}{package_type} {data.count} outdated {packages}',
                        'class'   : 'success',
                        'tooltip' : tooltip,
                    }
                else:
                    output = {
                        'text'    : f'{glyphs.md_package_variant}{glyphs.icon_spacer}{package_type} failed to find updates',
                        'class'   : 'success',
                        'tooltip' : f'{package_type} update error',
                    }
            else:
                output= {
                    'text'    : f'{glyphs.md_alert}{glyphs.icon_spacer}the network is unreachable',
                    'class'   : 'error',
                    'tooltip' : f'{package_type} update error',
                }

            print(json.dumps(output))

def refresh_handler(signum, frame):
    logging.info('Received SIGHUP — triggering find_updates')
    update_event.set()

signal.signal(signal.SIGHUP, refresh_handler)

@click.command(help='Check available system updates from different sources', context_settings=CONTEXT_SETTINGS)
@click.option('-t', '--package-type', required=True, help=f'The type of update to query; valid choices are: {", ".join(VALID_TYPES)}')
@click.option('-i', '--interval', type=int, default=1800, help='The update interval (in seconds)')
def main(package_type, interval):
    logging.info('[main] entering')
    threading.Thread(target=worker, args=(package_type,), daemon=True).start()
    update_event.set()

    while True:
        time.sleep(interval)
        update_event.set()

if __name__ == '__main__':
    main()
