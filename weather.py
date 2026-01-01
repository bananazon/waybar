#!/usr/bin/env python3

import json
import logging
import os
import signal
import sys
import threading
import time
from collections import OrderedDict
from typing import cast

import click
from dacite import Config, from_dict

from waybar import glyphs, http
from waybar.data import weather
from waybar.util import log, network, system, wtime

sys.stdout.reconfigure(line_buffering=True)  # type: ignore


cache_dir = system.get_cache_directory()
condition = threading.Condition()
context_settings = dict(help_option_names=["-h", "--help"])
format_index: int = 0
logger: logging.Logger
logfile = cache_dir / "waybar-weather.log"
needs_fetch: bool = False
needs_redraw: bool = False
weather_data: list[weather.LocationData] | None = []

formats: list[int] = []

update_event = threading.Event()


def refresh_handler(_signum: int, _frame: object | None):
    global needs_fetch, needs_redraw, logger
    logger.info("received SIGHUP — re-fetching data")
    with condition:
        needs_fetch = True
        needs_redraw = True
        condition.notify()


def toggle_format(_signum: int, _frame: object | None):
    global formats, format_index, needs_redraw, logger
    format_index = (format_index + 1) % len(formats)
    if weather_data and type(weather_data) is list:
        location = weather_data[format_index].location_full
    else:
        location = format_index + 1
    logger.info(f"received SIGUSR1 - switching output format to {location}")
    with condition:
        needs_redraw = True
        condition.notify()


_ = signal.signal(signal.SIGHUP, refresh_handler)
_ = signal.signal(signal.SIGUSR1, toggle_format)


def generate_tooltip(location_data: weather.LocationData, use_celsius: bool):
    global logger

    logger.debug(f"entering with mountpoint={location_data.location_full}")
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
        sunrise = wtime.to_24hour_time(input=sunrise_unix)
        sunset = wtime.to_24hour_time(input=sunset_unix)
        if sunrise and sunset:
            tooltip_od["Sunrise"] = sunrise
            tooltip_od["Sunset"] = sunset

    if moonrise_unix and moonset_unix:
        moonrise = wtime.to_24hour_time(input=moonrise_unix)
        moonset = wtime.to_24hour_time(input=moonset_unix)
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


def get_weather(api_key: str, location: str) -> weather.LocationData:
    global logger

    logger.info(f"entering function with location={location}")

    location_data: weather.LocationData = weather.LocationData()
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
                weather_data = from_dict(
                    data_class=weather.WeatherData,
                    data=json_data,
                    config=Config(cast=[int, str]),
                )

                for idx, _ in enumerate(weather_data.forecast.forecastday):
                    if weather_data.forecast.forecastday[idx].astro.moonrise:
                        weather_data.forecast.forecastday[
                            idx
                        ].astro.moonrise_unix = wtime.to_unix_time(
                            input=weather_data.forecast.forecastday[idx].astro.moonrise
                        )
                    if weather_data.forecast.forecastday[idx].astro.moonset:
                        weather_data.forecast.forecastday[
                            idx
                        ].astro.moonset_unix = wtime.to_unix_time(
                            input=weather_data.forecast.forecastday[idx].astro.moonset
                        )
                    if weather_data.forecast.forecastday[idx].astro.sunrise:
                        weather_data.forecast.forecastday[
                            idx
                        ].astro.sunrise_unix = wtime.to_unix_time(
                            input=weather_data.forecast.forecastday[idx].astro.sunrise
                        )
                    if weather_data.forecast.forecastday[idx].astro.sunset:
                        weather_data.forecast.forecastday[
                            idx
                        ].astro.sunset_unix = wtime.to_unix_time(
                            input=weather_data.forecast.forecastday[idx].astro.sunset
                        )

                return weather.LocationData(
                    success=True,
                    icon=get_weather_icon(
                        condition_code=weather_data.current.condition.code,
                        is_day=True if weather_data.current.is_day == 1 else False,
                    ),
                    location_short=weather_data.location.name,
                    location_full=location,
                    weather=weather_data,
                    updated=wtime.get_human_timestamp(),
                )

    return location_data


def render_output(
    location_data: weather.LocationData, use_celsius: bool, icon: str
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
        output_class = "success"
        tooltip = generate_tooltip(location_data=location_data, use_celsius=use_celsius)
    else:
        text = f"{glyphs.md_alert}{glyphs.icon_spacer}{location_data.location_full} {location_data.error if location_data.error is not None else 'Unknown error'}"
        output_class = "error"
        tooltip = f"{location_data.location_full} error"

    return text, output_class, tooltip


def worker(api_key: str, locations: list[str], use_celsius: bool):
    global weather_data, needs_fetch, needs_redraw, format_index, logger

    while True:
        with condition:
            while not (needs_fetch or needs_redraw):
                _ = condition.wait()

            fetch = needs_fetch
            redraw = needs_redraw
            needs_fetch = False
            needs_redraw = False

        logger.info("entering worker loop")

        if not network.network_is_reachable():
            output = {
                "text": f"{glyphs.md_alert}{glyphs.icon_spacer}the network is unreachable",
                "class": "error",
                "tooltip": "Weather update error",
            }
            print(json.dumps(output))
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
    global formats, needs_fetch, needs_redraw, logger

    logger = log.configure(
        debug=debug, name=os.path.basename(__file__), logfile=logfile
    )

    formats = list(range(len(location)))

    logger.info("entering function")

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
