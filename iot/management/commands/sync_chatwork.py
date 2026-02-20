from django.core.management.base import BaseCommand
import requests
import re
from datetime import datetime
from ...models import ChatworkMessage
from django.utils import timezone

CHATWORK_TOKEN = '91460d38143a3128bfad65e4b2e9a993'
ROOM_IDS = ['264687873', '292318431']  # Thêm các ROOM_ID bạn muốn

class Command(BaseCommand):
    help = 'Đồng bộ tin nhắn Chatwork về database'

    def handle(self, *args, **kwargs):
        headers = {'X-ChatWorkToken': CHATWORK_TOKEN}
        total_count = 0
        for room_id in ROOM_IDS:
            url = f'https://api.chatwork.com/v2/rooms/{room_id}/messages'
            try:
                res = requests.get(url, headers=headers, timeout=20)
                self.stdout.write(f'Phòng {room_id}: Status {res.status_code}, Nội dung trả về: "{res.text}"')
                if res.ok and res.text.strip():
                    count = 0
                    for msg in res.json():
                        body = extract_text_only(msg.get('body', ''))
                        message_id = str(msg.get('message_id', ''))
                        sender = msg.get('account', {}).get('name', '') or msg.get('account', {}).get('username', '')
                        send_time = msg.get('send_time', 0)
                        dt = datetime.fromtimestamp(send_time) if send_time else datetime.now()
                        aware_dt = timezone.make_aware(dt)
                        if not ChatworkMessage.objects.filter(message_id=message_id).exists():
                            ChatworkMessage.objects.create(
                                message_id=message_id,
                                message=body,
                                sender=sender,
                                time=aware_dt,
                            )
                            count += 1
                    total_count += count
                    self.stdout.write(self.style.SUCCESS(f'Phòng {room_id}: Đã thêm {count} tin nhắn mới vào DB.'))
                else:
                    self.stdout.write(self.style.ERROR(
                        f'Phòng {room_id}: Lỗi API: {res.status_code} - {res.text}'
                    ))
            except Exception as e:
                self.stdout.write(self.style.ERROR(
                    f'Phòng {room_id}: Lỗi khi kết nối Chatwork: {e}\nNội dung trả về: {getattr(res, "text", "")}'
                ))
        self.stdout.write(self.style.SUCCESS(f'Tổng số tin nhắn mới đã thêm: {total_count}'))

def extract_text_only(text):
    return re.sub(r'\[info\]\[title\]\[dtext:file_uploaded\].*?\[/info\]', '', text, flags=re.DOTALL).strip()