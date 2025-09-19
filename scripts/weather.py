#!/usr/bin/env python3

from pathlib import Path
from waybar import glyphs, state, util
from urllib.parse import quote, urlunparse
from typing import Any, Dict, List, Optional, NamedTuple
from urllib.request import urlopen, Request
import json
import os
import sys
import time
import urllib.request

util.validate_requirements(required=['click'])

import click

LABEL     : str | None=None
LOCATION  : str | None=None
LOCKFILE  : str | None=None
STATEFILE : str | None=None
TEMPFILE  : str | None=None

class WeatherData(NamedTuple):
    success           : Optional[bool]  = False
    error             : Optional[str]   = None
    icon              : Optional[str]   = None
    avg_humidity      : Optional[int]   = 0
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
    precipitation     : Optional[str]   = None
    region            : Optional[str]   = None
    sunrise           : Optional[str]   = None
    sunrise_unix      : Optional[int]   = 0
    sunset            : Optional[str]   = None
    sunset_unix       : Optional[int]   = 0
    todays_high       : Optional[str]   = None
    todays_low        : Optional[str]   = None
    visibility        : Optional[str]   = None
    wind_chill        : Optional[str]   = None
    wind_degree       : Optional[int]   = 0
    wind_dir          : Optional[str]   = None
    wind_speed        : Optional[str]   = None

CONTEXT_SETTINGS = dict(help_option_names=['-h', '--help'])
LOADING = f'{glyphs.md_timer_outline} Fetching weather...'

def set_globals(label: str=None, location: str=None):
    global LABEL
    global LOCATION
    global STATEFILE
    global TEMPFILE
    global LOCKFILE

    module = os.path.basename(__file__)
    module_no_ext = os.path.splitext(module)[0]

    LABEL     = label
    LOCATION  = location
    STATEFILE = Path.home() / f'.waybar-{module_no_ext}-{label}-state'
    TEMPFILE  = Path.home() / f'.waybar-{module_no_ext}-{LABEL}-result.txt'

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

def get_weather(api_key: str=None, location: str=None, use_celsius: bool=False, label: str=None, mode: int=0):
    global TEMPFILE

    weather_data = None

    url_parts = (
        'https',
        'api.weatherapi.com',
        f'v1/forecast.json?key={api_key}&q={quote(location)}&aqi=no&alerts=no',
        '',
        '',
        '',
    )
    url = urlunparse(url_parts)

    with urllib.request.urlopen(url) as response:
        body = response.read().decode('utf-8')
        if response.status == 200:
            json_data, err = util.parse_json_string(body)
            if err:
                weather_data = WeatherData(
                    success        = False,
                    error          = f'could not retrieve the weather for {location}: {err}',
                    location_full  = location,
                )
            else:
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
                        avg_humidity   = f'{forecast_data.get("avghumidity")}%' if forecast_data.get('avghumidity') is not None else 'Unknown',
                        condition_code = current_data.get('condition').get('code') if 'code' in current_data.get('condition') else 'Unknown',
                        country        = location_data.get('country') if location_data.get('country') is not None else 'Unknown',
                        current_temp   = f'{current_data.get(f"temp_{unit_lower}")}°{unit}' if current_data.get(f'temp_{unit_lower}') is not None else 'Unknown',
                        dewpoint       = f'{current_data.get(f"dewpoint_{unit_lower}")}°{unit}' if current_data.get(f'dewpoint_{unit_lower}') is not None else 'Unknown',
                        feels_like     = f'{current_data.get(f"feelslike_{unit_lower}")}°{unit}' if current_data.get(f'feelslike_{unit_lower}') is not None else 'Unknown',
                        gust           = f'{current_data.get(f"gust_{speed}")} {speed}' if current_data.get(f'gust_{speed}') is not None else 'Unknown',
                        heat_index     = f'{current_data.get(f"heatindex_{unit_lower}")}°{unit}' if current_data.get(f'heatindex_{unit_lower}') is not None else 'Unknown',
                        humidity       = f'{current_data.get("humidity")}%' if current_data.get('humidity') is not None else 'Unknown',
                        location_full  = location,
                        location_short = location_data.get('name') if location_data.get('name') is not None else 'Unknown',
                        moonrise       = astro_data.get('moonrise') if astro_data.get('moonrise') is not None else 'No moonrise',
                        moonrise_unix  = util.to_unix_time(astro_data.get('moonrise')),
                        moonset        = astro_data.get('moonset') if astro_data.get('moonset') is not None else 'No moonset',
                        moonset_unix   = util.to_unix_time(astro_data.get('moonset')),
                        sunrise        = astro_data.get('sunrise') if astro_data.get('sunrise') is not None else 'No sunrise',
                        sunrise_unix   = util.to_unix_time(astro_data.get('sunrise')),
                        sunset         = astro_data.get('sunset') if astro_data.get('sunset') is not None else 'No sunset',
                        sunset_unix    = util.to_unix_time(astro_data.get('sunset')),
                        precipitation  = f'{forecast_data.get(f"totalprecip_{height}")} {height}' if forecast_data.get(f'totalprecip_{height}') is not None else 'Unknown',
                        region         = location_data.get('region') if location_data.get('region') is not None else 'Unknown',
                        todays_high    = f'{forecast_data.get(f"maxtemp_{unit_lower}")}°{unit}' if forecast_data.get(f'maxtemp_{unit_lower}') is not None else 'Unknown',
                        todays_low     = f'{forecast_data.get(f"mintemp_{unit_lower}")}°{unit}' if forecast_data.get(f'mintemp_{unit_lower}') is not None else 'Unknown',
                        visibility     = f'{current_data.get(f"vis_{distance}")} {distance}' if current_data.get(f'vis_{distance}') is not None else 'Unknown',
                        wind_chill     = f'{current_data.get(f"windchill_{unit_lower}")}°{unit}' if current_data.get(f'windchill_{unit_lower}') is not None else 'Unknown',
                        wind_degree    = current_data.get('wind_degree') if current_data.get('wind_degree') is not None else 'Unknown',
                        wind_dir       = current_data.get('wind_dir') if current_data.get('wind_dir') is not None else 'Unknown',
                        wind_speed     = f'{current_data.get(f"wind_{speed}")} {speed}' if current_data.get(f'wind_{speed}') is not None else 'Unknown',
                    )
                except Exception as e:
                    weather_data = WeatherData(
                        success        = False,
                        error          = f'could not retrieve the weather for {location}: {err}',
                        location_full  = location,
                    )
        else:
            weather_data = WeatherData(
                success        = False,
                error          = f'a non-200 ({response.status}) was received',
                location_full  = location,
            )

    return weather_data

@click.group(context_settings=CONTEXT_SETTINGS)
def cli():
    """
    Retrieve weather from weatherapi.com
    """
    pass

@cli.command(help='Get weather info from World Weather API')
@click.option('-a', '--api-key', required=True, help=f'World Weather API key')
@click.option('-l', '--location', required=True, default='Los Angeles, CA, US', help='The location to query')
@click.option('-c', '--use-celsius', default=False, is_flag=True, help='Use Celsius instead of Fahrenheit')
@click.option('--label', required=True, help='A "friendly name" to be used to form the IPC calls')
@click.option('-t', '--toggle', is_flag=True, help='Toggle the output format', required=False)
def run(api_key, location, use_celsius, label, toggle):
    global LOCKFILE
    global STATEFILE

    mode_count = 6
    util.check_network()
    set_globals(label=label, location=location)

    if toggle:
        mode = state.next_state(statefile=STATEFILE, mode_count=mode_count)
    else:
        mode = state.read_state(statefile=STATEFILE)
    
    weather_data = get_weather(api_key=api_key, location=location, use_celsius=use_celsius, label=label, mode=mode)
    if weather_data.success:
        current_temp = weather_data.current_temp
        low_temp     = weather_data.todays_low
        high_temp    = weather_data.todays_high
        icon         = weather_data.icon
        location     = weather_data.location_short
        sunrise      = util.to_24hour_time(input=weather_data.sunrise_unix) if weather_data.sunrise_unix > 0 else weather_data.sunrise
        sunset       = util.to_24hour_time(input=weather_data.sunset_unix) if weather_data.sunset_unix > 0 else weather_data.sunset
        moonrise     = util.to_24hour_time(input=weather_data.moonrise_unix) if weather_data.moonrise_unix > 0 else weather_data.moonrise
        moonset      = util.to_24hour_time(input=weather_data.moonset_unix) if weather_data.moonset_unix > 0 else weather_data.moonset
        wind_degree  = weather_data.wind_degree
        wind_speed   = weather_data.wind_speed

        if mode == 0:
            output = {
                'text'    : f'{icon} {location} {current_temp}',
                'class'   : 'success',
                'tooltip' : f'{location} current condition and temperature',
            }
        elif mode == 1:
            output = {
                'text'    : f'{icon} {location} {glyphs.cod_arrow_small_up}{high_temp} {glyphs.cod_arrow_small_down}{low_temp}',
                'class'   : 'success',
                'tooltip' : f'{location} daily high and low temperaturea',
            }
        elif mode == 2:
            output = {
                'text'    : f'{icon} {location} {wind_speed} @ {wind_degree}°',
                'class'   : 'success',
                'tooltip' : f'{location} wind speed and direction',
            }
        elif mode == 3:
            output = {
                'text'    : f'{icon} {location}  {glyphs.weather_sunrise}  {sunrise} {glyphs.weather_sunset}  {sunset}',
                'class'   : 'success',
                'tooltip' : f'{location} sunrise and sunset times',
            }
        elif mode == 4:
            output = {
                'text'    : f'{icon} {location} {glyphs.weather_moonrise} {moonrise} {glyphs.weather_moonset} {moonset}',
                'class'   : 'success',
                'tooltip' : f'{location} moonrise and moonset times',
            }
        elif mode == 5:
            output = {
                'text'    : f'{icon} {location} humidity {weather_data.humidity}',
                'class'   : 'success',
                'tooltip' : f'{location} humidity level',
            }
    else:
        output = {
            'text'    : f'{icon} {location} {weather_data.error}',
            'class'   : 'error',
            'tooltip' : f'{location} error',
        }

    print(json.dumps(output))

if __name__ == '__main__':
    cli()
