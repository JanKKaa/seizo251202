from django.test import TestCase
from django.urls import reverse
from django.contrib.auth import get_user_model
from unittest.mock import patch

from .models import Esp32CardSnapshot, Machine, Mold, MoldLifetime
from .views import _update_esp32_machine_total, _update_machine_lifetime_counter, _update_mold_lifetime_counter, update_esp32_shot


class MachineLifetimeCounterTests(TestCase):
    def setUp(self):
        self.machine = Machine.objects.create(address="test-counter", name="Test machine")

    def test_first_counter_value_is_used_as_baseline(self):
        delta = _update_machine_lifetime_counter(self.machine, 95)
        self.machine.refresh_from_db()
        self.assertEqual(delta, 0)
        self.assertEqual(self.machine.last_shot, 95)
        self.assertEqual(self.machine.shot_total, 0)

    def test_counter_increase_adds_full_delta(self):
        self.machine.last_shot = 95
        self.machine.shot_total = 1000
        self.machine.save(update_fields=["last_shot", "shot_total"])
        delta = _update_machine_lifetime_counter(self.machine, 101)
        self.machine.refresh_from_db()
        self.assertEqual(delta, 6)
        self.assertEqual(self.machine.shot_total, 1006)

    def test_counter_reset_adds_new_counter_value(self):
        self.machine.last_shot = 4404
        self.machine.shot_total = 1000
        self.machine.save(update_fields=["last_shot", "shot_total"])
        delta = _update_machine_lifetime_counter(self.machine, 3)
        self.machine.refresh_from_db()
        self.assertEqual(delta, 3)
        self.assertEqual(self.machine.shot_total, 1003)


class Esp32MachineTotalShotTests(TestCase):
    def setUp(self):
        mold = Mold.objects.create(name="ESP32 running mold", code="ESP-MOLD-01")
        self.lifetime = MoldLifetime.objects.create(
            mold=mold,
            esp32_machine="ESP-M01",
            total_shot=100,
            lifetime=100000,
            last_shot=10,
        )
        self.snapshot = Esp32CardSnapshot.objects.create(address="ESP-M01", shot=16)

    def test_machine_total_uses_same_delta_as_running_mold(self):
        update_esp32_shot()
        self.lifetime.refresh_from_db()
        self.snapshot.refresh_from_db()
        self.assertEqual(self.lifetime.total_shot, 106)
        self.assertEqual(self.snapshot.total_shot, 16)

        update_esp32_shot()
        self.snapshot.refresh_from_db()
        self.assertEqual(self.snapshot.total_shot, 16)

    def test_machine_total_continues_after_esp32_counter_reset(self):
        update_esp32_shot()
        self.snapshot.shot = 2
        self.snapshot.save(update_fields=["shot"])
        update_esp32_shot()
        self.lifetime.refresh_from_db()
        self.snapshot.refresh_from_db()
        self.assertEqual(self.lifetime.total_shot, 108)
        self.assertEqual(self.snapshot.total_shot, 18)

    def test_machine_total_counts_without_mold_name_mapping(self):
        snapshot = Esp32CardSnapshot.objects.create(address="UNMAPPED-ESP", shot=120)
        delta = _update_esp32_machine_total(snapshot)
        snapshot.refresh_from_db()
        self.assertEqual(delta, 120)
        self.assertEqual(snapshot.total_shot, 120)

        snapshot.shot = 127
        snapshot.save(update_fields=["shot"])
        delta = _update_esp32_machine_total(snapshot)
        snapshot.refresh_from_db()
        self.assertEqual(delta, 7)
        self.assertEqual(snapshot.total_shot, 127)

    @patch("iot.views.requests.get", side_effect=RuntimeError("NET100 offline in test"))
    def test_machine_counter_page_shows_esp32_when_net100_is_unavailable(self, _mock_get):
        self.snapshot.total_shot = 12345
        self.snapshot.primary_product = "製品ESP"
        self.snapshot.save(update_fields=["total_shot", "primary_product"])
        response = self.client.get(reverse("iot:machine_counter"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "ESP32 ESP-M01")
        self.assertContains(response, "12,345")
        self.assertContains(response, "製品ESP")

    def test_superuser_can_create_edit_and_delete_esp32_counter(self):
        admin = get_user_model().objects.create_superuser(username="iot-admin", password="pw", email="iot@example.com")
        self.client.force_login(admin)

        response = self.client.post(
            reverse("iot:esp32_counter_create"),
            {
                "address": "CRUD-ESP",
                "primary_product": "製品A",
                "shot": "120",
                "total_shot": "5000",
                "cycletime": "12.5",
            },
        )
        self.assertRedirects(response, reverse("iot:machine_counter"))
        snapshot = Esp32CardSnapshot.objects.get(address="CRUD-ESP")
        self.assertEqual(snapshot.total_shot, 5000)
        self.assertEqual(snapshot.last_counted_shot, 120)

        response = self.client.post(
            reverse("iot:esp32_counter_edit", args=[snapshot.pk]),
            {
                "address": "CRUD-ESP",
                "primary_product": "製品B",
                "shot": "150",
                "total_shot": "4800",
                "cycletime": "13.0",
            },
        )
        self.assertRedirects(response, reverse("iot:machine_counter"))
        snapshot.refresh_from_db()
        self.assertEqual(snapshot.primary_product, "製品B")
        self.assertEqual(snapshot.total_shot, 4800)
        self.assertEqual(snapshot.last_counted_shot, 150)

        response = self.client.get(reverse("iot:esp32_counter_delete", args=[snapshot.pk]))
        self.assertEqual(response.status_code, 200)
        response = self.client.post(reverse("iot:esp32_counter_delete", args=[snapshot.pk]))
        self.assertRedirects(response, reverse("iot:machine_counter"))
        self.assertFalse(Esp32CardSnapshot.objects.filter(pk=snapshot.pk).exists())

    def test_non_superuser_cannot_change_esp32_counter(self):
        response = self.client.post(
            reverse("iot:esp32_counter_create"),
            {"address": "BLOCKED-ESP", "shot": "1", "total_shot": "1", "cycletime": ""},
        )
        self.assertEqual(response.status_code, 302)
        self.assertFalse(Esp32CardSnapshot.objects.filter(address="BLOCKED-ESP").exists())


class MoldLifetimeCounterTests(TestCase):
    def setUp(self):
        mold = Mold.objects.create(name="Pinion gear mold", code="50171-00111-04")
        self.lifetime = MoldLifetime.objects.create(
            mold=mold,
            condname="pinion gear",
            total_shot=0,
            lifetime=1_000_000,
            last_shot=0,
        )

    def test_first_counter_value_is_used_as_baseline(self):
        delta = _update_mold_lifetime_counter(self.lifetime, 95)

        self.lifetime.refresh_from_db()
        self.assertEqual(delta, 0)
        self.assertEqual(self.lifetime.last_shot, 95)
        self.assertEqual(self.lifetime.total_shot, 0)

    def test_counter_increase_adds_full_delta(self):
        self.lifetime.last_shot = 95
        self.lifetime.save(update_fields=["last_shot"])

        delta = _update_mold_lifetime_counter(self.lifetime, 99)

        self.lifetime.refresh_from_db()
        self.assertEqual(delta, 4)
        self.assertEqual(self.lifetime.last_shot, 99)
        self.assertEqual(self.lifetime.total_shot, 4)

    def test_counter_reset_adds_new_counter_value(self):
        self.lifetime.total_shot = 100
        self.lifetime.last_shot = 4404
        self.lifetime.save(update_fields=["total_shot", "last_shot"])

        delta = _update_mold_lifetime_counter(self.lifetime, 3)

        self.lifetime.refresh_from_db()
        self.assertEqual(delta, 3)
        self.assertEqual(self.lifetime.last_shot, 3)
        self.assertEqual(self.lifetime.total_shot, 103)
