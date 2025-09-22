# Configuring waybar

## Introduction
Writing the configuration was a bit of a pain, looking at other peoples' examples trying to piece together relevant bits. After playing around with a bunch of different things, I decided to templatize the generation of a config file. I looked around at different options and settled on [jinja](https://jinja.palletsprojects.com) as the template engine, [YAML](https://yaml.org) for the input, and [SQLite3](https://sqlite.org) for the keystore. I tried to use the Linux keyring but the Python keyring package would throw exceptions if KWallet wasn't running. Please execute the Python scripts with the `--help` flag before trying to use them. If a script has actions, you can do something like `manage-keystore.py set --help` to get help for the specified action.

## Components
Here is a list of the components and their respective purposes.
1. `keystore` - A library used for managing secure keys using an encrypted database as its backend.
2. `manage-keystore.py` - Script that uses `keystore.SecureKeyStore()` to manage the keystore. You will use it to add API keys, etc.
3. `config.yaml` - This is the input file we'll use to generate a `config.jsonc` file in this directory. It will technically generate a json file for now, but I will adapt it to preserve comments and such later.
4. `config.jsonc.j2` - This is the jinja template. It supports every module that I have in the repository and will be updated as needed.
5. `render-config.py` - Script that actually renders a config file using the YAML input and jinja template.

## Key Storage
Storing a key

```
% manage-keystore.py set -s waybar -k dummy_api -v foo
Successfully stored key "dummy_api" in the service "waybar"
```

Retrieving a key
```
% manage-keystore.py get -s waybar -k dummy_api
foo
```

## Keys in config.yaml
If you look at config.yaml, you will see a block for weather that looks like this
```
weather:
  api_key: "{key:wapi_key}"
  locations:
  - location: "San Diego, CA, US"
    enabled: true
    label: san-diego
    interval: 300
  - location: "Los Angeles, CA, US"
    enabled: false
    label: los-Angeles
    interval: 300
```
When you execute `render-config.py`, it traverses the YAML looking for any value in the format of `{key:xxxxx}` and attempts to retrieve the key from the keystore via `value = keystore.get('waybar', key_name)` and raises an exception if the key doesn't exist under the `waybar` service. You MUST use the waybar service for all of your keys since `render-config.py` has it hard coded. If the required keys exist in the keystore, the configuration file will be rendered with them in place. If you have an existing config.jsonc file, you can simply copy the generated bits to your file. I know it works because my config was generated via this script. As long as you don't monkey with the template or add dumb stuff to your YAML, you should be fine.

## Notes
1. I stated previously, you should use the `waybar` service when storing keys.
2. The `custom/nothing` entry at the end of the template is there because each module puts a comma at the end of its block. This is because we don't know which module will be the "last" in the list. A comma at end of the last block will break the JSON parsing. I put `custom/nothing` in there as a quick and dirty way to always ensure the JSON will render properly.
