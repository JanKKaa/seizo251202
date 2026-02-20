import sys
import os
import django
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.append(project_root)
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'seizo0.settings')
django.setup()

from django.core.management.base import BaseCommand
from iot.tasks import fetch_device_data

class Command(BaseCommand):
    help = 'Fetch device data and save to cache'

    def handle(self, *args, **options):
        fetch_device_data()
        self.stdout.write(self.style.SUCCESS('Fetched device data successfully.'))