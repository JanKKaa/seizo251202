from django.contrib import messages
from django.shortcuts import render, redirect, get_object_or_404
from .models import Product, Checksheet, LichSuKiemTra, Checker
from .forms import ProductForm
from django.utils.timezone import now
from django.contrib.auth.decorators import user_passes_test
from django.http import HttpResponseForbidden, JsonResponse
from django.db.models import Q
from datetime import datetime, timedelta
import base64
from django.core.files.base import ContentFile
from django.contrib.auth.models import User
from itertools import groupby

def index(request):
    # チェッカーリストを取得
    checkers = Checker.objects.all()

    if request.method == 'POST' and 'add_checker' in request.POST:
        # 新しいチェッカーを追加
        checker_name = request.POST.get('checker_name')
        if checker_name:
            Checker.objects.create(name=checker_name)
            messages.success(request, f"担当者 '{checker_name}' が正常に追加されました！")
        return redirect('mente_index')

    # その他のロジック...
    products = Product.objects.all()
    selected_product = None
    checksheets = []

    # 選択された製品を取得
    product_id = request.GET.get('product_id')
    if product_id:
        selected_product = Product.objects.filter(id=product_id).first()
        if selected_product:
            # 製品に関連するチェックシートを取得
            checksheets = Checksheet.objects.filter(product=selected_product)

    return render(request, 'mente/mente_index.html', {
        'products': products,
        'selected_product': selected_product,
        'checksheets': checksheets,
        'checkers': checkers,
    })

def add_product(request):
    products = Product.objects.all()  # Lấy danh sách sản phẩm
    if request.method == 'POST':
        form = ProductForm(request.POST, request.FILES)  # Xử lý dữ liệu từ form
        if form.is_valid():
            product = form.save(commit=False)
            # Gán người tạo là người dùng hiện tại
            if request.user.is_authenticated:
                product.creator = request.user
            else:
                product.creator = None  # Nếu không có người dùng, để trống
            product.save()
            messages.success(request, '新しい製品が正常に追加されました！')
            return redirect('add_product')  # Chuyển hướng về trang thêm sản phẩm
        else:
            messages.error(request, '入力内容にエラーがあります。もう一度確認してください。')
    else:
        form = ProductForm()

    return render(request, 'mente/add_product.html', {'form': form, 'products': products})

def add_new_checksheet(request, product):
    """必須条件を満たした場合、新しい行をチェックシートに追加します。"""
    new_item = request.POST.get('new_item')
    new_description = request.POST.get('new_description')
    new_reference_image = request.FILES.get('new_reference_image')
    new_current_image = request.FILES.get('new_current_image')  # 任意
    new_drawing_size = request.POST.get('new_drawing_size')  # 任意
    new_actual_size = request.POST.get('new_actual_size')  # 任意
    new_checker_name = request.POST.get('new_checker_name')  # 任意
    new_approver_name = request.POST.get('new_approver_name')  # 任意

    # 必須フィールドを確認
    if not new_item:
        messages.error(request, "項目 (列2) は必須です！")
        return
    if not new_description:
        messages.error(request, "説明 (列3) は必須です！")
        return
    

    # 必須条件を満たした場合、新しい行を作成
    try:
        Checksheet.objects.create(
            product=product,
            item=new_item,
            description=new_description,
            reference_image=new_reference_image,
            current_image=new_current_image,
            drawing_size=new_drawing_size,
            actual_size=new_actual_size,
            checker_name=new_checker_name,
            approver_name=new_approver_name,
        )
        messages.success(request, "新しい行が正常に追加されました！")
    except Exception as e:
        messages.error(request, f"新しい行を追加中にエラーが発生しました: {str(e)}")

def update_checksheet(request, checksheets):
    """既存のチェックシート行を保存します。"""
    for checksheet in checksheets:
        try:
            checksheet.item = request.POST.get(f'item_{checksheet.id}')
            checksheet.description = request.POST.get(f'description_{checksheet.id}')
            checksheet.drawing_size = request.POST.get(f'drawing_size_{checksheet.id}')
            checksheet.actual_size = request.POST.get(f'actual_size_{checksheet.id}')
            checksheet.is_checked = f'is_checked_{checksheet.id}' in request.POST
            checksheet.checker_name = request.POST.get(f'checker_name_{checksheet.id}')
            checksheet.approver_name = request.POST.get(f'approver_name_{checksheet.id}')

            if f'reference_image_{checksheet.id}' in request.FILES:
                checksheet.reference_image = request.FILES[f'reference_image_{checksheet.id}']
            if f'current_image_{checksheet.id}' in request.FILES:
                checksheet.current_image = request.FILES[f'current_image_{checksheet.id}']

            checksheet.save()
        except Exception as e:
            messages.error(request, f"行番号 {checksheet.id} を更新中にエラーが発生しました: {str(e)}")

    messages.success(request, "すべての行が正常に保存されました！")

def checksheet(request, product_id):
    """チェックシートを表示および処理するメイン関数。"""
    product = get_object_or_404(Product, id=product_id)
    checksheets = Checksheet.objects.filter(product=product)

    if request.method == 'POST':
        if 'add_new' in request.POST:  # "新しい行を追加" ボタンが押された場合
            add_new_checksheet(request, product)
        return redirect('checksheet', product_id=product.id)

    return render(request, 'mente/checksheet.html', {
        'product': product,
        'checksheets': checksheets,
    })

def delete_checksheet(request, checksheet_id, product_id):
    """Xử lý xóa một dòng checksheet."""
    checksheet = get_object_or_404(Checksheet, id=checksheet_id)
    try:
        checksheet.delete()
        messages.success(request, f" {checksheet_id} 削除された!")
    except Exception as e:
        messages.error(request, f"削除のエラー {checksheet_id}: {str(e)}")
    return redirect('checksheet', product_id=product_id)

def update_checksheet_fields(request, product_id):
    """Xử lý cập nhật các cột được phép trong bảng checksheet và lưu lịch sử kiểm tra."""
    product = get_object_or_404(Product, id=product_id)
    checksheets = Checksheet.objects.filter(product=product)

    if request.method == 'POST':
        # Lấy thời gian bắt đầu kiểm tra từ request (nếu có)
        start_time = request.POST.get('start_time', None)
        if start_time:
            product.start_time = start_time  # Lưu thời gian bắt đầu vào sản phẩm
            product.save()

        for checksheet in checksheets:
            try:
                # Cập nhật các cột được phép
                checksheet.current_image = request.FILES.get(f'current_image_{checksheet.id}', checksheet.current_image)
                checksheet.actual_size = request.POST.get(f'actual_size_{checksheet.id}', checksheet.actual_size)
                checksheet.is_checked = f'is_checked_{checksheet.id}' in request.POST
                checksheet.checker_name = request.POST.get(f'checker_name_{checksheet.id}', checksheet.checker_name)
                checksheet.approver_name = request.POST.get(f'approver_name_{checksheet.id}', checksheet.approver_name)

                # Lưu lịch sử kiểm tra
                LichSuKiemTra.objects.create(
                    product=checksheet.product,
                    item=checksheet.item,
                    description=checksheet.description or "Không có miêu tả",
                    reference_image=checksheet.reference_image,
                    current_image=checksheet.current_image,
                    drawing_size=checksheet.drawing_size,
                    actual_size=checksheet.actual_size,
                    is_checked=checksheet.is_checked,
                    checker_name=checksheet.checker_name,
                    approver_name=checksheet.approver_name,
                    start_time=product.start_time,  # Lấy thời gian bắt đầu từ sản phẩm
                    end_time=now(),  # Lưu thời gian kết thúc kiểm tra
                )

            except Exception as e:
                messages.error(request, f"変更のエラー {checksheet.id}: {str(e)}")

        # Xử lý ảnh base64
        for key, value in request.POST.items():
            if key.startswith('current_image_') and value:
                checksheet_id = key.replace('current_image_', '')
                checksheet = get_object_or_404(Checksheet, id=checksheet_id)

                # Kiểm tra xem dữ liệu có chứa ';base64,' không
                if ';base64,' in value:
                    try:
                        format, imgstr = value.split(';base64,')
                        ext = format.split('/')[-1]  # Lấy phần mở rộng (jpg, png, ...)
                        file_name = f'checksheet_{checksheet_id}.{ext}'
                        checksheet.current_image.save(file_name, ContentFile(base64.b64decode(imgstr)))
                    except Exception as e:
                        messages.error(request, f"写真のエラー {checksheet_id}: {str(e)}")
                else:
                    messages.error(request, f"写真データのエラー {checksheet_id}.")

        # Thêm thông báo thành công
        messages.success(request, "メンテナンス履歴書を変更された!")

        # Redirect về trang mente_index hoặc trang hiện tại
        return redirect('mente_index')  # Thay 'mente_index' bằng tên URL của trang bạn muốn quay lại

    # Trả về JSON nếu không phải POST
    return JsonResponse({'status': 'error', 'message': 'エラー発生している.'})

def lichsukiemtra_list(request, product_id):
    """Hiển thị danh sách lịch sử kiểm tra của một sản phẩm với chức năng lọc và nhóm."""
    product = get_object_or_404(Product, id=product_id)
    lich_su_kiem_tra = LichSuKiemTra.objects.filter(product=product).order_by('start_time')

    # Lấy giá trị bộ lọc từ request
    start_time_filter = request.GET.get('start_time', None)
    checker_name_filter = request.GET.get('checker_name', '')

    # Áp dụng bộ lọc nếu có
    if start_time_filter:
        try:
            # Chuyển đổi start_time_filter thành định dạng ngày
            start_date = datetime.strptime(start_time_filter, '%Y-%m-%d').date()
            # Lọc các bản ghi có start_time trùng với ngày được chọn
            lich_su_kiem_tra = lich_su_kiem_tra.filter(start_time__date=start_date)
        except ValueError:
            messages.error(request, "入力間違いました、やり直してください.")

    if checker_name_filter:
        # Lọc theo tên người kiểm tra (không phân biệt chữ hoa/thường)
        lich_su_kiem_tra = lich_su_kiem_tra.filter(checker_name__icontains=checker_name_filter)

    # Nhóm dữ liệu theo ngày kiểm tra
    grouped_records = []
    for key, group in groupby(lich_su_kiem_tra, key=lambda x: x.start_time.date()):
        grouped_records.append({
            'date': key,
            'records': list(group)
        })

    # Tính toán khoảng thời gian kiểm tra và định dạng thành hh:mm:ss
    for record in lich_su_kiem_tra:
        if record.start_time and record.end_time:
            duration_seconds = (record.end_time - record.start_time).total_seconds()
            duration = str(timedelta(seconds=duration_seconds)).split(".")[0]  # Loại bỏ microseconds
           
        else:
            record.duration_formatted = "不明"

    return render(request, 'mente/lichsukiemtra_list.html', {
        'product': product,
        'grouped_records': grouped_records,
        'start_time_filter': start_time_filter,
        'checker_name_filter': checker_name_filter,
    })

def delete_product(request, product_id):
    """製品をIDで削除します。"""
    product = get_object_or_404(Product, id=product_id)
    try:
        product.delete()
        messages.success(request, f"製品 '{product.name}' が正常に削除されました！")
    except Exception as e:
        messages.error(request, f"製品を削除できませんでした: {str(e)}")
    return redirect('mente_index')

@user_passes_test(lambda u: u.is_superuser)
def checker(request):
    """Trang quản lý danh sách người kiểm tra."""
    checkers = Checker.objects.all()

    if request.method == 'POST':
        # Thêm người kiểm tra mới
        checker_name = request.POST.get('checker_name')
        if checker_name:
            if not Checker.objects.filter(name=checker_name).exists():
                Checker.objects.create(name=checker_name)
                messages.success(request, f"担当者 '{checker_name}' 追加された!")
            else:
                messages.error(request, f"担当者 '{checker_name}' 存在します!")
        return redirect('checker')

    return render(request, 'mente/checker.html', {'checkers': checkers})

def delete_checker(request, checker_id):
    """Xóa một người kiểm tra."""
    checker = get_object_or_404(Checker, id=checker_id)
    try:
        checker.delete()
        messages.success(request, f"担当者 '{checker.name}' 削除された!")
    except Exception as e:
        messages.error(request, f"エラー発生している: {str(e)}")
    return redirect('checker')

@user_passes_test(lambda u: u.is_superuser)  # Chỉ cho phép admin
def delete_lichsukiemtra(request, record_id):
    """Xóa một bản ghi lịch sử kiểm tra."""
    from .models import LichSuKiemTra  # Import model LichSuKiemTra

    try:
        record = LichSuKiemTra.objects.get(id=record_id)
        record.delete()
        messages.success(request, "検査履歴が正常に削除されました。")
    except LichSuKiemTra.DoesNotExist:
        messages.error(request, "指定された検査履歴が見つかりませんでした。")
    except Exception as e:
        messages.error(request, f"削除中にエラーが発生しました: {str(e)}")

    return redirect('lichsukiemtra_list', product_id=record.product.id)
