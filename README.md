# waybar
I use [Xbar](https://xbarapp.com) and [SwiftBar](https://swiftbar.app) on my Macs and I really enjoy their functionality. I was looking for something similar in the Linux world and stumbled across [Polybar](https://polybar.github.io). I used it for some time but I found some limitations I didn't care for. I then discovered Waybar and tried it in a VM, since the distro I was using didn't support Wayland. Well, I've since switched to a distro that supports Wayland and here we are. I hope you enjoy my work.

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
2. `mpstat` (part of the `sysstat` package)

## Installation
What I do is pretty straight forward:
1. `cd ~/.config`
2. `git clone https://github.com/gdanko/waybar.git`
3. `systemctl --user daemon-reload`
4. `systemctl --user enable waybar.service`
5. `systemctl --user start waybar.service`

But if you're already using Waybar and have your setup in ~/.config/waybar`, do the following:
1. Clone the repository.
2. Copy the scripts directory to your Waybar directory. There are some common files in `./scripts/waybar` so you kind of need it all.

## Installing the User System Unit File (optional)
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
  core 00 user 1.40%, sys 0.88%, idle 96.45%
  core 01 user 0.94%, sys 0.66%, idle 97.52%
  core 02 user 1.39%, sys 0.90%, idle 96.73%
  core 03 user 0.91%, sys 0.64%, idle 97.62%
  core 04 user 1.38%, sys 0.87%, idle 96.83%
  core 05 user 0.88%, sys 0.65%, idle 97.61%
  core 06 user 1.38%, sys 0.87%, idle 96.82%
  core 07 user 0.89%, sys 0.66%, idle 97.58%
  core 08 user 1.56%, sys 1.00%, idle 96.45%
  core 09 user 1.00%, sys 0.73%, idle 97.40%
  core 10 user 1.46%, sys 1.00%, idle 96.50%
  core 11 user 0.97%, sys 0.72%, idle 97.42%
  core 12 user 1.53%, sys 0.96%, idle 96.55%
  core 13 user 0.95%, sys 0.70%, idle 97.45%
  core 14 user 1.54%, sys 0.97%, idle 96.51%
  core 15 user 1.12%, sys 0.79%, idle 97.22%
```

### Filesystem Usage
This module shows filesystem usage information with three available output formats that can be toggled by clicking the item in the bar.

#### Output Formats
1. `/foo 779.39 GiB / 3.58 TiB`
2. `/foo 22% used`
3. `/foo 779.41 GiB used / 2.64 TiB free`

#### Tooltip
```
Device      : /dev/mapper/luks-c7e5b1d9-cbce-4419-8982-0175169c92de
Mountpoint  : /
Type        : btrfs
Kernel name : dm-0
Removable   : no
Read-only   : no
```

### Memory Usage
This module shows memory usage information with three available output formats that can be toggled by clicking the item in the bar. This module relies on `dmidecode` so please see the [`permissions`](#permissions) section before implementing this module.

#### Output Formats
1. `8.04 GiB / 59.75 GiB`
2. `13% used`
3. `8.03 GiB used / 51.72 GiB free`

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

### Software Updates
This module displays the number of available outputs for the following package managers: `apt`, `brew`, `dnf`, `flatpak`, `mintupdate`, `pacman`, `snap`, `yay`, `yay-aur`, `yum`. Please see the [`permissions`](#permissions) section before implementing this module.

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

### Swap Usage
This module shows swap usage information with three available output formats that can be toggled by clicking the item in the bar.

#### Output Formats
1. `0.00 B / 1.91 GiB`
2. `0% used`
3. `0.00 B used / 1.91 GiB free`

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

## Permissions
You will need to add yourself to `/etc/sudoers` in order to execute some commands. Do something like this. Obviously pick only the ones you need.

### For Software Updates
```
# mint has a wrapper in /usr/local/bin
user ALL=(ALL) NOPASSWD: /usr/local/bin/apt
user ALL=(ALL) NOPASSWD: /usr/bin/apt
user ALL=(ALL) NOPASSWD: /usr/bin/dnf
user ALL=(ALL) NOPASSWD: /usr/bin/flatpak
user ALL=(ALL) NOPASSWD: /usr/bin/mintupdate-cli
user ALL=(ALL) NOPASSWD: /usr/bin/snap
user ALL=(ALL) NOPASSWD: /usr/bin/yay
user ALL=(ALL) NOPASSWD: /usr/bin/yum
```

### For Memory Usage
```
user ALL=(ALL) NOPASSWD: /usr/sbin/dmidecode
```
