from datetime import timedelta

from django.db.models.signals import post_save
from django.dispatch import receiver

from nhap_lieu.models import KetQuaNhapLieu, PhienNhapLieu

from .models import QAAutoInputLedger, QAResult


def _find_qa_result_for_phien(phien):
    if getattr(phien, "qa_result_id", None):
        return phien.qa_result

    ref_time = phien.ngay_tao
    return (
        QAResult.objects.filter(created_at__range=(ref_time - timedelta(minutes=30), ref_time + timedelta(minutes=30)))
        .select_related("device")
        .order_by("-created_at")
        .first()
    )


def _sync_ledger_from_phien(phien):
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


@receiver(post_save, sender=PhienNhapLieu)
def on_phien_saved(sender, instance, **kwargs):
    _sync_ledger_from_phien(instance)


@receiver(post_save, sender=KetQuaNhapLieu)
def on_ket_qua_saved(sender, instance, **kwargs):
    if instance.phien_id:
        _sync_ledger_from_phien(instance.phien)
