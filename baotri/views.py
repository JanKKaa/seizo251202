from django.shortcuts import render, redirect, get_object_or_404
from .models import MaintenanceTask, TaskDetail, TaskResult, TaskCode, TaskCodeDetail, MaintenanceMistake
from django.contrib.auth.decorators import login_required
from .forms import MaintenanceTaskForm, MaintenanceMistakeForm, MaintenanceMistakeFormSet, QuickMistakeFormSet
from datetime import datetime
from django.db import transaction
from django.contrib.auth.models import User
import base64
from django.core.files.base import ContentFile
from django.contrib import messages
from django.db.models import Q
from django.contrib.auth.models import User
from django.utils import timezone
from django.utils.timezone import localtime
import pytz
from django.db.models import Count, F, ExpressionWrapper, DurationField, Min, Avg
from django.db.models import F
from django.core.paginator import Paginator
from django.http import HttpResponse
from django.template.loader import render_to_string
from django.contrib.auth.decorators import login_required
from weasyprint import HTML
import csv
from .models import TaskCodeDetail
from collections import defaultdict
import json
import locale
from iot.models import MoldLifetime  # hoặc Mold nếu counter nằm ở Mold

def index(request):
    tasks = MaintenanceTask.objects.all()  # Lấy tất cả nhiệm vụ

    # Sắp xếp theo tên: alphabet, số, tiếng Nhật (unicode)
    # Nếu muốn sắp xếp tốt cho tiếng Nhật, nên dùng locale hoặc PyICU, ở đây dùng sort unicode mặc định:
    tasks = sorted(tasks, key=lambda t: str(t.name).lower())

    selected_task = None

    # Kiểm tra nếu có nhiệm vụ được chọn qua tham số `task_id`
    task_id = request.GET.get('task_id')
    if task_id:
        try:
            selected_task = MaintenanceTask.objects.get(id=task_id)
        except MaintenanceTask.DoesNotExist:
            selected_task = None

    return render(request, 'baotri/index.html', {
        'tasks': tasks,
        'selected_task': selected_task,
    })

@login_required
def task_list(request):
    tasks = MaintenanceTask.objects.all()  # Lấy danh sách tất cả nhiệm vụ
    return render(request, 'baotri/task_list.html', {'tasks': tasks})

@login_required
def add_task(request):
    if request.method == 'POST':
        form = MaintenanceTaskForm(request.POST, request.FILES)
        if form.is_valid():
            task = form.save(commit=False)
            task.creator = request.user  # Gán người tạo là user hiện tại
            task.save()
            form = MaintenanceTaskForm()  # Tạo form mới sau khi lưu thành công
            success_message = "正常に作成されました！"
        else:
            success_message = None
    else:
        form = MaintenanceTaskForm()
        success_message = None

    tasks = MaintenanceTask.objects.all()
    return render(request, 'baotri/add_task.html', {
        'form': form,
        'tasks': tasks,
        'success_message': success_message
    })

@login_required
def task_detail(request, task_id):
    task = get_object_or_404(MaintenanceTask, id=task_id)
    
    task_details = TaskDetail.objects.filter(task=task).order_by('order')

    if request.method == 'POST':
        # Cập nhật các chi tiết hiện có
        for detail in task_details:
            order = request.POST.get(f'order_{detail.id}')
            detail.item = request.POST.get(f'item_{detail.id}')
            detail.description = request.POST.get(f'description_{detail.id}')
            detail.drawing_size = request.POST.get(f'drawing_size_{detail.id}')
            if f'reference_image_{detail.id}' in request.FILES:
                detail.reference_image = request.FILES[f'reference_image_{detail.id}']
            detail.save()

        if 'save_order' in request.POST:
            # Chỉ cập nhật số thứ tự
            for detail in task_details:
                order = request.POST.get(f'order_{detail.id}')
                if order:
                    detail.order = int(order)
                    detail.save()
            messages.success(request, "順序が正常に保存されました！")
            return redirect('task_detail', task_id=task.id)

        # Thêm chi tiết mới
        if 'add_new' in request.POST:
            new_item = request.POST.get('new_item')
            new_description = request.POST.get('new_description')
            new_drawing_size = request.POST.get('new_drawing_size')
            new_reference_image = request.FILES.get('new_reference_image')

            if new_item and new_description and new_reference_image:
                TaskDetail.objects.create(
                    task=task,
                    item=new_item,
                    description=new_description,
                    drawing_size=new_drawing_size,
                    reference_image=new_reference_image,
                    order=TaskDetail.objects.filter(task=task).count() + 1
                )

        messages.success(request, "詳細が正常に更新されました！")
        return redirect('task_detail', task_id=task.id)

    return render(request, 'baotri/task_detail.html', {
        'task': task,
        'task_details': task_details,
    })

@login_required
def delete_task(request, task_id):
    task = get_object_or_404(MaintenanceTask, id=task_id)
    task.delete()  # Xóa nhiệm vụ
    messages.success(request, "削除されました！")
    return redirect('add_task')  # Chuyển hướng về trang thêm nhiệm vụ

@login_required
def delete_task_detail(request, task_id, detail_id):
    detail = get_object_or_404(TaskDetail, id=detail_id, task_id=task_id)
    detail.delete()
    messages.success(request, "詳細が正常に削除されました！")
    return redirect('task_detail', task_id=task_id)

@login_required
def task_code(request):
    # Lấy nhiệm vụ đã chọn từ request (GET hoặc POST)
    task_id = request.GET.get('task_id') or request.POST.get('task_id')
    if not task_id:
        return redirect('baotri_index')  # Nếu không có nhiệm vụ, quay lại trang index

    task = get_object_or_404(MaintenanceTask, id=task_id)

    # Tạo mã nhiệm vụ dựa trên thời gian
    task_code = f"MT-{datetime.now().strftime('%Y%m%d%H%M%S')}"

    if request.method == 'POST':
        # Kiểm tra tính duy nhất của mã nhiệm vụ
        while TaskCode.objects.filter(code=task_code).exists():
            task_code = f"MT-{datetime.now().strftime('%Y%m%d%H%M%S%f')}"  # Thêm microsecond để đảm bảo duy nhất

        # Tạo mã nhiệm vụ mới
        TaskCode.objects.create(
            code=task_code,
            task=task,
            created_by=request.user
        )

        messages.success(request, "コードが正常に作成されました！")
        return redirect('start_task', task_code=task_code)

    return render(request, 'baotri/task_code.html', {
        'task': task,
        'task_code': task_code,
    })

@login_required
def start_task(request, task_code):
    try:
        task_code_obj = TaskCode.objects.get(code=task_code)
        task = task_code_obj.task
    except TaskCode.DoesNotExist:
        return render(request, 'baotri/error.html', {
            'message': f"コードが見つかりません: {task_code}"
        })

    # --- ƯU TIÊN LƯU SHOT NGAY ĐẦU TIÊN ---
    def save_shot_to_taskcode(task_code_obj, task):
        task_name_norm = normalize_name(task.name)
        mold = None
        for m in MoldLifetime.objects.all():
            mold_name_norm = normalize_name(m.mold.name)
            if task_name_norm == mold_name_norm:
                mold = m
                break
        counter_total = mold.total_shot if mold else 0
        # Luôn cập nhật shot nếu lớn hơn giá trị cũ
        if task_code_obj.counter_total is None or counter_total > task_code_obj.counter_total:
            task_code_obj.counter_total = counter_total
            task_code_obj.save(update_fields=['counter_total'])

    save_shot_to_taskcode(task_code_obj, task)
    # --- KẾT THÚC ĐOẠN ƯU TIÊN LƯU SHOT ---

    task_details = TaskDetail.objects.filter(task=task).order_by('order')

    for detail in task_details:
        TaskCodeDetail.objects.get_or_create(
            task_code=task_code_obj,
            detail=detail,
            defaults={
                'result': '',
                'actual_size': '',
                'is_confirmed': False,
                'maintainer': request.user
            }
        )

    task_code_details = TaskCodeDetail.objects.filter(task_code=task_code_obj)

    # Reset start_time mỗi lần mở trang
    from django.utils import timezone
    task.start_time = timezone.now()
    task.save()
    start_time_ts = int(task.start_time.timestamp())

    # Lấy counter tổng ngay khi vào trang
    task_name_norm = normalize_name(task.name)
    mold = None
    for m in MoldLifetime.objects.all():
        mold_name_norm = normalize_name(m.mold.name)
        if task_name_norm == mold_name_norm:
            mold = m
            break
    counter_total = mold.total_shot if mold else None

    if request.method == 'POST':
        # Lấy counter tổng 1 lần khi bắt đầu lưu
        task_name_norm = normalize_name(task.name)
        mold = None
        for m in MoldLifetime.objects.all():
            mold_name_norm = normalize_name(m.mold.name)
            if task_name_norm == mold_name_norm:
                mold = m
                break
        counter_total = mold.total_shot if mold else None

        # Lưu counter vào TaskCode (lịch sử bảo trì)
        task_code_obj.counter_total = counter_total if counter_total is not None else 0
        task_code_obj.end_time = datetime.now()
        task_code_obj.save()

        for detail in task_code_details:
            result_value = request.POST.get(f'result_{detail.detail.id}')
            actual_size = request.POST.get(f'actual_size_{detail.detail.id}')
            actual_image_data = request.POST.get(f'actual_image_{detail.detail.id}')
            is_confirmed = request.POST.get(f'confirm_{detail.detail.id}') == 'on'

            if result_value:
                detail.result = result_value
            if actual_size:
                detail.actual_size = actual_size
            if actual_image_data:
                format, imgstr = actual_image_data.split(';base64,')
                ext = format.split('/')[-1]
                file_name = f"actual_image_{detail.detail.id}.{ext}"
                detail.actual_image.save(file_name, ContentFile(base64.b64decode(imgstr)), save=False)
            detail.is_confirmed = is_confirmed

            detail.save()

        missing_image = any(not d.actual_image for d in task_code_details)
        if missing_image:
            messages.error(request, "すべての項目で実際の写真を撮影してください。（未入力の項目があります）")
            return redirect('start_task', task_code=task_code)

        messages.success(request, "結果が正常に保存されました！")
        return redirect('baotri_index')

    # Lấy thời gian bắt đầu
    start_time = task.start_time or timezone.now()
    elapsed_seconds = (timezone.now() - start_time).total_seconds()

    # Nếu là POST hoặc đã vượt quá 6 tiếng (21600 giây), tiến hành lưu dữ liệu
    if request.method == 'POST' or elapsed_seconds >= 21600:
        # Bỏ qua mọi xác nhận, chỉ lưu dữ liệu hiện có
        for detail in task_code_details:
            result_value = request.POST.get(f'result_{detail.detail.id}', detail.result)
            actual_size = request.POST.get(f'actual_size_{detail.detail.id}', detail.actual_size)
            actual_image_data = request.POST.get(f'actual_image_{detail.detail.id}', None)
            is_confirmed = request.POST.get(f'confirm_{detail.detail.id}') == 'on' if f'confirm_{detail.detail.id}' in request.POST else detail.is_confirmed

            if result_value:
                detail.result = result_value
            if actual_size:
                detail.actual_size = actual_size
            if actual_image_data:
                try:
                    format, imgstr = actual_image_data.split(';base64,')
                    ext = format.split('/')[-1]
                    file_name = f"actual_image_{detail.detail.id}.{ext}"
                    detail.actual_image.save(file_name, ContentFile(base64.b64decode(imgstr)), save=False)
                except Exception:
                    pass
            detail.is_confirmed = is_confirmed
            detail.save()

        # Lưu thời gian kết thúc
        task_code_obj.end_time = timezone.now()
        task_code_obj.save()

        # Chuyển về trang chủ sau khi lưu
        return redirect('baotri_index')

    # Nếu là lần đầu mở start task, gán lại start_time
    if not task.start_time:
        task.start_time = timezone.now()
        task.save()
    start_time_ts = int(task.start_time.timestamp())

    # Lấy thời gian bắt đầu (timestamp)
    start_time_ts = int(task.start_time.timestamp()) if task.start_time else int(timezone.now().timestamp())

    return render(request, 'baotri/start_task.html', {
        'task_code': task_code,
        'task': task,
        'task_details': task_details,
        'task_code_details': task_code_details,
        'counter_total': counter_total,  # Truyền vào context
        'start_time_ts': start_time_ts,
    })

@login_required
def task_code_list(request):
    # Lấy tất cả các task_code
    task_codes = TaskCode.objects.all().order_by('-created_at')

    # Lọc theo từ khóa tìm kiếm
    search_query = request.GET.get('search', '')
    if search_query:
        task_codes = task_codes.filter(
            Q(code__icontains=search_query) | Q(task__name__icontains=search_query)
        )

    # Lọc theo người tạo
    creator_id = request.GET.get('creator', '')
    if creator_id:
        task_codes = task_codes.filter(created_by_id=creator_id)

    # Tính khoảng thời gian cho từng task_code (sau khi lọc)
    for task_code in task_codes:
        if task_code.end_time:
            duration = task_code.end_time - task_code.created_at
            hours, remainder = divmod(duration.total_seconds(), 3600)
            minutes = remainder // 60
            task_code.duration = f"{int(hours)}時間 {int(minutes)}分"
        else:
            task_code.duration = "N/A"

    # Lấy danh sách người tạo để hiển thị trong dropdown
    creators = User.objects.filter(taskcode__isnull=False).distinct()

    # Pagination
    paginator = Paginator(task_codes, 15)  # 15 dòng mỗi trang
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    return render(request, 'baotri/task_code_list.html', {
        'task_codes': page_obj,
        'creators': creators,
    })

@login_required
def delete_task_code(request, task_code_id):
    task_code = get_object_or_404(TaskCode, id=task_code_id)
    task_code.delete()  # Xóa mã nhiệm vụ
    messages.success(request, "コードが正常に削除されました！")
    return redirect('task_code_list')  # Chuyển hướng về danh sách mã nhiệm vụ

from django.http import HttpResponseForbidden

@login_required
def edit_task(request, task_id):
     # Kiểm tra quyền admin
    if not request.user.is_superuser:
        return HttpResponseForbidden("編集は出来ません！")
    # Sử dụng MaintenanceTask thay vì Task
    task = get_object_or_404(MaintenanceTask, id=task_id)

    if request.method == 'POST':
        task.name = request.POST.get('name')
        task.product_code = request.POST.get('product_code')
        task.code = request.POST.get('code')
        task.machine_count = request.POST.get('machine_count')
        task.material = request.POST.get('material')

        if 'task_image' in request.FILES:
            task.task_image = request.FILES['task_image']
        if 'product_image' in request.FILES:
            task.product_image = request.FILES['product_image']

        task.save()
        messages.success(request, "編集が出来ました!")
        return redirect('baotri_index')

    return render(request, 'baotri/index.html', {'selected_task': task})

@login_required
def edit_task_code_time(request, pk):
    task_code = get_object_or_404(TaskCode, pk=pk)
    if request.method == 'POST':
        new_time = request.POST.get('created_at')
        if new_time:
            import datetime
            # new_time dạng 'YYYY-MM-DDTHH:MM'
            dt = datetime.datetime.strptime(new_time, '%Y-%m-%dT%H:%M')
            # Gán timezone Tokyo
            tokyo = pytz.timezone('Asia/Tokyo')
            dt_tokyo = tokyo.localize(dt)
            # Chuyển về UTC nếu USE_TZ=True
            dt_utc = dt_tokyo.astimezone(pytz.UTC)
            task_code.created_at = dt_utc
            task_code.save()
    return redirect('task_code_list')

@login_required
def dashboard(request):
    # Lấy khoảng thời gian từ GET (hoặc mặc định 30 ngày gần nhất)
    start = request.GET.get('start')
    end = request.GET.get('end')
    if not start or not end:
        end_date = timezone.now()
        start_date = end_date - timezone.timedelta(days=30)
    else:
        start_date = datetime.strptime(start, '%Y-%m-%d')
        end_date = datetime.strptime(end, '%Y-%m-%d')
        end_date = timezone.make_aware(end_date)
        start_date = timezone.make_aware(start_date)

    # Lọc TaskCode theo khoảng thời gian
    task_codes = TaskCode.objects.filter(created_at__range=(start_date, end_date))

    # Người làm nhiều việc nhất
    most_tasks = (
        task_codes.values('created_by__id', 'created_by__first_name', 'created_by__last_name')
        .annotate(total=Count('id'))
        .order_by('-total')
        .first()
    )

    # Người hoàn thành nhanh nhất (nếu có trường end_time)
    fastest = (
        task_codes.annotate(
            duration=ExpressionWrapper(F('end_time') - F('created_at'), output_field=DurationField())
        )
        .exclude(end_time=None)
        .order_by('duration')
        .first()
    )

    # Lấy top 5 người làm nhiều nhất
    tasks_ranking = (
        TaskCode.objects.filter(created_at__range=(start_date, end_date))
        .values('created_by__first_name', 'created_by__last_name')
        .annotate(total=Count('id'))
        .order_by('-total')[:10]
    )
    # Lấy top 5 người có task nhanh nhất (có end_time)
    fastest_ranking = (
        TaskCode.objects.filter(created_at__range=(start_date, end_date), end_time__isnull=False)
        .annotate(
            duration=ExpressionWrapper(F('end_time') - F('created_at'), output_field=DurationField()),
            product_name=F('task__name')
        )
        .values('created_by__first_name', 'created_by__last_name', 'code', 'product_name', 'duration')
        .order_by('duration')[:10]
    )

    # Chuyển duration về số phút
    for item in fastest_ranking:
        if item['duration']:
            item['duration_min'] = round(item['duration'].total_seconds() / 60, 2)
        else:
            item['duration_min'] = 0


    # Lấy tất cả các lần bảo trì đã hoàn thành (theo khoảng thời gian đã chọn)
    maintenances = task_codes.select_related('created_by')

    # Gom nhóm theo giờ bắt đầu (start_time)
    hour_stats = defaultdict(lambda: {'count': 0, 'users': set()})
    for m in maintenances:
        hour = localtime(m.created_at).hour  # Dùng created_at thay cho start_time
        hour_stats[hour]['count'] += 1
        code_details = TaskCodeDetail.objects.filter(task_code=m)
        for d in code_details:
            if d.maintainer:
                hour_stats[hour]['users'].add(d.maintainer.get_full_name() or d.maintainer.username)

    # Chuyển sang list để render và truyền cho Chart.js
    hour_stats_list = []
    labels = []
    data = []
    users = []
    for h in range(24):
        user_list = ', '.join(hour_stats[h]['users']) if hour_stats[h]['users'] else ''
        hour_stats_list.append({
            'hour_range': f"{h:02d}:00 - {h+1:02d}:00",
            'count': hour_stats[h]['count'],
            'users': user_list,
        })
        labels.append(f"{h:02d}:00")
        data.append(hour_stats[h]['count'])
        users.append(user_list)

    # Lọc TaskCode có thời gian bảo trì hợp lệ (30 phút <= duration <= 6 tiếng)
    valid_tasks = (
        TaskCode.objects
        .filter(
            created_at__range=(start_date, end_date),
            end_time__isnull=False
        )
        .annotate(
            duration=ExpressionWrapper(F('end_time') - F('created_at'), output_field=DurationField()),
            duration_min=ExpressionWrapper((F('end_time') - F('created_at')) / 60, output_field=DurationField()),
            product_name=F('task__name')
        )
        .filter(
            duration__gte=timezone.timedelta(minutes=30),
            duration__lte=timezone.timedelta(hours=6)
        )
    )

    # Tính trung bình thời gian bảo trì cho từng sản phẩm
    avg_times = (
        valid_tasks
        .values('product_name')
        .annotate(avg_duration=Avg('duration'))
        .order_by('product_name')
    )

    # Chuyển avg_duration về số phút
    avg_time_list = []
    for item in avg_times:
        avg_min = round(item['avg_duration'].total_seconds() / 60, 2) if item['avg_duration'] else 0
        avg_time_list.append({
            'product_name': item['product_name'],
            'avg_min': avg_min
        })

    return render(request, 'baotri/dashboard.html', {
        'most_tasks': most_tasks,
        'fastest': fastest,
        'tasks_ranking': tasks_ranking,
        'fastest_ranking': fastest_ranking,
        'start': start_date.strftime('%Y-%m-%d'),  # Sửa lại thành chuỗi yyyy-MM-dd
        'end': end_date.strftime('%Y-%m-%d'),      # Sửa lại thành chuỗi yyyy-MM-dd
        'hour_stats_list': hour_stats_list,
        'chart_labels': json.dumps(labels),
        'chart_data': json.dumps(data),
        'chart_users': json.dumps(users),
        'avg_time_list': avg_time_list,
    })

@login_required
def export_maintenance_pdf(request):
    histories = TaskCodeDetail.objects.select_related('task_code', 'detail', 'maintainer').all()
    html_string = render_to_string('baotri/export_pdf.html', {'histories': histories})
    pdf_file = HTML(string=html_string, base_url=request.build_absolute_uri()).write_pdf()
    response = HttpResponse(pdf_file, content_type='application/pdf')
    response['Content-Disposition'] = 'attachment; filename="maintenance_history.pdf"'
    return response

@login_required
def export_maintenance_csv(request):
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="maintenance_history.csv"'
    writer = csv.writer(response)
    writer.writerow(['ID', 'コード', '作業名', '設備名', '担当者', '結果', '実際の寸法', '確認済み', '作成日時'])
    histories = TaskCodeDetail.objects.select_related('task_code', 'detail', 'maintainer').all()
    for h in histories:
        writer.writerow([
            h.id,
            h.task_code.code if h.task_code else '',
            h.detail.item if h.detail else '',
            h.task_code.task.name if h.task_code and h.task_code.task else '',
            f"{h.maintainer.last_name} {h.maintainer.first_name}" if h.maintainer else '',
            h.result or '',
            h.actual_size or '',
            'はい' if h.is_confirmed else 'いいえ',
            h.created_at.strftime('%Y-%m-%d %H:%M') if h.created_at else '',
        ])
    return response

from django.shortcuts import get_object_or_404, redirect, render
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from .models import TaskCode
from .forms import SupervisorConfirmForm
from django.contrib.admin.views.decorators import staff_member_required

@login_required
def confirm_task_code(request, pk):
    task_code = get_object_or_404(TaskCode, pk=pk)
    if request.method == 'POST':
        form = SupervisorConfirmForm(request.POST, request.FILES, instance=task_code)
        if form.is_valid():
            task_code = form.save(commit=False)
            task_code.is_confirmed_by_supervisor = True
            task_code.supervisor = request.user
            task_code.supervisor_confirmed_at = timezone.now()
            # Bình luận đã được lưu qua form
            task_code.save()
            return redirect('task_code_detail', task_code_id=pk)
    else:
        form = SupervisorConfirmForm(instance=task_code)
    return render(request, 'baotri/supervisor_confirm_form.html', {'form': form, 'task_code': task_code})

@staff_member_required
def remove_supervisor_confirm(request, pk):
    task_code = get_object_or_404(TaskCode, pk=pk)
    if request.method == 'POST':
        task_code.is_confirmed_by_supervisor = False
        task_code.supervisor_stamp.delete(save=False)
        task_code.supervisor_stamp = None
        task_code.supervisor = None
        task_code.supervisor_confirmed_at = None
        task_code.save()
    return redirect('task_code_detail', task_code_id=task_code.id)  # Sửa ở đây

@login_required
def mistake_manage(request, edit_pk=None):
    # Formset cho nhập nhiều dòng mới
    if request.method == 'POST' and 'add_submit' in request.POST:
        formset = QuickMistakeFormSet(request.POST, queryset=MaintenanceMistake.objects.none())
        if formset.is_valid():
            instances = formset.save(commit=False)
            for instance in instances:
                instance.created_by = request.user
                instance.save()
            messages.success(request, "ミス情報が保存されました。")
            return redirect('mistake_manage')
    else:
        formset = QuickMistakeFormSet(queryset=MaintenanceMistake.objects.none())

    # Form chỉnh sửa một dòng (nếu có)
    edit_instance = None
    edit_form = None
    if edit_pk:
        edit_instance = get_object_or_404(MaintenanceMistake, pk=edit_pk)
        if request.method == 'POST' and 'edit_submit' in request.POST:
            edit_form = MaintenanceMistakeForm(request.POST, request.FILES, instance=edit_instance)
            if edit_form.is_valid():
                edit_form.save()
                messages.success(request, "ミス情報が更新されました。")
                return redirect('mistake_manage')
        else:
            edit_form = MaintenanceMistakeForm(instance=edit_instance)

    # Danh sách mistake đã nhập
    mistakes = MaintenanceMistake.objects.select_related('product').order_by('-created_at')
    return render(request, 'baotri/mistake_manage.html', {
        'formset': formset,
        'mistakes': mistakes,
        'edit_form': edit_form,
        'edit_instance': edit_instance,
    })

def normalize_name(name):
    import re
    return re.sub(r'\W+', '', name).strip().lower()

@login_required
def task_code_detail(request, task_code_id):
    task_code = get_object_or_404(TaskCode, id=task_code_id)
    task = task_code.task
    task_code_details = TaskCodeDetail.objects.filter(task_code=task_code).order_by('detail__order')

    # Lấy counter tổng từ MoldLifetime theo tên sản phẩm
    counter_total = None
    if task and hasattr(task, 'name'):
        task_name_norm = normalize_name(task.name)
        for m in MoldLifetime.objects.all():
            mold_name_norm = normalize_name(m.mold.name)
            if task_name_norm == mold_name_norm:
                counter_total = m.total_shot
                break

    return render(request, 'baotri/task_code_detail.html', {
        'task_code': task_code,
        'task': task,
        'task_code_details': task_code_details,
        'counter_total': counter_total,  # Truyền vào template
    })

@login_required
def shot_report(request):
    task_codes_qs = (
        TaskCode.objects
        .select_related('task')
        .order_by('task_id', 'created_at')
    )

    task_groups = defaultdict(list)
    for code in task_codes_qs:
        task_groups[code.task_id].append(code)

    latest_rows = []
    monthly_groups = defaultdict(list)

    for task_id, codes in task_groups.items():
        if not codes:
            continue

        task = codes[0].task
        latest = codes[-1]
        previous = codes[-2] if len(codes) > 1 else None

        shot_diff = None
        if (
            previous
            and latest.counter_total is not None
            and previous.counter_total is not None
        ):
            delta = latest.counter_total - previous.counter_total
            if delta > 0:
                shot_diff = delta

        valid_intervals = []
        last_valid = None
        for code in codes:
            counter = code.counter_total
            if counter is None or counter <= 0:
                last_valid = None
                continue

            if last_valid is None or last_valid.counter_total is None:
                last_valid = code
                continue

            diff_val = code.counter_total - last_valid.counter_total
            if diff_val <= 0:
                last_valid = None
                continue

            valid_intervals.append((last_valid, code, diff_val))
            month_key = timezone.localtime(code.created_at).strftime('%Y-%m')
            monthly_groups[(task_id, month_key)].append(diff_val)
            last_valid = code

        avg_all = round(
            sum(val for _, _, val in valid_intervals) / len(valid_intervals)
        ) if valid_intervals else None

        if shot_diff is None:
            analysis = (
                "十分なショットデータがありません。"
                if avg_all is None
                else "最新データのカウンター不足のため評価できません。"
            )
        else:
            if avg_all is None:
                analysis = "ショット差分が取得できました。データの蓄積を継続してください。"
            elif shot_diff >= avg_all:
                analysis = "ショット数が増加しており、改善効果が確認できます。"
            else:
                analysis = "ショット数が短くなっているため、設備改善・保守が必要です。"

        latest_rows.append({
            "task": task,
            "latest": latest,
            "previous": previous,
            "shot_diff": shot_diff,
            "average_interval": avg_all,
            "analysis": analysis,
        })

        last_valid = None
        for code in codes:
            counter = code.counter_total
            if counter is None or counter <= 0:
                last_valid = None
                continue

            if last_valid is None or last_valid.counter_total is None:
                last_valid = code
                continue

            diff_val = counter - last_valid.counter_total
            if diff_val is None or diff_val <= 0:
                last_valid = None
                continue

            month_key = timezone.localtime(code.created_at).strftime('%Y-%m')
            monthly_groups[(task_id, month_key)].append(diff_val)
            last_valid = code

    latest_rows.sort(
        key=lambda row: row['task'].name.lower() if row['task'] and row['task'].name else ''
    )

    monthly_rows = []
    chart_matrix = defaultdict(dict)
    for (task_id, month_key), diffs in monthly_groups.items():
        if not diffs:
            continue
        task = task_groups[task_id][0].task if task_groups[task_id] else None
        product_name = task.name if task and task.name else "未設定"
        average = round(sum(diffs) / len(diffs)) if diffs else 0
        monthly_rows.append({
            "task": task,
            "month": month_key,
            "average": average,
            "samples": len(diffs),
        })
        chart_matrix[product_name][month_key] = average

    monthly_rows.sort(
        key=lambda row: (
            row['task'].name.lower() if row['task'] and row['task'].name else '',
            row['month']
        )
    )

    month_labels = sorted({row['month'] for row in monthly_rows})
    chart_dataset_map = {}
    chart_comments = {}
    for product_name, month_data in sorted(chart_matrix.items()):
        chart_dataset_map[product_name] = [
            month_data.get(month, None) for month in month_labels
        ]
        sorted_months = sorted(month_data.items())
        if len(sorted_months) < 2:
            chart_comments[product_name] = "データが不足しているため傾向を評価できません。"
            continue
        (_, prev_avg), (_, latest_avg) = sorted_months[-2], sorted_months[-1]
        if latest_avg > prev_avg:
            chart_comments[product_name] = "ショット差分が増加傾向です。改善が継続しています。"
        elif latest_avg < prev_avg:
            chart_comments[product_name] = "ショット差分が減少しています。設備の改善・保守を検討してください。"
        else:
            chart_comments[product_name] = "ショット差分は安定しています。現状維持を継続してください。"

    return render(request, 'baotri/quanlyshot.html', {
        'latest_rows': latest_rows,
        'monthly_rows': monthly_rows,
        'chart_labels': json.dumps(month_labels),
        'chart_dataset_map': json.dumps(chart_dataset_map),
        'chart_comments': json.dumps(chart_comments),
    })
