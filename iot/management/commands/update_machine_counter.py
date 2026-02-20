from django.core.management.base import BaseCommand
from iot.views import update_machine_counter

class Command(BaseCommand):
    help = 'Cập nhật shot_total cho tất cả máy từ JSW'

    def handle(self, *args, **options):
        update_machine_counter()