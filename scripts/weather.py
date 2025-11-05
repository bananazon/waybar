#!/usr/bin/env python3

from collections import OrderedDict
from dacite import from_dict, Config
from dataclasses import dataclass, field
from typing import cast
from waybar import glyphs, http, util
import click
import json
import logging
import signal
import sys
import threading
import time

sys.stdout.reconfigure(line_buffering=True)  # type: ignore


@dataclass
class WeatherLocation:
    country: str = ""
    lat: str = ""
    localtime_epoch: int = 0
    locatime: str = ""
    lon: str = ""
    name: str = ""
    region: str = ""
    tz_id: str = ""


# Condition
@dataclass
class WeatherCondition:
    code: int = 0
    icon: str | None = None
    text: str | None = None


@dataclass
class WeatherCurrent:
    cloud: int = 0
    condition: WeatherCondition = field(default_factory=WeatherCondition)
    dewpoint_c: float = 0.0
    dewpoint_f: float = 0.0
    feelslike_c: float = 0.0
    feelslike_f: float = 0.0
    gust_kph: float = 0.0
    gust_mph: float = 0.0
    heatindex_c: float = 0.0
    heatindex_f: float = 0.0
    humidity: int = 0
    is_day: int = 0
    last_updated: str | None = None
    last_updated_epoch: int = 0
    precip_in: float = 0.0
    precip_mm: float = 0.0
    pressure_in: float = 0.0
    pressure_mb: float = 0.0
    temp_c: float = 0.0
    temp_f: float = 0.0
    uv: float = 0.0
    vis_km: float = 0.0
    vis_miles: float = 0.0
    wind_degree: int = 0
    wind_dir: str | None = None
    wind_kph: float = 0.0
    wind_mph: float = 0.0
    windchill_c: float = 0.0
    windchill_f: float = 0.0


# Forecast
@dataclass
class WeatherAstro:
    in_sun_up: bool = False
    is_moon_up: bool = False
    moon_illumination: int = 0
    moon_phase: str | None = None
    moonrise: str | None = None
    moonrise_unix: int = 0
    moonset: str | None = None
    moonset_unix: int = 0
    sunrise: str | None = None
    sunrise_unix: int = 0
    sunset: str | None = None
    sunset_unix: int = 0


@dataclass
class WeatherDay:
    avghumidity: int = 0
    avgtemp_c: float = 0.0
    avgtemp_f: float = 0.0
    avgvis_km: float = 0.0
    avgvis_miles: float = 0.0
    condition: WeatherCondition = field(default_factory=WeatherCondition)
    daily_chance_of_rain: int = 0
    daily_chance_of_snow: int = 0
    daily_will_it_rain: int = 0
    daily_will_it_snow: int = 0
    maxtemp: float = 0.0
    maxtemp_c: float = 0.0
    maxtemp_f: float = 0.0
    maxwind_kph: float = 0.0
    maxwind_mph: float = 0.0
    mintemp_c: float = 0.0
    mintemp_f: float = 0.0
    totalprecip_in: float = 0.0
    totalprecip_mm: float = 0.0
    totalsnow_cm: float = 0.0
    uv: float = 0.0


@dataclass
class WeatherForecastHour:
    chance_of_rain: int = 0
    chance_of_snow: int = 0
    cloud: int = 0
    condition: WeatherCondition = field(default_factory=WeatherCondition)
    dewpoint_c: float = 0.0
    dewpoint_f: float = 0.0
    feelslike_c: float = 0.0
    feelslike_f: float = 0.0
    gust_kph: float = 0.0
    gust_mph: float = 0.0
    heatindex_c: float = 0.0
    heatindex_f: float = 0.0
    humidity: int = 0
    is_day: int = 0
    precip_in: float = 0.0
    precip_mm: float = 0.0
    pressure_in: float = 0.0
    pressure_mb: float = 0.0
    snow_cm: float = 0.0
    temp_c: float = 0.0
    temp_f: float = 0.0
    time_epoch: int = 0
    timestamp: str | None = None
    uv: int = 0
    vis_km: float = 0.0
    vis_miles: float = 0.0
    will_it_rain: int = 0
    will_it_snow: int = 0
    wind_degree: int = 0
    wind_dir: str | None = None
    wind_kph: float = 0.0
    wind_mph: float = 0.0
    windchill_c: float = 0.0
    windchill_f: float = 0.0


@dataclass
class WeatherForecastDay:
    astro: WeatherAstro = field(default_factory=WeatherAstro)
    date: str | None = None
    date_epoch: int = 0
    day: WeatherDay = field(default_factory=WeatherDay)
    hour: list[WeatherForecastHour] = field(default_factory=list)


@dataclass
class WeatherForecast:
    forecastday: list[WeatherForecastDay] = field(default_factory=list)


@dataclass
class WeatherData:
    location: WeatherLocation = field(default_factory=WeatherLocation)
    current: WeatherCurrent = field(default_factory=WeatherCurrent)
    forecast: WeatherForecast = field(default_factory=WeatherForecast)


@dataclass
class LocationData:
    success: bool = False
    error: str | None = None
    icon: str = ""
    location_short: str = ""
    location_full: str = ""
    updated: str | None = None
    weather: WeatherData = field(default_factory=WeatherData)


cache_dir = util.get_cache_directory()
condition = threading.Condition()
context_settings = dict(help_option_names=["-h", "--help"])
format_index: int = 0
logfile = cache_dir / "waybar-weather.log"
needs_fetch: bool = False
needs_redraw: bool = False
weather_data: list[LocationData] | None = []

formats: list[int] = []

update_event = threading.Event()


def configure_logging(debug: bool = False):
    logging.basicConfig(
        filename=logfile,
        filemode="w",  # 'a' = append, 'w' = overwrite
        format="%(asctime)s [%(levelname)-5s] - %(message)s",
        level=logging.DEBUG if debug else logging.INFO,
    )


def refresh_handler(_signum: int, _frame: object | None):
    global needs_fetch, needs_redraw
    logging.info("[refresh_handler] - received SIGHUP — re-fetching data")
    with condition:
        needs_fetch = True
        needs_redraw = True
        condition.notify()


def toggle_format(_signum: int, _frame: object | None):
    global formats, format_index, needs_redraw
    format_index = (format_index + 1) % len(formats)
    if weather_data and type(weather_data) is list:
        location = weather_data[format_index].location_full
    else:
        location = format_index + 1
    logging.info(
        f"[toggle_format] - received SIGUSR1 - switching output format to {location}"
    )
    with condition:
        needs_redraw = True
        condition.notify()


_ = signal.signal(signal.SIGHUP, refresh_handler)
_ = signal.signal(signal.SIGUSR1, toggle_format)


def generate_tooltip(location_data: LocationData, use_celsius: bool):
    # pprint(location_data)
    # exit()
    logging.debug(
        f"[generate_tooltip] - entering with mountpoint={location_data.location_full}"
    )
    tooltip: list[str] = []
    tooltip_od: OrderedDict[str, str | int | float] = OrderedDict()

    if use_celsius:
        distance = "km"
        unit = "C"
        speed = "kph"
        dewpoint = location_data.weather.current.dewpoint_c
        feels_like = location_data.weather.current.feelslike_c
        max_temp = location_data.weather.forecast.forecastday[0].day.maxtemp_c
        min_temp = location_data.weather.forecast.forecastday[0].day.mintemp_c
        visibility = location_data.weather.current.vis_km
        wind_speed = location_data.weather.current.wind_kph
    else:
        distance = "miles"
        unit = "F"
        speed = "mph"
        dewpoint = location_data.weather.current.dewpoint_f
        feels_like = location_data.weather.current.feelslike_f
        max_temp = location_data.weather.forecast.forecastday[0].day.maxtemp_f
        min_temp = location_data.weather.forecast.forecastday[0].day.mintemp_f
        visibility = location_data.weather.current.vis_miles
        wind_speed = location_data.weather.current.wind_mph

    sunrise_unix = location_data.weather.forecast.forecastday[0].astro.sunrise_unix
    sunset_unix = location_data.weather.forecast.forecastday[0].astro.sunset_unix
    moonrise_unix = location_data.weather.forecast.forecastday[0].astro.moonrise_unix
    moonset_unix = location_data.weather.forecast.forecastday[0].astro.moonset_unix
    moon_phase = location_data.weather.forecast.forecastday[0].astro.moon_phase

    if location_data.location_full:
        tooltip_od["Location"] = location_data.location_full
    elif location_data.location_short:
        tooltip_od["Location"] = location_data.location_short

    if location_data.weather.current.condition.text:
        tooltip_od["Condition"] = location_data.weather.current.condition.text

    if feels_like:
        tooltip_od["Feels Like"] = f"{feels_like}°{unit}"

    if max_temp and min_temp:
        tooltip_od["High / Low"] = f"{max_temp}°{unit} / {min_temp}°{unit}"

    if wind_speed and location_data.weather.current.wind_degree:
        tooltip_od["Wind"] = (
            f"{wind_speed} {speed} @ {location_data.weather.current.wind_degree}°"
        )

    if location_data.weather.current.cloud:
        tooltip_od["Cloud Cover"] = f"{location_data.weather.current.cloud}%"

    if location_data.weather.current.humidity:
        tooltip_od["Humidity"] = f"{location_data.weather.current.humidity}%"

    if dewpoint:
        tooltip_od["Dew Point"] = f"{dewpoint}°{unit}"

    if location_data.weather.current.uv:
        tooltip_od["UV Index"] = f"{location_data.weather.current.uv} of 11"

    if visibility:
        tooltip_od["Visibility"] = f"{visibility} {distance}"

    if sunrise_unix and sunset_unix:
        sunrise = util.to_24hour_time(input=sunrise_unix)
        sunset = util.to_24hour_time(input=sunset_unix)
        if sunrise and sunset:
            tooltip_od["Sunrise"] = sunrise
            tooltip_od["Sunset"] = sunset

    if moonrise_unix and moonset_unix:
        moonrise = util.to_24hour_time(input=moonrise_unix)
        moonset = util.to_24hour_time(input=moonset_unix)
        if moonrise and moonset:
            tooltip_od["Moonrise"] = moonrise
            tooltip_od["Moonset"] = moonset

    if moon_phase:
        tooltip_od["Moon Phase"] = moon_phase

    max_key_length = 0
    for key in tooltip_od.keys():
        max_key_length = len(key) if len(key) > max_key_length else max_key_length

    for key, value in tooltip_od.items():
        tooltip.append(f"{key:{max_key_length}} : {value}")

    if len(tooltip) > 0:
        tooltip.append("")
        tooltip.append(f"Last updated {location_data.updated}")

    return "\n".join(tooltip)


def get_weather_icon(condition_code: int, is_day: bool) -> str:
    # https://www.weatherapi.com/docs/weather_conditions.json
    if condition_code == 1000:  # Sunny
        if is_day == 1:
            return glyphs.md_weather_sunny
        else:
            return glyphs.md_weather_night

    elif condition_code == 1003:
        if is_day == 1:  # Partly cloudy
            return glyphs.md_weather_partly_cloudy
        else:
            return glyphs.md_weather_night_partly_cloudy

    elif condition_code == 1006:  # Cloudy
        if is_day == 1:
            return glyphs.weather_day_cloudy
        else:
            return glyphs.weather_night_cloudy

    elif condition_code == 1009:  # Overcast
        if is_day == 1:
            return glyphs.weather_day_sunny_overcast
        else:
            return glyphs.weather_night_cloudy

    elif condition_code == 1030:  # Mist
        if is_day == 1:
            return glyphs.md_weather_hazy
        else:
            return glyphs.md_weather_hazy

    elif condition_code == 1063:  # Patchy rain possible
        if is_day == 1:
            return glyphs.md_weather_partly_rainy
        else:
            return glyphs.md_weather_partly_rainy

    elif condition_code == 1066:  # Patchy snow possible
        if is_day == 1:
            return glyphs.md_weather_partly_snowy
        else:
            return glyphs.md_weather_partly_snowy

    elif condition_code == 1114:  # Blowing snow
        if is_day == 1:
            return glyphs.weather_snow_wind
        else:
            return glyphs.weather_day_snow_wind

    elif condition_code in [
        1069,
        1204,
        1249,
    ]:  # Patchy sleet possible / Light sleet /Light sleet showers
        if is_day == 1:
            return glyphs.weather_day_sleet
        else:
            return glyphs.weather_night_sleet

    elif condition_code in [
        1207,
        1252,
    ]:  # Moderate or heavy sleet / Moderate or heavy sleet showers
        if is_day == 1:
            return glyphs.weather_day_sleet_storm
        else:
            return glyphs.weather_night_alt_sleet_storm

    elif (
        condition_code in [1210, 1213, 1216, 1219, 1222, 1225]
    ):  # Patchy light snow / Light snow / Patchy moderate snow / Moderate snow / Patchy heavy snow / Heavy snow
        if is_day == 1:
            return glyphs.weather_day_snow
        else:
            return glyphs.weather_night_snow

    elif condition_code == 1240:  # Light rain shower
        if is_day == 1:
            return glyphs.weather_day_rain
        else:
            return glyphs.weather_night_rain

    elif condition_code == 1243:  # Moderate or heavy rain shower
        if is_day == 1:
            return glyphs.weather_day_showers
        else:
            return glyphs.weather_night_showers

    elif condition_code == 1246:  # Torrential rain shower
        if is_day == 1:
            return glyphs.weather_day_storm_showers
        else:
            return glyphs.weather_night_storm_showers

    return glyphs.md_weather_sunny


def get_weather(api_key: str, location: str) -> LocationData:
    logging.info(f"[get_weather] - entering function with location={location}")

    location_data: LocationData = LocationData()
    response = http.request(
        method="GET",
        url="https://api.weatherapi.com/v1/forecast.json",
        params={
            "key": api_key,
            "q": location,
            "aqi": "no",
            "alerts": "no",
        },
    )
    if response:
        if response.status == 200:
            if response.body:
                json_data = cast(dict[str, object], json.loads(response.body))
                weather = from_dict(
                    data_class=WeatherData,
                    data=json_data,
                    config=Config(cast=[int, str]),
                )

                for idx, _ in enumerate(weather.forecast.forecastday):
                    if weather.forecast.forecastday[idx].astro.moonrise:
                        weather.forecast.forecastday[
                            idx
                        ].astro.moonrise_unix = util.to_unix_time(
                            input=weather.forecast.forecastday[idx].astro.moonrise
                        )
                    if weather.forecast.forecastday[idx].astro.moonset:
                        weather.forecast.forecastday[
                            idx
                        ].astro.moonset_unix = util.to_unix_time(
                            input=weather.forecast.forecastday[idx].astro.moonset
                        )
                    if weather.forecast.forecastday[idx].astro.sunrise:
                        weather.forecast.forecastday[
                            idx
                        ].astro.sunrise_unix = util.to_unix_time(
                            input=weather.forecast.forecastday[idx].astro.sunrise
                        )
                    if weather.forecast.forecastday[idx].astro.sunset:
                        weather.forecast.forecastday[
                            idx
                        ].astro.sunset_unix = util.to_unix_time(
                            input=weather.forecast.forecastday[idx].astro.sunset
                        )

                return LocationData(
                    success=True,
                    icon=get_weather_icon(
                        condition_code=weather.current.condition.code,
                        is_day=True if weather.current.is_day == 1 else False,
                    ),
                    location_short=weather.location.name,
                    location_full=location,
                    weather=weather,
                    updated=util.get_human_timestamp(),
                )

    return location_data


def render_output(
    location_data: LocationData, use_celsius: bool, icon: str
) -> tuple[str, str, str]:
    text: str = ""
    output_class: str = ""
    tooltip: str = ""

    current_temp = (
        location_data.weather.current.temp_c
        if use_celsius
        else location_data.weather.current.temp_f
    )
    if location_data.success:
        text = f"{icon}{glyphs.icon_spacer}{location_data.location_short} {current_temp}°{'C' if use_celsius else 'F'}"
        output_class = "success!"
        tooltip = generate_tooltip(location_data=location_data, use_celsius=use_celsius)
    else:
        text = f"{glyphs.md_alert}{glyphs.icon_spacer}{location_data.location_full} {location_data.error if location_data.error is not None else 'Unknown error'}"
        output_class = "error"
        tooltip = f"{location_data.location_full} error"

    return text, output_class, tooltip


def worker(api_key: str, locations: list[str], use_celsius: bool):
    global weather_data, needs_fetch, needs_redraw, format_index

    while True:
        with condition:
            while not (needs_fetch or needs_redraw):
                _ = condition.wait()

            fetch = needs_fetch
            redraw = needs_redraw
            needs_fetch = False
            needs_redraw = False

        logging.info("[worker] - entering worker loop")
        if not util.waybar_is_running():
            logging.info("[worker] - waybar not running")
            sys.exit(0)
        else:
            if not util.network_is_reachable():
                output = {
                    "text": f"{glyphs.md_alert}{glyphs.icon_spacer}the network is unreachable",
                    "class": "error",
                    "tooltip": "Weather update error",
                }
                print(json.dumps(output))
                weather_data = None
                continue

            if fetch:
                weather_data = []
                for location in locations:
                    print(
                        json.dumps(
                            {
                                "text": f"{glyphs.md_timer_outline}{glyphs.icon_spacer}Fetching {location}...",
                                "class": "loading",
                                "tooltip": f"Fetching {location}...",
                            }
                        )
                    )
                    location_data = get_weather(api_key=api_key, location=location)
                    weather_data.append(location_data)

            if weather_data and len(weather_data) > 0:
                if redraw:
                    icon = weather_data[format_index].icon or glyphs.md_alert
                    text, output_class, tooltip = render_output(
                        location_data=weather_data[format_index],
                        use_celsius=use_celsius,
                        icon=icon,
                    )
                    output = {
                        "text": text,
                        "class": output_class,
                        "tooltip": tooltip,
                    }
                    print(json.dumps(output))


@click.command(
    help="Get weather info from World Weather API", context_settings=context_settings
)
@click.option("-a", "--api-key", required=True, help="World Weather API key")
@click.option(
    "-l",
    "--location",
    required=True,
    multiple=True,
    default=["San Diego, CA, US", "Los Angeles, CA, US"],
    help="The location to query",
)
@click.option(
    "-c",
    "--use-celsius",
    default=False,
    is_flag=True,
    help="Use Celsius instead of Fahrenheit",
)
@click.option(
    "-i", "--interval", type=int, default=300, help="The update interval (in seconds)"
)
@click.option(
    "-t", "--test", default=False, is_flag=True, help="Print the output and exit"
)
@click.option("-d", "--debug", default=False, is_flag=True, help="Enable debug logging")
def main(
    api_key: str,
    location: str,
    use_celsius: bool,
    interval: int,
    test: bool,
    debug: bool,
):
    global formats, needs_fetch, needs_redraw

    configure_logging(debug=debug)
    formats = list(range(len(location)))

    logging.info("[main] - entering function")

    if test:
        weather_data = get_weather(api_key=api_key, location=location[0])
        text, output_class, tooltip = render_output(
            location_data=weather_data,
            use_celsius=use_celsius,
            icon=weather_data.icon,
        )
        print(text)
        print(output_class)
        print(tooltip)
        return

    threading.Thread(
        target=worker,
        args=(
            api_key,
            location,
            use_celsius,
        ),
        daemon=True,
    ).start()

    with condition:
        needs_fetch = True
        needs_redraw = True
        condition.notify()

    while True:
        time.sleep(interval)
        with condition:
            needs_fetch = True
            needs_redraw = True
            condition.notify()


if __name__ == "__main__":
    main()
