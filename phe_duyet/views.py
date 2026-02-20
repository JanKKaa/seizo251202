from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.utils import timezone
from django.http import FileResponse, HttpResponse
from .forms import DocumentForm, ApprovalForm, MessageForm, RejectionForm, DocumentUpdateFileForm
from .models import Document, Approval, Message, Comment
from django.contrib.auth.models import User
from django.db import IntegrityError
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.core.mail import send_mail
from django.db.models import Case, When, IntegerField, BooleanField
from django.template.loader import get_template, render_to_string
from xhtml2pdf import pisa
from weasyprint import HTML
from django.conf import settings
@login_required
def index(request):
    if request.method == 'POST':
        document_id = request.POST.get('document_id')
        comment_text = request.POST.get('comment')
        document = get_object_or_404(Document, id=document_id)
        
        # アクセス権を確認
        if document.recipient != request.user and document.created_by != request.user and not request.user.is_superuser:
            raise PermissionDenied

        comment = Comment(document=document, user=request.user, text=comment_text)
        comment.save()
        messages.success(request, 'コメントが追加されました。')
        return redirect('phe_duyet:index')
    
    # スーパーユーザーはすべてのドキュメントを表示可能
    if request.user.is_superuser:
        documents = Document.objects.all()
    else:
        # 通常のユーザーはアクセス可能なドキュメントのみを表示
        documents = Document.objects.filter(recipient=request.user) | Document.objects.filter(created_by=request.user)

    # Sắp xếp: Ưu tiên các tài liệu có trạng thái "確認中"
    documents = documents.annotate(
        is_pending=Case(
            When(approvals__approved=False, approvals__rejected=False, then=0),  # "確認中" được ưu tiên (giá trị 0)
            default=1,  # Các trạng thái khác (giá trị 1)
            output_field=IntegerField()
        )
    ).order_by('is_pending', '-submission_date')  # Sắp xếp theo "確認中" trước, sau đó theo ngày nộp mới nhất

    paginator = Paginator(documents, 5)  # 1ページに最大5つのドキュメントを表示

    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    approve_button_count = sum(1 for document in page_obj if document.approvals.filter(approved=False, rejected=False, approver=request.user).exists())

    unread_messages_count = Message.objects.filter(recipient=request.user, read=False).count()
    return render(request, 'phe_duyet/index.html', {
        'page_obj': page_obj,
        'unread_messages_count': unread_messages_count,
        'approve_button_count': approve_button_count,
    })

@login_required
def create_document(request):
    if request.method == 'POST':
        form = DocumentForm(request.POST, request.FILES, user=request.user)
        if form.is_valid():
            document = form.save(commit=False)
            document.created_by = request.user
            document.save()

            # Kiểm tra xem người nhận có email hay không
            recipient_email = document.recipient.email
            if recipient_email:
                # メール通知を送信
                subject = '新しい承認リクエスト'
                message = f"""
                {document.recipient.last_name} 様、

                {request.user.last_name} から新しい承認リクエストがあります。
                詳細を確認するにはシステムにログインしてください。

                よろしくお願いいたします。
                承認管理システム
                """
                send_mail(subject, message, 'pts@hayashi-p.co.jp', [recipient_email])

            messages.success(request, '承認リクエストが作成されました。')
            if recipient_email:
                messages.info(request, '通知メールが送信されました。')
            else:
                messages.warning(request, '通知メールは送信されませんでした。受信者のメールアドレスがありません。')
            return redirect('phe_duyet:index')
    else:
        form = DocumentForm(user=request.user)
    return render(request, 'phe_duyet/create_document.html', {'form': form})

@login_required
def approve_document(request, document_id):
    document = get_object_or_404(Document, id=document_id)
    
    # アクセス権を確認
    if document.recipient != request.user and document.created_by != request.user and not request.user.is_superuser:
        raise PermissionDenied

    form = None  # フォーム変数を初期化
    
    if request.method == 'POST':
        if 'approve' in request.POST:
            form = ApprovalForm(request.POST)
            if form.is_valid():
                if request.FILES.get('approved_file'):
                    try:
                        approval, created = Approval.objects.get_or_create(
                            document=document,
                            approver=request.user,
                            defaults={'approved': True, 'approved_at': timezone.now()}
                        )
                        if not created:
                            approval.approved = True
                            approval.approved_at = timezone.now()
                            approval.save()
                        document.approved_by = request.user
                        document.approved_at = timezone.now()
                        document.approved_file = request.FILES['approved_file']
                        document.save()
                        messages.success(request, 'ドキュメントが承認され、正常にアップロードされました。')
                        return redirect('phe_duyet:approve_document', document_id=document_id)
                    except IntegrityError:
                        approval = Approval.objects.get(document=document, approver=request.user)
                        approval.approved = True
                        approval.approved_at = timezone.now()
                        approval.save()
                        document.approved_by = request.user
                        document.approved_at = timezone.now()
                        document.approved_file = request.FILES['approved_file']
                        document.save()
                        messages.success(request, 'ドキュメントが承認され、正常にアップロードされました。')
                        return redirect('phe_duyet:approve_document', document_id=document_id)
                else:
                    messages.error(request, '承認済みのドキュメントをアップロードしてください。')
        elif 'reject' in request.POST:
            form = RejectionForm(request.POST)
            if form.is_valid():
                try:
                    approval, created = Approval.objects.get_or_create(
                        document=document,
                        approver=request.user,
                        defaults={'rejected': True, 'rejected_at': timezone.now()}
                    )
                    if not created:
                        approval.rejected = True
                        approval.rejected_at = timezone.now()
                        approval.save()
                    messages.success(request, 'ドキュメントが拒否されました。')
                    return redirect('phe_duyet:rejection_notice', document_id=document_id)
                except IntegrityError:
                    approval = Approval.objects.get(document=document, approver=request.user)
                    approval.rejected = True
                    approval.rejected_at = timezone.now()
                    approval.save()
                    messages.success(request, 'ドキュメントが拒否されました。')
                    return redirect('phe_duyet:rejection_notice', document_id=document_id)
    
    # POSTリクエストでない場合、またはフォームがNoneの場合にデフォルトフォームを割り当てる
    if form is None:
        form = ApprovalForm() if 'approve' in request.POST else RejectionForm()

    return render(request, 'phe_duyet/approve_document.html', {'document': document, 'form': form})

@login_required
def rejection_notice(request, document_id):
    document = get_object_or_404(Document, id=document_id)
    return render(request, 'phe_duyet/rejection_notice.html', {'document': document})

@login_required
def upload_approved_file(request, document_id):
    document = get_object_or_404(Document, id=document_id)
    
    # Kiểm tra quyền truy cập
    if document.recipient != request.user and document.created_by != request.user and not request.user.is_superuser:
        raise PermissionDenied

    if request.method == 'POST' and request.FILES.get('approved_file'):
        document.approved_file = request.FILES['approved_file']
        document.save()
        messages.success(request, 'ドキュメントが正常にアップロードされました。')
    return redirect('phe_duyet:approve_document', document_id=document_id)

@login_required
def view_document(request, document_id):
    document = get_object_or_404(Document, id=document_id)
    
    # Kiểm tra quyền truy cập
    if document.recipient != request.user and document.created_by != request.user and not request.user.is_superuser:
        raise PermissionDenied

    return render(request, 'phe_duyet/view_document.html', {'document': document})

@login_required
def download_document(request, document_id):
    document = get_object_or_404(Document, id=document_id)
    
    # Kiểm tra quyền truy cập
    if document.recipient != request.user and document.created_by != request.user and not request.user.is_superuser:
        raise PermissionDenied

    response = FileResponse(document.file.open(), as_attachment=True)
    return response

@login_required
def approval_list(request):
    documents = Document.objects.all()
    return render(request, 'phe_duyet/index.html', {'documents': documents})

@login_required
def send_message(request):
    if request.method == 'POST':
        form = MessageForm(request.POST)
        if form.is_valid():
            message = form.save(commit=False)
            message.sender = request.user
            message.save()
            messages.success(request, 'メッセージが送信されました。')
            return redirect('phe_duyet:inbox')
    else:
        form = MessageForm()
    return render(request, 'phe_duyet/send_message.html', {'form': form})

@login_required
def inbox(request):
    received_messages = Message.objects.filter(recipient=request.user)
    sent_messages = Message.objects.filter(sender=request.user)
    unread_messages_count = Message.objects.filter(recipient=request.user, read=False).count()
    return render(request, 'phe_duyet/inbox.html', {
        'received_messages': received_messages,
        'sent_messages': sent_messages,
        'unread_messages_count': unread_messages_count,
    })

@login_required
def manage_messages(request):
    unread_messages_count = Message.objects.filter(recipient=request.user, read=False).count()
    return render(request, 'phe_duyet/manage_messages.html', {
        'unread_messages_count': unread_messages_count,
    })

@login_required
def delete_message(request, message_id):
    message = get_object_or_404(Message, id=message_id)
    if message.sender == request.user or message.recipient == request.user:
        message.delete()
        messages.success(request, 'メッセージが削除されました。')
    else:
        messages.error(request, 'このメッセージを削除する権限がありません。')
    return redirect('phe_duyet:inbox')

@login_required
@user_passes_test(lambda u: u.is_superuser)
def delete_document(request, document_id):
    document = get_object_or_404(Document, id=document_id)
    document.delete()
    messages.success(request, 'ドキュメントが削除されました。')
    return redirect('phe_duyet:index')

from django.core.mail import send_mail
from django.shortcuts import get_object_or_404, redirect
from django.contrib import messages
from .models import Document

def send_reminder_email(request, document_id):
    document = get_object_or_404(Document, id=document_id)

    # Kiểm tra quyền của người dùng
    if not request.user.is_authenticated or not request.user.is_superuser:
        messages.error(request, "メールを送信する権限がありません。")
        return redirect('phe_duyet:index')

    # Gửi email nhắc nhở
    if document.recipient:
        subject = f"【リマインダー】ドキュメント承認のお願い: {document.title}"
        message = f"""
        {document.recipient.first_name} {document.recipient.last_name} 様,

        ドキュメント「{document.title}」の承認がまだ完了していません。
        以下のリンクから承認をお願いいたします。

        ドキュメントリンク: {"https://192.168.10.250"}

        よろしくお願いいたします。
        """
        recipient_email = document.recipient.email

        try:
            send_mail(subject, message, 'pts@hayashi-p.co.jp', [recipient_email])
            messages.success(request, "リマインダーメールを送信しました。")
        except Exception as e:
            messages.error(request, f"メール送信中にエラーが発生しました: {str(e)}")
    else:
        messages.error(request, "承認者が設定されていません。")

    return redirect('phe_duyet:index')

@login_required
def export_pdf(request):
    documents = Document.objects.all()
    html_string = render_to_string('phe_duyet/export_pdf.html', {'documents': documents})
    pdf_file = HTML(string=html_string, base_url=request.build_absolute_uri()).write_pdf()
    response = HttpResponse(pdf_file, content_type='application/pdf')
    response['Content-Disposition'] = 'attachment; filename="documents.pdf"'
    return response

import csv
from django.http import HttpResponse
from .models import Document

@login_required
def export_csv(request):
    # Tạo HTTP response với header cho file CSV
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="documents.csv"'

    # Tạo writer cho file CSV
    writer = csv.writer(response)
    writer.writerow(['ID', 'Title', 'Submission Date', 'Created By', 'Recipient', 'Status'])

    # Lấy dữ liệu từ model Document
    documents = Document.objects.all()
    for document in documents:
        status = '承認' if document.is_approved else '不承認' if document.is_rejected else '確認中'
        writer.writerow([
            document.id,
            document.title,
            document.submission_date,
            f"{document.created_by.first_name} {document.created_by.last_name}",
            f"{document.recipient.first_name} {document.recipient.last_name}" if document.recipient else "N/A",
            status
        ])

    return response

@login_required
def update_document_file(request, document_id):
    document = get_object_or_404(Document, id=document_id)
    # Chỉ cho phép người tạo, recipient hoặc superuser sửa file
    if document.created_by != request.user and document.recipient != request.user and not request.user.is_superuser:
        raise PermissionDenied

    if request.method == 'POST':
        form = DocumentUpdateFileForm(request.POST, request.FILES, instance=document)
        if form.is_valid():
            form.save()
            messages.success(request, 'ファイルが差し替えられました。')
            return redirect('phe_duyet:index')
    else:
        form = DocumentUpdateFileForm(instance=document)
    return render(request, 'phe_duyet/update_document_file.html', {'form': form, 'document': document})