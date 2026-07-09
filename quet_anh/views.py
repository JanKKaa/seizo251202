import base64
import csv
import hashlib
import os
from io import BytesIO
from decimal import Decimal, InvalidOperation, ROUND_CEILING
import uuid
import time as pytime
import unicodedata
import logging
from urllib.parse import urlencode
from django.core.files.base import ContentFile
from django.shortcuts import render, redirect, get_object_or_404
from django.http import HttpResponse, HttpResponseRedirect, HttpResponseForbidden, JsonResponse
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from .forms import (
    QAResultForm,
    QADeviceInfoForm,
    QAMaterialMasterForm,
    QAMaterialStockLedgerForm,
    QAMaterialOutStockLedgerForm,
    QATabletDeviceForm,
    QATabletInspectionForm,
)
from .models import (
    QAResult,
    QADeviceInfo,
    QAMaterialMaster,
    QAAutoInputLedger,
    QAMaterialStockLedger,
    QAMaterialOutStockLedger,
    QADeletedJobMarker,
    QATabletDevice,
    QATabletInspection,
)
from django.contrib import messages
from django.core.mail import send_mail
from django.contrib.auth.models import User
from django.contrib.auth.decorators import login_required
from django.conf import settings
from django.core.paginator import Paginator
from django.db.models import Q, Sum, Max, Count
from django.db import OperationalError, ProgrammingError, IntegrityError, transaction
from django.utils.dateparse import parse_date
from django.views.decorators.http import require_GET, require_POST
from django.core.files.storage import default_storage
from django.core.cache import cache

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

logger = logging.getLogger(__name__)


def _is_auto_outstock_target(qa_result):
    """
    Từng thiết bị + nguyên liệu tự quản lý cờ ON/OFF tự động nhập liệu.
    Mặc định OFF để vận hành song song an toàn.
    """
    if not qa_result or not qa_result.device:
        return False
    return bool(getattr(qa_result.device, "outstock_auto_input_enabled", False))


def _run_db_with_retry(func, *, retries=5, base_delay=0.2):
    """
    Retry DB writes when SQLite reports 'database is locked'.
    """
    for attempt in range(retries):
        try:
            return func()
        except OperationalError as exc:
            if "database is locked" not in str(exc):
                raise
            if attempt >= retries - 1:
                raise
            pytime.sleep(base_delay * (attempt + 1))


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


def _outstock_idempotency_cache_key(
    *,
    device_id,
    machine_number,
    expected_text,
    input_weight,
    lot_color,
    lot_number,
    product_code,
    captured_image,
):
    payload = "||".join(
        [
            str(device_id or "").strip(),
            str(machine_number or "").strip(),
            str(expected_text or "").strip(),
            str(input_weight or "").strip(),
            str(lot_color or "").strip(),
            str(lot_number or "").strip(),
            str(product_code or "").strip(),
            str(captured_image or "").strip(),
        ]
    )
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    return f"qa_outstock_submit:{digest}"


def _can_supervisor_confirm(user):
    if not user or not user.is_authenticated:
        return False
    return bool(user.is_superuser or user.is_staff or (user.username or "").lower() == "kanri")


def _can_inventory_adjust(user):
    if not user or not user.is_authenticated:
        return False
    return bool(user.is_superuser)


def _can_bypass_tablet_tenken(user):
    if not user or not user.is_authenticated:
        return False
    return bool(user.is_superuser or (user.username or "").lower() == "admin")


IATF_ADJUSTMENT_REASON_LABELS = {
    QAMaterialStockLedger.ADJUST_REASON_CYCLE_COUNT: "棚卸差異",
    QAMaterialStockLedger.ADJUST_REASON_INPUT_ERROR: "入力ミス修正",
    QAMaterialStockLedger.ADJUST_REASON_DAMAGE: "廃棄・破損",
    QAMaterialStockLedger.ADJUST_REASON_MIGRATION: "移行データ補正",
    QAMaterialStockLedger.ADJUST_REASON_CUSTOMER_APPROVED: "顧客承認補正",
    QAMaterialStockLedger.ADJUST_REASON_OTHER: "その他",
}


LEDGER_STATE_STOCK_IN_SESSION_KEY = "qa_material_stock_ledger_query"
LEDGER_STATE_STOCK_OUT_SESSION_KEY = "qa_material_out_stock_ledger_query"


def _safe_next_redirect(request, fallback_view_name):
    next_url = (request.POST.get("next") or request.GET.get("next") or "").strip()
    if next_url and url_has_allowed_host_and_scheme(
        next_url,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        return HttpResponseRedirect(next_url)
    return redirect(fallback_view_name)


def _restore_or_store_ledger_query(request, *, view_name, session_key):
    if request.GET.get("reset") == "1":
        request.session.pop(session_key, None)
        return redirect(view_name)

    if not request.GET:
        stored_query = request.session.get(session_key)
        if stored_query:
            return HttpResponseRedirect(f"{reverse(view_name)}?{stored_query}")
        return None

    query = request.GET.copy()
    query.pop("reset", None)
    request.session[session_key] = query.urlencode()
    return None


def _csv_value(value):
    if value is None:
        return ""
    if hasattr(value, "strftime"):
        try:
            return timezone.localtime(value).strftime("%Y-%m-%d %H:%M:%S")
        except Exception:
            return value.strftime("%Y-%m-%d")
    return str(value)


def _csv_text(value):
    text = "" if value is None else str(value)
    return f'="{text.replace(chr(34), chr(34) + chr(34))}"'


def _transaction_label(value):
    return {
        "IN": "通常入庫",
        "OUT": "通常出庫",
        "ADJ+": "在庫調整（増）",
        "ADJ-": "在庫調整（減）",
        "CORR": "訂正",
    }.get(value or "", value or "")


def _reason_label(value):
    return IATF_ADJUSTMENT_REASON_LABELS.get(value or "", value or "")


def _iatf_csv_response(filename, title, request):
    response = HttpResponse(content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    response.write("\ufeff")
    writer = csv.writer(response)
    exported_at = timezone.localtime(timezone.now()).strftime("%Y-%m-%d %H:%M:%S")
    writer.writerow(["帳票名", title])
    writer.writerow(["IATF管理区分", "在庫トレーサビリティ記録"])
    writer.writerow(["確認印", "電子承認記録（上長確認・承認者・承認日時）"])
    writer.writerow(["出力者", _display_login_name(request.user) or getattr(request.user, "username", "")])
    writer.writerow(["出力日時", exported_at])
    writer.writerow(["データ保全", "既存データは削除せず、ADJ/CORRで履歴を保持"])
    writer.writerow([])
    return response, writer


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
    bag_count = _calculate_bag_count_by_material_code(material_code, qa_result.input_weight if qa_result else None)
    out_date = timezone.localtime(qa_result.created_at).date()
    product_code = (qa_result.product_code or "").strip()
    if not product_code and device:
        product_code = (device.product_management_code or "").strip()

    row, _ = QAMaterialOutStockLedger.objects.get_or_create(
        qa_result=qa_result,
        defaults={
            "material_name": material_name,
            "material_code": material_code,
            "stock_out_date": out_date,
            "lot_color": qa_result.lot_color or QAMaterialOutStockLedger.LOT_COLOR_GREEN,
            "weight_kg": qa_result.input_weight or Decimal("0"),
            "bag_sequence_no": bag_count,
            "lot_number": qa_result.lot_number or "",
            "product_code": product_code,
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
    if product_code and row.product_code != product_code:
        row.product_code = product_code
        changed = True
    if (row.weight_kg is None or row.weight_kg == 0) and qa_result.input_weight is not None:
        row.weight_kg = qa_result.input_weight
        changed = True
    if not row.bag_sequence_no and bag_count:
        row.bag_sequence_no = bag_count
        changed = True

    if changed:
        row.save()


def _is_valid_ipv4(ip):
    if not ip:
        return False
    pattern = r"^(?:[0-9]{1,3}\.){3}[0-9]{1,3}$"
    return bool(re.match(pattern, ip))


def _post_to_workstation_with_retry(ip, payload, endpoint="send_input"):
    endpoint_name = (endpoint or "send_input").strip().strip("/")
    url = f"http://{ip}:5000/{endpoint_name}"
    connect_timeout = float(getattr(settings, "NHAP_LIEU_CONNECT_TIMEOUT_SECONDS", 5))
    request_timeout = float(getattr(settings, "NHAP_LIEU_REQUEST_TIMEOUT_SECONDS", 120))
    busy_retry_count = int(getattr(settings, "NHAP_LIEU_BUSY_RETRY_COUNT", 30))
    busy_retry_delay = float(getattr(settings, "NHAP_LIEU_BUSY_RETRY_DELAY_SECONDS", 2))
    job_id = (payload or {}).get("job_id") or (payload or {}).get("ma_job") or "-"

    response = None
    busy_count = 0
    total_wait = 0.0
    for attempt in range(busy_retry_count + 1):
        response = requests.post(url, json=payload, timeout=(connect_timeout, request_timeout))
        if response.status_code != 409:
            if busy_count:
                logger.info(
                    "Workstation ready after busy wait: job_id=%s ip=%s busy_count=%s wait_seconds=%.1f status=%s",
                    job_id,
                    ip,
                    busy_count,
                    total_wait,
                    response.status_code,
                )
            return response
        busy_count += 1
        logger.warning(
            "Workstation busy (409): job_id=%s ip=%s attempt=%s/%s",
            job_id,
            ip,
            busy_count,
            busy_retry_count + 1,
        )
        if attempt >= busy_retry_count:
            logger.error(
                "Workstation busy retry exhausted: job_id=%s ip=%s busy_count=%s wait_seconds=%.1f",
                job_id,
                ip,
                busy_count,
                total_wait,
            )
            return response
        pytime.sleep(busy_retry_delay)
        total_wait += busy_retry_delay
    return response


def _close_workstation_app(ip, mode_value: str = "1"):
    """
    Yêu cầu máy trạm đóng app nhập/xuất kho theo mode.
    Trả về (ok, message).
    """
    url = f"http://{ip}:5000/close_app"
    connect_timeout = float(getattr(settings, "NHAP_LIEU_CONNECT_TIMEOUT_SECONDS", 5))
    request_timeout = float(getattr(settings, "NHAP_LIEU_REQUEST_TIMEOUT_SECONDS", 120))
    try:
        response = requests.post(
            url,
            json={"mode_value": str(mode_value or "").strip()},
            timeout=(connect_timeout, request_timeout),
        )
        if response.status_code == 200:
            return True, "closed"
        return False, f"HTTP {response.status_code}"
    except Exception as exc:
        return False, str(exc)


def _get_master_by_material_code(material_code: str):
    code = (material_code or "").strip()
    if not code:
        return None
    return QAMaterialMaster.objects.filter(material_code=code).first()


def _calculate_bag_count(weight_kg, bag_weight_kg):
    try:
        weight = Decimal(weight_kg)
        bag_weight = Decimal(bag_weight_kg)
    except Exception:
        return ""
    if weight <= 0 or bag_weight <= 0:
        return ""
    count = (weight / bag_weight).to_integral_value(rounding=ROUND_CEILING)
    if count < 1:
        count = Decimal("1")
    return str(int(count))


def _calculate_bag_count_by_material_code(material_code: str, weight_kg):
    master = _get_master_by_material_code(material_code)
    if not master or master.bag_weight_kg is None:
        return ""
    return _calculate_bag_count(weight_kg, master.bag_weight_kg)


def _normalize_order_base_no(raw: str) -> str:
    value = unicodedata.normalize("NFKC", (raw or "").strip())
    digits = re.sub(r"[^0-9]", "", value)
    if re.fullmatch(r"[0-9]{4,12}", digits or ""):
        return digits
    return ""


def _build_next_stock_in_order_no(order_base_no: str):
    """
    Trả về (order_no, suffix_no, error_message).
    Ví dụ base=5044 -> 5044-1 / 5044-2 / 5044-3; vượt quá 3 lần thì báo lỗi.
    """
    base = _normalize_order_base_no(order_base_no)
    if not base:
        return "", 0, "注文番号（ベース）は4～12桁の数字で入力してください。"

    candidates, next_suffix, error_message = _build_available_stock_in_order_nos(order_base_no)
    if error_message:
        return "", 0, error_message
    return candidates[0], next_suffix, ""


def _build_available_stock_in_order_nos(order_base_no: str):
    base = _normalize_order_base_no(order_base_no)
    if not base:
        return [], 0, "注文No.番号（ベース）は4〜12桁の数字で入力してください。"

    existing = {
        (order_no or "").strip()
        for order_no in QAMaterialStockLedger.objects.filter(order_no__startswith=f"{base}-").values_list("order_no", flat=True)
    }
    candidates = [f"{base}-{suffix}" for suffix in range(1, 4) if f"{base}-{suffix}" not in existing]
    if not candidates:
        return [], 0, f"注文No. {base} は既に3回入庫済みです（-1/-2/-3）。"

    next_suffix = int(candidates[0].rsplit("-", 1)[1])
    return candidates, next_suffix, ""


STOCK_IN_LOT_COLOR_VALUES = {
    QAMaterialStockLedger.LOT_COLOR_GREEN,
    QAMaterialStockLedger.LOT_COLOR_BLACK,
    QAMaterialStockLedger.LOT_COLOR_BLUE,
    QAMaterialStockLedger.LOT_COLOR_RED,
}


def _default_stock_in_lot_rows():
    return [
        {
            "input_weight": "",
            "lot_color": QAMaterialStockLedger.LOT_COLOR_GREEN,
            "lot_number": "",
        }
    ]


def _extract_stock_in_lot_rows(post_data):
    weight_values = post_data.getlist("input_weight")
    color_values = post_data.getlist("lot_color")
    lot_values = post_data.getlist("lot_number")

    row_count = max(len(weight_values), len(color_values), len(lot_values), 1)
    raw_rows = []
    parsed_rows = []
    total_weight = Decimal("0")

    for idx in range(row_count):
        weight_raw = (weight_values[idx] if idx < len(weight_values) else "").strip()
        lot_color = (color_values[idx] if idx < len(color_values) else "").strip() or QAMaterialStockLedger.LOT_COLOR_GREEN
        lot_number = (lot_values[idx] if idx < len(lot_values) else "").strip()

        if not any([weight_raw, lot_number]) and lot_color == QAMaterialStockLedger.LOT_COLOR_GREEN and row_count > 1:
            continue

        raw_row = {
            "input_weight": weight_raw,
            "lot_color": lot_color,
            "lot_number": lot_number,
        }
        raw_rows.append(raw_row)

        try:
            input_weight = Decimal(weight_raw)
        except (InvalidOperation, TypeError):
            return raw_rows or _default_stock_in_lot_rows(), [], Decimal("0"), f"{len(raw_rows)}行目の重量(kg)を正しく入力してください。"

        if input_weight <= 0:
            return raw_rows or _default_stock_in_lot_rows(), [], Decimal("0"), f"{len(raw_rows)}行目の重量(kg)は0より大きい値を入力してください。"

        if lot_color not in STOCK_IN_LOT_COLOR_VALUES:
            return raw_rows or _default_stock_in_lot_rows(), [], Decimal("0"), f"{len(raw_rows)}行目のロット識別色を選択してください。"

        if not lot_number:
            return raw_rows or _default_stock_in_lot_rows(), [], Decimal("0"), f"{len(raw_rows)}行目のロット番号を入力してください。"

        parsed_rows.append(
            {
                **raw_row,
                "input_weight_decimal": input_weight,
            }
        )
        total_weight += input_weight

    if not parsed_rows:
        return _default_stock_in_lot_rows(), [], Decimal("0"), "入庫するロット情報を1行以上入力してください。"

    return raw_rows, parsed_rows, total_weight, ""


def _finalize_success_phien(
    phien,
    *,
    data_ocr: str,
    full_text: str = "",
    done_message: str = "自動入力完了",
    expected_prefix: str = "3",
):
    code = (data_ocr or "").strip()
    if not code or code == "---":
        return False, "管理番号が取得できませんでした。再実行してください。", phien
    prefix = (expected_prefix or "").strip()
    if prefix and not re.fullmatch(rf"{re.escape(prefix)}\d{{4}}", code):
        return False, f"管理番号形式エラー: {code}（{prefix}で始まる5桁のみ有効）", phien

    def _do_finalize():
        with transaction.atomic():
            locked = (
                PhienNhapLieu.objects.select_for_update()
                .get(pk=phien.pk)
            )

            if (
                KetQuaNhapLieu.objects.filter(ma_nhap_lieu=code, trang_thai="Thành công")
                .exclude(phien=locked)
                .exists()
            ):
                locked.trang_thai = "failed"
                locked.thong_bao = f"管理番号重複: {code}"
                locked.save(update_fields=["trang_thai", "thong_bao", "ngay_cap_nhat"])
                return False, f"管理番号が重複しています: {code}", locked

            existing_success = (
                KetQuaNhapLieu.objects
                .filter(phien=locked, trang_thai="Thành công")
                .order_by("-id")
                .first()
            )
            if existing_success and (existing_success.ma_nhap_lieu or "").strip() != code:
                return False, "同一ジョブで管理番号が不一致です。処理を中断しました。", locked

            locked.trang_thai = "done"
            locked.ma_nhap_lieu = code
            locked.full_text = full_text or locked.full_text or ""
            locked.thong_bao = done_message
            locked.save(update_fields=["trang_thai", "ma_nhap_lieu", "full_text", "thong_bao", "ngay_cap_nhat"])

            if not existing_success:
                KetQuaNhapLieu.objects.create(
                    chuong_trinh=locked.chuong_trinh,
                    may_tinh=locked.may_tinh,
                    phien=locked,
                    ip_may=locked.ip_may or "",
                    ma_nhap_lieu=code,
                    full_text=locked.full_text or "",
                    trang_thai="Thành công",
                    ghi_chu="画像検査フローで確定保存",
                )
            elif full_text and (existing_success.full_text or "") != full_text:
                existing_success.full_text = full_text
                existing_success.save(update_fields=["full_text", "ngay_cap_nhat"])

            return True, done_message, locked

    ok, msg, locked = _run_db_with_retry(_do_finalize)
    if not ok:
        return False, msg, locked
    return True, done_message, locked


def _auto_send_to_nhap_lieu(qa_result, expected_text="", mode_value="2"):
    """
    Tự động gửi job sang app nhập liệu dựa trên material_code.
    Trả về (ok, message, phien_or_none).
    """
    if not qa_result or not qa_result.device:
        return False, "デバイス情報がないため自動入力を実行できません。", None

    material_code = (qa_result.device.material_code or "").strip()
    lot_color = (qa_result.lot_color or "").strip()
    lot_number = (qa_result.lot_number or "").strip()
    product_code = (
        (qa_result.product_code or "").strip()
        or ((qa_result.device.product_management_code or "").strip() if qa_result.device else "")
    )
    if not material_code:
        return False, "材料コードが未設定のため自動入力を実行できません。", None
    if lot_color not in {
        QAResult.LOT_COLOR_GREEN,
        QAResult.LOT_COLOR_BLACK,
        QAResult.LOT_COLOR_BLUE,
        QAResult.LOT_COLOR_RED,
    }:
        return False, "ロット識別色が未入力のため自動入力を実行できません。", None
    if not lot_number:
        return False, "ロット番号が未入力のため自動入力を実行できません。", None
    if not product_code:
        return False, "製品コードが未入力のため自動入力を実行できません。", None

    auto_program_name = (getattr(settings, "NHAP_LIEU_XUAT_KHO_PROGRAM_NAME", "5209-02") or "5209-02").strip()
    chuong_trinh = ChuongTrinhNhapLieu.objects.filter(ten_chuong_trinh=auto_program_name).first()
    if not chuong_trinh:
        return False, f"入力プログラム '{auto_program_name}' が見つかりません。", None

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
        "Dòng 3": lot_number,
        "Dòng 4": qa_result.machine_number or "",
        "Dòng 5": expected_text or "",
        "Dòng 6": product_code,
    }
    quy_tac_gui = [dong_map.get(item, item) for item in quy_tac]

    ma_job = f"job_{uuid.uuid4().hex[:16]}"
    payload = {
        "job_id": ma_job,
        "ten_chuong_trinh": chuong_trinh.ten_chuong_trinh,
        "quy_tac": quy_tac_gui,
        "kg_value": str(qa_result.input_weight or "").strip(),
        "material_code_value": material_code,
        "mode_value": str(mode_value or "2"),
        "lot_color": lot_color,
        "lot_number": lot_number,
        "product_code_value": product_code,
        "delay": 0.1,
        "qa_result_id": qa_result.id,
    }

    phien = _run_db_with_retry(
        lambda: PhienNhapLieu.objects.create(
            ma_job=ma_job,
            chuong_trinh=chuong_trinh,
            may_tinh=may_tinh,
            qa_result=qa_result,
            ip_may=may_tinh.ip,
            payload_json=json.dumps(payload, ensure_ascii=False),
            trang_thai="sending",
            thong_bao="画像検査から自動送信",
        )
    )

    try:
        response = _post_to_workstation_with_retry(may_tinh.ip, payload)
        if response.status_code != 200:
            phien.trang_thai = "failed"
            phien.thong_bao = f"送信失敗 HTTP {response.status_code}"
            phien.save(update_fields=["trang_thai", "thong_bao", "ngay_cap_nhat"])
            return False, f"自動入力送信失敗: HTTP {response.status_code}", phien

        data = response.json()
        callback_ok = bool(data.get("callback_ok"))
        data_ocr = (data.get("data_ocr") or "").strip()
        full_text = (data.get("full_text") or "").strip()

        # Ưu tiên dữ liệu phản hồi trực tiếp từ máy trạm.
        # Nếu đã có mã quản lý hợp lệ thì coi là hoàn thành,
        # kể cả callback ngược về Django tạm thời lỗi.
        if data_ocr:
            done_msg = "自動入力完了" if callback_ok else "自動入力完了（コールバック未達）"
            ok, finalize_msg, updated_phien = _finalize_success_phien(
                phien,
                data_ocr=data_ocr,
                full_text=full_text,
                done_message=done_msg,
                expected_prefix="3",
            )
            if not ok:
                return False, finalize_msg or "確定保存に失敗しました。", updated_phien
            if callback_ok:
                return True, f"自動入力完了: {chuong_trinh.ten_chuong_trinh} / {may_tinh.ip}", updated_phien
            return True, f"自動入力完了（コールバック未達）: {chuong_trinh.ten_chuong_trinh} / {may_tinh.ip}", updated_phien

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
        if isinstance(exc, requests.exceptions.ConnectTimeout):
            phien.trang_thai = "failed"
            phien.thong_bao = "接続タイムアウト: 端末API(5000)に接続できません"
            phien.save(update_fields=["trang_thai", "thong_bao", "ngay_cap_nhat"])
            return False, "端末APIに接続できません。端末側API起動/ネットワーク/Firewallをご確認ください。", phien
        phien.trang_thai = "failed"
        phien.thong_bao = f"送信例外: {exc}"
        phien.save(update_fields=["trang_thai", "thong_bao", "ngay_cap_nhat"])
        return False, f"自動入力送信エラー: {exc}", phien


def _normalize_hinmei_text(value: str) -> str:
    text = unicodedata.normalize("NFKC", (value or "").strip()).lower()
    return re.sub(r"\s+", "", text)


def _stock_in_hinmei_precheck(*, material_code: str, input_weight: Decimal, lot_number: str = "", order_no: str = ""):
    """
    入庫フローの品名確認ステップ（token: HINMEI_CHECK_KEYS/品名）。
    Trả về (ok, message, hinmei_text).
    """
    material_code = (material_code or "").strip()
    order_no = (order_no or "").strip()
    if not material_code:
        return False, "材料コードが未設定のため品名確認を実行できません。", ""
    if not order_no:
        return False, "注文No.が未入力のため品名確認を実行できません。", ""

    auto_program_name = (
        getattr(
            settings,
            "NHAP_LIEU_NHAP_KHO_PROGRAM_NAME",
            getattr(settings, "NHAP_LIEU_XUAT_KHO_PROGRAM_NAME", "5209-01"),
        )
        or "5209-01"
    ).strip()
    chuong_trinh = ChuongTrinhNhapLieu.objects.filter(ten_chuong_trinh=auto_program_name).first()
    if not chuong_trinh:
        return False, f"入力プログラム '{auto_program_name}' が見つかりません。", ""

    may_tinh = MayTinh.objects.filter(ten_may="server").first()
    if not may_tinh:
        return False, "固定送信先 server が見つかりません。", ""
    if may_tinh.trang_thai != "active":
        return False, "固定送信先 server が非アクティブです。", ""
    if not _is_valid_ipv4(may_tinh.ip):
        return False, "固定送信先 server のIPが無効です。", ""

    try:
        quy_tac = json.loads(chuong_trinh.quy_tac or "[]")
    except Exception:
        quy_tac = []

    stock_in_date_yymmdd = timezone.localdate().strftime("%y%m%d")
    dong_map = {
        "Dòng 1": material_code,
        "Dòng 2": str(input_weight or ""),
        "Dòng 3": lot_number or "",
        "Dòng 4": stock_in_date_yymmdd,
        "Dòng 5": order_no,
    }
    quy_tac_gui = [dong_map.get(item, item) for item in quy_tac]

    token_names = {"HINMEI_CHECK_KEYS", "HINMEI_KEYS", "品名"}
    token_idx = next((idx for idx, item in enumerate(quy_tac_gui) if str(item).strip() in token_names), -1)
    if token_idx < 0:
        return False, "テンプレートに品名確認トークン（HINMEI_CHECK_KEYS / 品名）がありません。", ""

    pre_rules = quy_tac_gui[: token_idx + 1]

    ma_job = f"job_{uuid.uuid4().hex[:16]}"
    payload = {
        "job_id": ma_job,
        "ten_chuong_trinh": chuong_trinh.ten_chuong_trinh,
        "quy_tac": pre_rules,
        "kg_value": str(input_weight or "").strip(),
        "material_code_value": material_code,
        "lot_number": lot_number or "",
        "mode_value": "1",
        "date_yymmdd_value": stock_in_date_yymmdd,
        "order_no_value": order_no,
        "hinmei_check_only": True,
        "delay": 0.1,
    }

    try:
        response = _post_to_workstation_with_retry(may_tinh.ip, payload)
        if response.status_code != 200:
            return False, f"品名確認送信失敗: HTTP {response.status_code}", ""
        data = response.json()
        if (data.get("status") or "") != "hinmei_checked":
            return False, "端末側で品名確認結果を取得できませんでした。", ""
        hinmei_text = (data.get("hinmei_text") or "").strip()
        return True, "品名確認OK", hinmei_text
    except Exception as exc:
        return False, f"品名確認エラー: {exc}", ""


def _auto_send_stock_in_to_nhap_lieu(
    *,
    material_code: str,
    input_weight: Decimal,
    lot_number: str = "",
    order_no: str = "",
    quy_tac_override=None,
    skip_open_app: bool = False,
    program_name_override: str = "",
    start_step: int = 1,
):
    """
    入庫フロー向けの自動入力送信（mode=1）。
    Trả về (ok, message, phien_or_none, ma_nhap_lieu).
    """
    material_code = (material_code or "").strip()
    if not material_code:
        return False, "材料コードが未設定のため自動入力を実行できません。", None, ""
    order_no = (order_no or "").strip()
    if not order_no:
        return False, "注文No.が未入力のため自動入力を実行できません。", None, ""

    if (program_name_override or "").strip():
        auto_program_name = (program_name_override or "").strip()
    else:
        auto_program_name = (
            getattr(
                settings,
                "NHAP_LIEU_NHAP_KHO_PROGRAM_NAME",
                getattr(settings, "NHAP_LIEU_XUAT_KHO_PROGRAM_NAME", "5209-01"),
            )
            or "5209-01"
        ).strip()
    chuong_trinh = ChuongTrinhNhapLieu.objects.filter(ten_chuong_trinh=auto_program_name).first()
    if not chuong_trinh:
        return False, f"入力プログラム '{auto_program_name}' が見つかりません。", None, ""

    may_tinh = MayTinh.objects.filter(ten_may="server").first()
    if not may_tinh:
        return False, "固定送信先 server が見つかりません。", None, ""
    if may_tinh.trang_thai != "active":
        return False, "固定送信先 server が非アクティブです。", None, ""
    if not _is_valid_ipv4(may_tinh.ip):
        return False, "固定送信先 server のIPが無効です。", None, ""

    stock_in_date_yymmdd = timezone.localdate().strftime("%y%m%d")
    if quy_tac_override is not None:
        quy_tac_gui = [str(item).strip() for item in (quy_tac_override or []) if str(item).strip()]
    else:
        try:
            quy_tac = json.loads(chuong_trinh.quy_tac or "[]")
        except Exception:
            quy_tac = []

        dong_map = {
            "Dòng 1": material_code,
            "Dòng 2": str(input_weight or ""),
            "Dòng 3": lot_number or "",
            "Dòng 4": stock_in_date_yymmdd,
            "Dòng 5": order_no,
        }
        quy_tac_gui = [dong_map.get(item, item) for item in quy_tac]

    ma_job = f"job_{uuid.uuid4().hex[:16]}"
    payload = {
        "job_id": ma_job,
        "ten_chuong_trinh": chuong_trinh.ten_chuong_trinh,
        "quy_tac": quy_tac_gui,
        "kg_value": str(input_weight or "").strip(),
        "material_code_value": material_code,
        "lot_number": lot_number or "",
        "mode_value": "1",  # 入庫
        "date_yymmdd_value": stock_in_date_yymmdd,
        "order_no_value": order_no,
        "skip_open_app": bool(skip_open_app),
        "start_step": int(start_step or 1),
        "delay": 0.1,
    }

    phien = _run_db_with_retry(
        lambda: PhienNhapLieu.objects.create(
            ma_job=ma_job,
            chuong_trinh=chuong_trinh,
            may_tinh=may_tinh,
            qa_result=None,
            ip_may=may_tinh.ip,
            payload_json=json.dumps(payload, ensure_ascii=False),
            trang_thai="sending",
            thong_bao="入庫フローから自動送信",
        )
    )

    try:
        endpoint = "send_input_typing_only" if skip_open_app else "send_input"
        response = _post_to_workstation_with_retry(may_tinh.ip, payload, endpoint=endpoint)
        if response.status_code != 200:
            phien.trang_thai = "failed"
            phien.thong_bao = f"送信失敗 HTTP {response.status_code}"
            phien.save(update_fields=["trang_thai", "thong_bao", "ngay_cap_nhat"])
            return False, f"自動入力送信失敗: HTTP {response.status_code}", phien, ""

        data = response.json()
        callback_ok = bool(data.get("callback_ok"))
        data_ocr = (data.get("data_ocr") or "").strip()
        full_text = (data.get("full_text") or "").strip()

        if data_ocr:
            done_msg = "自動入力完了（入庫）" if callback_ok else "自動入力完了（入庫・コールバック未達）"
            ok, finalize_msg, updated_phien = _finalize_success_phien(
                phien,
                data_ocr=data_ocr,
                full_text=full_text,
                done_message=done_msg,
                expected_prefix="2",
            )
            if not ok:
                return False, finalize_msg or "確定保存に失敗しました。", updated_phien, ""
            return True, f"{done_msg}: {chuong_trinh.ten_chuong_trinh} / {may_tinh.ip}", updated_phien, data_ocr

        if callback_ok:
            phien.trang_thai = "failed"
            phien.thong_bao = "管理番号未取得。処理未完了"
            phien.save(update_fields=["trang_thai", "thong_bao", "ngay_cap_nhat"])
            return False, "入力処理は完了していません（管理番号未取得）。", phien, ""

        phien.trang_thai = "failed"
        phien.thong_bao = f"Callback lỗi: {data.get('callback_info') or 'unknown'}"
        phien.save(update_fields=["trang_thai", "thong_bao", "ngay_cap_nhat"])
        return False, "自動入力のコールバックに失敗しました。", phien, ""
    except Exception as exc:
        if isinstance(exc, requests.exceptions.ConnectTimeout):
            phien.trang_thai = "failed"
            phien.thong_bao = "接続タイムアウト: 端末API(5000)に接続できません"
            phien.save(update_fields=["trang_thai", "thong_bao", "ngay_cap_nhat"])
            return False, "端末APIに接続できません。端末側API起動/ネットワーク/Firewallをご確認ください。", phien, ""
        phien.trang_thai = "failed"
        phien.thong_bao = f"送信例外: {exc}"
        phien.save(update_fields=["trang_thai", "thong_bao", "ngay_cap_nhat"])
        return False, f"自動入力送信エラー: {exc}", phien, ""


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
            .values("material_name", "material_code", "bag_weight_kg", "qr_content", "qr_content_in")
            .order_by("material_name", "material_code")
        )
        material_list = [
            {
                "material": row.get("material_name") or "",
                "material_code": row.get("material_code") or "",
                "bag_weight_kg": row.get("bag_weight_kg"),
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
                "bag_weight_kg": "",
                "qr_content": key[0],
            }
        )
    return legacy_list


def _build_outstock_machine_options():
    devices = QADeviceInfo.objects.all().order_by("name", "product", "material", "id")
    grouped = defaultdict(list)
    for device in devices:
        machine_name = (device.name or "").strip()
        if not machine_name:
            continue
        product_name = (device.product_name or "").strip()
        material_code = (device.material_code or "").strip()
        grouped[machine_name].append(
            {
                "id": device.id,
                "machine_name": machine_name,
                "product_name": product_name,
                "product_code": (device.product_management_code or "").strip(),
                "material": (device.material or "").strip(),
                "material_code": material_code,
                "ratio": (device.ratio or "").strip(),
                "auto_input_enabled": bool(device.outstock_auto_input_enabled),
                "label": " | ".join(
                    [
                        part
                        for part in [
                            product_name or "-",
                            material_code,
                            (device.material or "").strip(),
                        ]
                        if part
                    ]
                ),
            }
        )
    return [
        {
            "machine_name": machine_name,
            "devices": rows,
            "needs_product_choice": len(
                {
                    (
                        row.get("product_name") or "",
                        row.get("product_code") or "",
                        row.get("material_code") or "",
                    )
                    for row in rows
                }
            )
            > 1,
        }
        for machine_name, rows in grouped.items()
    ]


def _safe_next_url(request, fallback=None):
    next_url = (request.POST.get("next") or request.GET.get("next") or "").strip()
    if next_url and url_has_allowed_host_and_scheme(
        next_url,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        return next_url
    return fallback or reverse("index_qa")


def _today_tablet_tenken(tablet):
    if not tablet:
        return None
    return (
        QATabletInspection.objects.filter(
            tablet=tablet,
            check_date=timezone.localdate(),
            result=QATabletInspection.RESULT_OK,
            check_type__in=[QATabletInspection.CHECK_STARTUP, QATabletInspection.CHECK_DAILY],
        )
        .order_by("-id")
        .first()
    )


def _get_session_tablet(request):
    tablet_id = request.session.get("qa_tablet_id")
    if not tablet_id:
        return None
    return QATabletDevice.objects.filter(pk=tablet_id).first()


def _is_admin_pc_mode(request):
    if not request.session.get("qa_tablet_admin_bypass"):
        return False
    if _can_bypass_tablet_tenken(request.user):
        return True
    request.session.pop("qa_tablet_admin_bypass", None)
    return False


def _render_tablet_tenken_gate(request, next_url=None):
    selected_tablet = _get_session_tablet(request)
    active_tablets = list(QATabletDevice.objects.filter(status=QATabletDevice.STATUS_ACTIVE).order_by("code"))
    today = timezone.localdate()
    tenken_map = {
        row.tablet_id: row
        for row in QATabletInspection.objects.filter(
            check_date=today,
            result=QATabletInspection.RESULT_OK,
            check_type__in=[QATabletInspection.CHECK_STARTUP, QATabletInspection.CHECK_DAILY],
        ).order_by("tablet_id", "-id")
    }
    for tablet in active_tablets:
        tablet.today_tenken = tenken_map.get(tablet.id)
    return render(
        request,
        "quet_anh/tablet_tenken_gate.html",
        {
            "active_tablets": active_tablets,
            "selected_tablet": selected_tablet,
            "admin_pc_mode": _is_admin_pc_mode(request),
            "can_admin_bypass_tablet_tenken": _can_bypass_tablet_tenken(request.user),
            "today": today,
            "today_tenken": _today_tablet_tenken(selected_tablet),
            "tenken_map": tenken_map,
            "next_url": next_url or request.get_full_path(),
        },
    )


def _require_tablet_tenken_today(request):
    if _is_admin_pc_mode(request):
        return True, None
    selected_tablet = _get_session_tablet(request)
    if not selected_tablet:
        return False, None
    if selected_tablet.status != QATabletDevice.STATUS_ACTIVE:
        return False, selected_tablet
    return bool(_today_tablet_tenken(selected_tablet)), selected_tablet


@login_required
def upload_image(request):
    tenken_ok, _selected_tablet = _require_tablet_tenken_today(request)
    if not tenken_ok:
        return _render_tablet_tenken_gate(request)

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
        auto_input_for_device = bool(getattr(device, "outstock_auto_input_enabled", False))
        # 製品コードは保全マスター（baotri）から自動取得する
        product_code = (device.product_management_code or "").strip() if device else ""

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
        if not lot_number:
            messages.error(request, "ロット番号を入力してください。")
            device_list = QADeviceInfo.objects.all()
            return render(request, 'quet_anh/upload.html', {
                'form': QAResultForm(request.POST),
                'message': message,
                'expected_text': expected_text,
                'device_list': device_list,
                'device_id': device_id,
                'device': device,
            })
        if auto_input_for_device and not product_code:
            messages.error(request, "保全マスターに製品コードが未登録です。先に保全側で製品コードを設定してください。")
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

        submit_lock_key = _outstock_idempotency_cache_key(
            device_id=getattr(device, "id", ""),
            machine_number=machine_number,
            expected_text=expected_text,
            input_weight=input_weight,
            lot_color=lot_color,
            lot_number=lot_number,
            product_code=product_code,
            captured_image=captured_image,
        )
        existing_submit_state = cache.get(submit_lock_key)
        if existing_submit_state:
            if existing_submit_state.get("status") == "done":
                return render(
                    request,
                    "quet_anh/auto_success.html",
                    {
                        "flow_name": existing_submit_state.get("flow_name") or "蜃ｺ蠎ｫ蜃ｦ逅・,
                        "registration_code": existing_submit_state.get("registration_code") or "",
                        "detail_message": existing_submit_state.get("detail_message") or "同じ内容はすでに処理済みです。履歴をご確認ください。",
                    },
                )
            messages.warning(request, "同じ内容の送信がすでに処理中です。しばらく待って履歴を確認してください。")
            return redirect("qa_history")
        cache.set(submit_lock_key, {"status": "processing"}, timeout=300)

        if captured_image:
            format, imgstr = captured_image.split(';base64,')
            ext = format.split('/')[-1]
            img_content = ContentFile(base64.b64decode(imgstr), name=f"captured.{ext}")
            image_file = img_content

            form = QAResultForm(request.POST)
            if not form.is_valid():
                cache.delete(submit_lock_key)
                messages.error(request, f"フォームエラー: {form.errors}")
                device_list = QADeviceInfo.objects.all()
                cache.delete(submit_lock_key)
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
                os.environ.setdefault("OMP_NUM_THREADS", "1")
                os.environ.setdefault("MKL_NUM_THREADS", "1")
                from paddleocr import PaddleOCR
                ocr = PaddleOCR(
                    use_angle_cls=False,
                    lang='japan',
                    rec=True,
                    det=True,
                    use_gpu=False,
                    enable_mkldnn=False,
                    show_log=False,
                )
                img_np = np.array(image)
                result_ocr = ocr.ocr(img_np, cls=False)
                paddle_text = ''.join([line[1][0] for line in (result_ocr[0] or [])]) if result_ocr else ""
                paddle_text = paddle_text.replace('\n', '').replace('\r', '').replace(' ', '')
            except Exception as e:
                logger.exception("PaddleOCR failed during QA outstock scan: %s", e)
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
                    f"製品名: {device.product_name if device else ''}\n"
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
                cache.delete(submit_lock_key)
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
            qa_result.product_code = product_code
            qa_result.save()

            # Tự động gọi app nhập liệu nếu ảnh khớp (xuất nguyên liệu)
            registration_code = ""
            flow_detail_message = "出庫データの保存と自動入力が完了しました。"
            if qa_result.result == "一致":
                auto_input_for_device = bool(getattr(qa_result.device, "outstock_auto_input_enabled", False))
                material_code = (qa_result.device.material_code or "").strip() if qa_result.device else ""
                if auto_input_for_device and not material_code:
                    messages.warning(request, "材料コード未設定のため、自動入力はスキップしました。画像検査結果のみ保存します。")
                    return redirect("qa_history")
                elif not _is_auto_outstock_target(qa_result):
                    messages.success(
                        request,
                        f"この機械・原材料は自動入力OFFです（{qa_result.device.material or '-'} / {material_code}）。画像検査結果のみ保存しました。",
                    )
                    return redirect("qa_history")
                else:
                    auto_ok, auto_msg, auto_phien = _auto_send_to_nhap_lieu(
                        qa_result,
                        expected_text=expected_text or "",
                        mode_value="2",  # 出庫
                    )
                    if auto_ok:
                        messages.success(request, auto_msg)
                        registration_code = ((auto_phien.ma_nhap_lieu if auto_phien else "") or "").strip()
                    else:
                        _rollback_failed_qa_attempt(qa_result)
                        messages.error(request, f"{auto_msg} / 保存しません。再スキャンしてください。")
                        form = QAResultForm()
                        device_list = QADeviceInfo.objects.all()
                        cache.delete(submit_lock_key)
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

            return render(
                request,
                "quet_anh/auto_success.html",
                {
                    "flow_name": "出庫処理",
                    "registration_code": registration_code,
                    "detail_message": flow_detail_message,
                },
            )
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
    tenken_ok, selected_tablet = _require_tablet_tenken_today(request)
    if not tenken_ok:
        return _render_tablet_tenken_gate(request)

    device_list = QADeviceInfo.objects.all()
    material_list = _build_material_list_for_stock_in()
    outstock_machine_options = _build_outstock_machine_options()
    return render(request, 'quet_anh/index_qa.html', {
        'device_list': device_list,
        'material_list': material_list,
        'outstock_machine_options': outstock_machine_options,
        'selected_tablet': selected_tablet,
    })


@login_required
def stock_in_start(request):
    tenken_ok, _selected_tablet = _require_tablet_tenken_today(request)
    if not tenken_ok:
        return _render_tablet_tenken_gate(request)

    material_name = (request.POST.get("material_name") or request.GET.get("material_name") or "").strip()
    material_code = (request.POST.get("material_code") or request.GET.get("material_code") or "").strip()
    order_base_no_input = (request.POST.get("order_base_no") or request.GET.get("order_base_no") or "").strip()

    material_list = _build_material_list_for_stock_in()
    material_map = {
        ((item.get("material") or "").strip(), (item.get("material_code") or "").strip()): item
        for item in material_list
    }
    name_to_first_code = {}
    for item in material_list:
        n = (item.get("material") or "").strip()
        c = (item.get("material_code") or "").strip()
        if n and c and n not in name_to_first_code:
            name_to_first_code[n] = c

    # Nếu chỉ có tên nhưng chưa có mã, tự map theo master
    if material_name and not material_code:
        material_code = name_to_first_code.get(material_name, "")

    # Khi vào thẳng URL mà chưa chọn gì, tự gán item đầu tiên để UI thao tác được ngay
    if not material_name and not material_code and material_list:
        material_name = (material_list[0].get("material") or "").strip()
        material_code = (material_list[0].get("material_code") or "").strip()

    stock_in_lot_rows = _default_stock_in_lot_rows()

    def render_stock_in(extra_context=None):
        context = {
            "material_name": material_name,
            "material_code": material_code,
            "order_base_no": order_base_no_input,
            "material_list": material_list,
            "stock_in_lot_rows": stock_in_lot_rows,
        }
        if extra_context:
            context.update(extra_context)
        return render(request, "quet_anh/stock_in_start.html", context)

    if request.method == "POST":
        action = (request.POST.get("action") or "").strip().lower()
        if action == "cancel":
            may_tinh = MayTinh.objects.filter(ten_may="server").first()
            if may_tinh and _is_valid_ipv4(may_tinh.ip):
                _close_workstation_app(may_tinh.ip, mode_value="1")
            return redirect("index_qa")

        stock_in_lot_rows, lot_rows, total_input_weight, lot_err = _extract_stock_in_lot_rows(request.POST)
        order_base_no = _normalize_order_base_no(order_base_no_input)

        # Ưu tiên map theo mã, fallback theo tên để không bị kẹt luồng nhập kho
        matched = material_map.get((material_name, material_code))
        if not matched and material_name and material_code:
            matched = next(
                (item for item in material_list if (item.get("material") or "").strip() == material_name),
                None,
            )
        if not matched and material_name and not material_code:
            mapped_code = name_to_first_code.get(material_name, "")
            if mapped_code:
                material_code = mapped_code
                matched = next(
                    (
                        item
                        for item in material_list
                        if (item.get("material") or "").strip() == material_name
                        and (item.get("material_code") or "").strip() == material_code
                    ),
                    None,
                )
        if not matched:
            messages.error(request, "原材料マスターから対象原材料を選択してください。")
            return render_stock_in()

        if lot_err:
            messages.error(request, lot_err)
            return render_stock_in()

        if not order_base_no:
            messages.error(request, "注文No.ベース（例: 5044）を入力してください。")
            return render_stock_in()

        order_no, _, order_err = _build_next_stock_in_order_no(order_base_no)
        if order_err:
            messages.error(request, order_err)
            return render_stock_in({"block_order_limit": True})

        stage = (request.POST.get("stage") or "precheck").strip().lower()

        if stage == "confirm":
            pending = request.session.get("stock_in_hinmei_ok") or {}
            if not pending:
                messages.error(request, "品名確認が未完了です。先に品名確認を実行してください。")
                return render_stock_in()
            pending_material_code = (pending.get("material_code") or "").strip()
            if pending_material_code and pending_material_code != (material_code or "").strip():
                messages.error(request, "原材料コードが変更されています。再度品名確認を実行してください。")
                request.session.pop("stock_in_hinmei_ok", None)
                return render_stock_in()
            pending_order_no = (pending.get("order_no") or "").strip()
            if pending_order_no:
                pending_order_base = pending_order_no.rsplit("-", 1)[0]
                if pending_order_base != order_base_no:
                    messages.error(request, "注文No.が変更されています。再度品名確認を実行してください。")
                    request.session.pop("stock_in_hinmei_ok", None)
                    return render_stock_in()
                order_no = pending_order_no
            if pending_order_no and pending_order_no != order_no:
                messages.error(request, "注文No.が変更されています。再度品名確認を実行してください。")
                request.session.pop("stock_in_hinmei_ok", None)
                return render_stock_in()
            pending_total_weight = (pending.get("total_weight") or "").strip()
            if pending_total_weight and pending_total_weight != str(total_input_weight):
                messages.error(request, "合計重量が変更されています。再度品名確認を実行してください。")
                request.session.pop("stock_in_hinmei_ok", None)
                return render_stock_in()

            operator_name = _display_login_name(request.user) or ""
            lot_number_summary = ", ".join(
                [row["lot_number"] for row in lot_rows if (row.get("lot_number") or "").strip()]
            )
            ok, auto_msg, phien, ma_nhap_lieu = _auto_send_stock_in_to_nhap_lieu(
                material_code=material_code,
                input_weight=total_input_weight,
                lot_number=lot_number_summary,
                order_no=order_no,
                skip_open_app=True,
                program_name_override="nhapkho",
                start_step=11,
                quy_tac_override=None,
            )
            if not ok:
                may_tinh = MayTinh.objects.filter(ten_may="server").first()
                if may_tinh and _is_valid_ipv4(may_tinh.ip):
                    _close_workstation_app(may_tinh.ip, mode_value="1")
                messages.error(request, auto_msg)
                return render_stock_in(
                    {
                        "hinmei_text": pending.get("hinmei_text") or "",
                        "order_no_preview": order_no,
                        "hinmei_ok": True,
                    }
                )

            registration_code = (ma_nhap_lieu or "").strip()
            registration_codes = [registration_code] if registration_code else []
            auto_input_ledger = QAAutoInputLedger.objects.filter(phien_nhap_lieu=phien).first() if phien else None
            with transaction.atomic():
                for idx, lot_row in enumerate(lot_rows):
                    bag_sequence_no = _calculate_bag_count_by_material_code(material_code, lot_row["input_weight_decimal"]) or "1"
                    QAMaterialStockLedger.objects.create(
                        auto_input_ledger=auto_input_ledger if idx == 0 else None,
                        qa_result=None,
                        material_name=material_name or "",
                        material_code=material_code or "",
                        stock_in_date=timezone.localdate(),
                        lot_color=lot_row["lot_color"],
                        weight_kg=lot_row["input_weight_decimal"],
                        bag_sequence_no=bag_sequence_no,
                        lot_number=lot_row["lot_number"],
                        hinmei_name=(pending.get("hinmei_text") or ""),
                        order_no=order_no,
                        workstation_management_no=registration_code,
                        operator_name=operator_name,
                    )

            request.session.pop("stock_in_hinmei_ok", None)
            return render(
                request,
                "quet_anh/auto_success.html",
                {
                    "flow_name": "入庫処理",
                    "registration_code": ", ".join([code for code in registration_codes if code]),
                    "detail_message": f"入庫データの保存と自動入力が完了しました。注文No. {order_no} / ロット {len(lot_rows)}件",
                },
            )

        pre_ok, pre_msg, hinmei_text = _stock_in_hinmei_precheck(
            material_code=material_code,
            input_weight=total_input_weight,
            lot_number=lot_rows[0]["lot_number"] if lot_rows else "",
            order_no=order_no,
        )
        if not pre_ok:
            messages.error(request, pre_msg)
            return render_stock_in()

        hinmei_text = (hinmei_text or "").strip()

        request.session["stock_in_hinmei_ok"] = {
            "material_code": material_code,
            "order_no": order_no,
            "hinmei_text": hinmei_text,
            "total_weight": str(total_input_weight),
            "checked_at": timezone.localtime().isoformat(),
        }
        messages.success(
            request,
            f"品名確認OK: {hinmei_text or '-'} / 注文No. {order_no}。",
        )
        return render_stock_in(
            {
                "hinmei_text": hinmei_text,
                "order_no_preview": order_no,
                "hinmei_ok": True,
            }
        )

    return render_stock_in()

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
    if not request.user.is_superuser:
        return render(request, 'quet_anh/403.html', status=403)
    success_message = None
    if request.method == 'POST':
        form = QADeviceInfoForm(request.POST)
        if form.is_valid():
            item = form.save(commit=False)
            task = form.cleaned_data.get("maintenance_task")
            if task:
                item.product = (task.name or "").strip()
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
            task = form.cleaned_data.get("maintenance_task")
            if task:
                obj.product = (task.name or "").strip()
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

@login_required
def qa_device_list(request):
    device_list = list(QADeviceInfo.objects.all().order_by("name", "product", "material", "id"))
    machine_counts = defaultdict(int)
    machine_product_counts = defaultdict(int)
    for item in device_list:
        machine_key = (item.name or "").strip()
        product_key = (item.product_name or "").strip()
        if machine_key:
            machine_counts[machine_key] += 1
            machine_product_counts[(machine_key, product_key)] += 1

    for item in device_list:
        machine_key = (item.name or "").strip()
        product_key = (item.product_name or "").strip()
        item.duplicate_level = ""
        item.duplicate_note = ""
        if machine_key and machine_product_counts[(machine_key, product_key)] > 1:
            item.duplicate_level = "machine_product"
            item.duplicate_note = "機械番号・製品名が重複"
        elif machine_key and machine_counts[machine_key] > 1:
            item.duplicate_level = "machine"
            item.duplicate_note = "機械番号が重複"
    return render(
        request,
        'quet_anh/qa_device_list.html',
        {
            'device_list': device_list,
        },
    )


@login_required
def tablet_device_list(request):
    tablets = QATabletDevice.objects.all().order_by("code")
    latest_by_tablet = {}
    latest_rows = QATabletInspection.objects.select_related("tablet").order_by("tablet_id", "-check_date", "-id")
    for row in latest_rows:
        latest_by_tablet.setdefault(row.tablet_id, row)
    inspections = QATabletInspection.objects.select_related("tablet").order_by("-check_date", "-id")[:30]
    return render(
        request,
        "quet_anh/tablet_device_list.html",
        {
            "tablets": tablets,
            "latest_by_tablet": latest_by_tablet,
            "inspections": inspections,
            "can_edit_tablet": request.user.is_superuser,
            "can_confirm": _can_supervisor_confirm(request.user),
        },
    )


@login_required
def tablet_device_edit(request, pk=None):
    if not request.user.is_superuser:
        return render(request, "quet_anh/403.html", status=403)
    tablet = get_object_or_404(QATabletDevice, pk=pk) if pk else None
    if request.method == "POST":
        form = QATabletDeviceForm(request.POST, instance=tablet)
        if form.is_valid():
            form.save()
            messages.success(request, "タブレット情報を保存しました。")
            return redirect("tablet_device_list")
        messages.error(request, "入力内容を確認してください。")
    else:
        form = QATabletDeviceForm(instance=tablet)
    return render(request, "quet_anh/tablet_device_form.html", {"form": form, "tablet": tablet})


@login_required
@require_POST
def tablet_select(request):
    next_url = _safe_next_url(request)
    if request.POST.get("admin_pc_mode") == "1":
        if not _can_bypass_tablet_tenken(request.user):
            messages.error(request, "Admin / PC mode is only available for the admin account.")
            return _render_tablet_tenken_gate(request, next_url=next_url)
        request.session["qa_tablet_admin_bypass"] = True
        request.session.pop("qa_tablet_id", None)
        request.session.pop("qa_tablet_code", None)
        messages.success(request, "Admin / PC mode selected. Tablet tenken is skipped for this session.")
        return redirect(next_url)

    tablet_id = request.POST.get("tablet_id")
    tablet = QATabletDevice.objects.filter(pk=tablet_id, status=QATabletDevice.STATUS_ACTIVE).first()
    if not tablet:
        messages.error(request, "使用するタブレットを一覧から選択してください。")
        return _render_tablet_tenken_gate(request, next_url=next_url)
    request.session.pop("qa_tablet_admin_bypass", None)
    request.session["qa_tablet_id"] = tablet.id
    request.session["qa_tablet_code"] = tablet.code
    if _today_tablet_tenken(tablet):
        messages.success(request, f"{tablet.code} の本日点検は完了しています。")
    else:
        messages.warning(request, f"{tablet.code} は本日点検が未完了です。使用前点検を実施してください。")
    return redirect(next_url)


@login_required
def tablet_inspection_add(request):
    initial = {"check_date": timezone.localdate()}
    tablet_id = request.GET.get("tablet")
    next_url = _safe_next_url(request, fallback=reverse("index_qa"))
    if tablet_id:
        initial["tablet"] = tablet_id
    if request.method == "POST":
        next_url = _safe_next_url(request, fallback=reverse("index_qa"))
        form = QATabletInspectionForm(request.POST)
        if form.is_valid():
            inspection = form.save(commit=False)
            inspection.checked_by = _display_login_name(request.user)
            qr_text = (inspection.qr_sample_text or "").strip()
            inspection.qr_sample_ok = qr_text.startswith("QA-TABLET-CHECK")
            if qr_text and not inspection.qr_sample_checked_at:
                inspection.qr_sample_checked_at = timezone.now()
            if not inspection.qr_sample_ok:
                inspection.result = QATabletInspection.RESULT_NG
                if inspection.problem_category == QATabletInspection.PROBLEM_NONE:
                    inspection.problem_category = QATabletInspection.PROBLEM_QR
            if inspection.result == QATabletInspection.RESULT_OK:
                inspection.problem_category = QATabletInspection.PROBLEM_NONE
            inspection.save()
            if inspection.result == QATabletInspection.RESULT_NG:
                tablet = inspection.tablet
                tablet.status = QATabletDevice.STATUS_STOPPED
                tablet.save(update_fields=["status", "updated_at"])
                if request.session.get("qa_tablet_id") == tablet.id:
                    request.session.pop("qa_tablet_id", None)
                    request.session.pop("qa_tablet_code", None)
                messages.warning(request, "NG点検を登録しました。試験運用のためスキャンは停止しませんが、該当タブレットは使用停止として記録しました。")
            else:
                request.session["qa_tablet_id"] = inspection.tablet_id
                request.session["qa_tablet_code"] = inspection.tablet.code
                messages.success(request, "点検OKを登録しました。")
                return redirect(next_url)
            return redirect("tablet_device_list")
        messages.error(request, "入力内容を確認してください。")
    else:
        form = QATabletInspectionForm(initial=initial)
    return render(request, "quet_anh/tablet_inspection_form.html", {"form": form, "next_url": next_url})


@login_required
@require_POST
def tablet_inspection_confirm(request, pk):
    if not _can_supervisor_confirm(request.user):
        messages.error(request, "確認権限がありません。")
        return redirect("tablet_device_list")
    inspection = get_object_or_404(QATabletInspection, pk=pk)
    inspection.confirmed_by = _display_login_name(request.user)
    inspection.confirmed_at = timezone.now()
    inspection.save(update_fields=["confirmed_by", "confirmed_at", "updated_at"])
    if inspection.result == QATabletInspection.RESULT_OK and inspection.check_type == QATabletInspection.CHECK_RECOVERY:
        tablet = inspection.tablet
        tablet.status = QATabletDevice.STATUS_ACTIVE
        tablet.save(update_fields=["status", "updated_at"])
    messages.success(request, "点検記録を確認済みにしました。")
    return redirect("tablet_device_list")


@login_required
def material_master_list(request):
    keyword = (request.GET.get("keyword") or "").strip()
    qs = QAMaterialMaster.objects.all()
    if keyword:
        q = (
            Q(material_name__icontains=keyword)
            | Q(material_code__icontains=keyword)
            | Q(qr_content__icontains=keyword)
            | Q(qr_content_in__icontains=keyword)
        )
        try:
            q |= Q(bag_weight_kg=Decimal(keyword))
        except Exception:
            pass
        qs = qs.filter(q)
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
            if scan.device and scan.device.product_name:
                product_name = scan.device.product_name
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

    hour_stats = defaultdict(lambda: {'count': 0, 'users': set(), 'materials': set()})
    weekday_stats = {
        0: {"label": "月曜日", "count": 0, "kg": Decimal("0")},
        1: {"label": "火曜日", "count": 0, "kg": Decimal("0")},
        2: {"label": "水曜日", "count": 0, "kg": Decimal("0")},
        3: {"label": "木曜日", "count": 0, "kg": Decimal("0")},
        4: {"label": "金曜日", "count": 0, "kg": Decimal("0")},
    }
    for scan in results:
        hour = localtime(scan.created_at).hour
        weekday = localtime(scan.created_at).weekday()
        _, user_display = _operator_identity(scan)
        material = scan.device.material if scan.device and scan.device.material else "不明"
        hour_stats[hour]['count'] += 1
        hour_stats[hour]['users'].add(user_display)
        hour_stats[hour]['materials'].add(material)
        if scan.input_weight is not None:
            hour_stats[hour].setdefault('kg', Decimal("0"))
            hour_stats[hour]['kg'] += scan.input_weight
            if weekday in weekday_stats:
                weekday_stats[weekday]["kg"] += scan.input_weight
        if weekday in weekday_stats:
            weekday_stats[weekday]["count"] += 1

    hour_stats_list = []
    weekday_stats_list = []
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
            bar_colors.append('rgba(54, 162, 235, 0.7)')
        elif 13 <= h <= 22:
            bar_colors.append('rgba(255, 206, 86, 0.7)')
        elif h > 22 or h <= 7:
            bar_colors.append('rgba(255, 99, 132, 0.7)')
        else:
            bar_colors.append('rgba(200,200,200,0.3)')

    for wd in [0, 1, 2, 3, 4]:
        row = weekday_stats[wd]
        weekday_stats_list.append(
            {
                "label": row["label"],
                "count": row["count"],
                "kg": float(row["kg"]),
            }
        )

    top10_labels = [row.get("operator_name", "-") for row in top10_operators]
    top10_count_data = [int(row.get("total_count") or 0) for row in top10_operators]
    top10_kg_data = [float(row.get("total_kg") or 0) for row in top10_operators]

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
        'hour_stats_list': hour_stats_list,
        'weekday_stats_list': weekday_stats_list,
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
    # Giữ nguyên dữ liệu 入庫 thực tế.
    # Hàm cũ từng xóa toàn bộ dòng có auto_input_ledger, gây mất dữ liệu nhập kho.
    return


def _sync_material_out_stock_rows(limit=300):
    deleted_job_ids = QADeletedJobMarker.objects.values_list("job_id", flat=True)
    ledgers = (
        QAAutoInputLedger.objects.select_related("qa_result__device")
        .filter(job_status="done", qa_result__isnull=False)
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
        bag_count = _calculate_bag_count_by_material_code(material_code, weight_kg)
        mgmt_no = ledger.ma_nhap_lieu or ledger.job_id or ""
        product_code = (
            ((qa_result.product_code or "").strip() if qa_result else "")
            or ((device.product_management_code or "").strip() if device else "")
        )

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
                    "bag_sequence_no": bag_count,
                    "lot_number": (qa_result.lot_number if qa_result else ""),
                    "product_code": product_code,
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
        if not row.bag_sequence_no and bag_count:
            row.bag_sequence_no = bag_count
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
        if product_code and row.product_code != product_code:
            row.product_code = product_code
            changed = True

        if changed:
            row.save()


@login_required
def material_stock_ledger(request):
    state_redirect = _restore_or_store_ledger_query(
        request,
        view_name="material_stock_ledger",
        session_key=LEDGER_STATE_STOCK_IN_SESSION_KEY,
    )
    if state_redirect:
        return state_redirect

    qs = QAMaterialStockLedger.objects.all()
    keyword = request.GET.get("keyword", "").strip()
    date = request.GET.get("date", "").strip()
    confirmed = request.GET.get("confirmed", "").strip()

    if keyword:
        qs = qs.filter(
            Q(material_name__icontains=keyword)
            | Q(material_code__icontains=keyword)
            | Q(hinmei_name__icontains=keyword)
            | Q(lot_number__icontains=keyword)
            | Q(order_no__icontains=keyword)
            | Q(workstation_management_no__icontains=keyword)
            | Q(operator_name__icontains=keyword)
            | Q(transaction_type__icontains=keyword)
            | Q(adjustment_reason_code__icontains=keyword)
            | Q(adjustment_reason__icontains=keyword)
            | Q(adjustment_note__icontains=keyword)
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

    paginator = Paginator(qs.order_by("-stock_in_date", "-id"), 10)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)
    page_range = paginator.get_elided_page_range(
        number=page_obj.number,
        on_each_side=1,
        on_ends=1,
    )
    page_query_prefix = urlencode({
        "keyword": keyword,
        "date": date,
        "confirmed": confirmed,
    }) + "&"

    return render(
        request,
        "quet_anh/material_stock_ledger.html",
        {
            "rows": page_obj,
            "page_obj": page_obj,
            "page_range": page_range,
            "page_query_prefix": page_query_prefix,
            "keyword": keyword,
            "date": date,
            "confirmed": confirmed,
            "can_supervisor_confirm": _can_supervisor_confirm(request.user),
            "can_inventory_adjust": _can_inventory_adjust(request.user),
            "iatf_adjustment_reason_labels": IATF_ADJUSTMENT_REASON_LABELS,
        },
    )


@login_required
def material_stock_ledger_csv(request):
    qs = QAMaterialStockLedger.objects.all()
    keyword = request.GET.get("keyword", "").strip()
    date = request.GET.get("date", "").strip()
    confirmed = request.GET.get("confirmed", "").strip()

    if keyword:
        qs = qs.filter(
            Q(material_name__icontains=keyword)
            | Q(material_code__icontains=keyword)
            | Q(hinmei_name__icontains=keyword)
            | Q(lot_number__icontains=keyword)
            | Q(order_no__icontains=keyword)
            | Q(workstation_management_no__icontains=keyword)
            | Q(operator_name__icontains=keyword)
            | Q(transaction_type__icontains=keyword)
            | Q(adjustment_reason_code__icontains=keyword)
            | Q(adjustment_reason__icontains=keyword)
            | Q(adjustment_note__icontains=keyword)
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

    response, writer = _iatf_csv_response(
        f"iatf_stock_in_{timezone.localdate().strftime('%Y%m%d')}.csv",
        "原材料入庫台帳",
        request,
    )
    writer.writerow([
        "ID", "原材料名", "原材料コード", "入庫日", "登録日時", "重量kg", "袋数", "識別色",
        "取引区分", "ADJ理由", "ADJメモ", "調整前kg", "調整後kg",
        "品名", "ロット番号", "注文No.", "システムNo.", "作業者",
        "承認状態", "承認者", "承認日時",
    ])
    for row in qs.order_by("-stock_in_date", "-id"):
        writer.writerow([
            row.id,
            row.material_name,
            _csv_text(row.material_code),
            _csv_value(row.stock_in_date),
            _csv_value(row.created_at),
            row.weight_kg,
            row.bag_sequence_no,
            row.get_lot_color_display(),
            _transaction_label(row.transaction_type),
            _reason_label(row.adjustment_reason_code),
            row.adjustment_reason or row.adjustment_note,
            row.stock_before_kg,
            row.stock_after_kg,
            row.hinmei_name,
            row.lot_number,
            row.order_no,
            row.workstation_management_no,
            row.operator_name or (row.qa_result.operator_name if row.qa_result else ""),
            "承認済" if row.supervisor_confirmed else "未承認",
            row.supervisor_name,
            _csv_value(row.supervisor_confirmed_at),
        ])
    return response


@login_required
def material_out_stock_ledger(request):
    state_redirect = _restore_or_store_ledger_query(
        request,
        view_name="material_out_stock_ledger",
        session_key=LEDGER_STATE_STOCK_OUT_SESSION_KEY,
    )
    if state_redirect:
        return state_redirect

    _sync_material_out_stock_rows(limit=500)

    qs = QAMaterialOutStockLedger.objects.filter(
        Q(auto_input_ledger__job_status="done") | Q(auto_input_ledger__isnull=True)
    )
    keyword = request.GET.get("keyword", "").strip()
    date = request.GET.get("date", "").strip()
    confirmed = request.GET.get("confirmed", "").strip()

    if keyword:
        qs = qs.filter(
            Q(material_name__icontains=keyword)
            | Q(material_code__icontains=keyword)
            | Q(lot_number__icontains=keyword)
            | Q(product_code__icontains=keyword)
            | Q(workstation_management_no__icontains=keyword)
            | Q(operator_name__icontains=keyword)
            | Q(transaction_type__icontains=keyword)
            | Q(adjustment_reason_code__icontains=keyword)
            | Q(adjustment_reason__icontains=keyword)
            | Q(adjustment_note__icontains=keyword)
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

    paginator = Paginator(qs.order_by("-stock_out_date", "-id"), 10)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)
    page_range = paginator.get_elided_page_range(
        number=page_obj.number,
        on_each_side=1,
        on_ends=1,
    )
    page_query_prefix = urlencode({
        "keyword": keyword,
        "date": date,
        "confirmed": confirmed,
    }) + "&"

    return render(
        request,
        "quet_anh/material_out_stock_ledger.html",
        {
            "rows": page_obj,
            "page_obj": page_obj,
            "page_range": page_range,
            "page_query_prefix": page_query_prefix,
            "keyword": keyword,
            "date": date,
            "confirmed": confirmed,
            "can_supervisor_confirm": _can_supervisor_confirm(request.user),
            "can_inventory_adjust": _can_inventory_adjust(request.user),
            "iatf_adjustment_reason_labels": IATF_ADJUSTMENT_REASON_LABELS,
        },
    )


@login_required
def material_out_stock_ledger_csv(request):
    _sync_material_out_stock_rows(limit=500)
    qs = QAMaterialOutStockLedger.objects.filter(
        Q(auto_input_ledger__job_status="done") | Q(auto_input_ledger__isnull=True)
    )
    keyword = request.GET.get("keyword", "").strip()
    date = request.GET.get("date", "").strip()
    confirmed = request.GET.get("confirmed", "").strip()

    if keyword:
        qs = qs.filter(
            Q(material_name__icontains=keyword)
            | Q(material_code__icontains=keyword)
            | Q(lot_number__icontains=keyword)
            | Q(product_code__icontains=keyword)
            | Q(workstation_management_no__icontains=keyword)
            | Q(operator_name__icontains=keyword)
            | Q(transaction_type__icontains=keyword)
            | Q(adjustment_reason_code__icontains=keyword)
            | Q(adjustment_reason__icontains=keyword)
            | Q(adjustment_note__icontains=keyword)
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

    response, writer = _iatf_csv_response(
        f"iatf_stock_out_{timezone.localdate().strftime('%Y%m%d')}.csv",
        "原材料出庫台帳",
        request,
    )
    writer.writerow([
        "ID", "原材料名", "原材料コード", "出庫日", "登録日時", "重量kg", "袋数", "識別色",
        "取引区分", "ADJ理由", "ADJメモ", "調整前kg", "調整後kg",
        "ロット番号", "製品コード", "システムNo.", "作業者",
        "承認状態", "承認者", "承認日時",
    ])
    for row in qs.order_by("-stock_out_date", "-id"):
        writer.writerow([
            row.id,
            row.material_name,
            _csv_text(row.material_code),
            _csv_value(row.stock_out_date),
            _csv_value(row.created_at),
            row.weight_kg,
            row.bag_sequence_no,
            row.get_lot_color_display(),
            _transaction_label(row.transaction_type),
            _reason_label(row.adjustment_reason_code),
            row.adjustment_reason or row.adjustment_note,
            row.stock_before_kg,
            row.stock_after_kg,
            row.lot_number,
            row.product_code,
            row.workstation_management_no,
            row.operator_name or (row.qa_result.operator_name if row.qa_result else ""),
            "承認済" if row.supervisor_confirmed else "未承認",
            row.supervisor_name,
            _csv_value(row.supervisor_confirmed_at),
        ])
    return response


@login_required
def material_inventory_dashboard(request):
    keyword = (request.GET.get("keyword") or "").strip()
    status_filter = (request.GET.get("status") or "").strip().lower()
    try:
        low_stock_threshold = Decimal(str(request.GET.get("low_stock_threshold") or "0") or "0")
    except (InvalidOperation, ValueError, TypeError):
        low_stock_threshold = Decimal("0")

    in_rows = (
        QAMaterialStockLedger.objects.values("material_code", "material_name")
        .annotate(
            total_in_kg=Sum("weight_kg"),
            total_in_bags=Count("id"),
            last_in_date=Max("stock_in_date"),
        )
    )
    out_rows = (
        QAMaterialOutStockLedger.objects.values("material_code", "material_name")
        .annotate(
            total_out_kg=Sum("weight_kg"),
            total_out_bags=Count("id"),
            last_out_date=Max("stock_out_date"),
        )
    )
    master_rows = list(
        QAMaterialMaster.objects.values(
            "material_code", "material_name", "bag_weight_kg", "is_active"
        )
    )

    by_code = {}
    active_codes = {
        (row.get("material_code") or "").strip()
        for row in master_rows
        if (row.get("material_code") or "").strip() and row.get("is_active")
    }

    def _ensure_row(code, name="", *, bag_weight=None, is_active=True):
        key = (code or "").strip()
        if not key:
            return None
        if key not in by_code:
            by_code[key] = {
                "material_code": key,
                "material_name": (name or "").strip(),
                "bag_weight_kg": bag_weight,
                "is_active": bool(is_active),
                "total_in_kg": Decimal("0"),
                "total_out_kg": Decimal("0"),
                "total_in_bags": 0,
                "total_out_bags": 0,
                "last_in_date": None,
                "last_out_date": None,
            }
        else:
            if name and not by_code[key]["material_name"]:
                by_code[key]["material_name"] = (name or "").strip()
            if bag_weight is not None:
                by_code[key]["bag_weight_kg"] = bag_weight
            by_code[key]["is_active"] = bool(is_active)
        return by_code[key]

    if active_codes:
        for row in master_rows:
            code = (row.get("material_code") or "").strip()
            if code in active_codes:
                _ensure_row(
                    code,
                    row.get("material_name"),
                    bag_weight=row.get("bag_weight_kg"),
                    is_active=row.get("is_active"),
                )
    else:
        # Fallback: if master empty, allow any codes from ledgers.
        active_codes = set()

    for row in in_rows:
        code = (row.get("material_code") or "").strip()
        if active_codes and code not in active_codes:
            continue
        r = _ensure_row(code, row.get("material_name"))
        if not r:
            continue
        r["total_in_kg"] = row.get("total_in_kg") or Decimal("0")
        r["total_in_bags"] = int(row.get("total_in_bags") or 0)
        r["last_in_date"] = row.get("last_in_date")

    for row in out_rows:
        code = (row.get("material_code") or "").strip()
        if active_codes and code not in active_codes:
            continue
        r = _ensure_row(code, row.get("material_name"))
        if not r:
            continue
        r["total_out_kg"] = row.get("total_out_kg") or Decimal("0")
        r["total_out_bags"] = int(row.get("total_out_bags") or 0)
        r["last_out_date"] = row.get("last_out_date")

    for row in master_rows:
        r = _ensure_row(row.get("material_code"), row.get("material_name"))
        r["bag_weight_kg"] = row.get("bag_weight_kg")
        r["is_active"] = bool(row.get("is_active"))

    items = []
    total_in_kg = Decimal("0")
    total_out_kg = Decimal("0")
    total_stock_kg = Decimal("0")
    total_stock_bags = 0
    negative_count = 0
    low_count = 0

    for _, row in by_code.items():
        material_code = row["material_code"]
        material_name = row["material_name"] or "未設定"
        total_in = row["total_in_kg"] or Decimal("0")
        total_out = row["total_out_kg"] or Decimal("0")
        stock = total_in - total_out
        movement_count = int(row.get("total_in_bags") or 0) + int(row.get("total_out_bags") or 0)
        movement_kg = total_in + total_out
        bag_weight = row.get("bag_weight_kg")

        safety_stock_kg = Decimal("0")
        reorder_point_kg = Decimal("0")
        if bag_weight:
            safety_stock_kg = bag_weight * Decimal("5")
            reorder_point_kg = bag_weight * Decimal("10")
        if low_stock_threshold > 0:
            reorder_point_kg = low_stock_threshold
            safety_stock_kg = low_stock_threshold / Decimal("2")

        if stock < 0:
            status = "danger"
            status_label = "不足"
            negative_count += 1
        elif reorder_point_kg > 0 and stock <= safety_stock_kg:
            status = "critical"
            status_label = "要補充"
            low_count += 1
        elif reorder_point_kg > 0 and stock <= reorder_point_kg:
            status = "warning"
            status_label = "注意"
            low_count += 1
        else:
            status = "ok"
            status_label = "正常"

        searchable = f"{material_code} {material_name}".lower()
        if keyword and keyword.lower() not in searchable:
            continue
        if status_filter and status_filter != status:
            continue

        total_in_kg += total_in
        total_out_kg += total_out
        total_stock_kg += stock
        total_in_bags_calc = _calculate_bag_count(total_in, bag_weight) if bag_weight else ""
        total_out_bags_calc = _calculate_bag_count(total_out, bag_weight) if bag_weight else ""
        current_bags_calc = _calculate_bag_count(stock, bag_weight) if bag_weight and stock > 0 else ("0" if bag_weight else "")
        if str(current_bags_calc).isdigit():
            total_stock_bags += int(current_bags_calc)

        items.append(
            {
                **row,
                "material_code": material_code,
                "material_name": material_name,
                "current_stock_kg": stock,
                "movement_count": movement_count,
                "movement_kg": movement_kg,
                "status": status,
                "status_label": status_label,
                "safety_stock_kg": safety_stock_kg,
                "reorder_point_kg": reorder_point_kg,
                "current_bag_count": current_bags_calc,
                "total_in_bag_count": total_in_bags_calc,
                "total_out_bag_count": total_out_bags_calc,
            }
        )

    items.sort(
        key=lambda x: (
            -x["current_stock_kg"],
            -x["movement_count"],
            -x["movement_kg"],
            x["material_name"],
        )
    )
    paginator = Paginator(items, 10)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)
    page_range = paginator.get_elided_page_range(
        number=page_obj.number,
        on_each_side=1,
        on_ends=1,
    )
    page_query_prefix = urlencode({
        "keyword": keyword,
        "status": status_filter,
        "low_stock_threshold": low_stock_threshold,
    }) + "&"

    context = {
        "rows": page_obj,
        "page_obj": page_obj,
        "page_range": page_range,
        "page_query_prefix": page_query_prefix,
        "keyword": keyword,
        "status": status_filter,
        "low_stock_threshold": low_stock_threshold,
        "total_materials": len(items),
        "total_in_kg": total_in_kg,
        "total_out_kg": total_out_kg,
        "total_stock_kg": total_stock_kg,
        "total_stock_bags": total_stock_bags,
        "negative_count": negative_count,
        "low_count": low_count,
        "can_inventory_adjust": _can_inventory_adjust(request.user),
        "adjustment_reason_choices": QAMaterialStockLedger.ADJUST_REASON_CHOICES,
    }
    return render(request, "quet_anh/material_inventory_dashboard.html", context)


@login_required
def material_inventory_csv(request):
    keyword = (request.GET.get("keyword") or "").strip()
    status_filter = (request.GET.get("status") or "").strip().lower()
    try:
        low_stock_threshold = Decimal(str(request.GET.get("low_stock_threshold") or "0") or "0")
    except (InvalidOperation, ValueError, TypeError):
        low_stock_threshold = Decimal("0")

    in_rows = QAMaterialStockLedger.objects.values("material_code", "material_name").annotate(
        total_in_kg=Sum("weight_kg"),
        total_in_bags=Count("id"),
        last_in_date=Max("stock_in_date"),
    )
    out_rows = QAMaterialOutStockLedger.objects.values("material_code", "material_name").annotate(
        total_out_kg=Sum("weight_kg"),
        total_out_bags=Count("id"),
        last_out_date=Max("stock_out_date"),
    )
    master_rows = list(QAMaterialMaster.objects.values("material_code", "material_name", "bag_weight_kg", "is_active"))
    active_codes = {
        (row.get("material_code") or "").strip()
        for row in master_rows
        if (row.get("material_code") or "").strip() and row.get("is_active")
    }

    by_code = {}

    def ensure_row(code, name="", bag_weight=None, is_active=True):
        key = (code or "").strip()
        if not key:
            return None
        row = by_code.setdefault(
            key,
            {
                "material_code": key,
                "material_name": (name or "").strip(),
                "bag_weight_kg": bag_weight,
                "is_active": bool(is_active),
                "total_in_kg": Decimal("0"),
                "total_out_kg": Decimal("0"),
                "total_in_bags": 0,
                "total_out_bags": 0,
                "last_in_date": None,
                "last_out_date": None,
            },
        )
        if name and not row["material_name"]:
            row["material_name"] = (name or "").strip()
        if bag_weight is not None:
            row["bag_weight_kg"] = bag_weight
        row["is_active"] = bool(is_active)
        return row

    for row in master_rows:
        code = (row.get("material_code") or "").strip()
        if not active_codes or code in active_codes:
            ensure_row(code, row.get("material_name"), row.get("bag_weight_kg"), row.get("is_active"))
    for row in in_rows:
        code = (row.get("material_code") or "").strip()
        if active_codes and code not in active_codes:
            continue
        item = ensure_row(code, row.get("material_name"))
        if item:
            item["total_in_kg"] = row.get("total_in_kg") or Decimal("0")
            item["total_in_bags"] = int(row.get("total_in_bags") or 0)
            item["last_in_date"] = row.get("last_in_date")
    for row in out_rows:
        code = (row.get("material_code") or "").strip()
        if active_codes and code not in active_codes:
            continue
        item = ensure_row(code, row.get("material_name"))
        if item:
            item["total_out_kg"] = row.get("total_out_kg") or Decimal("0")
            item["total_out_bags"] = int(row.get("total_out_bags") or 0)
            item["last_out_date"] = row.get("last_out_date")

    response, writer = _iatf_csv_response(
        f"iatf_inventory_{timezone.localdate().strftime('%Y%m%d')}.csv",
        "原材料在庫一覧",
        request,
    )
    writer.writerow([
        "原材料名", "原材料コード", "現在庫kg", "現在庫袋数", "入庫合計kg", "入庫合計袋数",
        "出庫合計kg", "出庫合計袋数", "安全在庫kg", "発注点kg", "状態",
        "最終入庫日", "最終出庫日", "有効マスター",
    ])

    rows = []
    for row in by_code.values():
        material_code = row["material_code"]
        material_name = row["material_name"] or "未設定"
        total_in = row["total_in_kg"] or Decimal("0")
        total_out = row["total_out_kg"] or Decimal("0")
        stock = total_in - total_out
        movement_count = int(row.get("total_in_bags") or 0) + int(row.get("total_out_bags") or 0)
        movement_kg = total_in + total_out
        bag_weight = row.get("bag_weight_kg")
        safety_stock_kg = Decimal("0")
        reorder_point_kg = Decimal("0")
        if bag_weight:
            safety_stock_kg = bag_weight * Decimal("5")
            reorder_point_kg = bag_weight * Decimal("10")
        if low_stock_threshold > 0:
            reorder_point_kg = low_stock_threshold
            safety_stock_kg = low_stock_threshold / Decimal("2")
        if stock < 0:
            status = "danger"
            status_label = "不足"
        elif reorder_point_kg > 0 and stock <= safety_stock_kg:
            status = "critical"
            status_label = "要補充"
        elif reorder_point_kg > 0 and stock <= reorder_point_kg:
            status = "warning"
            status_label = "注意"
        else:
            status = "ok"
            status_label = "正常"
        if keyword and keyword.lower() not in f"{material_code} {material_name}".lower():
            continue
        if status_filter and status_filter != status:
            continue
        rows.append((stock, movement_count, movement_kg, material_name, {
            **row,
            "material_name": material_name,
            "current_stock_kg": stock,
            "current_bag_count": _calculate_bag_count(stock, bag_weight) if bag_weight and stock > 0 else ("0" if bag_weight else ""),
            "total_in_bag_count": _calculate_bag_count(total_in, bag_weight) if bag_weight else "",
            "total_out_bag_count": _calculate_bag_count(total_out, bag_weight) if bag_weight else "",
            "safety_stock_kg": safety_stock_kg,
            "reorder_point_kg": reorder_point_kg,
            "status_label": status_label,
        }))
    for _stock, _movement_count, _movement_kg, _name, row in sorted(
        rows,
        key=lambda item: (-item[0], -item[1], -item[2], item[3]),
    ):
        writer.writerow([
            row["material_name"],
            _csv_text(row["material_code"]),
            row["current_stock_kg"],
            row["current_bag_count"],
            row["total_in_kg"],
            row["total_in_bag_count"],
            row["total_out_kg"],
            row["total_out_bag_count"],
            row["safety_stock_kg"],
            row["reorder_point_kg"],
            row["status_label"],
            _csv_value(row["last_in_date"]),
            _csv_value(row["last_out_date"]),
            "有効" if row["is_active"] else "無効",
        ])
    return response


def _get_material_current_stock_kg(material_code: str) -> Decimal:
    code = (material_code or "").strip()
    if not code:
        return Decimal("0")
    total_in = (
        QAMaterialStockLedger.objects.filter(material_code=code)
        .aggregate(total=Sum("weight_kg"))
        .get("total")
        or Decimal("0")
    )
    total_out = (
        QAMaterialOutStockLedger.objects.filter(material_code=code)
        .aggregate(total=Sum("weight_kg"))
        .get("total")
        or Decimal("0")
    )
    return total_in - total_out


@login_required
@require_POST
def material_inventory_adjust(request):
    if not _can_inventory_adjust(request.user):
        messages.error(request, "在庫調整はスーパーユーザーのみ実行できます。")
        return redirect("material_inventory_dashboard")

    material_code = (request.POST.get("material_code") or "").strip()
    mode = (request.POST.get("adjust_mode") or "target").strip().lower()
    reason_code = (request.POST.get("reason_code") or "").strip()
    reason = (request.POST.get("reason") or "").strip()
    redirect_url = request.POST.get("next") or reverse("material_inventory_dashboard")
    if not redirect_url.startswith("/") or redirect_url.startswith("//"):
        redirect_url = reverse("material_inventory_dashboard")

    master = QAMaterialMaster.objects.filter(material_code=material_code, is_active=True).first()
    if not master:
        messages.error(request, "調整対象の原材料マスターが見つかりません。")
        return HttpResponseRedirect(redirect_url)

    valid_reason_codes = {code for code, _label in QAMaterialStockLedger.ADJUST_REASON_CHOICES}
    if not reason:
        reason = IATF_ADJUSTMENT_REASON_LABELS.get(reason_code, reason_code)
    if reason_code not in valid_reason_codes:
        messages.error(request, "IATF監査用の調整理由を選択してください。")
        return HttpResponseRedirect(redirect_url)
    if not reason:
        messages.error(request, "IATF監査用の調整理由メモを入力してください。")
        return HttpResponseRedirect(redirect_url)

    try:
        current_stock = _get_material_current_stock_kg(material_code)
        if mode == "delta":
            delta = Decimal(str(request.POST.get("delta_kg") or "0")).quantize(Decimal("0.01"))
        else:
            target_stock = Decimal(str(request.POST.get("target_stock_kg") or "0")).quantize(Decimal("0.01"))
            delta = (target_stock - current_stock).quantize(Decimal("0.01"))
    except (InvalidOperation, ValueError, TypeError):
        messages.error(request, "調整重量を正しく入力してください。")
        return HttpResponseRedirect(redirect_url)

    if delta == 0:
        messages.info(request, "差分が0kgのため、調整データは作成しませんでした。")
        return HttpResponseRedirect(redirect_url)

    now = timezone.localtime()
    operator_name = _display_login_name(request.user) or "superuser"
    note = reason or "在庫調整"
    management_no = f"ADJ-{now.strftime('%Y%m%d%H%M%S')}"
    weight = abs(delta)
    bag_count = _calculate_bag_count_by_material_code(material_code, weight) or "ADJ"
    reason_label = IATF_ADJUSTMENT_REASON_LABELS.get(reason_code, reason_code)
    note = f"{reason_label}: {reason}"
    stock_before = current_stock.quantize(Decimal("0.01"))
    stock_after = (current_stock + delta).quantize(Decimal("0.01"))

    with transaction.atomic():
        if delta > 0:
            QAMaterialStockLedger.objects.create(
                auto_input_ledger=None,
                qa_result=None,
                material_name=master.material_name or "",
                material_code=material_code,
                stock_in_date=timezone.localdate(),
                lot_color=QAMaterialStockLedger.LOT_COLOR_GREEN,
                weight_kg=weight,
                bag_sequence_no=str(bag_count),
                lot_number="ADJ",
                hinmei_name=note,
                order_no="ADJ",
                workstation_management_no=management_no,
                operator_name=operator_name,
                transaction_type=QAMaterialStockLedger.TRANSACTION_ADJ_POS,
                adjustment_reason_code=reason_code,
                adjustment_reason=reason,
                adjustment_note=note,
                stock_before_kg=stock_before,
                stock_after_kg=stock_after,
                supervisor_confirmed=True,
                supervisor_name=operator_name,
                supervisor_confirmed_at=now,
            )
            direction = "入庫"
        else:
            QAMaterialOutStockLedger.objects.create(
                auto_input_ledger=None,
                qa_result=None,
                material_name=master.material_name or "",
                material_code=material_code,
                stock_out_date=timezone.localdate(),
                lot_color=QAMaterialOutStockLedger.LOT_COLOR_GREEN,
                weight_kg=weight,
                bag_sequence_no=str(bag_count),
                lot_number="ADJ",
                product_code="ADJ",
                workstation_management_no=management_no,
                operator_name=operator_name,
                transaction_type=QAMaterialOutStockLedger.TRANSACTION_ADJ_NEG,
                adjustment_reason_code=reason_code,
                adjustment_reason=reason,
                adjustment_note=note,
                stock_before_kg=stock_before,
                stock_after_kg=stock_after,
                supervisor_confirmed=True,
                supervisor_name=operator_name,
                supervisor_confirmed_at=now,
            )
            direction = "出庫"

    messages.success(
        request,
        f"{master.material_name} ({material_code}) の在庫調整を登録しました: {direction} {weight}kg / {management_no}",
    )
    return HttpResponseRedirect(redirect_url)


@login_required
def material_stock_ledger_edit(request, pk):
    if not _can_inventory_adjust(request.user):
        messages.error(request, "在庫データの編集権限がありません。")
        return redirect("material_stock_ledger")
    row = get_object_or_404(QAMaterialStockLedger, pk=pk)

    if request.method == "POST":
        form = QAMaterialStockLedgerForm(request.POST, instance=row)
        if form.is_valid():
            form.save()
            messages.success(request, "原材料入庫台帳を更新しました。")
            return _safe_next_redirect(request, "material_stock_ledger")
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
    if not _can_inventory_adjust(request.user):
        messages.error(request, "在庫データの編集権限がありません。")
        return redirect("material_out_stock_ledger")
    row = get_object_or_404(QAMaterialOutStockLedger, pk=pk)

    if request.method == "POST":
        form = QAMaterialOutStockLedgerForm(request.POST, instance=row)
        if form.is_valid():
            form.save()
            messages.success(request, "原材料出庫台帳を更新しました。")
            return _safe_next_redirect(request, "material_out_stock_ledger")
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
    if not _can_inventory_adjust(request.user):
        messages.error(request, "在庫データの削除権限がありません。")
        return redirect("material_stock_ledger")
    row = get_object_or_404(QAMaterialStockLedger, pk=pk)
    messages.error(request, "IATF audit control: hard delete is disabled. Keep the record and create a correction/ADJ entry instead.")
    return redirect("material_stock_ledger")
    if row.auto_input_ledger_id:
        linked = row.auto_input_ledger
        QADeletedJobMarker.objects.get_or_create(
            job_id=linked.job_id,
            defaults={"note": "削除操作: 原材料入庫台帳"},
        )
        QAMaterialOutStockLedger.objects.filter(auto_input_ledger=linked).delete()
        row.delete()
        linked.delete()
        messages.success(request, "入庫台帳データを削除しました。")
        return redirect("material_stock_ledger")
    row.delete()
    messages.success(request, "入庫台帳データを削除しました。")
    return redirect("material_stock_ledger")


@login_required
@require_POST
def material_out_stock_ledger_delete(request, pk):
    if not _can_inventory_adjust(request.user):
        messages.error(request, "在庫データの削除権限がありません。")
        return redirect("material_out_stock_ledger")
    row = get_object_or_404(QAMaterialOutStockLedger, pk=pk)
    messages.error(request, "IATF audit control: hard delete is disabled. Keep the record and create a correction/ADJ entry instead.")
    return redirect("material_out_stock_ledger")
    if row.auto_input_ledger_id:
        linked = row.auto_input_ledger
        QADeletedJobMarker.objects.get_or_create(
            job_id=linked.job_id,
            defaults={"note": "削除操作: 原材料出庫台帳"},
        )
        QAMaterialStockLedger.objects.filter(auto_input_ledger=linked).delete()
        row.delete()
        linked.delete()
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
    return _safe_next_redirect(request, "material_stock_ledger")


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
    return _safe_next_redirect(request, "material_out_stock_ledger")


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
            "title": res.device.product_name if res.device and res.device.product_name else (res.device.name if res.device else "未設定"),
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
    """
    Chỉ dọn dữ liệu xuất kho bị lạc liên kết.
    Không đụng dữ liệu nhập kho (qa_result có thể null hợp lệ).
    """
    QAMaterialOutStockLedger.objects.filter(auto_input_ledger__qa_result__isnull=True).delete()


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
            ledger.qa_product = qa_result.device.product_name if qa_result.device else ""
            ledger.qa_ratio = qa_result.device.ratio if qa_result.device else ""
            ledger.qa_operator_name = qa_result.operator_name or ""
            ledger.qa_result_status = qa_result.result or ""
            ledger.qa_match_ratio = qa_result.match_ratio
            ledger.qa_input_weight = qa_result.input_weight

        ledger.save()


@login_required
def auto_input_ledger_list(request):
    return redirect("material_out_stock_ledger")
