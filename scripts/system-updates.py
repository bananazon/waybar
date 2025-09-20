#!/usr/bin/env python3

from pathlib import Path
from typing import Dict, List, NamedTuple, Optional, Tuple, Union
from waybar import glyphs, util
import json
import logging
import os
import re
import sys
import time

util.validate_requirements(required=['click'])
import click

class SystemUpdates(NamedTuple):
    success  : Optional[bool] = False
    error    : Optional[str]  = None
    count    : Optional[int]  = 0
    packages : Optional[List[str]] = None

CONTEXT_SETTINGS = dict(help_option_names=['-h', '--help'])
VALID_TYPES = ['apt', 'brew', 'dnf', 'flatpak', 'mintupdate', 'pacman', 'snap', 'yay', 'yay-aur', 'yum']
LOGFILE = Path.home() / '.waybar-system-update-result.log'

logging.basicConfig(
    filename=LOGFILE,
    filemode='a',  # 'a' = append, 'w' = overwrite
    format='%(asctime)s [%(levelname)-5s] - %(message)s',
    level=logging.INFO
)

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
        packages.append(obj['name'])

    for obj in brew_data['casks']:
        packages.append(obj['name'])

    logging.info(f'[find_brew_updates] returning data, package_type={package_type}')
    return SystemUpdates(success=True, count=len(packages), packages=packages)

def find_dnf_updates(package_type: str=None):
    """
    Execute dnf to search for new updates
    """
    logging.info(f'[find_dnf_updates] entering function, type={package_type}')

    command = f'sudo dnf update -y'
    rc, stdout, stderr = util.run_piped_command(command)
    if rc != 0:
        return SystemUpdates(success=False, error=f'Failed to execute "{command}"')

    command = f'sudo dnf check-update'
    rc, stdout, stderr = util.run_piped_command(command)
    if rc == 0:
        packages = []
        try:
            _, after = stdout.split('Repositories loaded.', 1)
            lines = after.lstrip().strip().split('\n')
        except:
            logging.info(f'[find_dnf_updates] regex not found, please run "{command}" manually to verify')
            lines = []

        for line in lines:
            bits = re.split(r'\s+', line)
            packages.append(bits[0])
    else:
        return SystemUpdates(success=False, error=f'Failed to execute "{command}"')

    # This is here to test locally as I don't have dnf
    # with open(os.path.join(util.get_script_directory(), 'yum-output.txt'), 'r', encoding='utf-8') as f:
    #     stdout = f.read()
    #     packages = []
    #     _, after = stdout.split('Repositories loaded.', 1)
    #     lines = after.lstrip().strip().split('\n')
    #     for line in lines:
    #         bits = re.split(r'\s+', line)
    #         packages.append(bits[0])

    logging.info(f'[find_dnf_updates] returning data, package_type={package_type}')
    return SystemUpdates(success=True, count=len(packages), packages=packages)

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
        lines = stdout.lstrip().strip().split('\n')
        for line in lines[1:]:
            bits = re.split(r'\s+', line)
            packages.append(bits[0])
    else:
        return SystemUpdates(success=False, error=f'Failed to execute "{command}"')

    # This is here to test locally as I don't have yum
    # with open(os.path.join(util.get_script_directory(), 'snap-output.txt'), 'r', encoding='utf-8') as f:
    #     stdout = f.read()
    #     packages = []
    #     lines = stdout.lstrip().strip().split('\n')
    #     for line in lines[1:]:
    #         bits = re.split(r'\s+', line)
    #         packages.append(bits[0])

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

    # This is here to test locally as I don't have yum
    # with open(os.path.join(util.get_script_directory(), 'yum-output.txt'), 'r', encoding='utf-8') as f:
    #     stdout = f.read()
    #     packages = []
    #     _, after = stdout.split('Repositories loaded.', 1)
    #     lines = after.lstrip().strip().split('\n')
    #     for line in lines:
    #         bits = re.split(r'\s+', line)
    #         packages.append(bits[0])

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
        'mintupdate' : find_mint_updates,
        'pacman'     : find_pacman_updates,
        'snap'       : find_snap_updates,
        'yay-aur'    : lambda package_type: find_yay_updates(package_type=package_type, aur=True),
        'yay'        : lambda package_type: find_yay_updates(package_type=package_type, aur=False),
        'yum'        : find_yum_updates,
    }

    func = dispatch.get(package_type)
    data = func(package_type=package_type) if func else None

    return data
    
    # if data:
    #     packages = 'package' if data.count == 1 else 'packages'
    #     message = f'{util.color_title(glyphs.md_package_variant)} {package_type} {data.count} outdated {packages}'
    # else:
    #     message = f'{util.color_title(glyphs.md_package_variant)} {util.color_error(package_type)} {util.color_error("failed to find updates")}'
    
    # logging.info(f'[find_updates] data received - output message={message}')

    # write_tempfile(tempfile, message)

@click.group(context_settings=CONTEXT_SETTINGS)
def cli():
    """
    System update checker
    """
    pass

@cli.command(help='Check available system updates from different sources', context_settings=CONTEXT_SETTINGS)
@click.option('-t', '--type', required=True, help=f'The type of update to query; valid choices are: {", ".join(VALID_TYPES)}')
def run(type):
    """
    Run a system update check
    """
    util.network_is_reachable()

    logging.info(f'[run] Starting - package_type={type}')

    logging.info(f'[run] running in foreground - package_type={type}')
    data = find_updates(package_type=type)

    if data.success:
        packages = 'package' if data.count == 1 else 'packages'
        output = {
            'text'    : f'{glyphs.md_package_variant} {type} {data.count} outdated {packages}',
            'class'   : 'success',
            'tooltip' : f'{type} updates',
        }
    else:
        output = {
            'text'    : f'{glyphs.md_package_variant} {type} failed to find updates',
            'class'   : 'success',
            'tooltip' : f'{type} updates',
        }

    print(json.dumps(output))

if __name__ == '__main__':
    cli()
