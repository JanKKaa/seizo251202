import requests
from datetime import datetime, timedelta, timezone
from django.http import JsonResponse

JST = timezone(timedelta(hours=9))
MINAMI_MINOWA_LAT = 35.8729
MINAMI_MINOWA_LON = 137.9753


def _open_meteo_description(code):
    descriptions = {
        0: "Clear",
        1: "Mainly clear",
        2: "Partly cloudy",
        3: "Overcast",
        45: "Fog",
        48: "Depositing rime fog",
        51: "Light drizzle",
        53: "Drizzle",
        55: "Dense drizzle",
        56: "Light freezing drizzle",
        57: "Dense freezing drizzle",
        61: "Slight rain",
        63: "Rain",
        65: "Heavy rain",
        66: "Light freezing rain",
        67: "Heavy freezing rain",
        71: "Slight snow",
        73: "Snow",
        75: "Heavy snow",
        77: "Snow grains",
        80: "Slight rain showers",
        81: "Rain showers",
        82: "Violent rain showers",
        85: "Slight snow showers",
        86: "Heavy snow showers",
        95: "Thunderstorm",
        96: "Thunderstorm with hail",
        99: "Thunderstorm with heavy hail",
    }
    return descriptions.get(int(code or 0), "Unknown")


def _nearest_hourly_index(times, target):
    best_index = -1
    best_diff = None
    for index, value in enumerate(times or []):
        try:
            point = datetime.fromisoformat(value).replace(tzinfo=JST)
        except (TypeError, ValueError):
            continue
        diff = abs((point - target).total_seconds())
        if best_diff is None or diff < best_diff:
            best_diff = diff
            best_index = index
    return best_index


def weather_minowa(request):
    params = {
        "latitude": MINAMI_MINOWA_LAT,
        "longitude": MINAMI_MINOWA_LON,
        "current": "temperature_2m,relative_humidity_2m,wind_speed_10m,weather_code",
        "hourly": "temperature_2m,precipitation,snowfall,weather_code",
        "timezone": "Asia/Tokyo",
        "forecast_days": 2,
    }
    try:
        r = requests.get('https://api.open-meteo.com/v1/forecast', params=params, timeout=7)
        r.raise_for_status()
        data = r.json()
        current = data.get("current") or {}
        code = current.get("weather_code")

        now = datetime.now(JST)
        target = now.replace(hour=17, minute=30, second=0, microsecond=0)
        if target < now:
            target = target + timedelta(days=1)
        hourly = data.get("hourly") or {}
        idx = _nearest_hourly_index(hourly.get("time"), target)
        forecast_1730 = None
        if idx >= 0:
            forecast_code = hourly.get("weather_code", [None])[idx]
            forecast_1730 = {
                "time": hourly.get("time", [None])[idx],
                "temp": hourly.get("temperature_2m", [None])[idx],
                "precipitation": hourly.get("precipitation", [None])[idx],
                "snowfall": hourly.get("snowfall", [None])[idx],
                "weather_code": forecast_code,
                "weather": _open_meteo_description(forecast_code),
            }

        result = {
            "ok": True,
            "temp": current.get("temperature_2m"),
            "weather": _open_meteo_description(code),
            "weather_code": code,
            "humidity": current.get("relative_humidity_2m"),
            "wind": current.get("wind_speed_10m"),
            "city": "Minami Minowa, Nagano",
            "latitude": MINAMI_MINOWA_LAT,
            "longitude": MINAMI_MINOWA_LON,
            "time": current.get("time") or now.isoformat(),
            "forecast_1730": forecast_1730,
            "source": "Open-Meteo",
        }
        return JsonResponse(result)
    except requests.RequestException as e:
        return JsonResponse({'ok': False, 'error': 'fetch_failed', 'detail': str(e)}, status=502)

def jma_forecast_nagano(request):
    url = "https://www.jma.go.jp/bosai/forecast/data/forecast/200000.json"
    try:
        r = requests.get(url, timeout=7)
        r.raise_for_status()
        data = r.json()
    except requests.RequestException as e:
        return JsonResponse({'error': 'jma_fetch_failed', 'detail': str(e)}, status=502)

    now = datetime.now(JST)
    target = now.replace(hour=17, minute=30, second=0, microsecond=0)
    result = {'time': target.isoformat(), 'source': 'JMA', 'city': 'Nagano', 'temp': None, 'pop': None, 'weather': None}

    try:
        time_series = data[0]['timeSeries']
    except (KeyError, IndexError, TypeError):
        return JsonResponse({'error': 'jma_format_unexpected'}, status=500)

    def nearest_index(times_iso):
        times = [datetime.fromisoformat(t.replace('Z', '+00:00')).astimezone(JST) for t in times_iso]
        diffs = [(abs((t - target).total_seconds()), i) for i, t in enumerate(times)]
        return min(diffs)[1] if diffs else -1

    for ts in time_series:
        times_iso = ts.get('timeDefines', [])
        idx = nearest_index(times_iso)
        if idx == -1 or not ts.get('areas'):
            continue
        area0 = ts['areas'][0]
        if 'weathers' in area0 and len(area0['weathers']) > idx:
            result['weather'] = area0['weathers'][idx]
            result['time'] = times_iso[idx]
        if 'temps' in area0 and len(area0['temps']) > idx:
            try:
                result['temp'] = float(area0['temps'][idx])
            except ValueError:
                result['temp'] = None
        if 'pops' in area0 and len(area0['pops']) > idx:
            try:
                result['pop'] = int(area0['pops'][idx])
            except ValueError:
                result['pop'] = None

    return JsonResponse(result)
