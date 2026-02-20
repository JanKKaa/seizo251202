import os
import requests
from datetime import datetime, timedelta, timezone
from django.http import JsonResponse

JST = timezone(timedelta(hours=9))

def weather_minowa(request):
    api_key = os.getenv('OWM_API_KEY')
    if not api_key:
        return JsonResponse({'error': 'missing_api_key'}, status=500)

    params = {
        'lat': 35.989,
        'lon': 137.981,
        'appid': api_key,
        'units': 'metric',
        'lang': 'ja'
    }
    try:
        r = requests.get('https://api.openweathermap.org/data/2.5/weather', params=params, timeout=5)
        r.raise_for_status()
        data = r.json()
        result = {
            'temp': data.get('main', {}).get('temp'),
            'weather': data.get('weather', [{}])[0].get('description', ''),
            'humidity': data.get('main', {}).get('humidity'),
            'wind': data.get('wind', {}).get('speed'),
            'city': data.get('name', 'Minowa'),
            'time': datetime.now(JST).isoformat(),
            'source': 'OWM'
        }
        return JsonResponse(result)
    except requests.RequestException as e:
        return JsonResponse({'error': 'fetch_failed', 'detail': str(e)}, status=502)

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