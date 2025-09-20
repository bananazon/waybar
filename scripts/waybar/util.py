from datetime import datetime
from pathlib import Path
from pprint import pprint as pp
from typing import List, Tuple, Optional, Union
import importlib.util
import json
import os
import psutil
import re
import shlex
import shutil
import socket
import subprocess
import sys
import time

def pprint(input):
    pp(input)

def run_piped_command(command: str=None, background: bool=False) -> Union[
    Tuple[int, bytes, bytes],  # blocking mode
    List[subprocess.Popen]     # background mode
]:
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
    parts = [shlex.split(cmd.strip()) for cmd in command.split('|')]
    processes = []
    prev_stdout = None

    for i, part in enumerate(parts):
        try:
            proc = subprocess.Popen(
                part,
                stdin=prev_stdout,
                stdout=subprocess.PIPE if not background else subprocess.DEVNULL,
                stderr=subprocess.PIPE if not background and i == len(parts) - 1 else subprocess.DEVNULL,
                preexec_fn=os.setpgrp if background else None
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
        p.wait()

    return processes[-1].returncode, stdout.decode().strip(), stderr.decode().strip()

#==========================================================
#  Process management
#==========================================================

def waybar_is_running() -> bool:
    rc, stdout, _ = run_piped_command('pgrep -x waybar')
    return True if rc == 0 and stdout != '' else False

def process_is_running(name: str=None, full: bool=False):
    flag = 'f' if full else 'x'
    command = f'pgrep -{flag} "{name}"'
    rc, stdout, stderr = run_piped_command(command)
    if rc == 0 and stdout != '':
        pids = stdout.split('\n')
        return True, pids
    else:
        return False, []

#==========================================================
#  Unit conversersion
#==========================================================

def network_speed(number: int=0, bytes: bool=False) -> str:
    """
    Intelligently determine network speed
    """
    # test this with dummy numbers
    suffix = 'iB/s' if bytes else 'bit/s'

    for unit in ['', 'K', 'M', 'G', 'T', 'P']:
        if abs(number) < 1024.0:
            if bytes:
                return f'{pad_float(number / 8)} {unit}{suffix}'
            return f'{pad_float(number)} {unit}{suffix}'
        number = number / 1024

def processor_speed(number: int=0) -> str:
    """
    Intelligently determine processor speed
    """
    suffix = 'Hz'

    for unit in ['', 'K', 'M', 'G', 'T']:
        if abs(number) < 1000.0:
            return f'{pad_float(number)} {unit}{suffix}'
        number = number / 1000

def byte_converter(number: int=0, unit: Optional[str] = None, use_int: bool=False) -> str:
    """
    Convert bytes to the given unit.
    """
    if unit is None:
        unit = 'auto'
    suffix = 'B'

    if unit == 'auto':
        for unit in ['', 'Ki', 'Mi', 'Gi', 'Ti', 'Pi', 'Ei', 'Zi', 'Yi']:
            if abs(number) < 1024.0:
                return f'{pad_float(number)} {unit}{suffix}'
            number = number / 1024
        return f'{pad_float(number)} Yi{suffix}'
    else:
        prefix = unit[0]
        divisor = 1000
        if len(unit) == 2 and unit.endswith('i'):
            divisor = 1024

        prefix_map = {'K': 1, 'Ki': 1, 'M': 2, 'Mi': 2,  'G': 3, 'Gi': 3, 'T': 4, 'Ti': 4, 'P': 5, 'Pi': 5, 'E': 6, 'Ei': 6, 'Z': 7, 'Zi': 7}
        if unit in prefix_map.keys():
            if use_int:
                return f'{int(number / (divisor ** prefix_map[prefix]))}{unit}{suffix}'
            else:
                return f'{pad_float(number / (divisor ** prefix_map[prefix]))} {unit}{suffix}'
        else:
            return f'{number} {suffix}'

#==========================================================
#  Time functions
#==========================================================

def to_unix_time(input: str=None) -> int:
    pattern = r'^(0[1-9]|1[0-2]):[0-5][0-9] (AM|PM)$'
    if re.match(pattern, input):
        try:
            # Parse as 12-hour format
            dt = datetime.strptime(input, '%I:%M %p')

            # Replace today's date with the parsed time
            now = datetime.now()
            dt = dt.replace(year=now.year, month=now.month, day=now.day)

            # Convert to Unix timestamp (local time)
            return int(time.mktime(dt.timetuple()))
        except:
            return 0
    else:
        return 0

def to_24hour_time(input: int=0):
    try:
        # Convert to datetime (local time)
        dt = datetime.fromtimestamp(input)

        # Format as 24-hour time (HH:MM)
        return dt.strftime("%H:%M")
    except:
        return None

def duration(seconds: int=0):
    seconds = int(seconds)
    days = int(seconds / 86400)
    hours = int(((seconds - (days * 86400)) / 3600))
    minutes = int(((seconds - days * 86400 - hours * 3600) / 60))
    secs = int((seconds - (days * 86400) - (hours * 3600) - (minutes * 60)))

    return days, hours, minutes, secs

#==========================================================
#  File and directory
#==========================================================

def file_exists(filename: str='') -> bool:
    return True if (os.path.exists(filename) and os.path.isfile(filename)) else False

def file_is_executable(filename: str='') -> bool:
    return True if os.access(filename, os.X_OK) else False

def get_home_directory() -> str:
    return Path.home()

def get_config_directory() -> str:
    return os.path.join(
        Path.home(),
        '.config',
        'waybar',
    )

def get_script_directory() -> str:
    return os.path.join(
        get_config_directory(),
        'scripts',
    )

#==========================================================
#  Dependencies and validation
#==========================================================

def parse_config_file(filename: str='', required_keys: list=[]):
    # Does the file exist?
    if not file_exists(filename):
        return {}, f'{filename} does not exist'

    # Can we parse the JSON?
    try:
        with open(filename, 'r') as f:
            config = json.load(f)
    except Exception as e:
        return {}, e

    # Check for missing required keys
    if len(required_keys) > 0:
        missing = []
        for required_key in required_keys:
            if not required_key in config:
                missing.append(required_key)
        if len(missing) > 0:
            return {}, f'required keys missing from config: {','.join(missing)}'

    return config, ''

def parse_json_string(input: str=''):
    try:
        json_data = json.loads(input)
        return json_data, None
    except Exception as err:
        return None, err, 

def is_binary_installed(binary_name: str) -> bool:
    return shutil.which(binary_name)

def missing_binaries(binaries: list=[]):
    missing = []
    for binary in binaries:
        if not is_binary_installed(binary):
            missing.append(binary)
    return missing

def network_is_reachable():
    host = '8.8.8.8'
    port = 53
    timeout = 3
    try:
        socket.setdefaulttimeout(timeout)
        with socket.create_connection((host, port)):
            return True
    except OSError:
        return False

def check_network():
    if not network_is_reachable():
        # How to immport glyphs?
        error_exit(
            icon    = surrogatepass('\udb83\udc9c'),
            message = 'the network is unreachable',
        )

def validate_requirements(required: list=[]):
    missing = []

    for module in required:
        if importlib.util.find_spec(module) is None:
            missing.append(module)

    if missing:
        icon = surrogatepass('\udb80\udc26')
        error_exit(
            icon    = icon,
            message = f'Please install via pip: {", ".join(missing)}',
        )

def interface_exists(interface: str=None) -> bool:
    return os.path.isdir(f'/sys/class/net/{interface}')
    # cat /sys/class/net/enp1s0/carrier

def interface_is_connected(interface: str=None) -> bool:
    with open(f'/sys/class/net/{interface}/carrier', 'r') as f:
        contents = f.read()
    return True if int(contents) == 1 else False

#==========================================================
#  Formatting and conversion
#==========================================================

def pad_float(number: int=0) -> str:
    """
    Pad a float to two decimal places.
    """
    if type(number) == str:
        number = float(number)

    if number.is_integer():
        return str(int(number))
    else:
        return f'{number:.2f}'

def to_snake_case(s: str) -> str:
    # Replace anything that's not a letter or number with underscore
    s = re.sub(r'[^0-9a-zA-Z]+', '_', s)
    # Add underscore between camelCase or PascalCase boundaries
    s = re.sub(r'([a-z0-9])([A-Z])', r'\1_\2', s)
    # Collapse multiple underscores into one
    s = re.sub(r'_+', '_', s)
    # Strip leading/trailing underscores, lowercase
    return s.strip('_').lower()

#==========================================================
#  Other
#==========================================================

def surrogatepass(code):
    return code.encode('utf-16', 'surrogatepass').decode('utf-16')

def get_valid_units() -> list:
    """
    Return a list of valid storage units
    """
    return ['K', 'Ki', 'M', 'Mi', 'G', 'Gi', 'T', 'Ti', 'P', 'Pi', 'E', 'Ei', 'Z', 'Zi', 'auto']
