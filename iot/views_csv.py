import csv
import re
from django.shortcuts import render, redirect, get_object_or_404
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.contrib import messages
from datetime import datetime, timedelta, date
from django.utils import timezone
from django.db.models import Q
from .models import ProductionPlan, ProductShotMaster, Net100CycleShot

MATERIAL_MACHINES = [str(code) for code in range(200, 221)]


def _decode_uploaded_csv(file_obj):
    try:
        return file_obj.read().decode('utf-8')
    except UnicodeDecodeError:
        file_obj.seek(0)
        return file_obj.read().decode('cp932')


def _parse_month_header(header_text):
    match = re.match(r'(\d+)年(\d+)月', header_text or "")
    if match:
        year = int(match.group(1))
        year = 2000 + year if year < 100 else year
        month = int(match.group(2))
        return year, month, f"{year}-{month:02d}", f"{year}年{month}月"
    today = datetime.today()
    return today.year, today.month, f"{today.year}-{today.month:02d}", f"{today.year}年{today.month}月"

def _strip_material_code(name: str) -> str:
    if not name:
        return ""
    cleaned = re.sub(r'^\s*8[0-9A-Za-z\-]*\s+', '', str(name))
    return cleaned.strip() or str(name).strip()


def get_latest_plan_created_date(machine_filter=None):
    qs = ProductionPlan.objects.all()
    if machine_filter == 'material':
        qs = qs.filter(machine__in=MATERIAL_MACHINES)
    elif machine_filter == 'production':
        qs = qs.exclude(machine__in=MATERIAL_MACHINES)
    latest = qs.order_by('-plan_created_date').first()
    return getattr(latest, 'plan_created_date', '')


@csrf_exempt
def upload_production_plan(request):
    debug_logs = []
    if request.method == "POST":
        if "delete_all" in request.POST:
            ProductionPlan.objects.exclude(machine__in=MATERIAL_MACHINES).delete()
            messages.success(request, "生産計画を全て削除しました（原材料は保持）。")
            return render(request, 'iot/upload_plan.html', {'debug_logs': debug_logs})
        file = request.FILES.get('csv_file')
        if not file or not file.name.endswith('.csv'):
            messages.error(request, "CSVファイルをアップロードしてください。")
            return redirect('upload_production_plan')
        try:
            decoded = _decode_uploaded_csv(file)
            rows = [row for row in csv.reader(decoded.splitlines()) if any(col.strip() for col in row)]
            if not rows:
                messages.error(request, "CSVにデータがありません。")
                return redirect('upload_production_plan')
            plan_month_year = rows[0][0].strip() if len(rows[0]) > 0 else ""
            plan_created_date = rows[0][3].strip() if len(rows[0]) > 3 else ""
            _, _, month_year, plan_month_year = _parse_month_header(plan_month_year)
            data_rows = rows[2:]
            plan_objs = []
            for idx, row in enumerate(data_rows, start=3):
                if len(row) < 10:
                    debug_logs.append(f"{idx}行目: 列数不足")
                    continue
                if row[5].strip() != '計画':
                    continue
                machine = row[0].strip()
                product_name = row[3].strip()
                if not machine:
                    debug_logs.append(f"{idx}行目: 機番が空")
                    continue
                for i in range(7, len(row)):
                    shot = row[i].strip()
                    if not shot.isdigit():
                        continue
                    qty = int(shot)
                    if qty == 0:
                        continue
                    day = i - 6
                    try:
                        plan_date = datetime.strptime(f"{month_year}-{day:02d}", "%Y-%m-%d").date()
                    except ValueError:
                        continue
                    plan_objs.append(ProductionPlan(
                        machine=machine,
                        plan_shot=qty,
                        plan_date=plan_date,
                        product_name=product_name,
                        plan_month_year=plan_month_year,
                        plan_created_date=plan_created_date,
                    ))
            if plan_objs:
                # CHỈ XÓA KẾ HOẠCH SẢN XUẤT, GIỮ NGUYÊN LIỆU
                ProductionPlan.objects.exclude(machine__in=MATERIAL_MACHINES).delete()
                ProductionPlan.objects.bulk_create(plan_objs)
                update_net100_current_product_by_plan()  # <--- Thêm dòng này
                messages.success(request, f"計画のアップロードが成功しました！{len(plan_objs)}行を保存しました。")
            else:
                messages.warning(request, "保存できる有効なデータがありません。")
        except Exception as exc:
            messages.error(request, f"ファイル処理エラー: {exc}")
    return render(request, 'iot/upload_plan.html', {'debug_logs': debug_logs})

@csrf_exempt
def upload_material_plan(request):
    debug_logs = []
    template_name = 'iot/upload_material_plan.html'
    if request.method == "POST":
        file = request.FILES.get('csv_file')
        if not file or not file.name.endswith('.csv'):
            messages.error(request, "原材料計画のCSVファイルをアップロードしてください。")
            return redirect('upload_material_plan')
        try:
            decoded = _decode_uploaded_csv(file)
            rows = [row for row in csv.reader(decoded.splitlines()) if any(col.strip() for col in row)]
            if not rows:
                messages.error(request, "CSVにデータがありません。")
                return redirect('upload_material_plan')
            plan_month_year = rows[0][0].strip() if len(rows[0]) > 0 else ""
            plan_created_date = rows[0][4].strip() if len(rows[0]) > 4 else datetime.now().strftime("%Y-%m-%d")
            _, _, month_year, plan_month_year = _parse_month_header(plan_month_year)
            plan_objs = []
            material_rows = []
            for idx, row in enumerate(rows, start=1):
                if len(row) < 7:
                    debug_logs.append(f"{idx}行目: 列数不足")
                    continue
                material_code = row[0].strip()
                product_name = row[1].strip()
                plan_flag = row[3].strip()
                if not material_code.startswith("8"):
                    debug_logs.append(f"{idx}行目: 部番が8で始まらないためスキップ")
                    continue
                if '納入' not in plan_flag:
                    debug_logs.append(f"{idx}行目: 納入がないためスキップ")
                    continue
                daily_entries = []
                # データ開始列: F (index 5)
                for i in range(5, len(row)):
                    shot = row[i].strip()
                    if not shot:
                        continue
                    normalized = shot.replace(",", "")
                    try:
                        qty_val = float(normalized)
                    except ValueError:
                        debug_logs.append(f"{idx}行目 列{chr(65+i)}: 数値ではないのでスキップ")
                        continue
                    qty = int(qty_val)
                    if qty <= 0:
                        continue
                    day = i - 4
                    try:
                        plan_date = datetime.strptime(f"{month_year}-{day:02d}", "%Y-%m-%d").date()
                    except ValueError:
                        continue
                    daily_entries.append((plan_date, qty))
                if daily_entries:
                    material_rows.append({
                        'product_name': (f"{material_code} {product_name}").strip() or f"Material-{idx}",
                        'entries': daily_entries,
                    })
            for m_idx, material_row in enumerate(material_rows):
                if m_idx >= len(MATERIAL_MACHINES):
                    break
                machine = MATERIAL_MACHINES[m_idx]
                for plan_date, qty in material_row['entries']:
                    plan_objs.append(ProductionPlan(
                        machine=machine,
                        plan_shot=qty,
                        plan_date=plan_date,
                        product_name=material_row['product_name'],
                        plan_month_year=plan_month_year,
                        plan_created_date=plan_created_date,
                    ))
            if plan_objs:
                ProductionPlan.objects.filter(machine__in=MATERIAL_MACHINES).delete()
                ProductionPlan.objects.bulk_create(plan_objs)
                messages.success(request, f"原材料計画を {len(plan_objs)} 行取り込みました。")
            else:
                messages.warning(request, "取り込める原材料データがありません。")
        except Exception as exc:
            messages.error(request, f"原材料CSVの処理に失敗しました: {exc}")
    return render(request, template_name, {'debug_logs': debug_logs})


def production_plan_status(request):
    first_plan = ProductionPlan.objects.first()
    plan_month_year = getattr(first_plan, 'plan_month_year', '') if first_plan else ""
    # Thêm 2 biến thời gian tạo cho từng loại
    plan_created_date_production = get_latest_plan_created_date('production')
    plan_created_date_material = get_latest_plan_created_date('material')
    plans = ProductionPlan.objects.all().order_by('machine', 'plan_date')
    table = {}
    days_with_data = set()
    for plan in plans:
        machine_key = plan.machine
        if machine_key not in table:
            table[machine_key] = {'machine': plan.machine, 'days': {day: [] for day in range(1, 32)}}
        display_name = plan.product_name
        if plan.machine in MATERIAL_MACHINES:
            display_name = _strip_material_code(plan.product_name)
        table[machine_key]['days'][plan.plan_date.day].append({
            'product_name': display_name,
            'plan_shot': plan.plan_shot,
            'cell_note': plan.cell_note,
            'id': plan.id,
        })
        if plan.plan_shot > 0:
            days_with_data.add(plan.plan_date.day)
    days_list = sorted(days_with_data)

    required_machines = ["100"] + MATERIAL_MACHINES
    for machine in required_machines:
        if machine not in table:
            table[machine] = {
                'machine': machine,
                'days': {day: [] for day in range(1, 32)}
            }

    def machine_sort_key(machine):
        if machine in MATERIAL_MACHINES:
            group = 2
        elif machine == "100":
            group = 1
        else:
            group = 0
        number = int(machine) if machine.isdigit() else 9999
        return (group, number)

    ordered_machines = sorted(table.keys(), key=machine_sort_key)
    table_rows = [{
        'machine': machine,
        'days': [table[machine]['days'][day] for day in days_list]
    } for machine in ordered_machines]

    today_day = datetime.today().day
    today_date = datetime.today().date()
    today_idx = days_list.index(today_day) if today_day in days_list else -1

    return render(request, 'iot/plan_status.html', {
        'table_rows': table_rows,
        'days_list': days_list,
        'plan_month_year': plan_month_year,
        'plan_created_date_production': plan_created_date_production,
        'plan_created_date_material': plan_created_date_material,
        'today_idx': today_idx,
        'material_machines': MATERIAL_MACHINES,
        'today_iso': today_date.strftime("%Y-%m-%d"),
    })


@csrf_exempt
def delete_plan_note(request):
    if request.method == "POST":
        plan_id = request.POST.get("plan_id")
        plan = get_object_or_404(ProductionPlan, id=plan_id)
        plan.cell_note = ""
        plan.note_type = ""
        plan.note_color = "bg-success"
        plan.save()
    return redirect('production_plan_status')


@csrf_exempt
def add_or_edit_plan_note(request):
    if request.method == "POST":
        plan_id = request.POST.get("plan_id")
        plan = get_object_or_404(ProductionPlan, id=plan_id)
        plan.cell_note = request.POST.get("cell_note", "")
        plan.note_type = request.POST.get("note_type", "")
        plan.note_color = request.POST.get("note_color", "bg-success")
        plan.save()
    return redirect('production_plan_status')


@csrf_exempt
def add_pallet_plan(request):
    if request.method == "POST":
        plan_date_str = request.POST.get("plan_date")
        plan_shot = request.POST.get("plan_shot")
        product_name = request.POST.get("product_name", "パレット回収").strip() or "パレット回収"
        if not plan_date_str or not plan_shot:
            messages.error(request, "日付と数量を入力してください。")
            return redirect('production_plan_status')
        try:
            plan_date = datetime.strptime(plan_date_str, "%Y-%m-%d").date()
            qty = int(plan_shot)
            if qty <= 0:
                raise ValueError
        except ValueError:
            messages.error(request, "日付または数量の形式が不正です。")
            return redirect('production_plan_status')
        ProductionPlan.objects.create(
            machine="100",
            plan_shot=qty,
            plan_date=plan_date,
            product_name=product_name,
            plan_month_year=f"{plan_date.year}年{plan_date.month}",
            plan_created_date=datetime.now().strftime("%Y-%m-%d"),
        )
        messages.success(request, "パレット計画を登録しました。")
    return redirect('iot:production_plan_status')


@csrf_exempt
@require_POST
def delete_pallet_plan(request):
    plan_id = request.POST.get("plan_id")
    plan = get_object_or_404(ProductionPlan, id=plan_id, machine="100")
    plan.delete()
    messages.success(request, "パレット計画を削除しました。")
    return redirect('iot:production_plan_status')


def master_import(request):
    if request.method == "POST" and request.FILES.get("csv_file"):
        csv_file = request.FILES["csv_file"]
        try:
            decoded = csv_file.read().decode("utf-8").splitlines()
        except UnicodeDecodeError:
            csv_file.seek(0)
            decoded = csv_file.read().decode("cp932").splitlines()
        reader = csv.DictReader(decoded)
        count = 0
        for row in reader:
            try:
                ProductShotMaster.objects.update_or_create(
                    machine=row["machine"].strip(),
                    product_name=row["product_name"].strip(),
                    defaults={
                        "standard_shot": int(row["standard_shot"]),
                        "kodori": int(row["kodori"]),
                        "note": row.get("note", ""),
                    }
                )
                count += 1
            except Exception as e:
                messages.error(request, f"行エラー: {row} ({e})")
        messages.success(request, f"{count}行をインポートしました。")
        return redirect("iot:master_import")
    # Trả về danh sách master, sắp xếp đúng thứ tự số máy
    import re
    def machine_sort_key(item):
        m = re.match(r'^(\d+)', str(item.machine))
        return int(m.group(1)) if m else 9999
    master_list = sorted(
        ProductShotMaster.objects.all(),
        key=machine_sort_key
    )
    return render(request, "iot/master.html", {"master_list": master_list})

@require_POST
def master_add(request):
    try:
        machine = request.POST["machine"].strip()
        product_name = request.POST["product_name"].strip()
        # 重複チェック（同じ機械・同じ製品名のみ警告）
        if ProductShotMaster.objects.filter(machine=machine, product_name=product_name).exists():
            messages.error(request, f"機械名「{machine}」の製品名「{product_name}」は既に存在します。")
        else:
            ProductShotMaster.objects.create(
                machine=machine,
                product_name=product_name,
                standard_shot=int(request.POST["standard_shot"]),
                kodori=int(request.POST["kodori"]),
                note=request.POST.get("note", ""),
            )
            messages.success(request, "マスターを追加しました。")
    except Exception as e:
        messages.error(request, f"追加時にエラーが発生しました: {e}")
    return redirect("iot:master_import")

@require_POST
def master_edit(request):
    try:
        obj = ProductShotMaster.objects.get(id=request.POST["id"])
        machine = request.POST["machine"].strip()
        product_name = request.POST["product_name"].strip()
        # 重複チェック（自分以外で同じ機械・同じ製品名のみ警告）
        if ProductShotMaster.objects.filter(machine=machine, product_name=product_name).exclude(id=obj.id).exists():
            messages.error(request, f"機械名「{machine}」の製品名「{product_name}」は既に存在します。")
        else:
            obj.machine = machine
            obj.product_name = product_name
            obj.standard_shot = int(request.POST["standard_shot"])
            obj.kodori = int(request.POST["kodori"])
            obj.note = request.POST.get("note", "")
            obj.save()
            messages.success(request, "マスターを更新しました。")
    except Exception as e:
        messages.error(request, f"更新時にエラーが発生しました: {e}")
    return redirect("iot:master_import")


def update_net100_current_product_by_plan():
    """
    Cập nhật Net100CycleShot.current_product theo ProductionPlan.
    Tối ưu: gom ProductionPlan theo máy, giảm truy vấn lặp.
    Logic vẫn giữ nguyên như cũ.
    """
    today = timezone.localdate()
    year = today.year
    month = today.month
    month_str = today.strftime("%Y-%m")

    # Lấy toàn bộ ProductionPlan của tháng, gom theo số máy chuẩn hóa
    plans = (
        ProductionPlan.objects
        .filter(
            plan_date__year=year,
            plan_date__month=month,
            plan_shot__gt=0,
        )
        .exclude(product_name__isnull=True)
        .exclude(product_name="")
        .values('machine', 'plan_date', 'product_name', 'plan_shot')
    )

    from collections import defaultdict

    def extract_num(machine):
        m = re.match(r'^(\d+)', str(machine))
        return str(int(m.group(1))) if m else None

    # Gom các kế hoạch theo số máy chuẩn hóa
    plan_map = defaultdict(list)
    for p in plans:
        num = extract_num(p['machine'])
        if num:
            plan_map[num].append(p)

    # Lấy toàn bộ Net100CycleShot của tháng
    shots = Net100CycleShot.objects.filter(month=month_str)

    for shot in shots:
        name = str(shot.name or "")
        addr = str(shot.address or "")
        m_name = re.match(r'^(\d+)', name)
        m_addr = re.match(r'^(\d+)', addr)
        raw_num = m_name.group(1) if m_name else (m_addr.group(1) if m_addr else None)
        if not raw_num:
            continue
        num = str(int(raw_num))

        # Gom các dạng máy có thể xuất hiện trong ProductionPlan
        num_int = int(num)
        cand_exact = {
            name,
            addr,
            num,
            f"{num_int:02d}",
            f"{num_int}号機",
        }

        # Regex: cho phép nhiều số 0 ở trước, nhưng sau num KHÔNG được là chữ số
        regex = rf'^\s*0*{re.escape(num)}(?!\d)'

        # Lọc các kế hoạch phù hợp với máy này
        plans_for_machine = [
            p for p in plan_map.get(num, [])
            if p['machine'] in cand_exact or re.match(regex, str(p['machine']))
        ]

        # Ưu tiên: hôm nay -> ngày gần nhất sau -> ngày gần nhất trước
        plan_today = None
        plan_after = None
        plan_before = None
        for p in plans_for_machine:
            if p['plan_date'] == today:
                plan_today = p
            elif p['plan_date'] > today:
                if not plan_after or p['plan_date'] < plan_after['plan_date']:
                    plan_after = p
            elif p['plan_date'] < today:
                if not plan_before or p['plan_date'] > plan_before['plan_date']:
                    plan_before = p

        plan = plan_today or plan_after or plan_before
        if plan and shot.current_product != plan['product_name']:
            shot.current_product = plan['product_name']
            shot.save(update_fields=['current_product'])
