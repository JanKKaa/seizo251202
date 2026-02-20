from django.core.management.base import BaseCommand
from django.utils import timezone
from django.core.mail import send_mail
from django.conf import settings
from menu.models import FaxStatus, Order, Holiday
from datetime import datetime, time, timedelta
import sys

class Command(BaseCommand):
    help = "Send reminder mail at 15:30 if next working day's fax has not been sent."

    def add_arguments(self, parser):
        parser.add_argument('--date', type=str, default=None)
        parser.add_argument('--force', action='store_true')

    def handle(self, *args, **options):
        self.stdout.write(f"[DEBUG] Python: {sys.executable}")
        self.stdout.write(f"[DEBUG] TZ: {settings.TIME_ZONE} USE_TZ={settings.USE_TZ}")

        # Ngày cơ sở (hôm nay hoặc --date)
        if options['date']:
            try:
                d_base = datetime.strptime(options['date'], "%Y-%m-%d").date()
            except ValueError:
                self.stderr.write("Invalid --date format.")
                return
        else:
            d_base = timezone.localdate()
        self.stdout.write(f"[DEBUG] Base date: {d_base}")

        holidays = set(Holiday.objects.values_list('date', flat=True))

        # Tìm ngày làm việc kế tiếp
        next_d = d_base + timedelta(days=1)
        while next_d.weekday() >= 5 or next_d in holidays:
            next_d += timedelta(days=1)
        d = next_d  # d là ngày cần FAX (ngày giao của đơn)
        self.stdout.write(f"[DEBUG] Target working day (FAX for): {d}")

        # Không dùng cơ chế STOP weekend/holiday cũ nữa
        skip_original_stop = True  # cờ để bỏ qua return cũ

        # (GIỮ NGUYÊN CODE GỐC – chỉ sửa điều kiện để không return)
        if d.weekday() >= 5 and not skip_original_stop:
            self.stdout.write("[STOP] Weekend")
            return
        if d in holidays and not skip_original_stop:
            self.stdout.write("[STOP] Holiday")
            return

        now_local = timezone.localtime()
        self.stdout.write(f"[DEBUG] Now: {now_local}")
        if not options['force']:
            # Cutoff vẫn dựa trên hôm nay (d_base) lúc 15:30
            if now_local.date() < d_base or (now_local.date() == d_base and now_local.time() < time(15, 30)):
                self.stdout.write("[STOP] Not past cutoff (15:30 today)")
                return

        order_count = Order.objects.filter(ngay_giao=d).count()
        self.stdout.write(f"[DEBUG] Orders for target day {d}: {order_count}")
        if not order_count:
            self.stdout.write("[STOP] No orders for target day")
            return

        fs = FaxStatus.objects.filter(ngay=d).first()
        if fs and fs.sent:
            self.stdout.write("[STOP] Already marked sent for target day")
            return

        subject = "【お弁当表システム】"
        message = (
            f"{d.strftime('%Y/%m/%d')}（次営業日）のFAX送信が未実施です。\n"
            f"本日中にFAX送信を実施し、画面で送信済みを記録してください。\n"
        )
        from_email = settings.DEFAULT_FROM_EMAIL
        recipients = ['kanri_2@hayashi-p.co.jp', 'giang@hayashi-p.co.jp']
        self.stdout.write(f"[DEBUG] Sending mail from {from_email} to {recipients}")
        try:
            sent = send_mail(subject, message, from_email, recipients, fail_silently=False)
            self.stdout.write(f"[OK] send_mail returned {sent}")
        except Exception as e:
            self.stderr.write(f"[ERROR] {e}")