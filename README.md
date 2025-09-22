# waybar
I use [Xbar](https://xbarapp.com) and [SwiftBar](https://swiftbar.app) on my Macs and I really enjoy their functionality. I was looking for something similar in the Linux world and stumbled across [Polybar](https://polybar.github.io). I used it for some time but I found some limitations I didn't care for. I then discovered Waybar and tried it in a VM, since distro I was using didn't support Wayland. Well, I've since switched to a distro that supports Wayland and here we are. I hope you enjoy my work.

## Installation
What I do is pretty straight forward:
1. `cd ~/.config`
2. `git clone https://github.com/gdanko/waybar.git`

But if you're already using Waybar and have your setup in ~/.config/waybar`, do the following:
1. Clone the repository.
2. Copy the scripts directory to your Waybar directory. There are some common files in `./scripts/waybar` so you kind of need it all.

There is a `configure` directory in the repository that has a means to generate a config.jsonc file from a template file. It has its own README.md so go take a look at that when you have a momemnt.

## Modules
Each module has a `--help` option, so you can see available options.

### CPU Usage
This module shows CPU information with four available output formats that can be toggled by clicking the item in the bar.

#### Output Formats
1. `user 0.99%, sys 0.46%, idle 98.43%`
2. `load 0.20,  0.27,  0.44`
3. `8C/16T x AMD Ryzen 7 5700U`
4. `current: 3.29 GHz, min: 400 Mhz, max: 4.37 GHz`

### Filesystem Usage
This module shows filesystem usage information with three available output formats that can be toggled by clicking the item in the bar.

#### Output Formats
1. `/foo 779.39 GiB / 3.58 TiB`
2. `/foo 22% used`
3. `/foo 779.41 GiB used / 2.64 TiB free`

### Memory Usage
This module shows memory usage information with four available output formats that can be toggled by clicking the item in the bar. This module relies on `dmidecode` so please see the [permissions](#permissions) section before implementing this module.

#### Output Formats
1. `8.04 GiB / 59.75 GiB`
2. `13% used`
3. `8.03 GiB used / 51.72 GiB free`
4. `2 x 32GB SODMIMM @ 3200 MT/s`

### Network Throughput
This module shows network throughtput, received and sent.

#### Output Formats
1. `wlo1 9.65 Kbit/s ↑8.42 Kbit/s`

### Speedtest
This module connects to [speedtest.net](https://speedtest.net) and gathers download and/or upload speeds. You can left click on it to refresh its output.

#### Output Formats
1. `<icon> ↓403.13 Mbit/s ↑493.98 Mbit/s`

#### Notes
The speedometer icon is dynamic. It shows slow, medium, or fast depending on the following:
- If only the download test is enabled, the icon is based on download speed.
- If only the upload test is enabled, the icon is based on the upload speed.
- If both download and upload tests are enabled, the icon is based on and average of both speeds.

### Swap Usage
This module shows swap usage information with three available output formats that can be toggled by clicking the item in the bar.

#### Output Formats
1. `0.00 B / 1.91 GiB`
2. `0% used`
3. `0.00 B used / 1.91 GiB free`

### System Updates
This module displays the number of available outputs for the following package managers: `apt`, `brew`, `dnf`, `flatpak`, `mintupdate`, `pacman`, `snap`, `yay`, `yay-aur`, `yum`. Please see the [permissions](#permissions) section before implementing this module.

#### Output Formats
1. `apt 0 outdated packages`

### Weather
This module retrieves weather from [weatherapi.com](https://www.weatherapi.com) and has six available output formats.

#### Output Formats
1. `San Diego 73.0°F`
2. `San Diego ↑76.5°F ↓64.6°F`
3. `San Diego <wind icon> 9.6 mph @ 267°`
4. `San Diego <sunrise icon> 06:32 <sunset icon> 18:55`
5. `San Diego <moonrise icon> 23:06 <moonset icon> 14:25`
6. `San Diego humidity 52%`

### Wi-Fi Status
This module displays the signal strength in dBm for the specified interface and has two available output formats.

#### Output Formats
1. `wlo1 -48 dBm`
2. `wlo1 channel 48 (5240 MHz) 160 MHz width`
