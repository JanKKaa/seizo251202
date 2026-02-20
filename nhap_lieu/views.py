import requests
from django.shortcuts import render, redirect
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .models import ChuongTrinhNhapLieu, MayTinh
from django.http import JsonResponse

from django.views.decorators.http import require_POST
import json
import re
import copy

# 入力データをFlask APIに送信する関数
def gui_du_lieu(payload, ip):
    url = f"http://{ip}:5000/send_input"
    try:
        response = requests.post(url, json=payload, timeout=10)
        if response.status_code == 200:
            data = response.json()
            return True, data.get("message", "成功"), data.get("clipboard", "")
        else:
            return False, f"エラー: {response.text}", ""
    except Exception as e:
        return False, f"接続エラー: {e}"

def is_valid_ip(ip):
    # IPv4の簡易チェック
    pattern = r"^(?:[0-9]{1,3}\.){3}[0-9]{1,3}$"
    return re.match(pattern, ip) is not None

@csrf_exempt
def index(request):
    chuong_trinh_list = ChuongTrinhNhapLieu.objects.all()
    may_tinh_list = MayTinh.objects.all()
    selected = None
    selected_may = None
    message = ""
    # 選択されたプログラム（GETまたはPOST）
    ten_chuong_trinh = request.POST.get("ten_chuong_trinh") or request.GET.get("ten_chuong_trinh")
    may_id = request.POST.get("may_tinh") or request.GET.get("may_tinh")
    if ten_chuong_trinh:
        try:
            selected = ChuongTrinhNhapLieu.objects.get(ten_chuong_trinh=ten_chuong_trinh)
        except ChuongTrinhNhapLieu.DoesNotExist:
            selected = None
            message = "入力プログラムが見つかりません。"
    if may_id:
        try:
            selected_may = MayTinh.objects.get(id=may_id)
        except MayTinh.DoesNotExist:
            selected_may = None

    # 入力コマンド送信処理
    if request.method == "POST":
        print("request.POST:", request.POST)
        if not ten_chuong_trinh:
            message = "入力プログラムを選択してください！"
        elif not may_id:
            message = "コマンドを受信するコンピューターを選択してください！"
        elif selected and selected_may:
            ip = selected_may.ip
            if not is_valid_ip(ip):
                message = f"無効なIPアドレス: {ip}"
            else:
                dong1 = request.POST.get("dong1", "")
                dong2 = request.POST.get("dong2", "")
                dong3 = request.POST.get("dong3", "")
                dong4 = request.POST.get("dong4", "")
                dong5 = request.POST.get("dong5", "")
                du_lieu = [dong1, dong2, dong3, dong4, dong5]

                # 空行または空白のみの行を除外
                du_lieu_gui = [d for d in du_lieu if d and d.strip()]

                if not du_lieu_gui:
                    message = "少なくとも1行のデータを入力してください！"
                else:
                    # ルールを取得し、"Dòng X"プレースホルダーを実際の値に置換
                    dong_map = {
                        "Dòng 1": dong1,
                        "Dòng 2": dong2,
                        "Dòng 3": dong3,
                        "Dòng 4": dong4,
                        "Dòng 5": dong5,
                    }
                    quy_tac = json.loads(selected.quy_tac)
                    quy_tac_gui = [dong_map.get(item, item) for item in quy_tac]
                    payload = {
                        "quy_tac": quy_tac_gui,
                        "delay": float(request.POST.get("delay", 2)),  # Đổi mặc định thành 2 giây
                    }
                    print("Flaskへ送信するペイロード:", payload)
                    success, msg, clipboard = gui_du_lieu(payload, ip)
                    if success:
                        message = f"入力コマンドを {selected_may.ten_hien_thi or selected_may.ten_may} (IP: {selected_may.ip}) に正常に送信しました！"
                    else:
                        message = f"コマンド送信エラー: {msg}"
                    # 必要に応じてサンプルデータを更新
                    selected.dong1 = dong1
                    selected.dong2 = dong2
                    selected.dong3 = dong3
                    selected.dong4 = dong4
                    selected.dong5 = dong5
                    selected.save()
        # 情報不足の場合はコマンド送信しない

    quy_tac_list = []
    if selected and selected.quy_tac:
        try:
            quy_tac_list = json.loads(selected.quy_tac)
        except Exception:
            quy_tac_list = []

    # AJAX（fetch）の場合はJSONを返す
    if request.method == "POST" and request.headers.get("x-requested-with") == "XMLHttpRequest":
        return JsonResponse({
            "message": message,
            "clipboard": clipboard if 'clipboard' in locals() else ""
        })

    return render(request, "nhap_lieu/index.html", {
        "chuong_trinh_list": chuong_trinh_list,
        "may_tinh_list": may_tinh_list,
        "selected": selected,
        "selected_may": selected_may,
        "message": message,
        "quy_tac_list": quy_tac_list,
    })


@csrf_exempt
@login_required
def quanly_may(request):
    may = None

    # 削除処理
    xoa_id = request.GET.get('xoa')
    if xoa_id:
        MayTinh.objects.filter(id=xoa_id).delete()
        return redirect('nhap_lieu:quanly_may')

    # 編集処理
    sua_id = request.GET.get('sua')
    if sua_id:
        may = MayTinh.objects.filter(id=sua_id).first()

    # 追加/編集処理
    if request.method == "POST":
        ten_may = request.POST.get('ten_may', '').strip()
        ip = request.POST.get('ip', '').strip()
        mo_ta = request.POST.get('mo_ta', '').strip()
        nguoi_phu_trach = request.POST.get('nguoi_phu_trach', '').strip()
        trang_thai = request.POST.get('trang_thai', 'active')

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
        return redirect('nhap_lieu:quanly_may')

    danh_sach_may = MayTinh.objects.all()
    return render(request, "nhap_lieu/quanly_may.html", {
        "may": may,
        "danh_sach_may": danh_sach_may,
    })

# 入力テンプレート設計ページ
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
            messages.error(request, "編集するテンプレートが見つかりません。")

    if request.method == "POST":
        ten_chuong_trinh = request.POST.get("ten_chuong_trinh", "").strip()
        quy_tac_list = request.POST.getlist("content[]")
        quy_tac_json = json.dumps(quy_tac_list, ensure_ascii=False)
        if edit_ten and mau:
            # 既存テンプレートを更新（行1-5は保存しない）
            mau.ten_chuong_trinh = ten_chuong_trinh
            mau.quy_tac = quy_tac_json
            mau.save()
            messages.success(request, f"テンプレート '{ten_chuong_trinh}' を正常に更新しました！")
        else:
            # 新規作成（行1-5は保存しない）
            ChuongTrinhNhapLieu.objects.create(
                ten_chuong_trinh=ten_chuong_trinh,
                quy_tac=quy_tac_json,
                nguoi_thiet_ke=request.user
            )
            messages.success(request, "テンプレートを正常に保存しました！")
        return redirect("nhap_lieu:mau_list")

    context = {
        "mau": mau,
        "quy_tac_list": quy_tac_list,
        "is_edit": bool(edit_ten),
        "f_keys": ["F1","F2","F3","F4","F5","F6","F7","F8","F9","F10","F11","F12"],
    }
    return render(request, "nhap_lieu/mau_nhaplieu.html", context)

@login_required
def mau_list(request):
    mau_list = ChuongTrinhNhapLieu.objects.all().order_by('-ngay_tao')
    return render(request, "nhap_lieu/mau_list.html", {
        "mau_list": mau_list,
    })

@login_required
@require_POST
def mau_xoa(request, ten_chuong_trinh):
    try:
        mau = ChuongTrinhNhapLieu.objects.get(ten_chuong_trinh=ten_chuong_trinh)
        mau.delete()
        messages.success(request, f"テンプレート '{ten_chuong_trinh}' を正常に削除しました！")
    except ChuongTrinhNhapLieu.DoesNotExist:
        messages.error(request, "削除するテンプレートが見つかりません。")
    return redirect("nhap_lieu:mau_list")



