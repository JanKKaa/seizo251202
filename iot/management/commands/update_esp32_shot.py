from django.core.management.base import BaseCommand
from iot.views import update_esp32_shot


class Command(BaseCommand):
    help = "Tự động cộng dồn shot cho MoldLifetime từ ESP32"

    def handle(self, *args, **options):
        update_esp32_shot()
        self.stdout.write(self.style.SUCCESS("Đã cập nhật shot ESP32 tự động!"))