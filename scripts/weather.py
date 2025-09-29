#!/usr/bin/env python3

from collections import OrderedDict
from pathlib import Path
from typing import Optional, NamedTuple
from waybar import glyphs, http, util
import json
import logging
import os
import signal
import sys
import threading
import time

util.validate_requirements(required=['click'])
import click

CACHE_DIR = util.get_cache_directory()
CONTEXT_SETTINGS = dict(help_option_names=['-h', '--help'])
LOADING = f'{glyphs.md_timer_outline}{glyphs.icon_spacer}Fetching weather...'
LOADING_DICT = { 'text': LOADING, 'class': 'loading', 'tooltip': 'Fetching weather...'}
LOGFILE = CACHE_DIR / 'waybar-weather-result.log'

update_event = threading.Event()
sys.stdout.reconfigure(line_buffering=True)

class WeatherData(NamedTuple):
    success           : Optional[bool]  = False
    error             : Optional[str]   = None
    icon              : Optional[str]   = None
    avg_humidity      : Optional[int]   = 0
    cloud_cover       : Optional[float] = None
    condition         : Optional[str]   = None
    condition_code    : Optional[int]   = 0
    country           : Optional[str]   = None
    dewpoint          : Optional[str]   = None
    current_temp      : Optional[str]   = None
    feels_like        : Optional[str]   = None
    gust              : Optional[str]   = None
    heat_index        : Optional[str]   = None
    humidity          : Optional[str]   = None
    location_full     : Optional[str]   = None
    location_short    : Optional[str]   = None
    moonrise          : Optional[str]   = None
    moonrise_unix     : Optional[int]   = 0
    moonset           : Optional[str]   = None
    moonset_unix      : Optional[int]   = 0
    moon_illumination : Optional[int]   = 0
    moon_phase        : Optional[str]   = None
    precipitation     : Optional[str]   = None
    region            : Optional[str]   = None
    sunrise           : Optional[str]   = None
    sunrise_unix      : Optional[int]   = 0
    sunset            : Optional[str]   = None
    sunset_unix       : Optional[int]   = 0
    todays_high       : Optional[str]   = None
    todays_low        : Optional[str]   = None
    uv                : Optional[float] = None
    visibility        : Optional[str]   = None
    wind_chill        : Optional[str]   = None
    wind_degree       : Optional[int]   = 0
    wind_dir          : Optional[str]   = None
    wind_speed        : Optional[str]   = None

logging.basicConfig(
    filename=LOGFILE,
    filemode='a',  # 'a' = append, 'w' = overwrite
    format='%(asctime)s [%(levelname)-5s] - %(message)s',
    level=logging.INFO
)

def generate_tooltip(weather_data):
    tooltip = []
    tooltip_od = OrderedDict()

    if weather_data.location_full:
        tooltip_od['Location'] = weather_data.location_full

    if weather_data.condition:
        tooltip_od['Condition'] = weather_data.condition

    if weather_data.feels_like:
        tooltip_od['Feels Like'] = weather_data.feels_like

    if weather_data.todays_high and weather_data.todays_low:
        tooltip_od['High / Low'] = f'{weather_data.todays_high} / {weather_data.todays_low}'

    if weather_data.wind_speed and weather_data.wind_degree:
        tooltip_od['Wind'] = f'{weather_data.wind_speed} @ {weather_data.wind_degree}'

    if weather_data.cloud_cover:
        tooltip_od['Cloud Cover'] = weather_data.cloud_cover

    if weather_data.humidity:
        tooltip_od['Humidity'] = weather_data.humidity

    if weather_data.dewpoint:
        tooltip_od['Dew Point'] = weather_data.dewpoint

    if weather_data.uv:
        tooltip_od['UV Index'] = f'{weather_data.uv} of 11'

    if weather_data.visibility:
        tooltip_od['Visibility'] = weather_data.visibility

    if weather_data.sunrise_unix and weather_data.sunset_unix:
        tooltip_od['Sunrise'] = util.to_24hour_time(weather_data.sunrise_unix)
        tooltip_od['Sunset'] = util.to_24hour_time(weather_data.sunset_unix)

    if weather_data.moonrise_unix and weather_data.moonset_unix:
        tooltip_od['Moonrise'] = util.to_24hour_time(weather_data.moonrise_unix)
        tooltip_od['Moonset'] = util.to_24hour_time(weather_data.moonset_unix)

    if weather_data.moon_phase:
        tooltip_od['Moon Phase'] = weather_data.moon_phase

    max_key_length = 0
    for key in tooltip_od.keys():
        max_key_length = len(key) if len(key) > max_key_length else max_key_length

    for key, value in tooltip_od.items():
        tooltip.append(f'{key:{max_key_length}} : {value}')

    return '\n'.join(tooltip)

def get_weather_icon(condition_code, is_day):
    # https://www.weatherapi.com/docs/weather_conditions.json
    if condition_code == 1000: # Sunny
        if is_day == 1:
            return glyphs.md_weather_sunny
        else:
            return glyphs.md_weather_night

    elif condition_code == 1003:
        if is_day == 1: # Partly cloudy
            return glyphs.md_weather_partly_cloudy
        else:
            return glyphs.md_weather_night_partly_cloudy

    elif condition_code == 1006: # Cloudy
        if is_day == 1:
            return glyphs.weather_day_cloudy
        else:
            return glyphs.weather_night_cloudy

    elif condition_code == 1009: # Overcast
        if is_day == 1:
            return glyphs.weather_day_sunny_overcast
        else:
            return glyphs.weather_night_cloudy

    elif condition_code == 1030: # Mist
        if is_day == 1:
            return glyphs.md_weather_hazy
        else:
            return glyphs.md_weather_hazy

    elif condition_code == 1063: # Patchy rain possible
        if is_day == 1:
            return glyphs.md_weather_partly_rainy
        else:
            return glyphs.md_weather_partly_rainy

    elif condition_code == 1066: # Patchy snow possible
        if is_day == 1:
            return glyphs.md_weather_partly_snowy
        else:
            return glyphs.md_weather_partly_snowy

    elif condition_code == 1114: # Blowing snow
        if is_day == 1:
            return glyphs.weather_snow_wind
        else:
            return glyphs.weather_day_snow_wind

    elif condition_code in [1069, 1204, 1249]: # Patchy sleet possible / Light sleet /Light sleet showers
        if is_day == 1:
            return glyphs.weather_day_sleet
        else:
            return glyphs.weather_night_sleet

    elif condition_code in [1207, 1252]: # Moderate or heavy sleet / Moderate or heavy sleet showers
        if is_day == 1:
            return glyphs.weather_day_sleet_storm
        else:
            return glyphs.weather_night_alt_sleet_storm

    elif condition_code in [1210, 1213, 1216, 1219, 1222, 1225] : # Patchy light snow / Light snow / Patchy moderate snow / Moderate snow / Patchy heavy snow / Heavy snow
        if is_day == 1:
            return glyphs.weather_day_snow
        else:
            return glyphs.weather_night_snow

    elif condition_code == 1240: # Light rain shower
        if is_day == 1:
            return glyphs.weather_day_rain
        else:
            return glyphs.weather_night_rain

    elif condition_code == 1243: # Moderate or heavy rain shower
        if is_day == 1:
            return glyphs.weather_day_showers
        else:
            return glyphs.weather_night_showers

    elif condition_code == 1246: # Torrential rain shower
        if is_day == 1:
            return glyphs.weather_day_storm_showers
        else:
            return glyphs.weather_night_storm_showers

    return glyphs.md_weather_sunny

def get_weather(api_key: str=None, location: str=None, use_celsius: bool=False, label: str=None):
    weather_data = None
    response = http.request(
        url    = 'https://api.weatherapi.com/v1/forecast.json',
        params = {
            'key'    : api_key,
            'q'      : location,
            'aqi'    : 'no',
            'alerts' : 'no',
        }
    )

    if response.status == 200:
        if response.body:
            json_data = response.body
            if use_celsius:
                distance = 'km'
                height = 'mm'
                speed = 'kph'
                unit = 'C'
            else:
                distance = 'miles'
                height = 'in'
                speed = 'mph'
                unit = 'F'

            unit_lower = unit.lower()

            try:
                astro_data     = json_data['forecast']['forecastday'][0]['astro']
                condition_data = json_data['current']['condition']
                current_data   = json_data['current']
                forecast_data  = json_data['forecast']['forecastday'][0]['day']
                location_data  = json_data['location']

                weather_data = WeatherData(
                    success        = True,
                    icon           = get_weather_icon(current_data['condition']['code'], current_data['is_day']),
                    avg_humidity   = f'{forecast_data.get("avghumidity")}%' or 'Unknown',
                    cloud_cover    = current_data.get('cloud') or 'Unknown',
                    condition      = (current_data.get('condition') or {}).get('text') or 'Unknown',
                    condition_code = (current_data.get('condition') or {}).get('code') or 'Unknown',
                    country        = location_data.get('country') or 'Unknown',
                    current_temp   = f'{current_data.get(f"temp_{unit_lower}")}°{unit}' or 'Unknown',
                    dewpoint       = f'{current_data.get(f"dewpoint_{unit_lower}")}°{unit}' or 'Unknown',
                    feels_like     = f'{current_data.get(f"feelslike_{unit_lower}")}°{unit}' or 'Unknown',
                    gust           = f'{current_data.get(f"gust_{speed}")} {speed}' or 'Unknown',
                    heat_index     = f'{current_data.get(f"heatindex_{unit_lower}")}°{unit}' or 'Unknown',
                    humidity       = f'{current_data.get("humidity")}%' or 'Unknown',
                    location_full  = location,
                    location_short = location_data.get('name') or 'Unknown',
                    moonrise       = astro_data.get('moonrise') or 'No moonrise',
                    moonrise_unix  = util.to_unix_time(astro_data.get('moonrise')),
                    moonset        = astro_data.get('moonset') or 'No moonset',
                    moonset_unix   = util.to_unix_time(astro_data.get('moonset')),
                    moon_phase     = astro_data.get('moon_phase') or None,
                    sunrise        = astro_data.get('sunrise') or 'No sunrise',
                    sunrise_unix   = util.to_unix_time(astro_data.get('sunrise')),
                    sunset         = astro_data.get('sunset') or 'No sunset',
                    sunset_unix    = util.to_unix_time(astro_data.get('sunset')),
                    precipitation  = f'{forecast_data.get(f"totalprecip_{height}")} {height}' or 'Unknown',
                    region         = location_data.get('region') or 'Unknown',
                    todays_high    = f'{forecast_data.get(f"maxtemp_{unit_lower}")}°{unit}' or 'Unknown',
                    todays_low     = f'{forecast_data.get(f"mintemp_{unit_lower}")}°{unit}' or 'Unknown',
                    uv             = current_data.get('uv') or None,
                    visibility     = f'{current_data.get(f"vis_{distance}")} {distance}' or 'Unknown',
                    wind_chill     = f'{current_data.get(f"windchill_{unit_lower}")}°{unit}' or 'Unknown',
                    wind_degree    = f'{current_data.get("wind_degree")}°' or 'Unknown',
                    wind_dir       = current_data.get('wind_dir') or 'Unknown',
                    wind_speed     = f'{current_data.get(f"wind_{speed}")} {speed}' or 'Unknown',
                )
            except Exception as e:
                    print(e)
                    exit()
                    weather_data = WeatherData(
                        success        = False,
                        error          = f'could not retrieve the weather for {location}: {str(e)}',
                        location_full  = location,
                    )
        else:
            weather_data = WeatherData(
                success        = False,
                error          = f'empty response was received',
                location_full  = location,
            )
    else:
        weather_data = WeatherData(
            success        = False,
            error          = f'a non-200 ({response.status}) was received',
            location_full  = location,
        )

    return weather_data

def worker(api_key: str=None, location: str=None, use_celsius: bool=False, label: str=None):
    logging.info('[worker] entering function')

    while True:
        update_event.wait()
        update_event.clear()

        if not util.waybar_is_running():
            logging.info('[worker] waybar not running')
            sys.exit(0)
        else:
            if util.network_is_reachable():
                print(json.dumps(LOADING_DICT))

                weather_data = get_weather(api_key=api_key, location=location, use_celsius=use_celsius, label=label)
                if weather_data.success:
                    tooltip = generate_tooltip(weather_data)

                    output = {
                        'text'    : f'{weather_data.icon}{glyphs.icon_spacer}{weather_data.location_short} {weather_data.current_temp}',
                        'class'   : 'success',
                        'tooltip' : tooltip,
                    }
                else:
                    icon = weather_data.icon or glyphs.md_alert
                    output = {
                        'text'    : f'{glyphs.md_alert} {location} {weather_data.error if weather_data.error is not None else "Unknown error"}',
                        'class'   : 'error',
                        'tooltip' : f'{location} error',
                    }
            else:
                output = {
                    'text'    : f'{glyphs.md_alert}{glyphs.icon_spacer}the network is unreachable',
                    'class'   : 'error',
                    'tooltip' : f'{location} error',
                }

            print(json.dumps(output))

def refresh_handler(signum, frame):
    logging.info('Received SIGHUP — triggering get_weather()')
    update_event.set()

signal.signal(signal.SIGHUP, refresh_handler)

@click.command(help='Get weather info from World Weather API', context_settings=CONTEXT_SETTINGS)
@click.option('-a', '--api-key', required=True, help=f'World Weather API key')
@click.option('-l', '--location', required=True, default='Los Angeles, CA, US', help='The location to query')
@click.option('-c', '--use-celsius', default=False, is_flag=True, help='Use Celsius instead of Fahrenheit')
@click.option('--label', required=True, help='A "friendly name" to be used to form the IPC calls')
@click.option('-i', '--interval', type=int, default=300, help='The update interval (in seconds)')
@click.option('-t', '--test', default=False, is_flag=True, help='Print the output and exit')
def main(api_key, location, use_celsius, label, interval, test):
    if test:
        weather_data = get_weather(api_key=api_key, location=location, use_celsius=use_celsius, label=label)
        util.pprint(weather_data)
        sys.exit(0)

    threading.Thread(
        target = worker,
        args   = (api_key, location, use_celsius, label,),
        daemon = True,
    ).start()
    update_event.set()

    while True:
        time.sleep(interval)
        update_event.set()

if __name__ == '__main__':
    main()
