from decimal import Decimal, ROUND_CEILING

from django.core.mail import send_mail
from django.db.models import Sum
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone

from nhap_lieu.models import KetQuaNhapLieu, PhienNhapLieu

from .models import QAAutoInputLedger, QAResult, QAMaterialMaster, QAMaterialStockLedger, QAMaterialOutStockLedger, QADeletedJobMarker


LOW_STOCK_ALERT_RECIPIENTS = [
    "k_arita@hayashi-p.co.jp",
    "t_miyasaka@hayashi-p.co.jp",
    "giang@hayashi-p.co.jp",
    "seisan_kanri@hayashi-p.co.jp",
]


def _find_qa_result_for_phien(phien):
    # Liên kết chặt: chỉ nhận qa_result được gắn trực tiếp.
    if getattr(phien, "qa_result_id", None):
        return phien.qa_result
    return None


def _calculate_bag_count_by_material_code(material_code, weight_kg):
    code = (material_code or "").strip()
    if not code:
        return ""
    master = QAMaterialMaster.objects.filter(material_code=code).first()
    if not master or master.bag_weight_kg is None:
        return ""
    try:
        weight = Decimal(weight_kg)
        bag_weight = Decimal(master.bag_weight_kg)
    except Exception:
        return ""
    if weight <= 0 or bag_weight <= 0:
        return ""
    count = (weight / bag_weight).to_integral_value(rounding=ROUND_CEILING)
    if count < 1:
        count = Decimal("1")
    return str(int(count))


def _decimal_or_zero(value):
    try:
        return Decimal(value or 0)
    except Exception:
        return Decimal("0")


def _get_current_stock_kg(material_code):
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
    return Decimal(total_in) - Decimal(total_out)


def _send_low_stock_alert_if_needed(row):
    if not row or row.low_stock_alert_sent_at:
        return

    material_code = (row.material_code or "").strip()
    if not material_code:
        return

    master = QAMaterialMaster.objects.filter(material_code=material_code, is_active=True).first()
    if not master or not master.bag_weight_kg:
        return

    bag_weight = _decimal_or_zero(master.bag_weight_kg)
    if bag_weight <= 0:
        return

    safety_stock = (bag_weight * Decimal("5")).quantize(Decimal("0.01"))
    current_stock = _get_current_stock_kg(material_code).quantize(Decimal("0.01"))
    last_out_weight = _decimal_or_zero(row.weight_kg)
    stock_before_this_out = (current_stock + last_out_weight).quantize(Decimal("0.01"))

    if not (stock_before_this_out > safety_stock and current_stock <= safety_stock):
        return

    operator_name = (
        (row.operator_name or "").strip()
        or (row.qa_result.operator_name if row.qa_result and row.qa_result.operator_name else "")
        or "-"
    )
    material_name = (row.material_name or "").strip() or (master.material_name or "").strip() or "未設定"
    stock_out_date = row.stock_out_date.strftime("%Y-%m-%d") if row.stock_out_date else "-"
    created_at = timezone.localtime(row.created_at).strftime("%Y-%m-%d %H:%M:%S") if row.created_at else "-"

    subject = f"【安全在庫アラート】{material_name} が安全在庫以下です"
    message = (
        "原材料の現在庫が安全在庫以下になりました。確認をお願いします。\n\n"
        f"原材料名: {material_name}\n"
        f"原材料コード: {material_code}\n"
        f"現在庫: {current_stock} kg\n"
        f"安全在庫: {safety_stock} kg（1袋 {bag_weight} kg × 5袋）\n"
        f"今回出庫量: {last_out_weight} kg\n"
        f"出庫前在庫: {stock_before_this_out} kg\n\n"
        f"最後の出庫日: {stock_out_date}\n"
        f"最後の出庫登録日時: {created_at}\n"
        f"最後に出庫した作業者: {operator_name}\n"
        f"ロット番号: {row.lot_number or '-'}\n"
        f"システムNo.: {row.workstation_management_no or '-'}\n\n"
        "在庫管理画面で補充要否を確認してください。\n"
    )

    sent_count = send_mail(
        subject,
        message,
        None,
        LOW_STOCK_ALERT_RECIPIENTS,
        fail_silently=True,
    )
    if sent_count:
        QAMaterialOutStockLedger.objects.filter(pk=row.pk, low_stock_alert_sent_at__isnull=True).update(
            low_stock_alert_sent_at=timezone.now()
        )


def _sync_ledger_from_phien(phien):
    if QADeletedJobMarker.objects.filter(job_id=phien.ma_job).exists():
        QAAutoInputLedger.objects.filter(phien_nhap_lieu=phien).delete()
        return

    # Chỉ lưu sổ cái job khi job đã hoàn thành thành công
    if (phien.trang_thai or "") != "done":
        QAAutoInputLedger.objects.filter(phien_nhap_lieu=phien).delete()
        return

    ledger, _ = QAAutoInputLedger.objects.get_or_create(
        phien_nhap_lieu=phien,
        defaults={"job_id": phien.ma_job},
    )

    qa_result = ledger.qa_result or _find_qa_result_for_phien(phien)
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


def _sync_material_stock_from_ledger(ledger):
    # Luồng hiện tại chỉ vận hành 出庫 (xuất kho).
    # Không tạo dữ liệu 入庫 (nhập kho) từ job auto input để tránh trùng sổ cái.
    QAMaterialStockLedger.objects.filter(auto_input_ledger=ledger).delete()
    return

    # Giữ code cũ phía dưới để tiện bật lại khi triển khai luồng 入庫 thực tế.
    if QADeletedJobMarker.objects.filter(job_id=ledger.job_id).exists():
        QAMaterialStockLedger.objects.filter(auto_input_ledger=ledger).delete()
        return

    if (ledger.job_status or "") != "done":
        QAMaterialStockLedger.objects.filter(auto_input_ledger=ledger).delete()
        return

    qa_result = ledger.qa_result
    device = qa_result.device if qa_result and qa_result.device else None
    source_date = qa_result.created_at if qa_result else ledger.created_at
    stock_in_date = timezone.localtime(source_date).date()

    material_name = (device.material if device else "") or ledger.qa_material or ""
    material_code = (device.material_code if device else "") or ""
    weight_kg = qa_result.input_weight if qa_result and qa_result.input_weight is not None else ledger.qa_input_weight
    bag_count = _calculate_bag_count_by_material_code(material_code, weight_kg)
    mgmt_no = ledger.ma_nhap_lieu or ledger.job_id or ""

    row, created = QAMaterialStockLedger.objects.get_or_create(
        auto_input_ledger=ledger,
        defaults={
            "qa_result": qa_result,
            "material_name": material_name,
            "material_code": material_code,
            "stock_in_date": stock_in_date,
            "lot_color": QAMaterialStockLedger.LOT_COLOR_GREEN,
            "weight_kg": weight_kg if weight_kg is not None else Decimal("0"),
            "workstation_management_no": mgmt_no,
            "operator_name": (qa_result.operator_name if qa_result else "") or "",
        },
    )

    if created:
        return

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
    if qa_result and qa_result.operator_name and not row.operator_name:
        row.operator_name = qa_result.operator_name
        changed = True
    if not row.stock_in_date:
        row.stock_in_date = stock_in_date
        changed = True

    if changed:
        row.save()


def _sync_material_out_stock_from_ledger(ledger):
    # Chỉ tạo 出庫台帳 khi ledger có liên kết trực tiếp từ luồng quét ảnh (qa_result tồn tại).
    # Job nhập kho không có qa_result, không được sync sang 出庫台帳.
    if not getattr(ledger, "qa_result_id", None):
        QAMaterialOutStockLedger.objects.filter(auto_input_ledger=ledger).delete()
        return

    if QADeletedJobMarker.objects.filter(job_id=ledger.job_id).exists():
        QAMaterialOutStockLedger.objects.filter(auto_input_ledger=ledger).delete()
        return

    if (ledger.job_status or "") != "done":
        QAMaterialOutStockLedger.objects.filter(auto_input_ledger=ledger).delete()
        return

    qa_result = ledger.qa_result
    device = qa_result.device if qa_result and qa_result.device else None
    source_date = qa_result.created_at if qa_result else ledger.created_at
    stock_out_date = timezone.localtime(source_date).date()

    material_name = (device.material if device else "") or ledger.qa_material or ""
    material_code = (device.material_code if device else "") or ""
    weight_kg = qa_result.input_weight if qa_result and qa_result.input_weight is not None else ledger.qa_input_weight
    bag_count = _calculate_bag_count_by_material_code(material_code, weight_kg)
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
                "bag_sequence_no": bag_count,
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

    if changed:
        row.save()


@receiver(post_save, sender=PhienNhapLieu)
def on_phien_saved(sender, instance, **kwargs):
    _sync_ledger_from_phien(instance)


@receiver(post_save, sender=KetQuaNhapLieu)
def on_ket_qua_saved(sender, instance, **kwargs):
    if instance.phien_id:
        _sync_ledger_from_phien(instance.phien)


@receiver(post_save, sender=QAAutoInputLedger)
def on_auto_ledger_saved(sender, instance, **kwargs):
    _sync_material_out_stock_from_ledger(instance)


@receiver(post_save, sender=QAMaterialOutStockLedger)
def on_material_out_stock_saved(sender, instance, **kwargs):
    _send_low_stock_alert_if_needed(instance)
