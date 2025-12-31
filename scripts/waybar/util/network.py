import json
import os
import re
import socket
from dataclasses import dataclass, field
from typing import cast

from dacite import Config, from_dict
from waybar import glyphs, http
from waybar.util import conversion, system


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


@dataclass
class Interface:
    Connected: bool = False
    Device: str = ""
    Flags: list[str] = field(default_factory=list)
    Icon: str = glyphs.md_alert
    Inet: str | None = None
    Inet6: str | None = None
    Mac: str | None = None
    Media: str | None = None
    PublicIP: str | None = None
    Options: list[str] = field(default_factory=list)
    Type: str | None = None


def _find_all_network_interfaces() -> list[str]:
    """
    Find and return a list of all interfaces using /sys/class/net.
    """
    network_interfaces: list[str] = []
    rc, stdout_raw, _ = system.run_piped_command("ls -1 /sys/class/net")

    stdout = stdout_raw if isinstance(stdout_raw, str) else ""
    if rc == 0:
        network_interfaces = [x for x in re.split(r"\n", stdout)]

    return sorted(network_interfaces)


def _interface_exists(interface: str) -> bool:
    try:
        return os.path.isdir(f"/sys/class/net/{interface}")
    except Exception:
        return False


def _interface_type(interface: str) -> str:
    if _interface_exists(interface=interface):
        if os.path.isdir(f"/sys/class/net/{interface}/wireless"):
            return "wireless"
        else:
            return "wired"

    return "wired"


def _interface_connected(interface: str) -> bool:
    if _interface_exists(interface=interface):
        filename = f"/sys/class/net/{interface}/carrier"
        with open(filename, "r") as fh:
            contents = fh.read().strip()
            return True if contents == "1" else False

    return False


def _get_icon(port_type: str, port_connected: bool) -> str:
    if port_type == "wireless":
        return (
            glyphs.md_wifi_strength_4
            if port_connected
            else glyphs.md_wifi_strength_alert_outline
        )
    elif port_type == "wired":
        return glyphs.md_network if port_connected else glyphs.md_network_off
    elif port_type == "thunderbolt":
        return glyphs.md_network if port_connected else glyphs.md_network_off

    return glyphs.md_network if port_connected else glyphs.md_network_off


def _ifconfig(
    interface: str,
) -> tuple[list[str], str | None, str | None, str | None]:
    command = f"ip addr show {interface}"
    flags, mac, inet, inet6 = (
        [],
        None,
        None,
        None,
    )
    rc, stdout_raw, _ = system.run_piped_command(command)

    stdout = stdout_raw if isinstance(stdout_raw, str) else ""
    if rc == 0 and stdout:
        match = re.search(
            rf"\d+:\s+{interface}: \<([^\>]+)\>",
            stdout,
            re.MULTILINE,
        )
        if match:
            flags = re.split(r"\s*,\s*", match.group(1))

        match = re.search(r"ether\s+([a-z0-9:]+)", stdout)
        if match:
            mac = match.group(1)

        match = re.findall(r"inet\s+(\d+\.\d+\.\d+\.\d+)", stdout, re.MULTILINE)
        if match:
            inet = match[0]

        match = re.findall(r"inet6\s+([a-z0-9:]+)", stdout, re.MULTILINE)
        if match:
            inet6 = match[0]

    return flags, mac, inet, inet6


def get_public_ip() -> str | None:
    _, stdout_raw, _ = system.run_piped_command("curl https://ifconfig.io")

    stdout = stdout_raw if isinstance(stdout_raw, str) else ""
    return stdout if stdout else None


def get_network_data() -> list[Interface]:
    interfaces: list[Interface] = []
    public_ip = get_public_ip()
    all_interfaces = _find_all_network_interfaces()
    for interface in all_interfaces:
        port_type = _interface_type(interface=interface)
        port_connected = _interface_connected(interface=interface)
        flags, mac, inet, inet6 = _ifconfig(interface=interface)

        interfaces.append(
            Interface(
                Connected=port_connected,
                Device=interface,
                Flags=flags,
                Icon=_get_icon(port_type=port_type, port_connected=port_connected),
                Inet6=inet6,
                Inet=inet,
                Mac=mac,
                PublicIP=public_ip,
                Type=port_type,
            )
        )

    return interfaces


def get_interface_data(interface: str) -> Interface:
    network_data = get_network_data()
    for item in network_data:
        if interface == item.Device:
            return item

    return Interface()


def network_speed(number: float = 0.0, bytes: bool = False) -> str | None:
    """
    Intelligently determine network speed
    """
    # test this with dummy numbers
    suffix = "iB/s" if bytes else "bit/s"

    for unit in ["", "K", "M", "G", "T", "P"]:
        if abs(number) < 1024.0:
            if bytes:
                return f"{conversion.pad_float(number=number / 8, round_int=False)} {unit}{suffix}"
            return (
                f"{conversion.pad_float(number=number, round_int=False)} {unit}{suffix}"
            )
        number = number / 1024


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
    )

    if response and response.status == 200 and response.body:
        json_data = cast(dict[str, str], json.loads(response.body))
        location_data = from_dict(
            data_class=LocationData, data=json_data, config=Config(cast=[str])
        )
        return location_data
    return None
