from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
import base64
from io import BytesIO
from django.core.files.base import ContentFile
from django.http import HttpResponseRedirect
from django.urls import reverse
from .forms import XuLyAnhForm, DeviceInfoForm
from .models import XuLyAnh2, DeviceInfo

from django.core.mail import send_mail
from PIL import Image, ImageOps
import cv2
import numpy as np
from django.db.models import Q
from django.utils import timezone
from django.db.utils import OperationalError

def preprocess_image(image):
    img = np.array(image.convert('L'))
    pil_img = Image.fromarray(img)
    pil_img = ImageOps.autocontrast(pil_img, cutoff=1)
    img = np.array(pil_img)
    img = cv2.medianBlur(img, 1)
    return Image.fromarray(img)

def upload_image(request):
    result = None
    message = None
    ocr_text = None
    expected_text = request.POST.get('expected_text') or request.GET.get('expected_text')
    machine_number = request.POST.get('machine_number', '1')
    device_id = request.GET.get('device_id') or request.POST.get('machine')
    device = None
    if device_id:
        try:
            device = DeviceInfo.objects.get(id=device_id)
        except DeviceInfo.DoesNotExist:
            device = None
    if request.method == 'POST':
        captured_image = request.POST.get('captured_image')
        form = XuLyAnhForm(request.POST, request.FILES)
        try:
            if captured_image:
                format, imgstr = captured_image.split(';base64,')
                ext = format.split('/')[-1]
                img_content = ContentFile(base64.b64decode(imgstr), name=f"captured.{ext}")
                xu_ly_anh = form.save(commit=False)
                if request.user.is_authenticated:
                    xu_ly_anh.user = request.user
                xu_ly_anh.image = img_content
                xu_ly_anh.machine = device
                if img_content:
                    img_content.seek(0)
                    image = Image.open(img_content)
                else:
                    image = None

                if image:
                    image = preprocess_image(image)
                    buffer = BytesIO()
                    image.save(buffer, format='PNG')
                    xu_ly_anh.processed_image.save(f"processed_{xu_ly_anh.id or 'new'}.png", ContentFile(buffer.getvalue()), save=False)

                    try:
                        from paddleocr import PaddleOCR
                        ocr = PaddleOCR(use_angle_cls=True, lang='japan')
                        img_np = np.array(image)
                        result_ocr = ocr.ocr(img_np, cls=True)
                        paddle_text = ''.join([line[1][0] for line in result_ocr[0]])
                        paddle_text = paddle_text.replace('\n', '').replace('\r', '').replace(' ', '')
                    except Exception as e:
                        paddle_text = f"データがありません"

                    ocr_text = f"読み取り内容:\n{paddle_text.strip()}\n"
                    if expected_text:
                        ocr_text += f"QRコード内容:\n{expected_text.strip()}\n"
                    xu_ly_anh.data = ocr_text

                    expected_text_clean = expected_text.strip().replace(' ', '').replace('\n', '').replace('\r', '') if expected_text else ''
                    paddle_text_clean = paddle_text.replace(' ', '').replace('\n', '').replace('\r', '')

                    is_match = False
                    matched_text = ""
                    if expected_text_clean and expected_text_clean in paddle_text_clean:
                        is_match = True
                        matched_text = expected_text
                        xu_ly_anh.result = "一致"
                    else:
                        is_match = False
                        matched_text = ""
                        xu_ly_anh.result = "不一致"
                        # Gửi mail nếu không trùng khớp
                        subject = "【警告】画像検査結果：不一致"
                        message_mail = (
                            "画像検査で不一致が検出されました。\n\n"
                            f"デバイス名: {device.name if device else ''}\n"
                            f"材料名: {device.material if device else ''}\n"
                            f"製品名: {device.product if device else ''}\n"
                            f"混合率: {device.ratio if device else ''}\n"
                            f"QRコード内容: {expected_text}\n"
                            f"OCR読み取り内容: {paddle_text}\n"
                            f"日時: {timezone.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
                        )
                        recipient_list = [
                            "giang@hayashi-p.co.jp",
                            "goro_h@hayashi-p.co.jp",
                            "arita_t@hayashi-p.co.jp",
                            "miyasaka_t@hayashi-p.co.jp"
                        ]
                        send_mail(
                            subject,
                            message_mail,
                            None,
                            recipient_list,
                            fail_silently=True
                        )
                else:
                    xu_ly_anh.data = "有効な画像がありません"
                
                xu_ly_anh.machine_number = int(machine_number)
                xu_ly_anh.save()

                form = XuLyAnhForm()
                device_list = DeviceInfo.objects.all()
                return render(request, 'xu_ly_anh/upload.html', {
                    'form': form,
                    'expected_text': expected_text,
                    'is_match': is_match,
                    'matched_text': matched_text,
                    'data': ocr_text,
                    'device_list': device_list,
                    'device_id': device_id,
                    'device': device,
                    'show_back_to_index': True,
                })
            else:
                messages.error(request, "カメラから画像を取得できませんでした。")
                return redirect('upload_image')
        except Exception as e:
            messages.error(request, f"画像のアップロードまたはOCR時にエラーが発生しました: {e}")
            return redirect('upload_image')
    else:
        form = XuLyAnhForm()
        is_match = None
        matched_text = None
        data = None
    device_list = DeviceInfo.objects.all()
    return render(request, 'xu_ly_anh/upload.html', {
        'form': form,
        'message': message,
        'expected_text': expected_text,
        'device_list': device_list,
        'device_id': device_id,
        'device': device,
        'is_match': is_match,
        'matched_text': matched_text,
        'data': data,
    })

def index_xla(request):
    device_list = DeviceInfo.objects.all()
    return render(request, 'xu_ly_anh/index_xla.html', {
        'device_list': device_list,
    })


def device_info_list(request):
    device_list = DeviceInfo.objects.all()
    return render(request, 'xu_ly_anh/device_info_list.html', {'device_list': device_list})

def add_device_info(request):
    if request.method == 'POST':
        form = DeviceInfoForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'デバイスが正常に追加されました。')
            return redirect('add_device_info')
    else:
        form = DeviceInfoForm()
    device_list = DeviceInfo.objects.all()
    return render(request, 'xu_ly_anh/add_device_info.html', {'form': form, 'device_list': device_list})

def delete_device_info(request, pk):
    item = get_object_or_404(DeviceInfo, pk=pk)
    item.delete()
    messages.success(request, 'デバイスが正常に削除されました。')
    return redirect('add_device_info')

def edit_device_info(request, pk):
    item = get_object_or_404(DeviceInfo, pk=pk)
    if request.method == 'POST':
        form = DeviceInfoForm(request.POST, instance=item)
        if form.is_valid():
            form.save()
            messages.success(request, 'デバイスが正常に更新されました。')
            return redirect('device_info_list')
    else:
        form = DeviceInfoForm(instance=item)
    device_list = DeviceInfo.objects.all()
    return render(request, 'xu_ly_anh/add_device_info.html', {
        'form': form,
        'device_list': device_list,
        'edit_item': item,
    })

def lich_su(request):
    try:
        results = XuLyAnh2.objects.all().select_related('machine', 'user').order_by('-created_at')
        keyword = request.GET.get('keyword', '').strip()
        date = request.GET.get('date', '').strip()

        if keyword:
            results = results.filter(
                Q(machine__name__icontains=keyword) |
                Q(machine__material__icontains=keyword) |
                Q(user__first_name__icontains=keyword) |
                Q(user__last_name__icontains=keyword)
            )
        if date:
            results = results.filter(created_at__date=date)

    except OperationalError:
        results = []
        messages.warning(request, "Chưa có dữ liệu lịch sử hoặc bảng dữ liệu chưa được tạo.")

    return render(request, 'xu_ly_anh/lich_su.html', {
        'results': results,
        'keyword': request.GET.get('keyword', '').strip(),
        'date': request.GET.get('date', '').strip(),
    })

def delete_lich_su(request, pk):
    item = get_object_or_404(XuLyAnh2, pk=pk)
    if request.method == 'POST':
        item.image.delete(save=False)
        if item.processed_image:
            item.processed_image.delete(save=False)
        item.delete()
        messages.success(request, '履歴が正常に削除されました。')
    return redirect('lich_su')
