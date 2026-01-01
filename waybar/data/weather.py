from dataclasses import dataclass, field


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
