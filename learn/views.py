from django.shortcuts import render, get_object_or_404, redirect
from .models import Course, Enrollment
from django.contrib.auth.models import User
from django.contrib.auth.decorators import login_required, user_passes_test
from django import forms
from menu.models import NhanVien
from django.contrib import messages
from .models import Course
from django.http import HttpResponse
import csv
from .models import Certificate
from django.utils import timezone
import requests
from bs4 import BeautifulSoup
from django.contrib.auth import logout
from django.urls import reverse
from django.http import StreamingHttpResponse
from urllib.parse import urljoin
import os
from django.conf import settings
from django.core.files.storage import default_storage
from django.db.models import Q
from django.core.paginator import Paginator
from .models import BangCap
from .forms import BangCapForm
from django.db import models
from django.core.mail import send_mail
from .models import MotivationalQuote
from .forms import MotivationalQuoteForm

def login_required_ma_nv(view_func):
    def wrapper(request, *args, **kwargs):
        if request.user.is_authenticated:
            if request.user.username == 'kanri':
                # Kanri login: auto clear employee-session login if exists.
                request.session.pop('ma_nv', None)
                request.session.pop('ten', None)
                return view_func(request, *args, **kwargs)
            # Chỉ cho phép tài khoản kanri. Tài khoản khác phải logout.
            logout(request)
            return redirect('learn:dangnhap')
        if not request.session.get('ma_nv'):
            return redirect('learn:dangnhap')
        return view_func(request, *args, **kwargs)
    return wrapper

def fetch_external_thumbnail(url):
    if not url:
        return ""
    try:
        response = requests.get(
            url,
            timeout=3,
            headers={"User-Agent": "Mozilla/5.0 (CourseThumbBot)"},
        )
        if response.status_code >= 400:
            return ""
        soup = BeautifulSoup(response.text, 'html.parser')
        for meta in [
            soup.find('meta', property='og:image'),
            soup.find('meta', attrs={'name': 'og:image'}),
            soup.find('meta', attrs={'name': 'twitter:image'}),
            soup.find('meta', property='twitter:image'),
            soup.find('meta', attrs={'itemprop': 'image'}),
        ]:
            if meta and meta.get('content'):
                return urljoin(url, meta.get('content').strip())
        link_img = soup.find('link', rel='image_src')
        if link_img and link_img.get('href'):
            return urljoin(url, link_img.get('href').strip())
        first_img = soup.find('img', src=True)
        if first_img and first_img.get('src'):
            src = first_img.get('src').strip()
            if src.startswith('data:'):
                return ""
            return urljoin(url, src)
    except Exception:
        return ""
    return ""

@login_required_ma_nv
def external_thumb_proxy(request):
    url = request.GET.get('url', '').strip()
    if not url or not (url.startswith('http://') or url.startswith('https://')):
        return HttpResponse(status=404)
    try:
        resp = requests.get(
            url,
            stream=True,
            timeout=5,
            headers={"User-Agent": "Mozilla/5.0 (CourseThumbProxy)"},
        )
    except Exception:
        return HttpResponse(status=502)
    if resp.status_code >= 400:
        return HttpResponse(status=404)
    content_type = resp.headers.get('Content-Type', 'image/jpeg')
    response = StreamingHttpResponse(resp.iter_content(chunk_size=8192), content_type=content_type)
    response['Cache-Control'] = 'public, max-age=86400'
    return response

class NhanVienForm(forms.ModelForm):
    CHUC_VU_CHOICES = [
        ('社長', '社長'),
        ('部長', '部長'),
        ('次長', '次長'),
        ('課長', '課長'),
        ('係長', '係長'),
        ('リーダー', 'リーダー'),
        ('技師', '技師'),
        ('他の', '他の'),
    ]
    chuc_vu = forms.ChoiceField(
        choices=[('', '---------')] + CHUC_VU_CHOICES,
        required=False,
        label='役職'
    )

    class Meta:
        model = NhanVien
        fields = ['ma_so', 'ten', 'email', 'chuc_vu', 'supervisor']
        labels = {
            'ma_so': '社員番号',
            'ten': '氏名',
            'email': 'メール',
            'chuc_vu': '役職',
            'supervisor': '上司'
        }

class CourseForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['start_date'].required = True
        self.fields['end_date'].required = True

    class Meta:
        model = Course
        fields = [
            'title', 'description', 'start_date', 'end_date', 'external_url', 'is_active',
            'price', 'duration', 'location', 'target', 'material'
        ]
        widgets = {
            'start_date': forms.DateInput(attrs={'type': 'date'}),
            'end_date': forms.DateInput(attrs={'type': 'date'}),
        }

    def clean_material(self):
        material = self.cleaned_data.get('material')
        if material:
            ext = material.name.split('.')[-1].lower()
            allowed_ext = ['pdf', 'xlsx', 'xls', 'jpg', 'jpeg', 'png', 'gif', 'bmp', 'webp']
            if ext not in allowed_ext:
                raise forms.ValidationError('PDF、Excel、または画像ファイル（.pdf, .xlsx, .xls, .jpg, .png等）のみアップロード可能です。')
        return material

class ReportForm(forms.ModelForm):
    class Meta:
        model = Enrollment
        fields = ['report_file']
        widgets = {
            'report_file': forms.FileInput(attrs={'accept': '.pdf,.xlsx,.xls'})
        }

@user_passes_test(lambda u: u.is_authenticated and u.username == 'kanri')
def nhanvien_create(request):
    if request.method == 'POST':
        form = NhanVienForm(request.POST)
        if form.is_valid():
            ma_so = form.cleaned_data['ma_so']
            if NhanVien.objects.filter(ma_so=ma_so).exists():
                form.add_error('ma_so', '社員番号が存在しています。')
            else:
                nhanvien = form.save()
                # Tạo user nếu chưa có
                if not User.objects.filter(username=ma_so).exists():
                    User.objects.create_user(username=ma_so, password='defaultpassword')
                messages.success(request, '新しい社員番号が作成されました。')
                return redirect('learn:nhanvien_list')
    else:
        form = NhanVienForm()
    return render(request, 'learn/nhanvien_create.html', {'form': form, 'title': '社員作成'})

@user_passes_test(lambda u: u.is_authenticated and u.username == 'kanri')
def nhanvien_update(request, pk):
    nv = get_object_or_404(NhanVien, pk=pk)
    if request.method == 'POST':
        form = NhanVienForm(request.POST, instance=nv)
        if form.is_valid():
            form.save()
            messages.success(request, '社員情報が更新されました。')
            return redirect('learn:nhanvien_list')
    else:
        form = NhanVienForm(instance=nv)
    return render(request, 'learn/nhanvien_create.html', {'form': form, 'title': '社員情報編集'})

@user_passes_test(lambda u: u.is_authenticated and u.username == 'kanri')
def nhanvien_delete(request, pk):
    nv = get_object_or_404(NhanVien, pk=pk)
    if request.method == 'POST':
        nv.delete()
        messages.success(request, '社員情報が削除されました。')
        return redirect('learn:nhanvien_list')
    return render(request, 'learn/nhanvien_confirm_delete.html', {'nhanvien': nv})

@user_passes_test(lambda u: u.is_authenticated and u.username == 'kanri')
def nhanvien_list(request):
    nhanvien_list = sorted(NhanVien.objects.all(), key=lambda x: int(x.ma_so))
    return render(request, 'learn/nhanvien_list.html', {'nhanvien_list': nhanvien_list})

@login_required_ma_nv
def course_create(request):
    if request.method == 'POST':
        # Đảm bảo truyền cả request.FILES vào form
        form = CourseForm(request.POST, request.FILES)
        if form.is_valid():
            course = form.save(commit=False)
            if request.user.is_authenticated:
                course.creator = request.user
            elif request.session.get('ma_nv'):
                user = User.objects.filter(username=request.session['ma_nv']).first()
                if user:
                    course.creator = user
                else:
                    messages.error(request, '社員コードが正しくありません。')
                    return redirect('learn:dangnhap')
            else:
                messages.error(request, '社員コードが正しくありません。')
                return redirect('learn:dangnhap')
            course.save()
            messages.success(request, "新しい研修・講習が作成されました。")
            return redirect('learn:course_list')
        else:
            messages.error(request, "入力内容に誤りがあります。下記のエラーを確認してください。")
    else:
        form = CourseForm()
    return render(request, 'learn/course_create.html', {'form': form, 'title': '研修・講習作成'})

@user_passes_test(lambda u: u.is_authenticated and u.username == 'kanri')
def course_update(request, pk):
    course = get_object_or_404(Course, pk=pk)
    if request.method == 'POST':
        form = CourseForm(request.POST, request.FILES, instance=course)
        if form.is_valid():
            # Cập nhật các trường khác
            for field in form.cleaned_data:
                if field != 'material':
                    setattr(course, field, form.cleaned_data[field])
            # Nếu có file mới, xóa file cũ và gán file mới
            if request.FILES.get('material'):
                if course.material:
                    course.material.delete(save=False)
                course.material = request.FILES['material']
            course.save()
            messages.success(request, '研修・講習情報が更新されました。')
            return redirect('learn:course_list')
    else:
        form = CourseForm(instance=course)
    return render(request, 'learn/course_create.html', {'form': form, 'title': '研修・講習編集'})

@user_passes_test(lambda u: u.is_authenticated and u.username == 'kanri')
def course_delete(request, pk):
    course = get_object_or_404(Course, pk=pk)
    if request.method == 'POST':
        course.delete()
        messages.success(request, '研修・講習が削除されました。')
        return redirect('learn:course_list')
    return render(request, 'learn/course_confirm_delete.html', {'course': course})

@login_required_ma_nv
def index(request):
    course_count = Course.objects.count()
    user_count = User.objects.count()
    completed_count = Enrollment.objects.filter(completed=True).count()
    return render(request, 'learn/index.html', {
        'course_count': course_count,
        'user_count': user_count,
        'completed_count': completed_count,
    })
@login_required_ma_nv
def course_list(request):
    query = request.GET.get('q', '')
    courses = Course.objects.all()
    if query:
        courses = courses.filter(
            Q(title__icontains=query) |
            Q(description__icontains=query) |
            Q(location__icontains=query) |
            Q(target__icontains=query)
        )
    now = timezone.now().date()
    for course in courses:
        if course.start_date:
            if now < course.start_date:
                course.status = 'active'
            else:
                course.status = 'expired'
        else:
            course.status = 'expired'
    # PHÂN TRANG: mỗi trang 10 khóa học
    paginator = Paginator(courses, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    # Gán tên người tạo + fetch thumbnail (chỉ xử lý backend)
    for course in page_obj:
        if course.creator:
            nv = NhanVien.objects.filter(ma_so=course.creator.username).first()
            course.creator_name = nv.ten if nv else "管理部"
        else:
            course.creator_name = "管理部"
        if course.external_url and not course.external_thumb_url:
            thumb_url = fetch_external_thumbnail(course.external_url)
            if thumb_url:
                course.external_thumb_url = thumb_url
                course.save(update_fields=['external_thumb_url'])

    # Xác định enrollments cần phê duyệt (giữ nguyên)
    enrollments_to_approve = Enrollment.objects.none()
    if request.user.is_authenticated and request.user.username == 'kanri':
        enrollments_to_approve = Enrollment.objects.filter(status='pending_kanri').select_related('user', 'course')
    elif request.session.get('ma_nv'):
        try:
            supervisor_ma_so = request.session['ma_nv']
            subordinates = NhanVien.objects.filter(supervisor__ma_so=supervisor_ma_so).values_list('ma_so', flat=True)
            enrollments_to_approve = Enrollment.objects.filter(status='pending_supervisor', user__username__in=subordinates).select_related('user', 'course')
        except:
            pass

    # Thêm ten cho user (giữ nguyên)
    for enrollment in enrollments_to_approve:
        try:
            nv = NhanVien.objects.get(ma_so=enrollment.user.username)
            enrollment.user.ten = nv.ten
        except NhanVien.DoesNotExist:
            enrollment.user.ten = '不明'
        # Gán tên người tạo cho khóa học trong danh sách duyệt
        if enrollment.course and enrollment.course.creator:
            nv_creator = NhanVien.objects.filter(ma_so=enrollment.course.creator.username).first()
            enrollment.course.creator_name = nv_creator.ten if nv_creator else "管理部"
        else:
            enrollment.course.creator_name = "管理部"

    # Xử lý phê duyệt (giữ nguyên)
    if request.method == 'POST' and enrollments_to_approve.exists():
        enrollment_id = request.POST.get('enrollment_id')
        action = request.POST.get('action')
        comment = request.POST.get('comment', '')
        enrollment = get_object_or_404(Enrollment, id=enrollment_id)
        if action == 'approve':
            if request.user.username == 'kanri' and enrollment.status == 'pending_kanri':
                enrollment.status = 'approved'
                enrollment.kanri_comment = comment
                acted_by = None  # kanri duyệt
            elif enrollment.status == 'pending_supervisor':
                enrollment.status = 'pending_kanri'
                enrollment.supervisor_comment = comment
                ma_nv = request.session.get('ma_nv')
                acted_by = None
                if ma_nv:
                    try:
                        acted_by = User.objects.get(username=ma_nv)
                    except User.DoesNotExist:
                        acted_by = None
        elif action == 'reject':
            if request.user.username == 'kanri' and enrollment.status == 'pending_kanri':
                enrollment.status = 'rejected_by_kanri'
                enrollment.kanri_comment = comment
                acted_by = None
            elif enrollment.status == 'pending_supervisor':
                enrollment.status = 'rejected_by_supervisor'
                enrollment.supervisor_comment = comment
                ma_nv = request.session.get('ma_nv')
                acted_by = None
                if ma_nv:
                    try:
                        acted_by = User.objects.get(username=ma_nv)
                    except User.DoesNotExist:
                        acted_by = None
            # Gửi mail cho nhân viên nếu muốn
            send_reject_notification(enrollment)
            messages.warning(request, '申請は今回は見送られました。')
        else:
            acted_by = None
        enrollment.save()
        ApprovalHistory.objects.create(
            enrollment=enrollment,
            action='reject_enrollment' if action == 'reject' else 'approve_enrollment',
            comment=comment,
            acted_by=acted_by
        )
        if action != 'reject':
            send_approval_notification(enrollment)
        return redirect('learn:course_list')

    # Enrollments của user hiện tại (giữ nguyên)
    user_enrollments = Enrollment.objects.filter(user__username=request.session.get('ma_nv', request.user.username)).select_related('course')

    # Kiểm tra xem có hiển thị bảng phê duyệt hay không
    show_approval_table = (
        (request.user.is_authenticated and request.user.username == 'kanri') or
        (request.session.get('ma_nv') and enrollments_to_approve.exists())
    )

    context = {
        'courses': page_obj,
        'enrollments_to_approve': enrollments_to_approve,
        'user_enrollments': user_enrollments,
        'search_query': query,
        'page_obj': page_obj,
        'show_approval_table': show_approval_table,
    }
    return render(request, 'learn/course_list.html', context)

@login_required_ma_nv
def enroll_course(request, course_id):
    # Nếu là kanri thì không cho phép đăng ký, thông báo và chuyển hướng
    if request.user.is_authenticated and request.user.username == 'kanri':
        messages.error(request, '管理部アカウントでは研修・講習を申請できません。ログアウトします。')
        logout(request)
        return redirect('learn:dangnhap')
    if request.method != 'POST':
        messages.error(request, '申請フォームからご登録ください。')
        return redirect('learn:course_list')
    course = get_object_or_404(Course, id=course_id)
    ma_nv = request.session.get('ma_nv')
    user = User.objects.filter(username=ma_nv).first()
    if not user:
        messages.error(request, '社員コードに対応するユーザーが存在しません。管理者へ連絡してください。')
        return redirect('learn:dangnhap')
    nv = NhanVien.objects.filter(ma_so=user.username).first()
    # Xử lý đặc biệt cho 係長
    if nv and nv.chuc_vu == '係長':
        status = 'pending_kanri'
        to_emails = []
        # Gửi cho bản thân
        if nv.email:
            to_emails.append(nv.email)
        # Gửi cho cấp trên (supervisor) nếu có
        supervisor_name = '未設定'
        if nv.supervisor and nv.supervisor.email:
            to_emails.append(nv.supervisor.email)
            supervisor_name = nv.supervisor.ten
        # Gửi cho kanri
        to_emails.append("kanri_2@hayashi-p.co.jp")
        subject = "【申請受付通知】係長の申請が管理部に送信されました"
        message = f"{nv.ten}さん（係長）の申請が管理部に送信されました。{supervisor_name}さんと管理部に通知されました。"
        send_mail(
            subject=subject,
            message=message,
            from_email=None,
            recipient_list=to_emails,
            fail_silently=False,
        )
    elif nv is None or nv.supervisor is None or not nv.supervisor.email:
        status = 'pending_kanri'
    else:
        status = 'pending_supervisor'
    q1_use_case = (request.POST.get('q1_use_case') or '').strip()
    q2_pre_issue = (request.POST.get('q2_pre_issue') or '').strip()
    q3_post_state = (request.POST.get('q3_post_state') or '').strip()
    q4_purpose_summary = (request.POST.get('q4_purpose_summary') or '').strip()
    if not all([q1_use_case, q2_pre_issue, q3_post_state, q4_purpose_summary]):
        messages.error(request, '申請には4つの質問すべての回答が必要です。')
        return redirect('learn:course_list')

    enrollment, created = Enrollment.objects.get_or_create(
        user=user,
        course=course,
        defaults={
            'status': status,
            'q1_use_case': q1_use_case,
            'q2_pre_issue': q2_pre_issue,
            'q3_post_state': q3_post_state,
            'q4_purpose_summary': q4_purpose_summary,
        }
    )
    if created and not (nv and nv.chuc_vu == '係長'):
        send_approval_notification(enrollment)
        messages.success(request, '申請を受け付けました。上司の承認をお待ちください。' if status == 'pending_supervisor' else '申請を受け付けました。管理部の承認をお待ちください。')
    elif created:
        messages.success(request, '申請を受け付けました。管理部の承認をお待ちください。')
    else:
        messages.info(request, '既に申請済みです。')
    return redirect('learn:course_list')


@login_required_ma_nv
def my_courses(request):
    user = request.user
    ma_so = request.session.get('ma_nv')
    query = request.GET.get('q', '')
    try:
        nhanvien = NhanVien.objects.get(ma_so=ma_so)
        has_subordinates = nhanvien.subordinates.exists()
    except NhanVien.DoesNotExist:
        nhanvien = None
        has_subordinates = False

    is_kanri = user.username == 'kanri'
    show_pending_reports = is_kanri or has_subordinates

    # --- XỬ LÝ UPLOAD BÁO CÁO ---
    if request.method == 'POST' and 'enrollment_id' in request.POST:
        enrollment_id = request.POST.get('enrollment_id')
        enrollment = get_object_or_404(Enrollment, id=enrollment_id, user__username=ma_so)
        if 'report_file' in request.FILES:
            if enrollment.report_file:
                enrollment.report_file.delete(save=False)
            enrollment.report_file = request.FILES['report_file']
        nv = NhanVien.objects.filter(ma_so=ma_so).first()
        if nv and (nv.chuc_vu == '係長' or not nv.supervisor or not nv.supervisor.email):
            enrollment.report_status = 'pending_kanri'
        else:
            enrollment.report_status = 'pending_supervisor'
        enrollment.save()
        send_report_approval_notification(enrollment)
        messages.success(request, 'レポートがアップロードされました。')

    # HIỂN THỊ ENROLLMENT
    if is_kanri:
        user_enrollments = Enrollment.objects.all().select_related('course', 'user')
    else:
        user_enrollments = Enrollment.objects.filter(
            user__username=ma_so,
            status='approved'
        ).select_related('course', 'user')
    
    if query:
        nv_ma_so_list = list(NhanVien.objects.filter(ten__icontains=query).values_list('ma_so', flat=True))
        user_enrollments = user_enrollments.filter(
            Q(course__title__icontains=query) |
            Q(course__description__icontains=query) |
            Q(course__location__icontains=query) |
            Q(course__target__icontains=query) |
            Q(user__username__icontains=query) |
            Q(user__first_name__icontains=query) |
            Q(user__last_name__icontains=query) |
            Q(user__username__in=nv_ma_so_list)
        )

    # LẤY DANH SÁCH BÁO CÁO CẦN PHÊ DUYỆT
    pending_reports = []
    if show_pending_reports:
        if is_kanri:
            pending_reports = Enrollment.objects.filter(
                report_status='pending_kanri'
            ).select_related('user', 'course')
        elif has_subordinates:
            sub_ma_so_list = list(nhanvien.subordinates.values_list('ma_so', flat=True))
            pending_reports = Enrollment.objects.filter(
                report_status='pending_supervisor',
                user__username__in=sub_ma_so_list
            ).exclude(report_file='').select_related('user', 'course')

    # Attach NhanVien to each enrollment for template access
    nhanvien_cache = {}
    for enrollment in user_enrollments:
        username = enrollment.user.username
        if username not in nhanvien_cache:
            try:
                nhanvien_cache[username] = NhanVien.objects.get(ma_so=username)
            except NhanVien.DoesNotExist:
                nhanvien_cache[username] = None
        enrollment.nhanvien = nhanvien_cache[username]
        if enrollment.course and enrollment.course.creator:
            creator = enrollment.course.creator.username
            if creator not in nhanvien_cache:
                try:
                    nhanvien_cache[creator] = NhanVien.objects.get(ma_so=creator)
                except NhanVien.DoesNotExist:
                    nhanvien_cache[creator] = None
            enrollment.course.creator_name = nhanvien_cache[creator].ten if nhanvien_cache[creator] else "管理部"
        else:
            enrollment.course.creator_name = "管理部"

    paginator = Paginator(user_enrollments, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    context = {
        'user_enrollments': page_obj,
        'page_obj': page_obj,
        'show_pending_reports': show_pending_reports,
        'pending_reports': pending_reports,
        'ma_so': ma_so,
        'nhanvien': nhanvien,
        'is_kanri': is_kanri,
        'has_subordinates': has_subordinates,
        'form': ReportForm(),
        'search_query': query,
    }
    return render(request, 'learn/my_courses.html', context)

def dangnhap_ma_nv(request):
    error = ''  # Khởi tạo error
    if request.method == 'POST':
        # Nếu đang login bằng kanri (Django user), logout trước khi login ma_nv.
        if request.user.is_authenticated:
            logout(request)
        ma_nv = request.POST.get('ma_nv')
        try:
            nhanvien = NhanVien.objects.get(ma_so=ma_nv)
            request.session['ma_nv'] = nhanvien.ma_so
            request.session['ten'] = nhanvien.ten
            return redirect('learn:index')
        except NhanVien.DoesNotExist:
            error = '社員コードが正しくありません。'
    return render(request, 'learn/dangnhap.html', {'error': error})

def logout_nv(request):
    request.session.pop('ma_nv', None)
    return redirect('learn:index')

@login_required_ma_nv
def issue_certificate(request, enrollment_id):
    if request.user.is_authenticated and request.user.username == 'kanri':
        enrollment = get_object_or_404(Enrollment, id=enrollment_id)
    else:
        enrollment = get_object_or_404(Enrollment, id=enrollment_id, user__username=request.session['ma_nv'])
    if not enrollment.completed:
        messages.error(request, '研修・講習が完了していません。')
        return redirect('learn:my_courses')
    Certificate.objects.get_or_create(enrollment=enrollment, defaults={'issued_date': timezone.now()})
    messages.success(request, '証明書が発行されました。')
    return redirect('learn:my_certificates')


@user_passes_test(lambda u: u.is_authenticated and u.username == 'kanri')
def training_report(request):
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="training_report.csv"'
    writer = csv.writer(response)
    writer.writerow(['社員コード', '名前', '研修・講習', '完了', '完了日'])
    for enrollment in Enrollment.objects.select_related('user', 'course'):
        nv = NhanVien.objects.filter(ma_so=enrollment.user.username).first()
        writer.writerow([
            nv.ma_so if nv else '',
            nv.ten if nv else '',
            enrollment.course.title,
            'はい' if enrollment.completed else 'いいえ',
            enrollment.completed_date.strftime('%Y-%m-%d') if enrollment.completed_date else ''
        ])
    return response

@login_required_ma_nv
def mark_completed(request, enrollment_id):
    if request.user.is_authenticated and request.user.username == 'kanri':
        enrollment = get_object_or_404(Enrollment, id=enrollment_id)
    else:
        enrollment = get_object_or_404(Enrollment, id=enrollment_id, user__username=request.session['ma_nv'])
    enrollment.completed = True
    enrollment.completed_date = timezone.now()
    enrollment.save()
    messages.success(request, '研修・講習が完了としてマークされました。')
    return redirect('learn:my_courses')

def logout_admin(request):
    logout(request)
    return redirect('learn:index')

def login_admin(request):
    return redirect(reverse('login') + '?next=' + reverse('learn:index'))

@login_required_ma_nv
def approve_enrollments(request):
    if request.user.is_authenticated and request.user.username == 'kanri':
        # Kanri xem tất cả pending_kanri
        enrollments = Enrollment.objects.filter(status='pending_kanri').select_related('user', 'course')
    else:
        # Supervisor xem pending_supervisor của subordinates
        try:
            supervisor_ma_so = request.session['ma_nv']
            subordinates = NhanVien.objects.filter(supervisor__ma_so=supervisor_ma_so).values_list('ma_so', flat=True)
            enrollments = Enrollment.objects.filter(status='pending_supervisor', user__username__in=subordinates).select_related('user', 'course')
        except:
            enrollments = Enrollment.objects.none()
    
    if request.method == 'POST':
        enrollment_id = request.POST.get('enrollment_id')
        action = request.POST.get('action')
        comment = request.POST.get('comment', '')
        enrollment = get_object_or_404(Enrollment, id=enrollment_id)
        if action == 'approve':
            if request.user.username == 'kanri' and enrollment.status == 'pending_kanri':
                enrollment.status = 'approved'
                enrollment.kanri_comment = comment  # Lưu comment của 管理者
            elif enrollment.status == 'pending_supervisor':
                enrollment.status = 'pending_kanri'
                enrollment.supervisor_comment = comment  # Lưu comment của 上司
        elif action == 'reject':
            if request.user.username == 'kanri':
                enrollment.kanri_comment = comment
            else:
                enrollment.supervisor_comment = comment
        enrollment.save()
        return redirect('learn:approve_enrollments')
    return render(request, 'learn/approve_enrollments.html', {'enrollments': enrollments})

def send_approval_notification(enrollment):
    """
    承認依頼の通知メールを送信（日本語）
    """
    nv = NhanVien.objects.filter(ma_so=enrollment.user.username).first()
    if enrollment.status == 'pending_supervisor':
        # 上司へ送信
        if nv and nv.supervisor and nv.supervisor.email:
            to_email = nv.supervisor.email
            subject = "【承認依頼】新しい申請が届きました"
            message = f"{nv.ten}さんから新しい申請があります。システムでご確認ください。"
            send_mail(
                subject=subject,
                message=message,
                from_email=None,
                recipient_list=[to_email],
                fail_silently=False,
            )
        # Gửi cho nhân viên biết đã gửi lên cấp trên
        if nv and nv.email:
            subject = "【申請受付通知】申請が上司に送信されました"
            message = f"{nv.ten}さん、申請が上司（{nv.supervisor.ten if nv.supervisor else '未設定'}）に送信されました。承認をお待ちください。"
            send_mail(
                subject=subject,
                message=message,
                from_email=None,
                recipient_list=[nv.email],
                fail_silently=False,
            )
    elif enrollment.status == 'pending_kanri':
        # 管理部へ送信
        to_email = "kanri_2@hayashi-p.co.jp"
        subject = "【承認依頼】新しい申請が上司から承認されました"
        message = f"{nv.ten}さんの申請が上司に承認されました。システムでご確認ください。"
        send_mail(
            subject=subject,
            message=message,
            from_email=None,
            recipient_list=[to_email],
            fail_silently=False,
        )
        # Gửi cho nhân viên biết đã được cấp trên duyệt, chờ kanri
        if nv and nv.email:
            subject = "【申請進捗通知】上司が申請を承認しました"
            message = f"{nv.ten}さん、上司が申請を承認しました。現在、管理部の最終承認をお待ちください。"
            send_mail(
                subject=subject,
                message=message,
                from_email=None,
                recipient_list=[nv.email],
                fail_silently=False,
            )
    elif enrollment.status == 'approved':
        # Gửi cho nhân viên và cấp trên khi kanri phê duyệt xong
        if nv and nv.email:
            subject = "【申請承認通知】申請が最終承認されました"
            message = f"{nv.ten}さんの申請が管理部により承認されて、申し込みを完了しました。案内が届くまでしばらくお待ちください。"
            send_mail(
                subject=subject,
                message=message,
                from_email=None,
                recipient_list=[nv.email],
                fail_silently=False,
            )
        if nv and nv.supervisor and nv.supervisor.email:
            subject = "【部下の申請承認通知】申請が最終承認されました"
            message = f"{nv.ten}さんの申請が管理部により最終承認されました。"
            send_mail(
                subject=subject,
                message=message,
                from_email=None,
                recipient_list=[nv.supervisor.email],
                fail_silently=False,
            )

from django.shortcuts import render, get_object_or_404
from .models import Enrollment

def approval_history(request, enrollment_id):
    enrollment = get_object_or_404(Enrollment, id=enrollment_id)
    histories = enrollment.histories.order_by('-acted_at')
    return render(request, 'learn/approval_history.html', {
        'enrollment': enrollment,
        'histories': histories,
    })

from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from .models import ApprovalHistory
from django.core.paginator import Paginator

def approval_history_list(request):
    # Nếu là kanri (admin)
    if request.user.is_authenticated and request.user.username == 'kanri':
        histories = ApprovalHistory.objects.select_related('enrollment', 'acted_by', 'enrollment__user', 'enrollment__course').order_by('-acted_at')
    # Nếu đăng nhập bằng mã số nhân viên
    elif request.session.get('ma_nv'):
        ma_nv = request.session['ma_nv']
        try:
            user = User.objects.get(username=ma_nv)
            histories = ApprovalHistory.objects.select_related('enrollment', 'acted_by', 'enrollment__user', 'enrollment__course') \
                .filter(enrollment__user=user).order_by('-acted_at')
        except User.DoesNotExist:
            histories = []
    else:
        # Nếu chưa đăng nhập, chuyển về trang đăng nhập
        return redirect('learn:dangnhap')

    q = request.GET.get('q', '').strip()
    if q:
        # Tìm các mã số nhân viên có tên phù hợp
        nv_ma_so_list = list(NhanVien.objects.filter(ten__icontains=q).values_list('ma_so', flat=True))
        histories = histories.filter(
            Q(enrollment__course__title__icontains=q) |
            Q(enrollment__user__username__icontains=q) |
            Q(enrollment__user__first_name__icontains=q) |
            Q(enrollment__user__last_name__icontains=q) |
            Q(enrollment__user__username__in=nv_ma_so_list)
        )

    # --- PHÂN TRANG: mỗi trang 15 dòng ---
    paginator = Paginator(histories, 15)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    nhanviens = list(NhanVien.objects.all())
    return render(request, 'learn/approval_history_list.html', {
        'histories': page_obj,
        'page_obj': page_obj,
        'search_query': q,
        'nhanviens': nhanviens,  # Thêm dòng này
    })

from django.shortcuts import redirect, get_object_or_404
from django.contrib.auth.decorators import login_required

@login_required_ma_nv
def approve_report_supervisor(request, enrollment_id):
    enrollment = get_object_or_404(Enrollment, id=enrollment_id)
    if request.method == 'POST':
        # Xử lý file upload
        if 'report_file' in request.FILES:
            if enrollment.report_file:
                enrollment.report_file.delete(save=False)
            enrollment.report_file = request.FILES['report_file']
        enrollment.report_status = 'pending_kanri'
        enrollment.report_approved_by_supervisor = True  # Cập nhật trạng thái
        enrollment.report_supervisor_approved_at = timezone.now()
        enrollment.report_supervisor_comment = request.POST.get('comment', '')
        enrollment.save()
        # Lấy đúng User acted_by
        ma_nv = request.session.get('ma_nv')
        acted_by = None
        if ma_nv:
            try:
                acted_by = User.objects.get(username=ma_nv)
            except User.DoesNotExist:
                acted_by = None
        ApprovalHistory.objects.create(
            enrollment=enrollment,
            action='approve_report',
            comment=enrollment.report_supervisor_comment,
            acted_by=acted_by
        )
        send_report_approval_notification(enrollment)  # Gửi mail cho 管理部
    return redirect('learn:my_courses')

@login_required
def approve_report_kanri(request, enrollment_id):
    enrollment = get_object_or_404(Enrollment, id=enrollment_id)
    if request.method == 'POST':
        # Xử lý file upload
        if 'report_file' in request.FILES:
            if enrollment.report_file:
                enrollment.report_file.delete(save=False)
            enrollment.report_file = request.FILES['report_file']
        enrollment.report_status = 'approved'
        enrollment.report_approved_by_kanri = True  # Cập nhật trạng thái
        enrollment.report_kanri_approved_at = timezone.now()
        enrollment.report_kanri_comment = request.POST.get('comment', '')
        enrollment.save()
        ApprovalHistory.objects.create(
            enrollment=enrollment,
            action='approve_report',
            comment=enrollment.report_kanri_comment,
            acted_by=None  # Luôn là None để hiện 管理部
        )
        send_report_approval_notification(enrollment)  # Gửi mail cho người liên quan nếu cần
    return redirect('learn:my_courses')

@user_passes_test(lambda u: u.is_authenticated and u.username == 'kanri')
def delete_report_file(request, enrollment_id):
    enrollment = get_object_or_404(Enrollment, id=enrollment_id)
    if enrollment.report_file:
        # Xóa file vật lý
        file_path = enrollment.report_file.path
        enrollment.report_file.delete(save=False)
        if os.path.exists(file_path):
            os.remove(file_path)
        # Reset trạng thái phê duyệt báo cáo
        enrollment.report_approved_by_supervisor = False
        enrollment.report_approved_by_kanri = False
        enrollment.save()
        messages.success(request, 'レポートファイルが削除されました。')
    else:
        messages.warning(request, 'レポートファイルがありません。')
    return redirect('learn:my_courses')

from django.shortcuts import get_object_or_404
from django.http import HttpResponseForbidden

@login_required_ma_nv
def course_edit(request, pk):
    course = get_object_or_404(Course, pk=pk)
    # Chỉ cho phép kanri hoặc người tạo
    if not (request.user.username == 'kanri' or course.creator == request.user):
        return HttpResponseForbidden("権限がありません。")
    if request.method == 'POST':
        form = CourseForm(request.POST, instance=course)
        if form.is_valid():
            form.save()
            return redirect('learn:course_list')
    else:
        form = CourseForm(instance=course)
    return render(request, 'learn/course_create.html', {'form': form, 'title': '研修・講習編集'})

@login_required_ma_nv
def bangcap_list(request):
    if request.user.is_authenticated and request.user.username == 'kanri':
        bangcaps = BangCap.objects.select_related('nhan_vien').all()
    else:
        ma_nv = request.session.get('ma_nv')
        nhanvien = NhanVien.objects.get(ma_so=ma_nv)
        bangcaps = BangCap.objects.filter(nhan_vien=nhanvien)
    query = request.GET.get('q', '')
    radar_data = None
    radar_labels = []
    radar_values = []
    radar_levels = []
    selected_nv = None

    if query:
        bangcaps = bangcaps.filter(
            models.Q(loai_bang__icontains=query) |
            models.Q(cap_do__icontains=query) |
            models.Q(ghi_chu__icontains=query) |
            models.Q(nhan_vien__ten__icontains=query)
        )
        nv = NhanVien.objects.filter(ten__icontains=query).first()
        if nv:
            selected_nv = nv
            caps = BangCap.objects.filter(nhan_vien=nv)
            radar_labels = [loai for loai, _ in BangCap.LOAI_BANG]
            radar_values = [caps.filter(loai_bang=loai).count() for loai in radar_labels]
            cap_do_order = {'特急': 5, '1級': 4, '2級': 3, '3級': 2, '4級': 1}
            radar_levels = []
            for loai in radar_labels:
                cap_list = list(caps.filter(loai_bang=loai).values_list('cap_do', flat=True))
                max_level = max([cap_do_order.get(c, 0) for c in cap_list], default=0)
                radar_levels.append(max_level)
            radar_data = {
                'labels': radar_labels,
                'values': radar_values,
                'levels': radar_levels,
            }

    # Thêm đoạn này để truyền bangcaps dạng list dict cho JS thống kê tổng thể
    bangcaps_list = list(
        bangcaps.values('id', 'loai_bang', 'cap_do', 'nhan_vien__ten')
    )

    return render(request, 'learn/bangcap_list.html', {
        'bangcaps': bangcaps,
        'search_query': query,
        'radar_data': radar_data,
        'selected_nv': selected_nv,
        'bangcaps_list': bangcaps_list,  # <-- thêm dòng này
    })

@login_required_ma_nv
def bangcap_upload(request):
    ma_nv = request.session.get('ma_nv')
    nhanvien = NhanVien.objects.get(ma_so=ma_nv)
    if request.method == 'POST':
        form = BangCapForm(request.POST, request.FILES)
        if form.is_valid():
            bangcap = form.save(commit=False)
            bangcap.nhan_vien = nhanvien
            bangcap.save()
            messages.success(request, '資格証明書をアップロードしました。')
            return redirect('learn:bangcap_list')
    else:
        form = BangCapForm()
    return render(request, 'learn/bangcap_upload.html', {'form': form})

@login_required_ma_nv
def bangcap_edit(request, pk):
    bangcap = get_object_or_404(BangCap, pk=pk)
    if request.method == 'POST':
        form = BangCapForm(request.POST, request.FILES, instance=bangcap)
        if form.is_valid():
            form.save()
            messages.success(request, '資格証明書を更新しました。')
            return redirect('learn:bangcap_list')
    else:
        form = BangCapForm(instance=bangcap)
    return render(request, 'learn/bangcap_edit.html', {'form': form, 'bangcap': bangcap})

@login_required_ma_nv
def bangcap_delete(request, pk):
    bangcap = get_object_or_404(BangCap, pk=pk)
    if request.method == 'POST':
        bangcap.delete()
        messages.success(request, '資格証明書を削除しました。')
        return redirect('learn:bangcap_list')
    return render(request, 'learn/bangcap_delete_confirm.html', {'bangcap': bangcap})

@login_required_ma_nv
def bangcap_detail(request, pk):
    bangcap = get_object_or_404(BangCap, pk=pk)
    return render(request, 'learn/bangcap_detail.html', {'bangcap': bangcap})

def send_report_approval_notification(enrollment):
    nv = NhanVien.objects.filter(ma_so=enrollment.user.username).first()
    # Nếu là 係長 (kakarichou) hoặc không có supervisor, gửi thẳng cho kanri
    if nv and (nv.chuc_vu == '係長' or not nv.supervisor or not nv.supervisor.email):
        to_emails = []
        if nv.email:
            to_emails.append(nv.email)
        if nv.supervisor and nv.supervisor.email:
            to_emails.append(nv.supervisor.email)
        to_emails.append("kanri_2@hayashi-p.co.jp")
        subject = "【レポート提出通知】係長または上司未設定のレポートが提出されました"
        message = f"{nv.ten}さん（{nv.chuc_vu}）のレポートが提出されました。"
        send_mail(subject, message, from_email=None, recipient_list=to_emails, fail_silently=False)
        return

    # pending_supervisor: gửi cho supervisor và nhân viên
    if enrollment.report_status == 'pending_supervisor':
        if nv and nv.supervisor and nv.supervisor.email:
            subject = "【レポート承認依頼】新しいレポートが提出されました"
            message = f"{nv.ten}さんから新しいレポートが提出されました。システムでご確認ください。"
            send_mail(subject, message, from_email=None, recipient_list=[nv.supervisor.email], fail_silently=False)
        if nv and nv.email:
            subject = "【レポート受付通知】レポートが上司に送信されました"
            message = f"{nv.ten}さん、レポートが上司（{nv.supervisor.ten if nv.supervisor else '未設定'}）に送信されました。承認をお待ちください。"
            send_mail(subject, message, from_email=None, recipient_list=[nv.email], fail_silently=False)

    # pending_kanri: gửi cho kanri và nhân viên
    elif enrollment.report_status == 'pending_kanri':
        to_email = "kanri_2@hayashi-p.co.jp"
        subject = "【レポート承認依頼】上司がレポートを承認しました"
        message = f"{nv.ten}さんのレポートが上司に承認されました。システムでご確認ください。"
        send_mail(subject, message, from_email=None, recipient_list=[to_email], fail_silently=False)
        if nv and nv.email:
            subject = "【レポート進捗通知】上司がレポートを承認しました"
            message = f"{nv.ten}さん、上司がレポートを承認しました。現在、管理部の最終承認をお待ちください。"
            send_mail(subject, message, from_email=None, recipient_list=[nv.email], fail_silently=False)

    # approved: gửi cho nhân viên và supervisor
    elif enrollment.report_status == 'approved':
        if nv and nv.email:
            subject = "【レポート承認通知】レポートが最終承認されました"
            message = f"{nv.ten}さんのレポートが管理部により最終承認されました。"
            send_mail(subject, message, from_email=None, recipient_list=[nv.email], fail_silently=False)
        if nv and nv.supervisor and nv.supervisor.email:
            subject = "【部下のレポート承認通知】レポートが最終承認されました"
            message = f"{nv.ten}さんのレポートが管理部により最終承認されました。"
            send_mail(subject, message, from_email=None, recipient_list=[nv.supervisor.email], fail_silently=False)

def send_reject_notification(enrollment):
    nv = NhanVien.objects.filter(ma_so=enrollment.user.username).first()
    if nv and nv.email:
        subject = "【申請通知】申請は今回は見送られました。"
        if enrollment.status == 'rejected_by_supervisor':
            message = f"{nv.ten}さんの申請は今回は見送られました。説明: {enrollment.supervisor_comment}"
        elif enrollment.status == 'rejected_by_kanri':
            message = f"{nv.ten}さんの申請は今回は見送られました。説明: {enrollment.kanri_comment}"
        else:
            message = f"{nv.ten}さんの申請は今回は見送られました。"
        send_mail(
            subject=subject,
            message=message,
            from_email=None,
            recipient_list=[nv.email],
            fail_silently=False,
        )

@user_passes_test(lambda u: u.is_authenticated and u.username == 'kanri')
def quote_list(request):
    quotes = MotivationalQuote.objects.all().order_by('-created_at')
    if request.method == 'POST':
        form = MotivationalQuoteForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "名言が追加されました。")
            return redirect('learn:quote_list')
    else:
        form = MotivationalQuoteForm()
    return render(request, 'learn/quote_list.html', {'quotes': quotes, 'form': form})

@user_passes_test(lambda u: u.is_authenticated and u.username == 'kanri')
def quote_delete(request, pk):
    quote = get_object_or_404(MotivationalQuote, pk=pk)
    quote.delete()
    messages.success(request, "名言が削除されました。")
    return redirect('learn:quote_list')



