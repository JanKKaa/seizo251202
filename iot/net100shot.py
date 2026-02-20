import re
from django.utils import timezone
from .models import Net100CycleShot, ProductionPlan
from .snapshot_service import fetch_runtime_index
from iot.models import ProductMonthlyShot
from django.db.models import F
from django.core.exceptions import MultipleObjectsReturned


def save_net100_shot(machine, month, shot, cycletime, name: str = "", current_product: str = ""):
    """
    Dùng cho nơi nào vẫn gọi theo kiểu cũ:
    - machine: dict realtime từ NET100 (có address, name, ...)
    - month: 'YYYY-MM'
    - shot: shot counter hiện tại
    - cycletime: thời gian chu kỳ hiện tại
    Tự động gán current_product từ kế hoạch nếu không truyền vào.
    """
    address = machine.get("address", "")
    name = name or machine.get("name", "")
    month_str = month  # dạng 'YYYY-MM'

    # Nếu caller không truyền current_product → lấy từ kế hoạch
    current_product = current_product or get_current_product(name, month_str)

    obj = update_net100_shot(
        address=address,
        name=name,
        shot=shot,
        current_product=current_product,
        month_str=month_str,
    )

    # Cập nhật thêm cycletime nếu có
    obj.cycletime = cycletime
    obj.save(update_fields=["cycletime"])
    return obj




def get_current_product(machine_name: str, month_str: str | None = None) -> str:
    """
    Lấy sản phẩm đang chạy cho máy Net100 dựa trên kế hoạch NGÀY HÔM NAY.
    Hỗ trợ map tên máy '6号機' <-> kế hoạch '06', '6', '06号機'.
    """
    today = timezone.localdate()
    if month_str:
        year, month = map(int, month_str.split("-"))
        today = today.replace(year=year, month=month)
    name = (machine_name or "").strip()
    m = re.match(r"^(\d+)", name)
    machine_keys = [name]
    if m:
        num = int(m.group(1))
        machine_keys.extend([
            str(num),
            f"{num:02d}",
            f"{num}号機",
            f"{num:02d}号機",
        ])
    # Lấy đúng kế hoạch NGÀY HÔM NAY
    plan = (
        ProductionPlan.objects
        .filter(
            machine__in=machine_keys,
            plan_date=today,
            plan_shot__gt=0,
        )
        .order_by("-plan_date", "-id")
        .first()
    )
    return plan.product_name if plan else ""

def update_net100_shot(address: str, name: str, shot: int, current_product: str, month_str: str | None = None):
    """
    Cộng dồn sản lượng thực tế theo tháng cho từng máy + sản phẩm.

    - shot: counter hiện tại của máy (shotno) đọc từ NET100.
    - monthly_shot: tổng sản lượng thực tế trong tháng (đã cộng dồn).
    - Xử lý luôn trường hợp shot bị reset (về 0).
    - current_product: tên sản phẩm hiện tại (đã map từ kế hoạch).
    """
    if month_str is None:
        today = timezone.localdate()
        month_str = today.strftime("%Y-%m")

    # 1 record / (address, name, month, current_product)
    try:
        obj, _ = Net100CycleShot.objects.get_or_create(
            address=address,
            name=name,
            month=month_str,
            current_product=current_product,
            defaults={'shot': 0, 'monthly_shot': 0},
        )
    except MultipleObjectsReturned:
        # Nếu dữ liệu cũ bị trùng key, lấy record mới nhất để dùng tiếp
        obj = (
            Net100CycleShot.objects
            .filter(
                address=address,
                name=name,
                month=month_str,
                current_product=current_product,
            )
            .order_by('-id')
            .first()
        )

    prev_shot = obj.shot or 0
    current_shot = max(int(shot or 0), 0)

    # Lần đầu khởi tạo: chỉ set giá trị, chưa cộng dồn
    if prev_shot == 0 and obj.monthly_shot == 0:
        obj.shot = current_shot
        obj.save(update_fields=["shot"])
        return obj

    # Tính delta, có xử lý reset counter
    if current_shot >= prev_shot:
        delta = current_shot - prev_shot
    else:
        # Máy reset counter (về 0), coi như sản lượng mới là current_shot
        delta = current_shot

    if delta > 0:
        obj.monthly_shot += delta

    obj.shot = current_shot
    obj.save(update_fields=["shot", "monthly_shot"])

    # --- Ghi vào ProductMonthlyShot (Net100) ---
    if delta > 0 and current_product:
        pms, _ = ProductMonthlyShot.objects.get_or_create(
            source="net100",
            address=address,
            product_name=current_product,
            month=month_str,
            defaults={"machine_name": name, "shot": 0},
        )
        pms.shot = (pms.shot or 0) + delta
        pms.save(update_fields=["shot"])

    return obj


def update_all_net100_shots():
    """
    Gọi định kỳ (cron / Task Scheduler / Celery):
    - Đọc realtime NET100 (fetch_runtime_index).
    - Xác định sản phẩm hiện tại từ ProductionPlan (theo tháng hiện tại).
    - Cộng dồn monthly_shot theo tháng / máy / sản phẩm.
    """
    machines = fetch_runtime_index()
    month_str = timezone.now().strftime('%Y-%m')

    for machine in machines:
        name = machine.get('name', '')
        address = machine.get('address', '')
        shot = int(machine.get('shotno', 0) or 0)

        current_product = get_current_product(name, month_str)

        update_net100_shot(
            address=address,
            name=name,
            shot=shot,
            current_product=current_product,
            month_str=month_str,
        )

    return f"Updated {len(machines)} Net100 machines for month {month_str}"