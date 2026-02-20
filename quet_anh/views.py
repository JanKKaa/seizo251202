import base64
from io import BytesIO
from django.core.files.base import ContentFile
from django.shortcuts import render, redirect, get_object_or_404
from django.http import HttpResponseRedirect, HttpResponseForbidden, JsonResponse
from django.urls import reverse
from .forms import QAResultForm
from .models import QAResult, QADeviceInfo
from .forms import QADeviceInfoForm
from django.contrib import messages
from django.core.mail import send_mail
from django.contrib.auth.models import User
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Sum, Count
from django.utils.dateparse import parse_date
from django.views.decorators.http import require_GET

from PIL import Image
import cv2
import numpy as np
import re
from django.db.models import Q
from django.utils import timezone
import difflib
from collections import defaultdict
from django.utils.timezone import localtime
import json

def preprocess_image(image):
    img = np.array(image.convert('L'))
    from PIL import ImageOps
    pil_img = Image.fromarray(img)
    pil_img = ImageOps.autocontrast(pil_img, cutoff=1)
    img = np.array(pil_img)
    img = cv2.medianBlur(img, 1)
    return Image.fromarray(img)

@login_required
def upload_image(request):
    result = None
    message = None
    ocr_text = None
    expected_text = request.POST.get('expected_text') or request.GET.get('expected_text')
    machine_number = request.POST.get('machine_number', '1')
    device_id = request.GET.get('device_id') or request.POST.get('device')
    device = None
    if device_id:
        try:
            device = QADeviceInfo.objects.get(id=device_id)
        except QADeviceInfo.DoesNotExist:
            device = None
    if request.method == 'POST':
        captured_image = request.POST.get('captured_image')
        input_weight = request.POST.get('input_weight')

        # ==== BẮT BUỘC: kiểm tra các trường quan trọng ===
        if not captured_image:
            messages.error(request, "画像を撮影してください。")
            device_list = QADeviceInfo.objects.all()
            return render(request, 'quet_anh/upload.html', {
                'form': QAResultForm(request.POST),
                'message': message,
                'expected_text': expected_text,
                'device_list': device_list,
                'device_id': device_id,
                'device': device,
            })
        if not expected_text or expected_text.strip() == "None":
            messages.error(request, "QRコードを読み取ってください。")
            device_list = QADeviceInfo.objects.all()
            return render(request, 'quet_anh/upload.html', {
                'form': QAResultForm(request.POST),
                'message': message,
                'expected_text': expected_text,
                'device_list': device_list,
                'device_id': device_id,
                'device': device,
            })
        if not input_weight or str(input_weight).strip() == "":
            messages.error(request, "重量(kg)を入力してください。")
            device_list = QADeviceInfo.objects.all()
            return render(request, 'quet_anh/upload.html', {
                'form': QAResultForm(request.POST),
                'message': message,
                'expected_text': expected_text,
                'device_list': device_list,
                'device_id': device_id,
                'device': device,
            })
        # ==== END kiểm tra ===

        if captured_image:
            format, imgstr = captured_image.split(';base64,')
            ext = format.split('/')[-1]
            img_content = ContentFile(base64.b64decode(imgstr), name=f"captured.{ext}")
            image_file = img_content

            form = QAResultForm(request.POST)
            if not form.is_valid():
                messages.error(request, f"フォームエラー: {form.errors}")
                device_list = QADeviceInfo.objects.all()
                return render(request, 'quet_anh/upload.html', {
                    'form': form,
                    'message': message,
                    'expected_text': expected_text,
                    'device_list': device_list,
                    'device_id': device_id,
                    'device': device,
                })
            qa_result = form.save(commit=False)
            qa_result.image = image_file
            qa_result.device = device

            user = request.user
            qa_result.operator_name = f"{user.last_name}".strip()

            image_file.seek(0)
            image = Image.open(image_file)
            image = preprocess_image(image)
            buffer = BytesIO()
            image.save(buffer, format='PNG')
            qa_result.processed_image.save(f"processed_{qa_result.id or 'new'}.png", ContentFile(buffer.getvalue()), save=False)

            try:
                from paddleocr import PaddleOCR
                ocr = PaddleOCR(use_angle_cls=True, lang='japan', rec=True, det=True)
                img_np = np.array(image)
                result_ocr = ocr.ocr(img_np, cls=True)
                paddle_text = ''.join([line[1][0] for line in result_ocr[0]])
                paddle_text = paddle_text.replace('\n', '').replace('\r', '').replace(' ', '')
            except Exception as e:
                paddle_text = f"データがありません"

            ocr_text = f"\n{paddle_text.strip()}\n"
            if expected_text:
                ocr_text += f"QRコード内容:\n{expected_text.strip()}\n"
            qa_result.data = ocr_text

            def normalize_text(text):
                import re
                if not text:
                    return ''
                return re.sub(r'\s+', '', text)

            expected_parts = [normalize_text(part) for part in (expected_text or '').split() if part.strip()]
            paddle_text_clean = normalize_text(paddle_text)

            def max_ratio(part, text):
                max_r = 0
                for i in range(len(text) - len(part) + 1):
                    window = text[i:i+len(part)]
                    ratio = difflib.SequenceMatcher(None, part, window).ratio()
                    if ratio > max_r:
                        max_r = ratio
                return max_r

            match_ratios = []
            for part in expected_parts:
                ratio = max_ratio(part, paddle_text_clean)
                match_ratios.append(round(ratio * 100, 1))

            min_ratio = min(match_ratios) if match_ratios else 0

            is_match = False
            matched_text = ""
            if device and hasattr(device, 'compare_ratio'):
                try:
                    match_threshold = float(device.compare_ratio)
                    if not match_threshold:
                        match_threshold = 80.0
                except (TypeError, ValueError):
                    match_threshold = 80.0
            else:
                match_threshold = 80.0

            if expected_parts and min_ratio >= match_threshold:
                is_match = True
                matched_text = expected_text
                qa_result.result = "一致"
            else:
                is_match = False
                matched_text = ""
                qa_result.result = "不一致"
                subject = "【警告】画像検査結果：不一致"
                message_mail = (
                    "画像検査で不一致が検出されました。\n\n"
                    f"作業者: {qa_result.operator_name}\n"
                    f"デバイス名: {device.name if device else ''}\n"
                    f"材料名: {device.material if device else ''}\n"
                    f"製品名: {device.product if device else ''}\n"
                    f"混合率: {device.ratio if device else ''}\n"
                    f"QRコード内容: {expected_text}\n"
                    f"OCR読み取り内容: {paddle_text}\n"
                    f"日時: {timezone.localtime(timezone.now()).strftime('%Y-%m-%d %H:%M:%S')}\n"
                )
                recipient_list = [
                  "giang@hayashi-p.co.jp",
                  "k_arita@hayashi-p.co.jp",
                  "t_miyasaka@hayashi-p.co.jp"
                ]
                send_mail(
                    subject,
                    message_mail,
                    None,
                    recipient_list,
                    fail_silently=True
                )

            qa_result.machine_number = machine_number
            qa_result.match_ratio = min_ratio  # Đảm bảo model có trường này
            qa_result.input_weight = input_weight  # Đảm bảo model có trường này
            qa_result.save()

            form = QAResultForm()
            device_list = QADeviceInfo.objects.all()
            return render(request, 'quet_anh/upload.html', {
                'form': form,
                'expected_text': expected_text,
                'is_match': is_match,
                'matched_text': matched_text,
                'data': ocr_text,
                'device_list': device_list,
                'device_id': device_id,
                'device': device,
                'show_back_to_index': True,
                'match_ratios': match_ratios,
                'min_ratio': min_ratio,
            })
        else:
            messages.error(request, "カメラから画像を取得できませんでした。")
            return redirect('upload_image')
    else:
        form = QAResultForm()
        is_match = None
        matched_text = None
        data = None
    device_list = QADeviceInfo.objects.all()
    return render(request, 'quet_anh/upload.html', {
        'form': form,
        'message': message,
        'expected_text': expected_text,
        'device_list': device_list,
        'device_id': device_id,
        'device': device,
        'is_match': is_match if 'is_match' in locals() else None,
        'matched_text': matched_text if 'matched_text' in locals() else None,
        'data': ocr_text if 'ocr_text' in locals() else None,
    })

@login_required
def index_qa(request):
    device_list = QADeviceInfo.objects.all()
    return render(request, 'quet_anh/index_qa.html', {
        'device_list': device_list,
    })

@login_required
def qa_history(request):
    results = QAResult.objects.all().select_related('device', 'user')
    keyword = request.GET.get('keyword', '').strip()
    date = request.GET.get('date', '').strip()

    if keyword:
        results = results.filter(
            Q(device__name__icontains=keyword) |
            Q(device__material__icontains=keyword) |
            Q(user__first_name__icontains=keyword) |
            Q(user__last_name__icontains=keyword) |
            Q(operator_name__icontains=keyword)
        )
    if date:
        results = results.filter(created_at__date=date)

    results = results.order_by('-created_at')
    paginator = Paginator(results, 5)  # 5 dòng mỗi trang
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    context = {
        'results': page_obj,
        'keyword': keyword,
        'date': date,
        'page_obj': page_obj,
    }
    return render(request, 'quet_anh/qa_history.html', context)

@login_required
def delete_qa_history(request, pk):
    if not request.user.is_superuser:
        return render(request, 'quet_anh/403.html', status=403)
    item = get_object_or_404(QAResult, pk=pk)
    if request.method == 'POST':
        item.image.delete(save=False)
        if item.processed_image:
            item.processed_image.delete(save=False)
        item.delete()
        messages.success(request, '履歴が正常に削除されました。')
    return redirect('qa_history')

@login_required
def add_qa_device(request):
    success_message = None
    if request.method == 'POST':
        form = QADeviceInfoForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'デバイスが正常に追加されました。')
            form = QADeviceInfoForm()
            return redirect('qa_device_list')
        else:
            messages.error(request, '入力内容に誤りがあります。')
    else:
        form = QADeviceInfoForm()
    device_list = QADeviceInfo.objects.all()
    return render(request, 'quet_anh/add_qa_device.html', {
        'form': form,
        'device_list': device_list,
        'success_message': success_message,
        'show_compare_ratio': True,
    })

@login_required
def edit_qa_device(request, pk):
    if not request.user.is_superuser:
        return render(request, 'quet_anh/403.html', status=403)
    item = get_object_or_404(QADeviceInfo, pk=pk)
    if request.method == 'POST':
        form = QADeviceInfoForm(request.POST, instance=item)
        if form.is_valid():
            form.save()
            messages.success(request, 'デバイスが正常に更新されました。')
            return redirect('qa_device_list')
        else:
            messages.error(request, '入力内容に誤りがあります。')
    else:
        form = QADeviceInfoForm(instance=item)
    device_list = QADeviceInfo.objects.all()
    return render(request, 'quet_anh/add_qa_device.html', {
        'form': form,
        'device_list': device_list,
        'edit_item': item,
        'show_compare_ratio': True,
    })

def delete_qa_device(request, pk):
    if not request.user.is_superuser:
        return render(request, 'quet_anh/403.html', status=403)
    item = get_object_or_404(QADeviceInfo, pk=pk)
    item.delete()
    messages.success(request, 'デバイスが正常に削除されました。')
    return redirect('qa_device_list')

def qa_device_list(request):
    device_list = QADeviceInfo.objects.all()
    return render(request, 'quet_anh/qa_device_list.html', {'device_list': device_list})

@login_required
def dashboard_qa(request):
    from_date = request.GET.get('from_date')
    to_date = request.GET.get('to_date')

    results = QAResult.objects.all()
    if from_date:
        results = results.filter(created_at__date__gte=from_date)
    if to_date:
        results = results.filter(created_at__date__lte=to_date)

    device_count = QADeviceInfo.objects.count()
    result_count = results.count()
    match_count = results.filter(result="一致").count()
    unmatch_count = results.filter(result="不一致").count()

    kg_by_operator = (
        results.values('operator_name')
        .annotate(total_kg=Sum('input_weight'))
        .order_by('-total_kg')
    )
    count_by_operator = (
        results.values('operator_name')
        .annotate(total_count=Count('id'))
        .order_by('-total_count')
    )
    top10_operators = count_by_operator[:10]

    # ===== Thống kê theo khung giờ và người thực hiện =====
    hour_stats = defaultdict(lambda: {'count': 0, 'users': set(), 'materials': set()})
    for scan in results:
        hour = localtime(scan.created_at).hour
        # Lấy tên người thực hiện
        if scan.user and (scan.user.get_full_name() or scan.user.username):
            user_display = scan.user.get_full_name() or scan.user.username
        elif scan.operator_name:
            user_display = scan.operator_name
        else:
            user_display = "不明"
        # Lấy tên nguyên liệu (材料)
        material = scan.device.material if scan.device and scan.device.material else "不明"
        hour_stats[hour]['count'] += 1
        hour_stats[hour]['users'].add(user_display)
        hour_stats[hour]['materials'].add(material)

    hour_stats_list = []
    labels = []
    data = []
    users = []
    materials = []
    bar_colors = []
    for h in range(24):
        user_list = ', '.join(hour_stats[h]['users']) if hour_stats[h]['users'] else ''
        material_list = ', '.join(hour_stats[h]['materials']) if hour_stats[h]['materials'] else ''
        hour_stats_list.append({
            'hour_range': f"{h:02d}:00 - {h+1:02d}:00",
            'count': hour_stats[h]['count'],
            'users': user_list,
            'materials': material_list,
        })
        labels.append(f"{h:02d}:00")
        data.append(hour_stats[h]['count'])
        users.append(user_list)
        materials.append(material_list)

        if 8 <= h <= 17:
            bar_colors.append('rgba(54, 162, 235, 0.7)')      # Ca 1: xanh dương
        elif 13 <= h <= 22:
            bar_colors.append('rgba(255, 206, 86, 0.7)')      # Ca 2: vàng
        elif h > 22 or h <= 7:
            bar_colors.append('rgba(255, 99, 132, 0.7)')      # Ca 3: đỏ
        else:
            bar_colors.append('rgba(200,200,200,0.3)')        # Ngoài ca: xám nhạt

    # ===== Truyền thêm dữ liệu cho template =====
    return render(request, 'quet_anh/dashboard.html', {
        'device_count': device_count,
        'result_count': result_count,
        'match_count': match_count,
        'unmatch_count': unmatch_count,
        'kg_by_operator': kg_by_operator,
        'count_by_operator': count_by_operator,
        'top10_operators': top10_operators,
        'from_date': from_date,
        'to_date': to_date,
        # Thêm các biến sau:
        'hour_stats_list': hour_stats_list,
        'chart_labels': json.dumps(labels),
        'chart_data': json.dumps(data),
        'chart_users': json.dumps(users),
        'chart_materials': json.dumps(materials),
        'bar_colors': json.dumps(bar_colors),
    })

@require_GET
def latest_vision_events(request):
    today = timezone.localdate()
    results = (
        QAResult.objects
        .select_related("device", "user")
        .filter(created_at__date=today)
        .order_by("-created_at")[:10]
    )

    events = []
    for res in results:
        operator = ""
        if res.operator_name:
            operator = res.operator_name
        elif res.user:
            operator = res.user.get_full_name() or res.user.username

        events.append({
            "title": res.device.product if res.device and res.device.product else (res.device.name if res.device else "未設定"),
            "result": res.result,
            "operator": operator,
            "device_name": res.device.name if res.device else "",
            "material": res.device.material if res.device else "",
            "ratio": res.device.ratio if res.device else "",
            "weight": str(res.input_weight) if res.input_weight is not None else "",
            "timestamp": timezone.localtime(res.created_at).strftime("%Y-%m-%d %H:%M:%S"),
        })

    return JsonResponse({"vision_events": events, "date": today.strftime("%Y-%m-%d")})
