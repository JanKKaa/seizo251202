from django.core.management.base import BaseCommand
import imaplib, email, re
from django.utils import timezone
from iot.models import DashboardNotification
import poplib
from email.parser import BytesParser
from iot.models import MailLog  # Import MailLog model

now = timezone.localtime()

IMAP_HOST = 'sv10181.xserver.jp'
IMAP_USER = 'pts@hayashi-p.co.jp'
IMAP_PASS = '798701ht'
MAILBOX = 'INBOX'

POP3_HOST = 'sv10181.xserver.jp'
POP3_PORT = 995
POP3_USER = 'pts@hayashi-p.co.jp'
POP3_PASS = '798701ht'

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

    message = ''
    times = []
    level = 1  # Mặc định là 1
    for line in lines[1:]:
        if line.startswith('内容:'):
            message = line.split('内容:', 1)[1].strip()
        elif line.startswith('時間:'):
            time_part = line.split('時間:', 1)[1].strip()
            # CHỈ nhận dạng 14:15, 21:45, ... (bỏ "now" và giờ đơn lẻ)
            for m in re.finditer(r'(\d{1,2}):(\d{1,2})', time_part):
                hour = int(m.group(1))
                minute = int(m.group(2))
                times.append(('time', (hour, minute)))
        elif line.startswith('レベル:'):
            try:
                level = int(line.split('レベル:', 1)[1].strip())
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

    mail = poplib.POP3_SSL(POP3_HOST, POP3_PORT)
    mail.user(POP3_USER)
    mail.pass_(POP3_PASS)
    num_messages = len(mail.list()[1])
    for i in range(max(0, num_messages-2), num_messages):
        raw_email = b"\n".join(mail.retr(i+1)[1])
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
    mail.quit()

def print_last_emails(n=5):
    mail = poplib.POP3_SSL(POP3_HOST, POP3_PORT)
    mail.user(POP3_USER)
    mail.pass_(POP3_PASS)
    num_messages = len(mail.list()[1])
    print(f"Tổng số email: {num_messages}")
    for i in range(max(0, num_messages-n), num_messages):
        raw_email = b"\n".join(mail.retr(i+1)[1])
        msg = BytesParser().parsebytes(raw_email)
        print(f"\n--- Email thứ {i+1} ---")
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
    mail.quit()

class Command(BaseCommand):
    help = 'Fetch dashboard notifications from email'

    def handle(self, *args, **options):
        fetch_and_save_notifications()
        self.stdout.write(self.style.SUCCESS('Fetched mail notifications.'))
        print_last_emails(1)
