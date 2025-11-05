#!/usr/bin/env python3

from collections.abc import Mapping
from dacite import from_dict, Config
from dataclasses import dataclass, field, fields, is_dataclass, Field
from keystore import SecureKeyStore
from jinja2 import Template
from pathlib import Path
from typing import cast, Protocol, TypeVar
import click
import json
import os
import re
import sys
import yaml as y


class DataclassInstance(Protocol):
    __dataclass_fields__: dict[str, Field[object]]


@dataclass
class StaticModule:
    api_key: str | None = None
    enabled: bool = False
    interval: int = 3600  # to be safe
    ip: str | None = None
    limit: int = 0
    magnitude: float = 0.0
    name: str = ""
    port: int = 0
    radius: str | None = None
    unit: str | None = None


@dataclass
class DiskConsumers:
    enabled: bool = False
    interval: int = 3600
    paths: list[str] = field(default_factory=list)
    unit: str = "auto"


@dataclass
class FilesystemUsage:
    debug: bool = False
    enabled: bool = False
    interval: int = 3600
    mountpoints: list[str] = field(default_factory=list)
    show_stats: bool = False
    unit: str = "auto"


@dataclass
class NetworkThroughput:
    enabled: bool = False
    interval: int = 1800
    interfaces: list[str] = field(default_factory=list)


@dataclass
class SoftwareUpdates:
    enabled: bool = False
    interval: int = 3600
    package_types: list[str] = field(default_factory=list)


@dataclass
class WifiStatus:
    enabled: bool = False
    interval: int = 1800
    interfaces: list[str] = field(default_factory=list)


@dataclass
class Weather:
    api_key: str | None = None
    enabled: bool = False
    interval: int = 1800
    locations: list[str] = field(default_factory=list)


@dataclass
class Configuration:
    exclusive: bool = False
    font: str | None = None
    height: int = 0
    layer: str | None = None
    position: str | None = None
    scripts_path: str | None = None
    spacing: int = 0
    static_modules: list[StaticModule] = field(default_factory=list)
    disk_consumers: DiskConsumers = field(default_factory=DiskConsumers)
    filesystem_usage: FilesystemUsage = field(default_factory=FilesystemUsage)
    network_throughput: NetworkThroughput = field(default_factory=NetworkThroughput)
    software_updates: SoftwareUpdates = field(default_factory=SoftwareUpdates)
    weather: Weather = field(default_factory=Weather)
    wifi_status: WifiStatus = field(default_factory=WifiStatus)


BASE_DIR = Path.home() / ".config/waybar"
CONFIG_DIR = BASE_DIR / "configure"
TEMPLATE_FILE = CONFIG_DIR / "config.jsonc.j2"
OUTPUT_FILE = CONFIG_DIR / "config.jsonc"
YAML_FILE = CONFIG_DIR / "config.yaml"
DEFAULT_DB = Path.home() / ".local/share/secure_keystore.db"
DEFAULT_KEY = Path.home() / ".local/share/secure_keystore.key"

context_settings = dict(help_option_names=["-h", "--help"])


def replace_key_refs(obj: object) -> object:
    """
    Traverse any dataclass / list / dict / tuple
    and replace "{key:xxxxx}" strings via keystore
    """
    pattern = re.compile(r"^\{key:([a-zA-Z0-9_]+)\}$")

    # string case
    if isinstance(obj, str):
        m = pattern.match(obj)
        if m:
            key_name = m.group(1)
            value = keystore.get("waybar", key_name)
            if value is None:
                raise KeyError(f'Key "{key_name}" not found')
            return value  # type: ignore[return-value]
        return obj

    # dataclass fields
    if is_dataclass(obj) and not isinstance(obj, type):
        # basedpyright cannot verify dataclass instances for fields()
        # so we must ignore the type check here
        dc = obj  # type: ignore[reportGeneralTypeIssues]
        kw: dict[str, object] = {}
        for f in fields(dc):
            v = cast(str | int | float, getattr(dc, f.name))
            kw[f.name] = replace_key_refs(v)
        return type(dc)(**kw)

    if isinstance(obj, Mapping):
        return cast(dict[str, object], {k: replace_key_refs(v) for k, v in obj.items()})

    if isinstance(obj, list):
        obj_list = cast(list[object], obj)
        return [replace_key_refs(v) for v in obj_list]

    if isinstance(obj, tuple):
        obj_tuple = cast(tuple[object, ...], obj)
        return tuple(replace_key_refs(v) for v in obj_tuple)

    return obj


def load_yaml(input: Path) -> Configuration:
    configuration: Configuration = Configuration()
    if input.exists():
        try:
            with open(input, "r") as f:
                yaml_data = cast(dict[str, object], y.safe_load(f))
                configuration = from_dict(
                    data_class=Configuration,
                    data=yaml_data,
                    config=Config(cast=[str, int, float]),
                )
                return configuration

        except Exception as e:
            click.echo(f"Failed to parse the YAML file: {str(e)}")
            sys.exit(1)
    else:
        click.echo(f'yaml file "{input}" doesn\'t exist')
        sys.exit(1)


def load_template(input: Path) -> str:
    if input.exists():
        try:
            with open(input, "r") as f:
                return f.read()
        except Exception as e:
            click.echo(f"Failed to parse the template file: {str(e)}")
            sys.exit(1)
    else:
        click.echo(f'template file "{input}" doesn\'t exist')
        sys.exit(1)


def render_template(
    template_file: Path, yaml_file: Path, output_file: Path, dryrun: bool
):
    modules_right: list[str] = []
    configuration = load_yaml(input=yaml_file)
    template_str = load_template(input=template_file)
    configuration = cast(Configuration, replace_key_refs(configuration))
    static_module_map: dict[str, StaticModule] = {}
    for module in configuration.static_modules:
        static_module_map[module.name] = module

    output: str = ""

    if configuration.static_modules:
        for module in configuration.static_modules:
            if module.enabled:
                modules_right.append(f"custom/{module.name}")

    if configuration.disk_consumers and configuration.disk_consumers.enabled:
        if len(configuration.disk_consumers.paths) > 0:
            configuration.disk_consumers.paths = [
                os.path.expanduser(item).rstrip("/")
                for item in configuration.disk_consumers.paths
            ]
            modules_right.append("custom/disk-consumers")

    if configuration.filesystem_usage and configuration.filesystem_usage.enabled:
        if len(configuration.filesystem_usage.mountpoints) > 0:
            modules_right.append("custom/filesystem-usage")

    if configuration.network_throughput and configuration.network_throughput.enabled:
        if len(configuration.network_throughput.interfaces) > 0:
            modules_right.append("custom/network-throughput")

    if configuration.software_updates and configuration.software_updates.enabled:
        if len(configuration.software_updates.package_types) > 0:
            modules_right.append("custom/software-updates")

    if configuration.weather and configuration.weather.enabled:
        if configuration.weather.api_key and len(configuration.weather.locations) > 0:
            modules_right.append("custom/weather")

    if configuration.wifi_status and configuration.wifi_status.enabled:
        if len(configuration.wifi_status.interfaces) > 0:
            modules_right.append("custom/wifi-status")

    modules_right = sorted(modules_right)

    try:
        config_template = cast(
            Template, Template(template_str, trim_blocks=False, lstrip_blocks=False)
        )
    except Exception as e:
        print(f'Failed to generate the jinja template from "{template_file}": {str(e)}')
        sys.exit(1)

    try:
        output = config_template.render(
            cpu_usage=static_module_map.get("cpu-usage", StaticModule()),
            dc=configuration.disk_consumers or [],
            exclusive=configuration.exclusive,
            fs=configuration.filesystem_usage or [],
            font=configuration.font or "Arimo Nerd Font 12",
            height=configuration.height or 31,
            layer=configuration.layer or "bottom",
            memory_usage=static_module_map.get("memory-usage", StaticModule()),
            modules_right=modules_right,
            nt=configuration.network_throughput or StaticModule(),
            plex_status=static_module_map.get("plex-status", StaticModule()),
            position=configuration.position or "top",
            quakes=static_module_map.get("quakes", StaticModule()),
            scripts_path=configuration.scripts_path or "~/.config/waybar/scripts",
            su=configuration.software_updates or StaticModule(),
            spacing=configuration.spacing or 5,
            speedtest=static_module_map.get("speedtest", StaticModule()),
            wifi=configuration.wifi_status or StaticModule(),
            weather=configuration.weather or StaticModule(),
        )

    except Exception as e:
        print(
            f'Failed to render the output using "{template_file}" as the template and "{yaml_file}" as the yaml input: {str(e)}'
        )
        sys.exit(1)

    if dryrun:
        print(json.dumps(json.loads(output), indent=4))
        sys.exit(0)

    if os.access(os.path.dirname(output_file), os.W_OK):
        if output_file.exists():
            print(
                f'The output file "{output_file}" already exists, please try a different path'
            )
            sys.exit(1)
        else:
            try:
                with open(output_file, "w") as f:
                    _ = f.write(json.dumps(json.loads(output), indent=4) + "\n")
                    print(f'Successfully wrote the output file "{output_file}"')
            except Exception as e:
                print(f'Failed to write the output file "{output_file}": {str(e)}')
                sys.exit(1)
    else:
        print(f'The output directory "{os.path.dirname(output_file)}" isn\'t writable')
        sys.exit(1)


@click.command(
    help="Render a waybar config file from a jinja template",
    context_settings=context_settings,
)
@click.option(
    "-t",
    "--template",
    default=TEMPLATE_FILE,
    show_default=True,
    help="Specify an alternate template file (not recommended)",
)
@click.option(
    "-y",
    "--yaml",
    default=YAML_FILE,
    show_default=True,
    help="Specify an alternate yaml file (not recommended)",
)
@click.option(
    "-o",
    "--output",
    default=OUTPUT_FILE,
    show_default=True,
    help="Specify an output file",
)
@click.option(
    "-n", "--dryrun", is_flag=True, help="Print the config but do not write the file"
)
def main(template: Path, yaml: Path, output: Path, dryrun: bool):
    global keystore

    keystore = SecureKeyStore(db_path=DEFAULT_DB, key_path=DEFAULT_KEY)
    template = Path(template)
    yaml = Path(yaml)
    output = Path(output)

    render_template(
        template_file=template, yaml_file=yaml, output_file=output, dryrun=dryrun
    )


if __name__ == "__main__":
    main()
