from django.core.management.base import BaseCommand
from iot.net100shot import update_all_net100_shots

class Command(BaseCommand):
    help = 'Cập nhật dữ liệu Net100CycleShot từ runtime index'

    def handle(self, *args, **kwargs):
        result = update_all_net100_shots()
        self.stdout.write(self.style.SUCCESS(result))