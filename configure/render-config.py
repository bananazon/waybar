#!/usr/bin/env python3

from jinja2 import Template
from pathlib import Path
from pprint import pprint
import click
import json
import os
import sys
import yaml as y

# Paths
BASE_DIR      = Path.home() / '.config/waybar'
SCRIPTS_DIR   = BASE_DIR / 'scripts'
CONFIG_DIR    = BASE_DIR / 'config'
TEMPLATE_FILE = CONFIG_DIR / 'config.jsonc.j2'
OUTPUT_FILE   = CONFIG_DIR / 'config.jsonc'
YAML_FILE     = CONFIG_DIR / 'config.yaml'

CONTEXT_SETTINGS = dict(help_option_names=['-h', '--help'])

def load_yaml(input=None):
    if input.exists():
        try:
            with open(input, 'r') as f:
                return y.safe_load(f)
        except Exception as e:
            click.echo(f'Failed to parse the YAML file: {str(e)}')
            sys.exit(1)
    else:
        click.echo(f'yaml file "{input}" doesn\'t exist')
        sys.exit(1)

def load_template(input=None):
    if input.exists():
        try:
            with open(input, 'r') as f:
                return f.read()
        except Exception as e:
            click.echo(f'Failed to parse the template file: {str(e)}')
            sys.exit(1)
    else:
        click.echo(f'template file "{input}" doesn\'t exist')
        sys.exit(1)

def render_template(template_file, yaml_file, output_file):
    yaml_data = load_yaml(input=yaml_file)
    template_str = load_template(input=template_file)

    static_modules = yaml_data.get('static_modules', [])
    scripts_path = yaml_data.get('scripts_path', SCRIPTS_DIR)
    static_module_map = {item['name']: item for item in static_modules}
    modules_right = []

    # Build modules_right
    if yaml_data.get('static_modules') is not None:
        for module in yaml_data['static_modules']:
            if module['enabled']:
                name = module['name']
                modules_right.append(f'custom/{name}')

    if yaml_data.get('filesystems') is not None:
        for filesystem in yaml_data['filesystems']:
            if filesystem['enabled']:
                label = filesystem['label']
                modules_right.append(f'custom/filesystem-usage-{label}')

    if yaml_data.get('network_interfaces') is not None:
        for iface in yaml_data['network_interfaces']:
            if iface['enabled']:
                name = iface['name']
                if iface['type'] == 'wifi':
                    modules_right.append(f'custom/wifi-status-{name}')
                modules_right.append(f'custom/network-throughput-{name}')

    if yaml_data.get('software_updates') is not None:
        for item in yaml_data['software_updates']:
            package_type = item['type']
            modules_right.append(f'custom/software-updates-{package_type}')

    if yaml_data.get('weather') is not None:
        if yaml_data['weather'].get('locations') is not None:
            for item in yaml_data['weather']['locations']:
                label = item['label']
                modules_right.append(f'custom/weather-{label}')
    
    modules_right = sorted(modules_right)

    try:
        config_template = Template(template_str, trim_blocks=False, lstrip_blocks=False)
    except Exception as e:
        print(f'Failed to generate the jinja template from "{template_file}": {str(e)}')
        sys.exit(1)
    
    try:
        output = config_template.render(
            filesystems        = yaml_data.get('filesystems', []),
            modules_right      = modules_right,
            network_interfaces = yaml_data.get('network_interfaces', []),
            scripts_path       = yaml_data.get('scripts_path', '~/.config/waybar/scripts'), 
            software_updates   = yaml_data.get('software_updates', []),
            static_modules     = static_module_map,
            weather            = yaml_data.get('weather', []),
        )
    except Exception as e:
        print(f'Failed to render the output using "{template_file}" as the template and "{yaml_file}" as the yaml input: {str(e)}')
        sys.exit(1)
    
    if os.access(os.path.dirname(output_file), os.W_OK):
        if output_file.exists():
            print(f'The output file "{output_file}" already exists, please try a different path')
            sys.exit(1)
        else:
            try:
                with open(output_file, 'w') as f:
                    f.write(json.dumps(json.loads(output), indent=4) + '\n')
                    print(f'Successfully wrote the output file "{output_file}"')
            except Exception as e:
                print(f'Failed to write the output file "{output_file}": {str(e)}')
                sys.exit(1)
    else:
        print(f'The output directory "{os.path.dirname(output_file)}" isn\'t writable')
        sys.exit(1)

@click.command(help='Render a waybar config file from a jinja template', context_settings=CONTEXT_SETTINGS)
@click.option('-t', '--template', default=TEMPLATE_FILE, show_default=True, help='Specify an alternate template file (not recommended)')
@click.option('-y', '--yaml', default=YAML_FILE, show_default=True, help='Specify an alternate yaml file (not recommended)')
@click.option('-o', '--output', default=OUTPUT_FILE, show_default=True, help='Specify an output file')
def main(template, yaml, output):
    template = Path(template)
    yaml = Path(yaml)
    output = Path(output)

    render_template(template, yaml, output)
    
if __name__ == '__main__':
    main()
