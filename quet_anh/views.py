import base64
from io import BytesIO
from decimal import Decimal
import uuid
import time as pytime
import unicodedata
from django.core.files.base import ContentFile
from django.shortcuts import render, redirect, get_object_or_404
from django.http import HttpResponseRedirect, HttpResponseForbidden, JsonResponse
from django.urls import reverse
from .forms import (
    QAResultForm,
    QADeviceInfoForm,
    QAMaterialMasterForm,
    QAMaterialStockLedgerForm,
    QAMaterialOutStockLedgerForm,
)
from .models import (
    QAResult,
    QADeviceInfo,
    QAMaterialMaster,
    QAAutoInputLedger,
    QAMaterialStockLedger,
    QAMaterialOutStockLedger,
    QADeletedJobMarker,
)
from django.contrib import messages
from django.core.mail import send_mail
from django.contrib.auth.models import User
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.db import OperationalError, ProgrammingError, IntegrityError
from django.utils.dateparse import parse_date
from django.views.decorators.http import require_GET, require_POST
from django.core.files.storage import default_storage

from PIL import Image
import cv2
import numpy as np
import re
from django.utils import timezone
from datetime import timedelta, datetime, time
import difflib
from collections import defaultdict
from django.utils.timezone import localtime
import json
import requests
from nhap_lieu.models import PhienNhapLieu
from nhap_lieu.models import ChuongTrinhNhapLieu, MayTinh, KetQuaNhapLieu


def _display_login_name(user):
    if not user:
        return ""
    if getattr(user, "last_name", "") and getattr(user, "first_name", ""):
        return f"{user.last_name} {user.first_name}".strip()
    if getattr(user, "last_name", ""):
        return user.last_name.strip()
    full_name = (user.get_full_name() or "").strip()
    if full_name:
        return full_name
    return (user.username or "").strip()


def _can_supervisor_confirm(user):
    if not user or not user.is_authenticated:
        return False
    return bool(user.is_superuser or user.is_staff or (user.username or "").lower() == "kanri")


def preprocess_image(image):
    img = np.array(image.convert('L'))
    from PIL import ImageOps
    pil_img = Image.fromarray(img)
    pil_img = ImageOps.autocontrast(pil_img, cutoff=1)
    img = np.array(pil_img)
    img = cv2.medianBlur(img, 1)
    return Image.fromarray(img)


def _upsert_out_stock_from_qa_result(qa_result):
    if not qa_result:
        return

    device = qa_result.device
    material_name = device.material if device else ""
    material_code = device.material_code if device else ""
    out_date = timezone.localtime(qa_result.created_at).date()

    row, _ = QAMaterialOutStockLedger.objects.get_or_create(
        qa_result=qa_result,
        defaults={
            "material_name": material_name,
            "material_code": material_code,
            "stock_out_date": out_date,
            "lot_color": qa_result.lot_color or QAMaterialOutStockLedger.LOT_COLOR_GREEN,
            "weight_kg": qa_result.input_weight or Decimal("0"),
            "bag_sequence_no": "",
            "lot_number": qa_result.lot_number or "",
            "workstation_management_no": "",
        },
    )

    changed = False
    if not row.material_name and material_name:
        row.material_name = material_name
        changed = True
    if not row.material_code and material_code:
        row.material_code = material_code
        changed = True
    if not row.stock_out_date:
        row.stock_out_date = out_date
        changed = True
    if qa_result.lot_color and row.lot_color != qa_result.lot_color:
        row.lot_color = qa_result.lot_color
        changed = True
    if qa_result.lot_number and row.lot_number != qa_result.lot_number:
        row.lot_number = qa_result.lot_number
        changed = True
    if (row.weight_kg is None or row.weight_kg == 0) and qa_result.input_weight is not None:
        row.weight_kg = qa_result.input_weight
        changed = True

    if changed:
        row.save()


def _is_valid_ipv4(ip):
    if not ip:
        return False
    pattern = r"^(?:[0-9]{1,3}\.){3}[0-9]{1,3}$"
    return bool(re.match(pattern, ip))


def _auto_send_to_nhap_lieu(qa_result, expected_text=""):
    """
    Tự động gửi job sang app nhập liệu dựa trên material_code.
    Trả về (ok, message, phien_or_none).
    """
    if not qa_result or not qa_result.device:
        return False, "デバイス情報がないため自動入力を実行できません。", None

    material_code = (qa_result.device.material_code or "").strip()
    if not material_code:
        return False, "材料コードが未設定のため自動入力を実行できません。", None

    chuong_trinh = ChuongTrinhNhapLieu.objects.filter(ten_chuong_trinh=material_code).first()
    if not chuong_trinh:
        return False, f"入力プログラム '{material_code}' が見つかりません。", None

    may_tinh = MayTinh.objects.filter(ten_may="server").first()
    if not may_tinh:
        return False, "固定送信先 server が見つかりません。", None
    if may_tinh.trang_thai != "active":
        return False, "固定送信先 server が非アクティブです。", None
    if not _is_valid_ipv4(may_tinh.ip):
        return False, "固定送信先 server のIPが無効です。", None

    try:
        quy_tac = json.loads(chuong_trinh.quy_tac or "[]")
    except Exception:
        quy_tac = []

    # Map nhanh cho placeholder Dòng 1..5
    dong_map = {
        "Dòng 1": material_code,
        "Dòng 2": str(qa_result.input_weight or ""),
        "Dòng 3": qa_result.lot_number or "",
        "Dòng 4": qa_result.machine_number or "",
        "Dòng 5": expected_text or "",
    }
    quy_tac_gui = [dong_map.get(item, item) for item in quy_tac]

    ma_job = f"job_{uuid.uuid4().hex[:16]}"
    payload = {
        "job_id": ma_job,
        "ten_chuong_trinh": chuong_trinh.ten_chuong_trinh,
        "quy_tac": quy_tac_gui,
        "kg_value": str(qa_result.input_weight or "").strip(),
        "delay": 0.1,
        "qa_result_id": qa_result.id,
    }

    phien = PhienNhapLieu.objects.create(
        ma_job=ma_job,
        chuong_trinh=chuong_trinh,
        may_tinh=may_tinh,
        qa_result=qa_result,
        ip_may=may_tinh.ip,
        payload_json=json.dumps(payload, ensure_ascii=False),
        trang_thai="sending",
        thong_bao="画像検査から自動送信",
    )

    try:
        url = f"http://{may_tinh.ip}:5000/send_input"
        response = requests.post(url, json=payload, timeout=20)
        if response.status_code != 200:
            phien.trang_thai = "failed"
            phien.thong_bao = f"送信失敗 HTTP {response.status_code}"
            phien.save(update_fields=["trang_thai", "thong_bao", "ngay_cap_nhat"])
            return False, f"自動入力送信失敗: HTTP {response.status_code}", phien

        data = response.json()
        callback_ok = bool(data.get("callback_ok"))
        data_ocr = (data.get("data_ocr") or "").strip()

        if callback_ok and data_ocr:
            if data_ocr == "---":
                phien.trang_thai = "failed"
                phien.thong_bao = "管理番号が無効です (---)"
                phien.save(update_fields=["trang_thai", "thong_bao", "ngay_cap_nhat"])
                return False, "管理番号が取得できませんでした。再実行してください。", phien

            # Callback có thể đã lưu KetQuaNhapLieu cho chính job hiện tại.
            # Chỉ coi là trùng khi cùng mã đã tồn tại ở job khác.
            if (
                KetQuaNhapLieu.objects.filter(ma_nhap_lieu=data_ocr, trang_thai="Thành công")
                .exclude(phien=phien)
                .exists()
            ):
                phien.trang_thai = "failed"
                phien.thong_bao = f"管理番号重複: {data_ocr}"
                phien.save(update_fields=["trang_thai", "thong_bao", "ngay_cap_nhat"])
                return False, f"管理番号が重複しています: {data_ocr}", phien

            phien.trang_thai = "done"
            phien.ma_nhap_lieu = data_ocr
            phien.thong_bao = "自動入力完了"
            phien.save(update_fields=["trang_thai", "ma_nhap_lieu", "thong_bao", "ngay_cap_nhat"])
            return True, f"自動入力完了: {chuong_trinh.ten_chuong_trinh} / {may_tinh.ip}", phien

        if callback_ok:
            phien.trang_thai = "failed"
            phien.thong_bao = "管理番号未取得。処理未完了"
            phien.save(update_fields=["trang_thai", "thong_bao", "ngay_cap_nhat"])
            return False, "入力処理は完了していません（管理番号未取得）。", phien

        phien.trang_thai = "failed"
        phien.thong_bao = f"Callback lỗi: {data.get('callback_info') or 'unknown'}"
        phien.save(update_fields=["trang_thai", "thong_bao", "ngay_cap_nhat"])
        return False, "自動入力のコールバックに失敗しました。", phien
    except Exception as exc:
        phien.trang_thai = "failed"
        phien.thong_bao = f"送信例外: {exc}"
        phien.save(update_fields=["trang_thai", "thong_bao", "ngay_cap_nhat"])
        return False, f"自動入力送信エラー: {exc}", phien


def _rollback_failed_qa_attempt(qa_result):
    if not qa_result or not qa_result.pk:
        return
    PhienNhapLieu.objects.filter(qa_result=qa_result).exclude(trang_thai="done").delete()
    qa_result.delete()


def _build_material_list_for_stock_in():
    # 優先: 材料マスター一覧
    # Bảo vệ runtime: nếu chưa migrate bảng mới thì fallback dữ liệu cũ.
    try:
        master_rows = (
            QAMaterialMaster.objects.filter(is_active=True)
            .values("material_name", "material_code", "qr_content", "qr_content_in")
            .order_by("material_name", "material_code")
        )
        material_list = [
            {
                "material": row.get("material_name") or "",
                "material_code": row.get("material_code") or "",
                # 入庫フロー: ưu tiên QR nhập kho, fallback QR xuất kho nếu chưa cấu hình riêng
                "qr_content": (row.get("qr_content_in") or row.get("qr_content") or ""),
            }
            for row in master_rows
        ]
        if material_list:
            return material_list
    except (OperationalError, ProgrammingError):
        pass

    # 互換性維持: 旧データ（機械マスタ）をフォールバック
    material_rows = (
        QADeviceInfo.objects.exclude(material__exact="")
        .values("material", "material_code")
        .order_by("material", "material_code")
    )
    seen = set()
    legacy_list = []
    for row in material_rows:
        key = (row.get("material") or "", row.get("material_code") or "")
        if key in seen:
            continue
        seen.add(key)
        legacy_list.append(
            {
                "material": key[0],
                "material_code": key[1],
                "qr_content": key[0],
            }
        )
    return legacy_list

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
        lot_color = request.POST.get('lot_color', '').strip()
        lot_number = request.POST.get('lot_number', '').strip()

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
        if lot_color not in {
            QAResult.LOT_COLOR_GREEN,
            QAResult.LOT_COLOR_BLACK,
            QAResult.LOT_COLOR_BLUE,
            QAResult.LOT_COLOR_RED,
        }:
            messages.error(request, "ロット識別色を選択してください。")
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

            qa_result.operator_name = _display_login_name(request.user)

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

                messages.error(request, "一致しません。再スキャンしてください。データは保存されません。")
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
                    'show_back_to_index': False,
                    'match_ratios': match_ratios,
                    'min_ratio': min_ratio,
                })

            qa_result.machine_number = machine_number
            qa_result.match_ratio = min_ratio  # Đảm bảo model có trường này
            qa_result.input_weight = input_weight  # Đảm bảo model có trường này
            qa_result.lot_color = lot_color
            qa_result.lot_number = lot_number
            qa_result.save()

            # Tự động gọi app nhập liệu nếu ảnh khớp (xuất nguyên liệu)
            if qa_result.result == "一致":
                material_code = (qa_result.device.material_code or "").strip() if qa_result.device else ""
                if not material_code:
                    messages.warning(request, "材料コード未設定のため、自動入力はスキップしました。画像検査結果のみ保存します。")
                else:
                    auto_ok, auto_msg, _ = _auto_send_to_nhap_lieu(qa_result, expected_text=expected_text or "")
                    if auto_ok:
                        messages.success(request, auto_msg)
                    else:
                        _rollback_failed_qa_attempt(qa_result)
                        messages.error(request, f"{auto_msg} / 保存しません。再スキャンしてください。")
                        form = QAResultForm()
                        device_list = QADeviceInfo.objects.all()
                        return render(request, 'quet_anh/upload.html', {
                            'form': form,
                            'expected_text': expected_text,
                            'is_match': True,
                            'matched_text': matched_text,
                            'data': ocr_text,
                            'device_list': device_list,
                            'device_id': device_id,
                            'device': device,
                            'show_back_to_index': False,
                            'match_ratios': match_ratios,
                            'min_ratio': min_ratio,
                        })

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
    material_list = _build_material_list_for_stock_in()
    return render(request, 'quet_anh/index_qa.html', {
        'device_list': device_list,
        'material_list': material_list,
    })


@login_required
def stock_in_start(request):
    material_name = (request.GET.get("material_name") or "").strip()
    material_code = (request.GET.get("material_code") or "").strip()

    material_list = _build_material_list_for_stock_in()

    return render(
        request,
        "quet_anh/stock_in_start.html",
        {
            "material_name": material_name,
            "material_code": material_code,
            "material_list": material_list,
        },
    )

@login_required
def qa_history(request):
    results = QAResult.objects.all().select_related('device', 'user')
    keyword = request.GET.get('keyword', '').strip()
    date = request.GET.get('date', '').strip()

    if keyword:
        results = results.filter(
            Q(device__name__icontains=keyword) |
            Q(device__material_code__icontains=keyword) |
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
@require_POST
def cleanup_qa_history_images(request):
    if not request.user.is_superuser:
        return render(request, 'quet_anh/403.html', status=403)

    cutoff_date_str = (request.POST.get("cutoff_date") or "").strip()
    cutoff_date = parse_date(cutoff_date_str) if cutoff_date_str else None
    if not cutoff_date:
        messages.error(request, "削除基準日を正しく入力してください。")
        return redirect("qa_history")

    cutoff_dt = timezone.make_aware(
        datetime.combine(cutoff_date, time.min),
        timezone.get_current_timezone(),
    )

    rows = list(
        QAResult.objects.filter(created_at__lt=cutoff_dt)
        .filter(
            (Q(image__isnull=False) & ~Q(image=""))
            | (Q(processed_image__isnull=False) & ~Q(processed_image=""))
        )
        .values("id", "image", "processed_image")
    )

    if not rows:
        messages.info(request, "削除対象の画像データはありません。")
        return redirect("qa_history")

    ids = []
    count_rows = 0
    count_image = 0
    count_processed = 0

    # 1) Xóa file vật lý trước (không giữ DB lock trong lúc xóa file)
    for row in rows:
        row_id = row["id"]
        image_name = (row.get("image") or "").strip()
        processed_name = (row.get("processed_image") or "").strip()
        changed = False

        if image_name:
            default_storage.delete(image_name)
            count_image += 1
            changed = True

        if processed_name:
            default_storage.delete(processed_name)
            count_processed += 1
            changed = True

        if changed:
            ids.append(row_id)
            count_rows += 1

    # 2) Update DB theo lô ngắn + retry tránh SQLite lock
    now_ts = timezone.now()
    batch_size = 300
    for i in range(0, len(ids), batch_size):
        batch_ids = ids[i : i + batch_size]
        updated = False
        last_error = None
        for attempt in range(3):
            try:
                QAResult.objects.filter(id__in=batch_ids).update(
                    image="",
                    processed_image=None,
                    updated_at=now_ts,
                )
                updated = True
                break
            except OperationalError as exc:
                last_error = exc
                if "locked" in str(exc).lower():
                    pytime.sleep(0.4 * (attempt + 1))
                    continue
                raise
        if not updated and last_error:
            raise last_error

    messages.success(
        request,
        f"画像削除完了: 対象日<{cutoff_date_str} / 件数 {count_rows} / 元画像 {count_image} / 前処理画像 {count_processed}",
    )
    return redirect("qa_history")

@login_required
def add_qa_device(request):
    success_message = None
    if request.method == 'POST':
        form = QADeviceInfoForm(request.POST)
        if form.is_valid():
            item = form.save(commit=False)
            master = form.cleaned_data.get("material_master")
            if master:
                item.material = master.material_name
                item.material_code = master.material_code
            item.save()
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
            obj = form.save(commit=False)
            master = form.cleaned_data.get("material_master")
            if master:
                obj.material = master.material_name
                obj.material_code = master.material_code
            obj.save()
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
def material_master_list(request):
    keyword = (request.GET.get("keyword") or "").strip()
    qs = QAMaterialMaster.objects.all()
    if keyword:
        qs = qs.filter(
            Q(material_name__icontains=keyword)
            | Q(material_code__icontains=keyword)
            | Q(qr_content__icontains=keyword)
            | Q(qr_content_in__icontains=keyword)
        )
    items = qs.order_by("material_name", "material_code", "id")
    return render(
        request,
        "quet_anh/material_master_list.html",
        {
            "items": items,
            "keyword": keyword,
        },
    )


@login_required
def material_master_add(request):
    if request.method == "POST":
        form = QAMaterialMasterForm(request.POST)
        if form.is_valid():
            try:
                form.save()
                messages.success(request, "材料マスターを追加しました。")
                return redirect("material_master_list")
            except IntegrityError:
                messages.error(
                    request,
                    "保存時に一意制約エラーが発生しました。DBマイグレーション未適用の可能性があります。",
                )
        messages.error(request, "入力内容を確認してください。")
    else:
        form = QAMaterialMasterForm()
    return render(
        request,
        "quet_anh/material_master_form.html",
        {
            "form": form,
            "page_title": "材料マスター追加",
        },
    )


@login_required
def material_master_edit(request, pk):
    item = get_object_or_404(QAMaterialMaster, pk=pk)
    if request.method == "POST":
        form = QAMaterialMasterForm(request.POST, instance=item)
        if form.is_valid():
            try:
                form.save()
                messages.success(request, "材料マスターを更新しました。")
                return redirect("material_master_list")
            except IntegrityError:
                messages.error(
                    request,
                    "更新時に一意制約エラーが発生しました。DBマイグレーション未適用の可能性があります。",
                )
        messages.error(request, "入力内容を確認してください。")
    else:
        form = QAMaterialMasterForm(instance=item)
    return render(
        request,
        "quet_anh/material_master_form.html",
        {
            "form": form,
            "item": item,
            "page_title": "材料マスター編集",
        },
    )


@login_required
@require_POST
def material_master_delete(request, pk):
    item = get_object_or_404(QAMaterialMaster, pk=pk)
    item.delete()
    messages.success(request, "材料マスターを削除しました。")
    return redirect("material_master_list")


@login_required
def dashboard_qa(request):
    from_date = request.GET.get('from_date')
    to_date = request.GET.get('to_date')

    results = QAResult.objects.select_related("user", "device").all()
    if from_date:
        results = results.filter(created_at__date__gte=from_date)
    if to_date:
        results = results.filter(created_at__date__lte=to_date)

    device_count = QADeviceInfo.objects.count()
    result_count = results.count()
    match_count = results.filter(result="一致").count()
    unmatch_count = results.filter(result="不一致").count()
    total_weight_kg = Decimal("0")

    # 統計キーは user_id 優先にして、表示名変更時でも同一人物を集約する
    def _operator_identity(scan):
        if scan.user_id:
            return f"user:{scan.user_id}", _display_login_name(scan.user) or (scan.user.username or "")
        legacy_name = (scan.operator_name or "").strip()
        if legacy_name:
            return f"legacy:{legacy_name.lower()}", legacy_name
        return "unknown", "不明"

    operator_stats = {}
    material_stats = {}

    def _material_key(text):
        s = (text or "").strip()
        if not s:
            return "不明"
        # NFKCで全角/半角（英数・カナ）差を吸収し、名称は省略しない
        s = unicodedata.normalize("NFKC", s)
        s = s.replace("\u3000", " ")
        s = re.sub(r"\s+", " ", s).strip()
        return s or "不明"
    for scan in results:
        operator_key, operator_display = _operator_identity(scan)
        row = operator_stats.setdefault(
            operator_key,
            {
                "operator_name": operator_display or "不明",
                "total_kg": Decimal("0"),
                "total_count": 0,
            },
        )
        if scan.input_weight is not None:
            row["total_kg"] += scan.input_weight
            total_weight_kg += scan.input_weight

            material_name_raw = "不明"
            product_name = "不明"
            if scan.device and scan.device.material:
                material_name_raw = scan.device.material
            if scan.device and scan.device.product:
                product_name = scan.device.product
            material_name = _material_key(material_name_raw)
            mkey = material_name
            mrow = material_stats.setdefault(
                mkey,
                {
                    "material_name": material_name,
                    "product_names": set(),
                    "total_kg": Decimal("0"),
                    "total_count": 0,
                },
            )
            mrow["total_kg"] += scan.input_weight
            mrow["total_count"] += 1
            if product_name and product_name != "不明":
                mrow["product_names"].add(product_name)
        row["total_count"] += 1

    kg_by_operator = sorted(
        operator_stats.values(),
        key=lambda x: (x["total_kg"], x["total_count"]),
        reverse=True,
    )
    count_by_operator = sorted(
        operator_stats.values(),
        key=lambda x: (x["total_count"], x["total_kg"]),
        reverse=True,
    )
    top10_operators = count_by_operator[:10]
    material_rows = []
    for _, item in material_stats.items():
        products = sorted(item["product_names"])
        material_rows.append(
            {
                "material_name": item["material_name"],
                "product_names_display": " / ".join(products) if products else "不明",
                "total_kg": item["total_kg"],
                "total_count": item["total_count"],
            }
        )

    kg_by_material = sorted(
        material_rows,
        key=lambda x: (x["total_kg"], x["total_count"]),
        reverse=True,
    )

    # ===== Thống kê theo khung giờ và người thực hiện =====
    hour_stats = defaultdict(lambda: {'count': 0, 'users': set(), 'materials': set()})
    for scan in results:
        hour = localtime(scan.created_at).hour
        # user_id ベースの同一人物表示（改名後も統一）
        _, user_display = _operator_identity(scan)
        # Lấy tên nguyên liệu (材料)
        material = scan.device.material if scan.device and scan.device.material else "不明"
        hour_stats[hour]['count'] += 1
        hour_stats[hour]['users'].add(user_display)
        hour_stats[hour]['materials'].add(material)
        if scan.input_weight is not None:
            hour_stats[hour].setdefault('kg', Decimal("0"))
            hour_stats[hour]['kg'] += scan.input_weight

    hour_stats_list = []
    labels = []
    data = []
    hour_kg_data = []
    users = []
    materials = []
    bar_colors = []
    for h in range(24):
        user_list = ', '.join(hour_stats[h]['users']) if hour_stats[h]['users'] else ''
        material_list = ', '.join(hour_stats[h]['materials']) if hour_stats[h]['materials'] else ''
        hour_kg = hour_stats[h].get('kg', Decimal("0"))
        hour_stats_list.append({
            'hour_range': f"{h:02d}:00 - {h+1:02d}:00",
            'count': hour_stats[h]['count'],
            'kg': float(hour_kg),
            'users': user_list,
            'materials': material_list,
        })
        labels.append(f"{h:02d}:00")
        data.append(hour_stats[h]['count'])
        hour_kg_data.append(float(hour_kg))
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

    # Top10 chart data: 回数 + kg を同時表示
    top10_labels = [row.get("operator_name", "-") for row in top10_operators]
    top10_count_data = [int(row.get("total_count") or 0) for row in top10_operators]
    top10_kg_data = [float(row.get("total_kg") or 0) for row in top10_operators]

    # ===== Truyền thêm dữ liệu cho template =====
    return render(request, 'quet_anh/dashboard.html', {
        'device_count': device_count,
        'result_count': result_count,
        'match_count': match_count,
        'unmatch_count': unmatch_count,
        'total_weight_kg': float(total_weight_kg),
        'kg_by_operator': kg_by_operator,
        'count_by_operator': count_by_operator,
        'top10_operators': top10_operators,
        'kg_by_material': kg_by_material,
        'from_date': from_date,
        'to_date': to_date,
        # Thêm các biến sau:
        'hour_stats_list': hour_stats_list,
        'chart_labels': json.dumps(labels),
        'chart_data': json.dumps(data),
        'chart_hour_kg_data': json.dumps(hour_kg_data),
        'chart_users': json.dumps(users),
        'chart_materials': json.dumps(materials),
        'bar_colors': json.dumps(bar_colors),
        'chart_top10_labels': json.dumps(top10_labels),
        'chart_top10_count_data': json.dumps(top10_count_data),
        'chart_top10_kg_data': json.dumps(top10_kg_data),
    })


def _sync_material_stock_rows(limit=300):
    # Luồng hiện tại chỉ hỗ trợ 出庫 (xuat kho).
    # Tạm khóa toàn bộ sync 入庫 (nhap kho) để không phát sinh dữ liệu sai.
    return


def _cleanup_auto_generated_stock_rows():
    # Xóa dữ liệu 入庫 đã sinh nhầm từ luồng 出庫 (có auto_input_ledger).
    QAMaterialStockLedger.objects.filter(auto_input_ledger__isnull=False).delete()


def _sync_material_out_stock_rows(limit=300):
    deleted_job_ids = QADeletedJobMarker.objects.values_list("job_id", flat=True)
    ledgers = (
        QAAutoInputLedger.objects.select_related("qa_result__device")
        .filter(job_status="done")
        .exclude(job_id__in=deleted_job_ids)
        .order_by("-created_at")[:limit]
    )

    for ledger in ledgers:
        qa_result = ledger.qa_result
        device = qa_result.device if qa_result and qa_result.device else None

        material_name = (device.material if device else "") or ledger.qa_material or ""
        material_code = (device.material_code if device else "") or ""
        source_date = qa_result.created_at if qa_result else ledger.created_at
        stock_out_date = timezone.localtime(source_date).date()
        weight_kg = qa_result.input_weight if qa_result and qa_result.input_weight is not None else ledger.qa_input_weight
        mgmt_no = ledger.ma_nhap_lieu or ledger.job_id or ""

        row = None
        if qa_result:
            row = QAMaterialOutStockLedger.objects.filter(qa_result=qa_result).first()
            if row and not row.auto_input_ledger_id:
                duplicate = (
                    QAMaterialOutStockLedger.objects
                    .filter(auto_input_ledger=ledger)
                    .exclude(pk=row.pk)
                    .first()
                )
                if duplicate:
                    if not row.workstation_management_no and duplicate.workstation_management_no:
                        row.workstation_management_no = duplicate.workstation_management_no
                    if (row.weight_kg is None or row.weight_kg == 0) and duplicate.weight_kg is not None:
                        row.weight_kg = duplicate.weight_kg
                    if not row.lot_number and duplicate.lot_number:
                        row.lot_number = duplicate.lot_number
                    if not row.material_name and duplicate.material_name:
                        row.material_name = duplicate.material_name
                    if not row.material_code and duplicate.material_code:
                        row.material_code = duplicate.material_code
                    duplicate.delete()
                row.auto_input_ledger = ledger
                row.save()

        if not row:
            row, _ = QAMaterialOutStockLedger.objects.get_or_create(
                auto_input_ledger=ledger,
                defaults={
                    "qa_result": qa_result,
                    "material_name": material_name,
                    "material_code": material_code,
                    "stock_out_date": stock_out_date,
                    "lot_color": (qa_result.lot_color if qa_result and qa_result.lot_color else QAMaterialOutStockLedger.LOT_COLOR_GREEN),
                    "weight_kg": weight_kg if weight_kg is not None else Decimal("0"),
                    "bag_sequence_no": "",
                    "lot_number": (qa_result.lot_number if qa_result else ""),
                    "workstation_management_no": mgmt_no,
                },
            )

        changed = False
        if qa_result and row.qa_result_id != qa_result.id:
            row.qa_result = qa_result
            changed = True
        if not row.material_name and material_name:
            row.material_name = material_name
            changed = True
        if not row.material_code and material_code:
            row.material_code = material_code
            changed = True
        if (row.weight_kg is None or row.weight_kg == 0) and weight_kg is not None:
            row.weight_kg = weight_kg
            changed = True
        if not row.workstation_management_no and mgmt_no:
            row.workstation_management_no = mgmt_no
            changed = True
        if not row.stock_out_date:
            row.stock_out_date = stock_out_date
            changed = True
        if qa_result and qa_result.lot_color and row.lot_color != qa_result.lot_color:
            row.lot_color = qa_result.lot_color
            changed = True
        if qa_result and qa_result.lot_number and row.lot_number != qa_result.lot_number:
            row.lot_number = qa_result.lot_number
            changed = True

        if changed:
            row.save()


@login_required
def material_stock_ledger(request):
    _cleanup_auto_generated_stock_rows()
    qs = QAMaterialStockLedger.objects.all()
    keyword = request.GET.get("keyword", "").strip()
    date = request.GET.get("date", "").strip()
    confirmed = request.GET.get("confirmed", "").strip()

    if keyword:
        qs = qs.filter(
            Q(material_name__icontains=keyword)
            | Q(material_code__icontains=keyword)
            | Q(lot_number__icontains=keyword)
            | Q(workstation_management_no__icontains=keyword)
            | Q(supervisor_name__icontains=keyword)
        )
    if date:
        parsed = parse_date(date)
        if parsed:
            qs = qs.filter(stock_in_date=parsed)
    if confirmed == "yes":
        qs = qs.filter(supervisor_confirmed=True)
    elif confirmed == "no":
        qs = qs.filter(supervisor_confirmed=False)

    paginator = Paginator(qs.order_by("-stock_in_date", "-id"), 20)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    return render(
        request,
        "quet_anh/material_stock_ledger.html",
        {
            "rows": page_obj,
            "page_obj": page_obj,
            "keyword": keyword,
            "date": date,
            "confirmed": confirmed,
            "can_supervisor_confirm": _can_supervisor_confirm(request.user),
        },
    )


@login_required
def material_out_stock_ledger(request):
    _sync_material_out_stock_rows(limit=500)

    qs = QAMaterialOutStockLedger.objects.filter(auto_input_ledger__job_status="done")
    keyword = request.GET.get("keyword", "").strip()
    date = request.GET.get("date", "").strip()
    confirmed = request.GET.get("confirmed", "").strip()

    if keyword:
        qs = qs.filter(
            Q(material_name__icontains=keyword)
            | Q(material_code__icontains=keyword)
            | Q(lot_number__icontains=keyword)
            | Q(workstation_management_no__icontains=keyword)
            | Q(supervisor_name__icontains=keyword)
        )
    if date:
        parsed = parse_date(date)
        if parsed:
            qs = qs.filter(stock_out_date=parsed)
    if confirmed == "yes":
        qs = qs.filter(supervisor_confirmed=True)
    elif confirmed == "no":
        qs = qs.filter(supervisor_confirmed=False)

    paginator = Paginator(qs.order_by("-stock_out_date", "-id"), 20)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    return render(
        request,
        "quet_anh/material_out_stock_ledger.html",
        {
            "rows": page_obj,
            "page_obj": page_obj,
            "keyword": keyword,
            "date": date,
            "confirmed": confirmed,
            "can_supervisor_confirm": _can_supervisor_confirm(request.user),
        },
    )


@login_required
def material_stock_ledger_edit(request, pk):
    row = get_object_or_404(QAMaterialStockLedger, pk=pk)

    if request.method == "POST":
        form = QAMaterialStockLedgerForm(request.POST, instance=row)
        if form.is_valid():
            form.save()
            messages.success(request, "原材料入庫台帳を更新しました。")
            return redirect("material_stock_ledger")
        messages.error(request, "入力内容を確認してください。")
    else:
        form = QAMaterialStockLedgerForm(instance=row)

    return render(
        request,
        "quet_anh/material_stock_ledger_edit.html",
        {
            "form": form,
            "row": row,
        },
    )


@login_required
def material_out_stock_ledger_edit(request, pk):
    row = get_object_or_404(QAMaterialOutStockLedger, pk=pk)

    if request.method == "POST":
        form = QAMaterialOutStockLedgerForm(request.POST, instance=row)
        if form.is_valid():
            form.save()
            messages.success(request, "原材料出庫台帳を更新しました。")
            return redirect("material_out_stock_ledger")
        messages.error(request, "入力内容を確認してください。")
    else:
        form = QAMaterialOutStockLedgerForm(instance=row)

    return render(
        request,
        "quet_anh/material_out_stock_ledger_edit.html",
        {
            "form": form,
            "row": row,
        },
    )


@login_required
@require_POST
def auto_input_ledger_delete(request, pk):
    item = get_object_or_404(QAAutoInputLedger, pk=pk)
    QADeletedJobMarker.objects.get_or_create(
        job_id=item.job_id,
        defaults={"note": "削除操作: 自動入力ジョブ台帳"},
    )
    QAMaterialStockLedger.objects.filter(auto_input_ledger=item).delete()
    QAMaterialOutStockLedger.objects.filter(auto_input_ledger=item).delete()
    item.delete()
    messages.success(request, "ジョブ台帳データを削除しました。")
    return redirect("auto_input_ledger_list")


@login_required
@require_POST
def material_stock_ledger_delete(request, pk):
    row = get_object_or_404(QAMaterialStockLedger, pk=pk)
    if row.auto_input_ledger_id:
        QADeletedJobMarker.objects.get_or_create(
            job_id=row.auto_input_ledger.job_id,
            defaults={"note": "削除操作: 原材料入庫台帳"},
        )
        QAMaterialOutStockLedger.objects.filter(auto_input_ledger=row.auto_input_ledger).delete()
        row.auto_input_ledger.delete()
        messages.success(request, "入庫台帳データを削除しました。")
        return redirect("material_stock_ledger")
    row.delete()
    messages.success(request, "入庫台帳データを削除しました。")
    return redirect("material_stock_ledger")


@login_required
@require_POST
def material_out_stock_ledger_delete(request, pk):
    row = get_object_or_404(QAMaterialOutStockLedger, pk=pk)
    if row.auto_input_ledger_id:
        QADeletedJobMarker.objects.get_or_create(
            job_id=row.auto_input_ledger.job_id,
            defaults={"note": "削除操作: 原材料出庫台帳"},
        )
        QAMaterialStockLedger.objects.filter(auto_input_ledger=row.auto_input_ledger).delete()
        row.auto_input_ledger.delete()
        messages.success(request, "出庫台帳データを削除しました。")
        return redirect("material_out_stock_ledger")
    row.delete()
    messages.success(request, "出庫台帳データを削除しました。")
    return redirect("material_out_stock_ledger")


@login_required
@require_POST
def material_stock_ledger_confirm(request, pk):
    if not _can_supervisor_confirm(request.user):
        messages.error(request, "上長確認権限がありません。")
        return redirect("material_stock_ledger")

    row = get_object_or_404(QAMaterialStockLedger, pk=pk)
    action = (request.POST.get("action") or "confirm").strip()
    if action == "unconfirm":
        row.supervisor_confirmed = False
        row.supervisor_name = ""
        row.supervisor_confirmed_at = None
        row.save(update_fields=["supervisor_confirmed", "supervisor_name", "supervisor_confirmed_at", "updated_at"])
        messages.success(request, "入庫台帳の上長確認を解除しました。")
    else:
        row.supervisor_confirmed = True
        row.supervisor_name = _display_login_name(request.user)
        row.supervisor_confirmed_at = timezone.now()
        row.save(update_fields=["supervisor_confirmed", "supervisor_name", "supervisor_confirmed_at", "updated_at"])
        messages.success(request, "入庫台帳を上長確認しました。")
    return redirect("material_stock_ledger")


@login_required
@require_POST
def material_out_stock_ledger_confirm(request, pk):
    if not _can_supervisor_confirm(request.user):
        messages.error(request, "上長確認権限がありません。")
        return redirect("material_out_stock_ledger")

    row = get_object_or_404(QAMaterialOutStockLedger, pk=pk)
    action = (request.POST.get("action") or "confirm").strip()
    if action == "unconfirm":
        row.supervisor_confirmed = False
        row.supervisor_name = ""
        row.supervisor_confirmed_at = None
        row.save(update_fields=["supervisor_confirmed", "supervisor_name", "supervisor_confirmed_at", "updated_at"])
        messages.success(request, "出庫台帳の上長確認を解除しました。")
    else:
        row.supervisor_confirmed = True
        row.supervisor_name = _display_login_name(request.user)
        row.supervisor_confirmed_at = timezone.now()
        row.save(update_fields=["supervisor_confirmed", "supervisor_name", "supervisor_confirmed_at", "updated_at"])
        messages.success(request, "出庫台帳を上長確認しました。")
    return redirect("material_out_stock_ledger")


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


def _pick_related_qa_result(phien):
    """Liên kết chặt: chỉ nhận qa_result gắn trực tiếp từ luồng quét ảnh."""
    if getattr(phien, "qa_result_id", None):
        return phien.qa_result
    return None


def _cleanup_unlinked_ledgers():
    """Xóa dữ liệu ledger không có liên kết trực tiếp tới QAResult."""
    QAMaterialStockLedger.objects.filter(auto_input_ledger__qa_result__isnull=True).delete()
    QAMaterialOutStockLedger.objects.filter(auto_input_ledger__qa_result__isnull=True).delete()
    QAAutoInputLedger.objects.filter(qa_result__isnull=True).delete()


def sync_auto_input_ledger(limit=200):
    """Đồng bộ sổ cái job: chỉ lưu job đã hoàn thành thành công."""
    _cleanup_unlinked_ledgers()
    _cleanup_auto_generated_stock_rows()
    # Dọn các job không thành công khỏi sổ cái quản lý job
    QAAutoInputLedger.objects.exclude(job_status="done").delete()
    deleted_job_ids = QADeletedJobMarker.objects.values_list("job_id", flat=True)

    phien_qs = (
        PhienNhapLieu.objects.select_related("chuong_trinh", "may_tinh")
        .filter(trang_thai="done", qa_result__isnull=False)
        .exclude(ma_job__in=deleted_job_ids)
        .order_by("-ngay_tao")[:limit]
    )

    for phien in phien_qs:
        ledger, _ = QAAutoInputLedger.objects.get_or_create(
            phien_nhap_lieu=phien,
            defaults={"job_id": phien.ma_job},
        )

        qa_result = ledger.qa_result or _pick_related_qa_result(phien)
        if qa_result and not ledger.qa_result:
            ledger.qa_result = qa_result

        ledger.job_id = phien.ma_job
        ledger.job_status = phien.trang_thai or ""
        ledger.job_message = phien.thong_bao or ""
        ledger.workstation_ip = phien.ip_may or ""
        ledger.ma_nhap_lieu = phien.ma_nhap_lieu or ""
        ledger.full_text = phien.full_text or ""

        if qa_result:
            ledger.qa_machine_number = qa_result.machine_number or ""
            ledger.qa_device_name = qa_result.device.name if qa_result.device else ""
            ledger.qa_material = qa_result.device.material if qa_result.device else ""
            ledger.qa_product = qa_result.device.product if qa_result.device else ""
            ledger.qa_ratio = qa_result.device.ratio if qa_result.device else ""
            ledger.qa_operator_name = qa_result.operator_name or ""
            ledger.qa_result_status = qa_result.result or ""
            ledger.qa_match_ratio = qa_result.match_ratio
            ledger.qa_input_weight = qa_result.input_weight

        ledger.save()


@login_required
def auto_input_ledger_list(request):
    return redirect("material_out_stock_ledger")
