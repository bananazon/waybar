# waybar
I use [Xbar](https://xbarapp.com) and [SwiftBar](https://swiftbar.app) on my Macs and I really enjoy their functionality. I was looking for something similar in the Linux world and stumbled across [Polybar](https://polybar.github.io). I used it for some time but I found some limitations I didn't care for. I then discovered Waybar and tried it in a VM, since the distro I was using didn't support Wayland. Well, I've since switched to a distro that supports Wayland and here we are. I hope you enjoy my work.

## Some Fun Features
* Some modules take a little time to fetch their data. When Waybar loads up for the first time, there's no data available so the module will display some sort of `Working...` text, which will be in a lighter color. Its icon will be a timer. On subsequent refreshes, the icon changes to a timer, and the text lightens until the data has been updated. However, you don't see the generic `Working...` text, you see the last results. Try it and see.
* Some modules, e.g., `memory-usage` have multiple output formats. You can click on its text to cycle between them. I ran into an issue where when I added showing read/write statistics in the `filesystem-usage` tooltip. See, to gather statistics, you read `/proc/diskstats`, pause for a second, and read it again. Then you do math, etc, etc.. Well, if you try to toggle the output format like you do `memory-usage`, the module logic is re-run and the output format wouldn't update until after the statistics are gathered. I found a way to accommodate all of the features I wanted by
    1. Using Python `threading.Condition()` to allow me to deal with `needs_redraw` and `needs_fetch` conditions.
    2. Trapping `SIGHUP` to refresh the data
    3. Trapping `SIGUSR1` to change the output format and refresh the data

## Prerequisites
The following Python modules are required
1. [`click`](https://pypi.org/project/click)
2. [`cryptography`](https://pypi.org/project/cryptography)
3. [`Jinja2`](https://pypi.org/project/Jinja2)
4. [`psutil`](https://pypi.org/project/psutil)
5. [`PyYAML`](https://pypi.org/project/PyYAML)
6. [`speedtest-cli`](https://pypi.org/project/speedtest-cli)

The following binaries are required and may not be installed by default
1. `dmidecode`
2. [`jc`](https://github.com/kellyjonbrazil/jc) (I installed with `sudo dnf install jc`)
3. `mpstat` (part of the `sysstat` package)

## Installation
What I do is pretty straight forward. This is not carved in stone, but you get the idea.
1. `cd ~/.config`
2. `git clone https://github.com/gdanko/waybar.git`
3. `python3 -m pip install click cryptography Jinja2 psutil PyYAML speedtest-cli --user`
4. `sudo dnf install dmidecode jc sysstat`
5. `cd ~/.config/waybar/configure` Please see the [`configure`](#the-configure-directory) directory section
6. Edit `config.yaml` to my liking
7. `./render-config.py`
8. Copy the resultant `config.jsonc` to `~/.config/waybar`
9. `~/.config/waybar/launch.py start`

But if you're already using Waybar and have your setup in ~/.config/waybar`, do the following:
1. Clone the repository.
2. Copy the scripts directory to your Waybar directory. There are some common files in `./scripts/waybar` so you kind of need it all.

## The `configure` Directory
This directory allows you to generate a `config.jsonc` file from a Jinga2 template. Both python scripts contain `--help` flags.

### Contents
* `config.jsonc.j2` - Template that `render-config.py` uses to generate a `config.jsonc` file based on the `config.yaml` file.
* `config.yaml` - YAML template that feeds `render-config.py` in order to generate `config.jsonc`.
* `manage-keystore.py` - Script to manage a secure sqlite3-based keystore.
* `render-config.py` - Script to generate `config.jsonc`

#### Managing Keys
We don't want to put API keys and the link in `config.jsonc`, at least I don't. I created a basic keystore that uses an encrypted sqlite3 database to store sensitive values. To use the keystore with the templates, the service must always be `waybar` as it's hard-coded in `render-config.py` (for now).

##### Setting a Key
```
% ./manage-keystore.py set --service waybar --key foo --value bar
Successfully stored key "foo" in the service "waybar"
```

##### Getting a Key
```
% ./manage-keystore.py get --service waybar --key foo
bar
```

##### Updating a Key
```
% ./manage-keystore.py update --service waybar --key foo --value baz
Successfully updated key "foo" in the service "waybar"

% ./manage-keystore.py get --service waybar --key foo
baz
```

##### Deleting a Key
```
% ./manage-keystore.py delete --service waybar --key foo
Successfully deleted key "foo" from the service "waybar"

% ./manage-keystore.py get --service waybar --key foo
The key "foo" doesn't exist in the service "waybar"
```

#### Using Keys in `config.yaml`
Please see this excerpt for details. It's pretty straightforward.
```yaml
weather:
  api_key: "{key:wapi_key}"
  locations:
  - location: "San Diego, CA, US"
    enabled: true
    label: san-diego
    interval: 300
```

### Notes
* Some modules will accommodate multiple entries, e.g., `filesystem-usage` mountpoints or `weather` locations. If there are multiple entries, left clicking the item in the bar will cycle between the different configured entries. The config template will disable the `on-click` action if there is only one configured item because it makes little sense to enable the click when there is nothing to do.

## Installing the User System Unit File (optional and not fully working...yet)
1. `mkdir -p ~/.config/systemctl/user`
2. `copy waybar.service ~/.config/systemctl/user`

There is a `configure` directory in the repository that has a means to generate a config.jsonc file from a template file. It has its own README.md so go take a look at that when you have a moment.

## Modules
Each module has a `--help` option, so you can see available options.

### CPU Usage
This module shows CPU load.

#### Output Format
`user 0.99%, sys 0.46%, idle 98.43%`

#### Tooltip
```
AMD Ryzen 7 5700U with Radeon Graphics
Physical cores: 8, Threads/core: 2, Logical cores: 16
Frequency: 411.66 MHz > 4.37 GHz
CPU Load:
  core 00 user 3.48%, sys 1.98%, idle 92.10% (4.34 GHz)
  core 01 user 2.23%, sys 1.55%, idle 94.67% (2.35 GHz)
  core 02 user 3.41%, sys 1.97%, idle 93.17% (1.93 GHz)
  core 03 user 2.21%, sys 1.47%, idle 94.99% (1.93 GHz)
  core 04 user 3.39%, sys 1.95%, idle 93.29% (4.34 GHz)
  core 05 user 2.11%, sys 1.42%, idle 95.14% (4.34 GHz)
  core 06 user 3.39%, sys 1.98%, idle 93.29% (1.11 GHz)
  core 07 user 2.18%, sys 1.45%, idle 95.04% (1.93 GHz)
  core 08 user 3.64%, sys 2.15%, idle 92.61% (4.33 GHz)
  core 09 user 2.31%, sys 1.56%, idle 94.81% (4.34 GHz)
  core 10 user 3.47%, sys 2.08%, idle 93.09% (1.93 GHz)
  core 11 user 2.31%, sys 1.59%, idle 94.69% (1.93 GHz)
  core 12 user 3.49%, sys 2.08%, idle 93.09% (1.93 GHz)
  core 13 user 2.32%, sys 1.54%, idle 94.81% (1.11 GHz)
  core 14 user 3.55%, sys 2.07%, idle 93.03% (2.88 GHz)
  core 15 user 2.29%, sys 1.53%, idle 94.84% (2.08 GHz)
Caches:
  L1 - Cache - 512 kB @ 1 ns
  L2 - Cache - 4 MB   @ 1 ns
  L3 - Cache - 8 MB   @ 1 ns
```

### Disk Consumers
This module shows the top consumers for specified directories.

#### Output format
`/work/Dropbox/Documents`

#### Tooltip
```
Plex           637.90 GiB
Dropbox        165.01 GiB
home           23.47 GiB
Mismatched     2.60 GiB
Pictures       1.62 GiB
AppImages      653.47 MiB
OpenEmu        46.29 MiB
dfimage        9.21 MiB
old-time-radio 5.91 MiB
waybar-temp    1.51 MiB
Videos         1.27 MiB
```

#### Actions
* `on-click` - Switch between configured paths
* `on-click-right` - Refresh data

### Dropbox Status
This module show Dropbox status.

#### Output Format
`Syncing 881 files`

#### Tooltip
```
Uploading 881 files (624.6 KB/sec, 18 mins)
```

### Filesystem Usage
This module shows filesystem usage information and statistics.

#### Output Format
`/foo 779.39 GiB / 3.58 TiB`

#### Tooltip
```
Device        : /dev/mapper/luks-c7e5b1d9-cbce-4419-8982-0175169c92de
Mountpoint    : /
Type          : btrfs
Kernel name   : dm-0
Removable     : no
Read-only     : no
Reads/sec     : 0
Writes/sec    : 0
Read Time/sec : 0 ms
Write Time/sec: 0 ms
```

#### Actions
* `on-click` - Switch between configured mountpoints
* `on-click-right` - Refresh data

### Memory Usage
This module shows memory usage information. This module relies on `dmidecode` so please see the [`permissions`](#permissions) section before implementing this module.

#### Output Format
`8.04 GiB / 59.75 GiB`

#### Tooltip
```
Total     = 64.14 GB
Used      = 9.95 GB
Free      = 54.18 GB
Shared    = 0.49 GB
Buffers   = 0.01 GB
Cache     = 17.73 GB
Available = 54.18 GB

DIMM 00 - 32 GB DDR4 SODIMM @ 3200 MT/s
DIMM 01 - 32 GB DDR4 SODIMM @ 3200 MT/s
```

### Network Throughput
This module shows network throughtput, received and sent.

#### Output Format
`wlo1 ↓9.65 Kbit/s ↑8.42 Kbit/s`

#### Tooltip
```
Intel Corporation data.Wi-Fi 6 AX200 (NGW)
MAC Address  : xx:xx:xx:xx:xx:xx
IP (Public)  : xxx.xxx.xxx.xxx
IP (Private) : 192.168.1.20
Device Name  : Onboard LAN Brodcom
Driver       : iwlwifi
Alias        : /sys/subsystem/net/devices/wlo1
```

#### Actions
* `on-click` - Switch between configured interfaces

### Quakes
This module shows recent earthquakes near you. It uses your IP to geolocate you.

#### Output Format
`<icon> Earthquakes: 19`

#### Tooltip
```
2025-09-28 07:01 - mag 1.37 16 km NW of Ocotillo, CA
2025-09-28 06:53 - mag 0.89 27 km SSW of Ocotillo Wells, CA
2025-09-28 06:25 - mag 0.82 7 km ENE of Yucaipa, CA
2025-09-28 05:39 - mag 1.14 10 km NW of Calipatria, CA
2025-09-28 05:13 - mag 1.32 1 km NE of Colton, CA
2025-09-28 04:01 - mag 0.61 3 km E of Moreno Valley, CA
2025-09-28 01:55 - mag 1.13 5 km SW of Palomar Observatory, CA
2025-09-28 01:10 - mag 0.43 7 km NW of Anza, CA
2025-09-28 00:12 - mag 0.69 25 km SSW of Ocotillo Wells, CA
2025-09-28 00:09 - mag 0.86 6 km WNW of Borrego Springs, CA
```

#### Actions
* `on-click-right` - Refresh data

### Software Updates
This module displays the number of available outputs for the following package managers: `apk`, `apt`, `brew`, `dnf`, `emerge`, `flatpak`, `mintupdate`, `pacman`, `snap`, `xbps`, `yay`, `yay-aur`, `yum`. Please see the [`permissions`](#permissions) section before implementing this module.

#### Output Format
`dnf 801 outdated packages`

#### Tooltip
```
aardvark-dns              => 2:1.16.0-1.fc42
alsa-lib                  => 1.2.14-3.fc42
alsa-sof-firmware         => 2025.05.1-1.fc42
alsa-ucm                  => 1.2.14-3.fc42
alsa-utils                => 1.2.14-1.fc42
alternatives              => 1.33-1.fc42
amd-gpu-firmware          => 20250808-1.fc42
amd-ucode-firmware        => 20250808-1.fc42
anaconda                  => 42.27.13-1.fc42
anaconda-core             => 42.27.13-1.fc42
anaconda-gui              => 42.27.13-1.fc42
anaconda-install-env-deps => 42.27.13-1.fc42
anaconda-live             => 42.27.13-1.fc42
anaconda-tui              => 42.27.13-1.fc42
anaconda-widgets          => 42.27.13-1.fc42
apr                       => 1.7.6-3.fc42
at                        => 3.2.5-16.fc42
at-spi2-atk               => 2.56.3-1.fc42
at-spi2-core              => 2.56.3-1.fc42
atheros-firmware.noarch   => 20250808-1.fc42
and 764 more...
```

#### Actions
* `on-click` - Switch between configured package types
* `on-click-right` - Refresh data

### Speedtest
This module connects to [speedtest.net](https://speedtest.net) and gathers download and/or upload speeds. You can left click on it to refresh its output.

#### Output Format
`<icon> ↓403.13 Mbit/s ↑493.98 Mbit/s`

#### Tooltip
```
Bytes sent     : 144.50 MiB
Bytes received : 390.41 MiB
Upload speed   : 550.77 Mbit/s
Download speed : 380.33 Mbit/s
Ping           : 10.45 ms

Server
IP       : 195.206.104.222
Location : Los Angeles, California, US
Hostname : lax.mega.host.speedtest.net
Sponsor  : OneProvider

Client
IP       : 136.26.86.207
Location : San Diego, California, US
ISP      : AS19165 Webpass Inc.
```

#### Actions
* `on-click-right` - Refresh data

### Weather
This module retrieves weather from [weatherapi.com](https://www.weatherapi.com).

#### Output Format
`San Diego 73.0°F`

#### Tooltip
```
Location    : San Diego, CA, US
Condition   : Partly Cloudy
Feels like  : 78.0°F
High / Low  : 76.8°F / 62.2°F
Wind        : 8.7 mph @ 255°
Cloud Cover : 25%
Humidity    : 60%
Dew Point   : 63.4°F
UV Index    : 2.8 of 11
Visibility  : 9.0 miles
Sunrise     : 06:41
Sunset      : 18:36
Moonrise    : 13:08
Moonset     : 22:43
Moon Phase  : Waxing Crescent
```

#### Actions
* `on-click` - Switch between configured locations
* `on-click-right` - Refresh data

### Wi-Fi Status
This module displays the signal strength in dBm for the specified interface.

#### Output Format
`wlo1 -48 dBm`

#### Tooltip
```
Connected To      : <ssid> (xx:xx:xx:xx:xx:xx)
Connection Time   : 15h 27m 11s
Channel           : 48 (5240 MHz) 160 MHz width
Authenticated     : Yes
Authorized        : Yes
Available Ciphers :
  CCMP-128
  CMAC
  GCMP-128
  GCMP-256
  GMAC-128
  GMAC-256
  TKIP
  WEP104
  WEP40
```

#### Actions
* `on-click` - Switch between configured interfaces

## Permissions
You will need to add yourself to `/etc/sudoers` in order to execute some commands. Do something like this. Obviously pick only the ones you need.

I did this on my system:
```
% mkdir /work/sudoers.d
% touch /work/sudoers.d/sudoers
% sudo chown -R 0:0 /work/sudoers
```
I put my entries in `/work/sudoers.d/sudoers` and at the end of `/etc/sudoers`, add this line
```
#includedir /work/sudoers.d
```

### For Software Updates
```
# mint has a wrapper in /usr/local/bin
user ALL=(ALL) NOPASSWD: /usr/local/bin/apt
user ALL=(ALL) NOPASSWD: /usr/bin/apt
user ALL=(ALL) NOPASSWD: /usr/bin/dnf
user ALL=(ALL) NOPASSWD: /usr/bin/mintupdate-cli
user ALL=(ALL) NOPASSWD: /usr/bin/snap
user ALL=(ALL) NOPASSWD: /usr/bin/yay
user ALL=(ALL) NOPASSWD: /usr/sbin/emerge
```

### For Memory Usage
```
user ALL=(ALL) NOPASSWD: /usr/sbin/dmidecode
```
