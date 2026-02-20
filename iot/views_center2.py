from django.shortcuts import render
from django.utils import timezone
from django.db.models import Sum
from datetime import timedelta
from .models import Esp32CycleShot, ProductShotMaster, ProductionPlan
from calendar import monthrange
from datetime import date

MATERIAL_MACHINES = [str(code) for code in range(200, 216)]



def get_plan_for_day(target_date):
    # Lấy kế hoạch cho tất cả máy (không chỉ nguyên liệu)
    return list(
        ProductionPlan.objects.filter(
            plan_date=target_date,
            plan_shot__gt=0
        )
        .values('machine', 'product_name')
        .annotate(total_plan=Sum('plan_shot'))
        .order_by('machine')
    )

def center_panel2_partial(request):
    today = timezone.localdate()
    first_day = today.replace(day=1)
    last_day = today.replace(day=monthrange(today.year, today.month)[1])

    # Lấy tất cả ngày có kế hoạch trong tháng, loại trùng và sắp xếp
    plan_dates = list(
        ProductionPlan.objects.filter(
            plan_shot__gt=0,
            plan_date__range=(first_day, last_day)
        ).values_list('plan_date', flat=True)
    )
    unique_dates = sorted(set(plan_dates))

    # Tìm ngày tiếp theo thực sự có kế hoạch sau hôm nay
    next_plan_date = None
    for d in unique_dates:
        if d > today:
            next_plan_date = d
            break

    tomorrow = next_plan_date  # <-- Sửa chỗ này

    # Lấy kế hoạch hôm nay và ngày tiếp theo có kế hoạch
    plans_today = get_plan_for_day(today)
    plans_tomorrow = get_plan_for_day(tomorrow) if tomorrow else []

    # Tạo dict để so sánh theo máy
    today_dict = {p['machine']: p['product_name'] for p in plans_today}
    tomorrow_dict = {p['machine']: p['product_name'] for p in plans_tomorrow}

    compare_list = []
    all_machines = set(today_dict.keys()) | set(tomorrow_dict.keys())
    for machine in sorted(all_machines, key=lambda x: int(x) if str(x).isdigit() else str(x)):
        today_product = today_dict.get(machine)
        tomorrow_product = tomorrow_dict.get(machine)
        if tomorrow_product is not None:
            if today_product == tomorrow_product:
                status = "không thay đổi"
            else:
                status = tomorrow_product
            compare_list.append({
                'machine': machine,
                'today_product': today_product,
                'tomorrow_product': tomorrow_product,
                'status': status,
            })

    progress_list = get_progress_list()
    context = {
        'days_with_plan': [str(d) for d in unique_dates],
        'compare_list': compare_list,
        'today': today,
        'tomorrow': tomorrow,  # <-- Đảm bảo truyền ngày tiếp theo thực sự có kế hoạch
        'progress_list': progress_list,
    }
    return render(request, 'iot/partials/_center_panel2.html', context)




def get_material_plan_for_day(target_date):
    return list(
        ProductionPlan.objects.filter(
            machine__in=MATERIAL_MACHINES,
            plan_date=target_date
        )
        .values('machine', 'product_name')
        .annotate(total_plan=Sum('plan_shot'))
        .order_by('machine', 'product_name')
    )


def kpi_panel2_partial(request):
    today = timezone.localdate()
    tomorrow = today + timedelta(days=1)

    material_plans_today = get_material_plan_for_day(today)
    material_plans_tomorrow = get_material_plan_for_day(tomorrow)

    # Tính tổng số kg hôm nay từ danh sách đã có
    total_material_today = sum((plan.get('total_plan') or 0) for plan in material_plans_today)

    context = {
        'total_material_today': total_material_today,
        # Nếu không cần bảng chi tiết, có thể bỏ 2 dòng dưới
        'material_plans_today': material_plans_today,
        'material_plans_tomorrow': material_plans_tomorrow,
        'today_label': f"本日（{today:%m/%d}）",
        'tomorrow_label': f"翌日（{tomorrow:%m/%d}）",
    }
    return render(request, 'iot/partials/_kpi_panel2.html', context)

def get_progress_list():
    today = timezone.localdate()
    plans = (
        ProductionPlan.objects
        .filter(plan_shot__gt=0)
        .values('machine', 'product_name', 'plan_date')
        .annotate(total_plan=Sum('plan_shot'))
        .order_by('plan_date', 'machine', 'product_name')
    )
    progress_list = []
    for p in plans:
        machine = str(p['machine'])
        product_name = str(p['product_name'])
        plan_date = p['plan_date']
        total_plan = p['total_plan'] or 0

        # Lấy produced_qty và kodori nếu có (tùy logic thực tế)
        produced_qty = 0  # Thay bằng logic thực tế nếu có
        kodori = 1
        master = ProductShotMaster.objects.filter(machine=machine, product_name=product_name).first()
        if master:
            kodori = master.kodori

        percent = int(produced_qty * 100 / total_plan) if total_plan > 0 else 0
        is_done = plan_date < today
        progress_list.append({
            'machine': machine,
            'product_name': product_name,
            'plan_date': plan_date,
            'total_plan': total_plan,
            'produced_qty': produced_qty,
            'percent': percent,
            'kodori': kodori,
            'is_done': is_done,
        })
    # Sắp xếp: chưa xong lên trên, đã qua ngày xuống dưới
    progress_list.sort(key=lambda x: (x['is_done'], x['plan_date'], x['machine']))
    return progress_list