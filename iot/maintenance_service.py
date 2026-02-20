from datetime import timedelta
from django.utils import timezone

def compute_component_prediction(lifetime: int, baseline_shot: int, current_shot: int, cycletime_s: float):
    """
    Trả về dict: used, remaining, pct_used, hours_left, eta_datetime (hoặc None)
    """
    if lifetime is None or lifetime <= 0:
        return {
            'used': None, 'remaining': None, 'pct_used': None,
            'hours_left': None, 'eta': None
        }
    used = max(current_shot - (baseline_shot or 0), 0)
    remaining = lifetime - used
    pct_used = min(round(used / lifetime * 100, 1), 999.9)
    if remaining <= 0:
        return {
            'used': used, 'remaining': 0, 'pct_used': 100.0,
            'hours_left': 0, 'eta': None
        }
    if not cycletime_s or cycletime_s <= 0:
        return {
            'used': used, 'remaining': remaining, 'pct_used': pct_used,
            'hours_left': None, 'eta': None
        }
    total_seconds_left = remaining * cycletime_s
    hours_left = total_seconds_left / 3600
    eta = timezone.now() + timedelta(seconds=total_seconds_left)
    return {
        'used': used,
        'remaining': remaining,
        'pct_used': pct_used,
        'hours_left': round(hours_left, 2),
        'eta': eta
    }