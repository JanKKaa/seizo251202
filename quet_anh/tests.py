from decimal import Decimal

from django.contrib.auth.models import User
from django.http import QueryDict
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .forms import QAMaterialOutStockLedgerForm, QAMaterialStockLedgerForm
from .models import (
    QADeviceInfo,
    QAMaterialMaster,
    QAMaterialOutStockLedger,
    QAMaterialStockLedger,
    QATabletDevice,
    QATabletInspection,
)
from .views import _extract_stock_in_lot_rows


class QAOutstockProductChoiceTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="qa-user", password="pass")

    def _set_today_tenken(self):
        tablet = QATabletDevice.objects.create(code="TAB-01", name="QA Tablet 01")
        QATabletInspection.objects.create(
            tablet=tablet,
            check_type=QATabletInspection.CHECK_STARTUP,
            check_date=timezone.localdate(),
            camera_ok=True,
            qr_sample_ok=True,
            ocr_sample_ok=True,
            network_ok=True,
            workstation_ok=True,
            result=QATabletInspection.RESULT_OK,
        )
        session = self.client.session
        session["qa_tablet_id"] = tablet.id
        session.save()
        return tablet

    def test_index_marks_same_machine_multiple_products_for_choice(self):
        QADeviceInfo.objects.create(
            name="MC-01",
            material="ABS",
            material_code="ABS-1",
            product="Product A",
            outstock_auto_input_enabled=True,
        )
        QADeviceInfo.objects.create(
            name="MC-01",
            material="ABS",
            material_code="ABS-2",
            product="Product B",
            outstock_auto_input_enabled=True,
        )

        self.client.force_login(self.user)
        self._set_today_tenken()
        response = self.client.get(reverse("index_qa"))

        self.assertEqual(response.status_code, 200)
        machine_options = response.context["outstock_machine_options"]
        mc01 = next(item for item in machine_options if item["machine_name"] == "MC-01")
        self.assertTrue(mc01["needs_product_choice"])
        self.assertEqual(len(mc01["devices"]), 2)

    def test_index_requires_tablet_tenken_before_use(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse("index_qa"))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "quet_anh/tablet_tenken_gate.html")

    def test_index_allows_selected_tablet_after_today_tenken(self):
        self.client.force_login(self.user)
        tablet = self._set_today_tenken()
        response = self.client.get(reverse("index_qa"))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "quet_anh/index_qa.html")
        self.assertEqual(response.context["selected_tablet"], tablet)

    def test_admin_pc_mode_skips_tablet_tenken_after_selection(self):
        admin = User.objects.create_superuser(username="admin", password="pass")

        self.client.force_login(admin)
        gate_response = self.client.get(reverse("index_qa"))

        self.assertEqual(gate_response.status_code, 200)
        self.assertTemplateUsed(gate_response, "quet_anh/tablet_tenken_gate.html")
        self.assertTrue(gate_response.context["can_admin_bypass_tablet_tenken"])

        select_response = self.client.post(
            reverse("tablet_select"),
            {"admin_pc_mode": "1", "next": reverse("index_qa")},
        )

        self.assertEqual(select_response.status_code, 302)
        response = self.client.get(reverse("index_qa"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "quet_anh/index_qa.html")
        self.assertIsNone(response.context["selected_tablet"])

    def test_non_admin_cannot_use_admin_pc_mode(self):
        self.client.force_login(self.user)
        response = self.client.post(
            reverse("tablet_select"),
            {"admin_pc_mode": "1", "next": reverse("index_qa")},
        )

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "quet_anh/tablet_tenken_gate.html")
        self.assertFalse(self.client.session.get("qa_tablet_admin_bypass"))

    def test_device_list_marks_duplicate_machine_and_product(self):
        first = QADeviceInfo.objects.create(name="MC-01", material="ABS", material_code="ABS-1", product="Product A")
        second = QADeviceInfo.objects.create(name="MC-01", material="ABS", material_code="ABS-2", product="Product A")
        third = QADeviceInfo.objects.create(name="MC-02", material="PP", material_code="PP-1", product="Product A")

        self.client.force_login(self.user)
        response = self.client.get(reverse("qa_device_list"))

        self.assertEqual(response.status_code, 200)
        rows = {item.id: item for item in response.context["device_list"]}
        self.assertEqual(rows[first.id].duplicate_level, "machine_product")
        self.assertEqual(rows[second.id].duplicate_level, "machine_product")
        self.assertEqual(rows[third.id].duplicate_level, "")

    def test_device_list_marks_duplicate_machine_only(self):
        first = QADeviceInfo.objects.create(name="MC-01", material="ABS", material_code="ABS-1", product="Product A")
        second = QADeviceInfo.objects.create(name="MC-01", material="PP", material_code="PP-1", product="Product B")

        self.client.force_login(self.user)
        response = self.client.get(reverse("qa_device_list"))

        self.assertEqual(response.status_code, 200)
        rows = {item.id: item for item in response.context["device_list"]}
        self.assertEqual(rows[first.id].duplicate_level, "machine")
        self.assertEqual(rows[second.id].duplicate_level, "machine")

    def test_material_inventory_orders_by_stock_then_movement_frequency(self):
        today = timezone.localdate()

        for code, name in [
            ("HIGH", "High Stock"),
            ("MID-A", "Mid Stock Low Movement"),
            ("MID-B", "Mid Stock High Movement"),
            ("LOW", "Low Stock"),
        ]:
            QAMaterialMaster.objects.create(
                material_code=code,
                material_name=name,
                bag_weight_kg=Decimal("10.00"),
                qr_content=f"QR-{code}",
            )

        QAMaterialStockLedger.objects.create(
            material_code="HIGH", material_name="High Stock", stock_in_date=today, weight_kg=Decimal("100.00")
        )
        QAMaterialOutStockLedger.objects.create(
            material_code="HIGH", material_name="High Stock", stock_out_date=today, weight_kg=Decimal("10.00")
        )
        QAMaterialStockLedger.objects.create(
            material_code="MID-A", material_name="Mid Stock Low Movement", stock_in_date=today, weight_kg=Decimal("50.00")
        )
        QAMaterialStockLedger.objects.create(
            material_code="MID-B", material_name="Mid Stock High Movement", stock_in_date=today, weight_kg=Decimal("60.00")
        )
        QAMaterialOutStockLedger.objects.create(
            material_code="MID-B", material_name="Mid Stock High Movement", stock_out_date=today, weight_kg=Decimal("10.00")
        )
        QAMaterialStockLedger.objects.create(
            material_code="LOW", material_name="Low Stock", stock_in_date=today, weight_kg=Decimal("20.00")
        )
        QAMaterialOutStockLedger.objects.create(
            material_code="LOW", material_name="Low Stock", stock_out_date=today, weight_kg=Decimal("15.00")
        )

        self.client.force_login(self.user)
        response = self.client.get(reverse("material_inventory_dashboard"))

        self.assertEqual(response.status_code, 200)
        ordered_codes = [row["material_code"] for row in response.context["rows"]]
        self.assertEqual(ordered_codes[:4], ["HIGH", "MID-B", "MID-A", "LOW"])

    def test_stock_in_lot_number_is_required_server_side(self):
        post_data = QueryDict(mutable=True)
        post_data.setlist("input_weight", ["25"])
        post_data.setlist("lot_color", [QAMaterialStockLedger.LOT_COLOR_GREEN])
        post_data.setlist("lot_number", [""])

        raw_rows, parsed_rows, total_weight, error = _extract_stock_in_lot_rows(post_data)

        self.assertEqual(raw_rows[0]["input_weight"], "25")
        self.assertEqual(parsed_rows, [])
        self.assertEqual(total_weight, Decimal("0"))
        self.assertIn("ロット番号", error)

    def test_stock_ledger_edit_forms_require_lot_number(self):
        today = timezone.localdate()
        common = {
            "material_name": "ABS",
            "material_code": "ABS-1",
            "lot_color": QAMaterialStockLedger.LOT_COLOR_GREEN,
            "weight_kg": "25.00",
            "bag_sequence_no": "1",
            "lot_number": "",
            "workstation_management_no": "",
            "operator_name": "",
            "adjustment_reason_code": "",
            "adjustment_reason": "",
            "adjustment_note": "",
            "stock_before_kg": "",
            "stock_after_kg": "",
        }

        stock_form = QAMaterialStockLedgerForm(
            data={
                **common,
                "stock_in_date": today.isoformat(),
                "hinmei_name": "",
                "order_no": "",
                "transaction_type": QAMaterialStockLedger.TRANSACTION_IN,
            }
        )
        out_form = QAMaterialOutStockLedgerForm(
            data={
                **common,
                "stock_out_date": today.isoformat(),
                "product_code": "",
                "transaction_type": QAMaterialOutStockLedger.TRANSACTION_OUT,
            }
        )

        self.assertFalse(stock_form.is_valid())
        self.assertFalse(out_form.is_valid())
        self.assertIn("lot_number", stock_form.errors)
        self.assertIn("lot_number", out_form.errors)

    def test_stock_ledger_remembers_last_query_state(self):
        today = timezone.localdate()
        QAMaterialStockLedger.objects.create(
            material_code="ABS-1",
            material_name="ABS",
            stock_in_date=today,
            weight_kg=Decimal("25.00"),
            lot_number="LOT-1",
        )

        self.client.force_login(self.user)
        response = self.client.get(
            reverse("material_stock_ledger"),
            {"keyword": "ABS", "confirmed": "no", "page": "2"},
        )
        self.assertEqual(response.status_code, 200)

        response = self.client.get(reverse("material_stock_ledger"))
        self.assertEqual(response.status_code, 302)
        self.assertIn("keyword=ABS", response["Location"])
        self.assertIn("confirmed=no", response["Location"])
        self.assertIn("page=2", response["Location"])

        response = self.client.get(reverse("material_stock_ledger"), {"reset": "1"})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], reverse("material_stock_ledger"))

    def test_stock_ledger_confirm_redirects_back_to_current_state(self):
        admin = User.objects.create_superuser(username="ledger-admin", password="pass")
        row = QAMaterialStockLedger.objects.create(
            material_code="ABS-1",
            material_name="ABS",
            stock_in_date=timezone.localdate(),
            weight_kg=Decimal("25.00"),
            lot_number="LOT-1",
        )
        next_url = f"{reverse('material_stock_ledger')}?keyword=ABS&confirmed=no&page=2"

        self.client.force_login(admin)
        response = self.client.post(
            reverse("material_stock_ledger_confirm", args=[row.id]),
            {"next": next_url},
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], next_url)

    def test_out_stock_ledger_confirm_redirects_back_to_current_state(self):
        admin = User.objects.create_superuser(username="out-ledger-admin", password="pass")
        row = QAMaterialOutStockLedger.objects.create(
            material_code="ABS-1",
            material_name="ABS",
            stock_out_date=timezone.localdate(),
            weight_kg=Decimal("25.00"),
            lot_number="LOT-1",
        )
        next_url = f"{reverse('material_out_stock_ledger')}?keyword=ABS&confirmed=no&page=2"

        self.client.force_login(admin)
        response = self.client.post(
            reverse("material_out_stock_ledger_confirm", args=[row.id]),
            {"next": next_url},
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], next_url)
