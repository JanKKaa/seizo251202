from .models import Enrollment, MotivationalQuote
from menu.models import NhanVien
from django.db.models import Q

def is_kanri_account(user):
    if not user or not user.is_authenticated:
        return False
    username = (user.username or '').strip().lower()
    return bool(username == 'kanri' or user.is_staff or user.is_superuser)

def get_subordinate_ma_so_list(ma_so):
    try:
        nv = NhanVien.objects.get(ma_so=ma_so)
        return list(nv.subordinates.values_list('ma_so', flat=True))
    except NhanVien.DoesNotExist:
        return []

def pending_counts(request):
    user = getattr(request, "user", None)
    if is_kanri_account(user):
        # Kanri thấy tất cả đơn chờ kanri duyệt
        pending_course = Enrollment.objects.filter(status='pending_kanri').count()
        pending_report = Enrollment.objects.filter(report_status='pending_kanri').count()
    else:
        ma_so = request.session.get('ma_nv')
        if ma_so:
            subordinates = get_subordinate_ma_so_list(ma_so)
            if subordinates:
                pending_course = Enrollment.objects.filter(
                    user__username__in=subordinates,
                    status='pending_supervisor'
                ).count()
                pending_report = Enrollment.objects.filter(
                    user__username__in=subordinates,
                    status='approved',
                    report_status='pending_supervisor',
                ).filter(~Q(report_file=''), ~Q(report_file=None)).count()
            else:
                pending_course = 0
                pending_report = 0
        else:
            pending_course = 0
            pending_report = 0

    return {
        'pending_course_count': pending_course,
        'pending_report_count': pending_report,
    }

def motivational_quotes(request):
    db_quotes = list(MotivationalQuote.objects.values('text', 'author'))
    return {'db_quotes': db_quotes}
