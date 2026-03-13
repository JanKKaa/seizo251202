import time
from .models import AccessLog
from menu.models import NhanVien


class LearnAccessLogMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        start = time.time()
        response = self.get_response(request)
        duration_ms = int((time.time() - start) * 1000)

        if not request.path.startswith('/learn/'):
            return response
        if request.path.startswith('/learn/thumb/'):
            return response
        if request.method not in {'GET', 'POST'}:
            return response

        user = request.user if request.user.is_authenticated else None
        ma_so = request.session.get('ma_nv', '') or (user.username if user and user.username != 'kanri' else '')
        ten = ''
        if ma_so:
            nv = NhanVien.objects.filter(ma_so=ma_so).first()
            if nv:
                ten = nv.ten

        ip = request.META.get('HTTP_X_FORWARDED_FOR', '').split(',')[0].strip() or request.META.get('REMOTE_ADDR', '')
        user_agent = request.META.get('HTTP_USER_AGENT', '')[:255]

        # Throttle pageview: count as a new access only if last pageview > 10 minutes ago
        now_ts = time.time()
        last_ts = request.session.get('learn_last_pageview_ts')
        should_log_pageview = True
        try:
            if last_ts and (now_ts - float(last_ts)) < 600:
                should_log_pageview = False
        except Exception:
            should_log_pageview = True

        if should_log_pageview:
            AccessLog.objects.create(
                user=user,
                ma_so=ma_so,
                ten=ten,
                event_type="pageview",
                path=request.path,
                method=request.method,
                ip=ip,
                user_agent=user_agent,
                duration_ms=duration_ms,
            )
            request.session['learn_last_pageview_ts'] = now_ts

        return response
