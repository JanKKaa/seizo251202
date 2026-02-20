from django.core.management.base import BaseCommand
from iot.views import update_mold_shot

class Command(BaseCommand):
    help = 'Tự động cộng dồn shot cho MoldLifetime'

    def handle(self, *args, **kwargs):
        update_mold_shot()
        self.stdout.write(self.style.SUCCESS('Đã cập nhật shot tự động!'))