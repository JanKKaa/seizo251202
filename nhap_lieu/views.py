import json
import re
import time

import requests
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, StreamingHttpResponse
from django.shortcuts import redirect, render
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from .models import ChuongTrinhNhapLieu, KetQuaNhapLieu, MayTinh


def gui_du_lieu(payload, ip, timeout=20):
    """Gửi payload sang Flask máy trạm nhập liệu."""
    url = f"http://{ip}:5000/send_input"
    try:
        response = requests.post(url, json=payload, timeout=timeout)
    except Exception as exc:
        return False, f"Lỗi kết nối: {exc}", {}

    if response.status_code != 200:
        return False, f"Lỗi: HTTP {response.status_code} - {response.text}", {}

    try:
        data = response.json()
    except Exception:
        data = {"message": "OK", "raw": response.text}

    return True, data.get("message", "Thành công"), data


def is_valid_ip(ip):
    pattern = r"^(?:[0-9]{1,3}\.){3}[0-9]{1,3}$"
    return bool(re.match(pattern, ip or ""))


@csrf_exempt
def index(request):
    chuong_trinh_list = ChuongTrinhNhapLieu.objects.all()
    may_tinh_list = MayTinh.objects.all()
    selected = None
    selected_may = None
    message = ""

    ten_chuong_trinh = request.POST.get("ten_chuong_trinh") or request.GET.get("ten_chuong_trinh")
    may_id = request.POST.get("may_tinh") or request.GET.get("may_tinh")

    if ten_chuong_trinh:
        try:
            selected = ChuongTrinhNhapLieu.objects.get(ten_chuong_trinh=ten_chuong_trinh)
        except ChuongTrinhNhapLieu.DoesNotExist:
            selected = None
            message = "Không tìm thấy chương trình nhập liệu."

    if may_id:
        try:
            selected_may = MayTinh.objects.get(id=may_id)
        except MayTinh.DoesNotExist:
            selected_may = None

    clipboard = ""

    if request.method == "POST":
        if not ten_chuong_trinh:
            message = "Vui lòng chọn chương trình nhập liệu!"
        elif not may_id:
            message = "Vui lòng chọn máy tính nhận lệnh!"
        elif selected and selected_may:
            ip = selected_may.ip
            if not is_valid_ip(ip):
                message = f"Địa chỉ IP không hợp lệ: {ip}"
            else:
                dong1 = request.POST.get("dong1", "")
                dong2 = request.POST.get("dong2", "")
                dong3 = request.POST.get("dong3", "")
                dong4 = request.POST.get("dong4", "")
                dong5 = request.POST.get("dong5", "")

                if not any((dong1.strip(), dong2.strip(), dong3.strip(), dong4.strip(), dong5.strip())):
                    message = "Vui lòng nhập ít nhất một dòng dữ liệu!"
                else:
                    dong_map = {
                        "Dòng 1": dong1,
                        "Dòng 2": dong2,
                        "Dòng 3": dong3,
                        "Dòng 4": dong4,
                        "Dòng 5": dong5,
                    }

                    try:
                        quy_tac = json.loads(selected.quy_tac)
                    except Exception:
                        quy_tac = []

                    quy_tac_gui = [dong_map.get(item, item) for item in quy_tac]
                    payload = {
                        "quy_tac": quy_tac_gui,
                        "delay": float(request.POST.get("delay", 0.1)),
                    }

                    success, msg, response_data = gui_du_lieu(payload, ip)
                    clipboard = response_data.get("clipboard", "") if isinstance(response_data, dict) else ""

                    if success:
                        message = (
                            f"Đã gửi lệnh nhập liệu tới {selected_may.ten_hien_thi or selected_may.ten_may} "
                            f"(IP: {selected_may.ip}). Đợi callback kết quả..."
                        )
                    else:
                        message = f"Lỗi gửi lệnh: {msg}"

                    selected.dong1 = dong1
                    selected.dong2 = dong2
                    selected.dong3 = dong3
                    selected.dong4 = dong4
                    selected.dong5 = dong5
                    selected.save()

    quy_tac_list = []
    if selected and selected.quy_tac:
        try:
            quy_tac_list = json.loads(selected.quy_tac)
        except Exception:
            quy_tac_list = []

    if request.method == "POST" and request.headers.get("x-requested-with") == "XMLHttpRequest":
        latest_result = None
        if selected_may and selected_may.ip:
            latest_result = KetQuaNhapLieu.objects.filter(ip_may=selected_may.ip).order_by("-ngay_nhan").first()

        return JsonResponse(
            {
                "message": message,
                "clipboard": clipboard,
                "latest_result": (
                    {
                        "id": latest_result.id,
                        "ma_nhap_lieu": latest_result.ma_nhap_lieu,
                        "ngay_nhan": latest_result.ngay_nhan.isoformat(),
                    }
                    if latest_result
                    else None
                ),
            }
        )

    return render(
        request,
        "nhap_lieu/index.html",
        {
            "chuong_trinh_list": chuong_trinh_list,
            "may_tinh_list": may_tinh_list,
            "selected": selected,
            "selected_may": selected_may,
            "message": message,
            "quy_tac_list": quy_tac_list,
        },
    )


@csrf_exempt
@login_required
def quanly_may(request):
    may = None

    xoa_id = request.GET.get("xoa")
    if xoa_id:
        MayTinh.objects.filter(id=xoa_id).delete()
        return redirect("nhap_lieu:quanly_may")

    sua_id = request.GET.get("sua")
    if sua_id:
        may = MayTinh.objects.filter(id=sua_id).first()

    if request.method == "POST":
        ten_may = request.POST.get("ten_may", "").strip()
        ip = request.POST.get("ip", "").strip()
        mo_ta = request.POST.get("mo_ta", "").strip()
        nguoi_phu_trach = request.POST.get("nguoi_phu_trach", "").strip()
        trang_thai = request.POST.get("trang_thai", "active")

        if may:
            may.ten_may = ten_may
            may.ip = ip
            may.mo_ta = mo_ta
            may.nguoi_phu_trach = nguoi_phu_trach
            may.trang_thai = trang_thai
            may.save()
        else:
            MayTinh.objects.create(
                ten_may=ten_may,
                ip=ip,
                mo_ta=mo_ta,
                nguoi_phu_trach=nguoi_phu_trach,
                trang_thai=trang_thai,
            )
        return redirect("nhap_lieu:quanly_may")

    danh_sach_may = MayTinh.objects.all()
    return render(request, "nhap_lieu/quanly_may.html", {"may": may, "danh_sach_may": danh_sach_may})


@login_required
def mau_nhaplieu(request):
    edit_ten = request.GET.get("edit")
    mau = None
    quy_tac_list = []

    if edit_ten:
        try:
            mau = ChuongTrinhNhapLieu.objects.get(ten_chuong_trinh=edit_ten)
            try:
                quy_tac_list = json.loads(mau.quy_tac)
            except Exception:
                quy_tac_list = []
        except ChuongTrinhNhapLieu.DoesNotExist:
            messages.error(request, "Không tìm thấy mẫu để sửa.")

    if request.method == "POST":
        ten_chuong_trinh = request.POST.get("ten_chuong_trinh", "").strip()
        quy_tac_list = request.POST.getlist("content[]")
        quy_tac_json = json.dumps(quy_tac_list, ensure_ascii=False)

        if edit_ten and mau:
            mau.ten_chuong_trinh = ten_chuong_trinh
            mau.quy_tac = quy_tac_json
            mau.save()
            messages.success(request, f"Đã cập nhật mẫu '{ten_chuong_trinh}' thành công!")
        else:
            ChuongTrinhNhapLieu.objects.create(
                ten_chuong_trinh=ten_chuong_trinh,
                quy_tac=quy_tac_json,
                nguoi_thiet_ke=request.user,
            )
            messages.success(request, "Đã lưu chương trình mẫu thành công!")

        return redirect("nhap_lieu:mau_list")

    context = {
        "mau": mau,
        "quy_tac_list": quy_tac_list,
        "is_edit": bool(edit_ten),
        "f_keys": ["F1", "F2", "F3", "F4", "F5", "F6", "F7", "F8", "F9", "F10", "F11", "F12"],
    }
    return render(request, "nhap_lieu/mau_nhaplieu.html", context)


@login_required
def mau_list(request):
    ds = ChuongTrinhNhapLieu.objects.all().order_by("-ngay_tao")
    return render(request, "nhap_lieu/mau_list.html", {"mau_list": ds})


@login_required
@require_POST
def mau_xoa(request, ten_chuong_trinh):
    try:
        mau = ChuongTrinhNhapLieu.objects.get(ten_chuong_trinh=ten_chuong_trinh)
        mau.delete()
        messages.success(request, f"Đã xóa mẫu '{ten_chuong_trinh}' thành công!")
    except ChuongTrinhNhapLieu.DoesNotExist:
        messages.error(request, "Không tìm thấy mẫu để xóa.")
    return redirect("nhap_lieu:mau_list")


@csrf_exempt
@require_POST
def api_cap_nhat_ket_qua(request):
    """Nhận callback từ Flask và lưu lịch sử."""
    try:
        data = json.loads(request.body)
    except Exception:
        return JsonResponse({"status": "error", "message": "JSON không hợp lệ"}, status=400)

    ma_so = (data.get("ma_nhap_lieu") or "").strip()
    ip_may = (data.get("ip") or "").strip()
    full_text = data.get("full_text") or ""
    ten_chuong_trinh = (data.get("ten_chuong_trinh") or "").strip()

    if not ip_may:
        return JsonResponse({"status": "error", "message": "Thiếu ip"}, status=400)

    may = MayTinh.objects.filter(ip=ip_may).first()
    chuong_trinh = (
        ChuongTrinhNhapLieu.objects.filter(ten_chuong_trinh=ten_chuong_trinh).first() if ten_chuong_trinh else None
    )

    ket_qua = KetQuaNhapLieu.objects.create(
        chuong_trinh=chuong_trinh,
        may_tinh=may,
        ip_may=ip_may,
        ma_nhap_lieu=ma_so,
        full_text=full_text,
        trang_thai="Thành công",
        ghi_chu="Nhận callback từ Flask",
    )

    return JsonResponse(
        {
            "status": "success",
            "message": "Đã nhận và lưu",
            "data": {"id": ket_qua.id, "ma": ket_qua.ma_nhap_lieu},
        },
        status=201,
    )


@csrf_exempt
def api_get_latest_result(request):
    """Polling kết quả mới nhất theo IP. Dùng after_id để tránh lấy lại dữ liệu cũ."""
    ip = (request.GET.get("ip") or "").strip()
    if not ip:
        return JsonResponse({"status": "error", "message": "Thiếu IP"}, status=400)

    after_id = request.GET.get("after_id")
    qs = KetQuaNhapLieu.objects.filter(ip_may=ip, trang_thai="Thành công").order_by("-id")

    if after_id:
        try:
            qs = qs.filter(id__gt=int(after_id))
        except ValueError:
            pass

    ket_qua = qs.first()
    if not ket_qua:
        return JsonResponse({"status": "pending"})

    return JsonResponse(
        {
            "status": "success",
            "id": ket_qua.id,
            "ma_so": ket_qua.ma_nhap_lieu,
            "ngay_nhan": ket_qua.ngay_nhan.isoformat(),
        }
    )


@csrf_exempt
def api_get_latest_by_ip(request):
    ip = (request.GET.get("ip") or "").strip()
    if not ip:
        return JsonResponse({"status": "error", "message": "Thiếu IP"}, status=400)

    ket_qua = KetQuaNhapLieu.objects.filter(ip_may=ip).order_by("-ngay_nhan").first()
    if not ket_qua:
        return JsonResponse({"status": "no_data"})

    return JsonResponse(
        {
            "status": "success",
            "id": ket_qua.id,
            "ma_nhap_lieu": ket_qua.ma_nhap_lieu,
            "ngay_nhan": ket_qua.ngay_nhan.isoformat(),
        }
    )


@csrf_exempt
def sse_latest_result(request):
    """SSE: stream kết quả mới theo IP.

    Gửi heartbeat mỗi 2 giây, tự timeout sau ~60 giây để tránh giữ worker quá lâu.
    """
    ip = (request.GET.get("ip") or "").strip()
    if not ip:
        return JsonResponse({"error": "Missing IP"}, status=400)

    try:
        last_id = int(request.GET.get("last_id") or 0)
    except ValueError:
        last_id = 0

    def event_stream():
        started = time.time()
        timeout_seconds = 60

        while True:
            if time.time() - started > timeout_seconds:
                break

            ket_qua = (
                KetQuaNhapLieu.objects.filter(ip_may=ip, id__gt=last_id, trang_thai="Thành công")
                .order_by("id")
                .first()
            )

            if ket_qua:
                payload = {
                    "id": ket_qua.id,
                    "ma_nhap_lieu": ket_qua.ma_nhap_lieu,
                    "ngay_nhan": ket_qua.ngay_nhan.isoformat(),
                }
                yield f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"
                break

            yield "event: heartbeat\ndata: {}\n\n"
            time.sleep(2)

    response = StreamingHttpResponse(event_stream(), content_type="text/event-stream")
    response["Cache-Control"] = "no-cache"
    response["X-Accel-Buffering"] = "no"
    return response
