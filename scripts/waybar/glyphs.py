def surrogatepass(code):
    return code.encode('utf-16', 'surrogatepass').decode('utf-16')

# Weather
fa_wind                             = surrogatepass('\uef16')
md_weather_cloudy                   = surrogatepass('\udb81\udd90')
md_weather_hazy                     = surrogatepass('\udb83\udf30')
md_weather_night                    = surrogatepass('\udb81\udd94')
md_weather_night_partly_cloudy      = surrogatepass('\udb83\udf31')
md_weather_partly_cloudy            = surrogatepass('\udb81\udd95')
md_weather_partly_rainy             = surrogatepass('\udb83\udf33')
md_weather_partly_snowy             = surrogatepass('\udb83\udf34')
md_weather_partly_snowy_rainy       = surrogatepass('\udb83\udf35')
md_weather_snowy                    = surrogatepass('\udb81\udd98')
md_weather_snowy_heavy              = surrogatepass('\udb83\udf36')
md_weather_snowy_rainy              = surrogatepass('\udb81\ude7f')
md_weather_sunny                    = surrogatepass('\uf185')
md_weather_sunset_down              = surrogatepass('\udb81\udd9b')
weather_day_cloudy                  = surrogatepass('\ue302')
weather_day_rain                    = surrogatepass('\ue308')
weather_day_showers                 = surrogatepass('\ue309')
weather_day_sleet                   = surrogatepass('\ue3aa')
weather_day_sleet_storm             = surrogatepass('\ue362')
weather_day_snow                    = surrogatepass('\ue30a')
weather_day_snow_thunderstorm       = surrogatepass('\ue365')
weather_day_snow_wind               = surrogatepass('\ue35f')
weather_day_storm_showers           = surrogatepass('\ue30e')
weather_day_sunny_overcast          = surrogatepass('\ue30c')
weather_day_thunderstorm            = surrogatepass('\ue30f')
weather_moonrise                    = surrogatepass('\ue3c1')
weather_moonset                     = surrogatepass('\ue3c2')
weather_night_alt_sleet             = surrogatepass('\ue3ac')
weather_night_alt_sleet_storm       = surrogatepass('\ue364')
weather_night_alt_snow              = surrogatepass('\ue327')
weather_night_alt_snow_thunderstorm = surrogatepass('\ue367')
weather_night_alt_snow_wind         = surrogatepass('\ue361')
weather_night_cloudy                = surrogatepass('\ue32e')
weather_night_rain                  = surrogatepass('\ue333')
weather_night_showers               = surrogatepass('\ue334')
weather_night_sleet                 = surrogatepass('\ue3ab')
weather_night_sleet_storm           = surrogatepass('\ue363')
weather_night_snow                  = surrogatepass('\ue335')
weather_night_snow_thunderstorm     = surrogatepass('\ue366')
weather_night_snow_wind             = surrogatepass('\ue360')
weather_night_storm_showers         = surrogatepass('\ue337')
weather_night_thunderstorm          = surrogatepass('\ue338')
weather_sleet                       = surrogatepass('\ue3ad')
weather_snow_wind                   = surrogatepass('\ue35e')
weather_sunrise                     = surrogatepass('\ue34c')
weather_sunset                      = surrogatepass('\ue34d')

# WiFi
md_wifi_strength_1                  = surrogatepass('\udb82\udd1f')
md_wifi_strength_1_alert            = surrogatepass('\udb82\udd20')
md_wifi_strength_1_lock             = surrogatepass('\udb82\udd21')
md_wifi_strength_1_lock_open        = surrogatepass('\udb85\udecb')
md_wifi_strength_2                  = surrogatepass('\udb82\udd22')
md_wifi_strength_2_alert            = surrogatepass('\udb82\udd23')
md_wifi_strength_2_lock             = surrogatepass('\udb82\udd24')
md_wifi_strength_2_lock_open        = surrogatepass('\udb85\udecc')
md_wifi_strength_3                  = surrogatepass('\udb82\udd25')
md_wifi_strength_3_alert            = surrogatepass('\udb82\udd26')
md_wifi_strength_3_lock             = surrogatepass('\udb82\udd27')
md_wifi_strength_3_lock_open        = surrogatepass('\udb85\udecd')
md_wifi_strength_4                  = surrogatepass('\udb82\udd28')
md_wifi_strength_4_alert            = surrogatepass('\udb82\udd29')
md_wifi_strength_4_lock             = surrogatepass('\udb82\udd2a')
md_wifi_strength_4_lock_open        = surrogatepass('\udb85\udece')
md_wifi_strength_alert_outline      = surrogatepass('\udb82\udd2b')
md_wifi_strength_lock_open_outline  = surrogatepass('\udb85\udecf')
md_wifi_strength_lock_outline       = surrogatepass('\udb82\udd2c')
md_wifi_strength_off                = surrogatepass('\udb82\udd2d')
md_wifi_strength_off_outline        = surrogatepass('\udb82\udd2e')
md_wifi_strength_outline            = surrogatepass('\udb82\udd2f')

# Weather
cod_arrow_small_down = surrogatepass('\uea9d')
cod_arrow_small_up   = arrow_up = surrogatepass('\ueaa0')
cod_graph_line       = surrogatepass('\uebe2')

# CPU
oct_cpu       = surrogatepass('\uf4bc')
md_cpu_32_bit = surrogatepass('\udb83\udedf')
md_cpu_64_bit = surrogatepass('\udb83\udee0')

# Disk
md_harddisk = surrogatepass('\udb80\udeca')

# Memory
cod_arrow_swap = surrogatepass('\uebcb')
fa_memory      = surrogatepass('\uefc5')
md_memory      = surrogatepass('\udb80\udf5b')

# Speedtest
md_speedometer_slow   = surrogatepass('\udb83\udf86')
md_speedometer_medium = surrogatepass('\udb83\udf85')
md_speedometer_fast   = surrogatepass('\udb81\udcc5')

# Others
cod_package           = surrogatepass('\ueb29')
fa_arrow_rotate_right = surrogatepass('\uf01e')
md_package_variant    = surrogatepass('\udb80\udfd6')
md_timer_outline      = surrogatepass('\udb81\udd1b')
icon_spacer           = '  '

# Alerts
md_alert               = surrogatepass('\udb80\udc26')
md_network_off         = surrogatepass('\udb83\udc9b')
md_network_off_outline = surrogatepass('\udb83\udc9c')
oct_alert              = surrogatepass('\uf421')

# Network
md_network = surrogatepass('\udb81\udef3')

# Plex
md_plex = surrogatepass('\udb81\udeba')
