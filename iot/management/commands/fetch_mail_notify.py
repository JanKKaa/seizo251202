from django.core.management.base import BaseCommand
from django.core.mail import send_mail
import imaplib, email, re
from email.utils import parseaddr
from django.utils import timezone
from django.conf import settings
from iot.models import DashboardNotification
from email.parser import BytesParser
from iot.models import MailLog  # Import MailLog model

now = timezone.localtime()

IMAP_HOST = getattr(settings, 'EMAIL_HOST', 'smtp.gmail.com')
IMAP_USER = getattr(settings, 'EMAIL_HOST_USER', '')
IMAP_PASS = getattr(settings, 'EMAIL_HOST_PASSWORD', '')
MAILBOX = 'INBOX'

POP3_HOST = getattr(settings, 'POP3_HOST', 'pop.gmail.com')  # legacy, no longer used
POP3_PORT = 995  # legacy, no longer used
POP3_USER = IMAP_USER  # legacy, no longer used
POP3_PASS = IMAP_PASS  # legacy, no longer used

def parse_mail_content(content):
    import unicodedata
    lines = [unicodedata.normalize('NFKC', l).strip() for l in content.strip().splitlines()]
    print("==== DEBUG LINES ====")
    for idx, l in enumerate(lines):
        print(f"{idx}: [{l}]")
    # Tìm block đầu tiên bắt đầu bằng 'post' (không phân biệt hoa thường)
    start = None
    for idx, l in enumerate(lines):
        if l.strip().lower() == 'post':
            start = idx
            break
    if start is None:
        print("==== NO POST FOUND ====")
        return []

    # Chỉ lấy block đầu tiên cho đến khi gặp dòng 'post' tiếp theo hoặc hết file
    block = []
    for l in lines[start:]:
        if l.strip().lower() == 'post' and len(block) > 0:
            break
        block.append(l)
    lines = block

    def _extract_after(label, line):
        if not line.startswith(label):
            return None
        rest = line[len(label):].lstrip()
        if rest.startswith(':') or rest.startswith('：'):
            rest = rest[1:]
        return rest.strip()

    def _find_label_block(text, label):
        idx = text.find(label)
        if idx == -1:
            return None
        rest = text[idx + len(label):].lstrip()
        if rest.startswith(':') or rest.startswith('：'):
            rest = rest[1:]
        # cắt trước label tiếp theo nếu có
        for nxt in ['時間', 'レベル', '内容']:
            if nxt == label:
                continue
            nidx = rest.find(nxt)
            if nidx != -1:
                rest = rest[:nidx]
                break
        return rest.strip()

    message = ''
    times = []
    level = 1  # Mặc định là 1
    for line in lines[1:]:
        if line.startswith('内容'):
            extracted = _extract_after('内容', line)
            if extracted is not None:
                message = extracted
        elif line.startswith('時間'):
            extracted = _extract_after('時間', line)
            if extracted:
                # CHỈ nhận dạng 14:15, 21:45, ... (bỏ "now" và giờ đơn lẻ)
                for t in re.finditer(r'(\d{1,2}):(\d{1,2})', extracted):
                    hour = int(t.group(1))
                    minute = int(t.group(2))
                    times.append(('time', (hour, minute)))
        elif line.startswith('レベル'):
            extracted = _extract_after('レベル', line)
            if extracted:
                try:
                    level = int(extracted)
                except Exception:
                    level = 1
    # Fallback: nếu nội dung nằm cùng một dòng hoặc format không chuẩn
    if not message or not times:
        joined = " ".join(lines)
        if not message:
            extracted = _find_label_block(joined, '内容')
            if extracted:
                message = extracted
            elif len(lines) > 1:
                # フォールバック: 1行目(内容行)をそのまま使う
                raw = lines[1].strip()
                message = re.sub(r'^(内容[:：]?\s*)', '', raw).strip()
        if not times:
            time_part = _find_label_block(joined, '時間')
            if time_part:
                for t in re.finditer(r'(\d{1,2}):(\d{1,2})', time_part):
                    hour = int(t.group(1))
                    minute = int(t.group(2))
                    times.append(('time', (hour, minute)))
            else:
                # フォールバック: 内容行以外から時間を拾う
                for line in lines[1:]:
                    if line == lines[1] and '時間' not in line:
                        continue
                    for t in re.finditer(r'(\d{1,2}):(\d{1,2})', line):
                        hour = int(t.group(1))
                        minute = int(t.group(2))
                        times.append(('time', (hour, minute)))
        if 'レベル' in joined:
            extracted = _find_label_block(joined, 'レベル')
            if extracted:
                try:
                    level = int(extracted)
                except Exception:
                    level = 1

    # Quy định thời gian theo level
    level_duration = {1: 120, 2: 300, 3: 500}
    duration = level_duration.get(level, 120)
    priority = level
    is_alarm = (priority == 3)

    notifs = []
    now = timezone.localtime()  # Giờ JST nếu đã cấu hình TIME_ZONE
    for t in times:
        if t[0] == 'time' and t[1] is not None:
            hour, minute = t[1]
            # Kiểm tra giá trị hour và minute hợp lệ
            if isinstance(hour, int) and 0 <= hour <= 23 and isinstance(minute, int) and 0 <= minute <= 59:
                appear_at = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
                if appear_at < now:
                    appear_at += timezone.timedelta(days=1)
            else:
                continue  # Bỏ qua nếu giá trị không hợp lệ
        else:
            continue
        expire_at = appear_at + timezone.timedelta(seconds=duration)
        notifs.append(dict(
            message=message,
            priority=priority,
            is_alarm=is_alarm,
            appear_at=appear_at,
            expire_at=expire_at
        ))
    print("==== PARSED NOTIF LIST ====")
    print(notifs)
    return notifs

def fetch_and_save_notifications():
    # Xóa thông báo hết hạn trước khi xử lý mail mới
    DashboardNotification.objects.filter(expire_at__lt=timezone.now()).delete()

    mail = imaplib.IMAP4_SSL(IMAP_HOST)
    mail.login(IMAP_USER, IMAP_PASS)
    mail.select(MAILBOX)
    status, data = mail.search(None, 'UNSEEN')
    if status != 'OK' or not data or not data[0]:
        status, data = mail.search(None, 'ALL')
    if status != 'OK':
        mail.logout()
        return
    mail_ids = data[0].split()
    target_ids = mail_ids[-10:] if len(mail_ids) > 10 else mail_ids
    for mail_id in target_ids:
        status, msg_data = mail.fetch(mail_id, '(RFC822)')
        if status != 'OK' or not msg_data:
            continue
        raw_email = msg_data[0][1]
        msg = BytesParser().parsebytes(raw_email)
        sender = msg.get('From', '')
        subject = msg.get('Subject', '')
        received_at = msg.get('Date', '')
        mail_uid = f"{sender}|{subject}|{received_at}"  # Tạo UID đơn giản
        # Kiểm tra đã xử lý chưa
        if not MailLog.objects.filter(mail_uid=mail_uid).exists():
            content = None
            if msg.is_multipart():
                for part in msg.walk():
                    ctype = part.get_content_type()
                    if ctype == 'text/plain':
                        content = part.get_payload(decode=True).decode(part.get_content_charset() or 'utf-8', errors='ignore')
                        break
                    elif ctype == 'text/html' and content is None:
                        content = part.get_payload(decode=True).decode(part.get_content_charset() or 'utf-8', errors='ignore')
            else:
                content = msg.get_payload(decode=True).decode(msg.get_content_charset() or 'utf-8', errors='ignore')
            if content:
                # HELPメール: 本文が「help」の場合は使い方を返信
                def _normalize_help_text(text):
                    import unicodedata
                    norm = unicodedata.normalize('NFKC', text or '')
                    norm = re.sub(r'\s+', '', norm).lower()
                    return norm

                def _strip_html(text):
                    return re.sub(r'<[^>]+>', ' ', text or '')

                raw_text = _normalize_help_text(content)
                first_line = next((l.strip() for l in content.splitlines() if l.strip()), "")
                subject_lower = _normalize_help_text(subject or "")
                first_line_norm = _normalize_help_text(first_line)
                html_norm = _normalize_help_text(_strip_html(content))

                if raw_text == 'help' or first_line_norm == 'help' or subject_lower == 'help' or html_norm == 'help':
                    sender_email = parseaddr(sender)[1]
                    if sender_email:
                        help_subject = "IoT通知メールの送信方法（書式）"
                        help_body = (
                            "下記の書式で送信してください。\n\n"
                            "【例】\n"
                            "Post\n"
                            "内容：2026年3月17日 16:00\n"
                            "時間：16:15 16:00\n"
                            "レベル：1\n\n"
                            "【ルール】\n"
                            "・1行目は「Post」\n"
                            "・「内容」「時間」「レベル」は日本語でOK（全角コロン：も可）\n"
                            "・時間は HH:MM 形式で複数指定できます\n"
                            "・レベルは 1/2/3（3はアラーム）\n"
                            "・レベルに応じて表示時間が変わります：\n"
                            "　- レベル1：120秒\n"
                            "　- レベル2：300秒\n"
                            "　- レベル3：500秒（アラーム扱い）\n"
                        )
                        try:
                            send_mail(help_subject, help_body, None, [sender_email])
                        except Exception:
                            pass
                    MailLog.objects.create(
                        mail_uid=mail_uid,
                        sender=sender,
                        subject=subject,
                        received_at=timezone.now(),
                        processed=True
                    )
                    continue
                print("==== MAIL CONTENT ====")
                print(content)
                print("==== CALLING parse_mail_content ====")
                notif_list = parse_mail_content(content.strip())
                print("==== PARSED NOTIF LIST ====")
                print(notif_list)
                if notif_list:
                    for notif in notif_list:
                        notif['sender'] = sender
                        DashboardNotification.objects.create(**notif)
            # Lưu log
            MailLog.objects.create(
                mail_uid=mail_uid,
                sender=sender,
                subject=subject,
                received_at=timezone.now(),
                processed=True
            )
    mail.logout()

def print_last_emails(n=5):
    mail = imaplib.IMAP4_SSL(IMAP_HOST)
    mail.login(IMAP_USER, IMAP_PASS)
    mail.select(MAILBOX)
    status, data = mail.search(None, 'ALL')
    if status != 'OK':
        mail.logout()
        return
    mail_ids = data[0].split()
    print(f"Tổng số email: {len(mail_ids)}")
    target_ids = mail_ids[-n:] if len(mail_ids) > n else mail_ids
    for mail_id in target_ids:
        status, msg_data = mail.fetch(mail_id, '(RFC822)')
        if status != 'OK' or not msg_data:
            continue
        raw_email = msg_data[0][1]
        msg = BytesParser().parsebytes(raw_email)
        try:
            mail_id_label = mail_id.decode()
        except Exception:
            mail_id_label = str(mail_id)
        print(f"\n--- Email ID {mail_id_label} ---")
        print("Subject:", msg.get('Subject'))
        print("From:", msg.get('From'))
        print("Date:", msg.get('Date'))
        # In nội dung text/plain hoặc text/html
        if msg.is_multipart():
            for part in msg.walk():
                ctype = part.get_content_type()
                if ctype == 'text/plain' or ctype == 'text/html':
                    content = part.get_payload(decode=True).decode(part.get_content_charset() or 'utf-8', errors='ignore')
                    print(f"Nội dung ({ctype}):\n", content)
        else:
            ctype = msg.get_content_type()
            content = msg.get_payload(decode=True).decode(msg.get_content_charset() or 'utf-8', errors='ignore')
            print(f"Nội dung ({ctype}):\n", content)
    mail.logout()

class Command(BaseCommand):
    help = 'Fetch dashboard notifications from email'

    def handle(self, *args, **options):
        fetch_and_save_notifications()
        self.stdout.write(self.style.SUCCESS('Fetched mail notifications.'))
        print_last_emails(1)
