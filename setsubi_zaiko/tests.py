from decimal import Decimal
from io import StringIO
from tempfile import TemporaryDirectory

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone
from django.urls import reverse
from openpyxl import Workbook

from .models import EquipmentCatalogNode, EquipmentCategory, EquipmentItem, EquipmentPartLink, EquipmentStockLedger


class SetsubiZaikoSmokeTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="dev", password="pw")
        self.client.force_login(self.user)
        self.category = EquipmentCategory.objects.create(code="IT-TEST", name="IT端末", group="it_device")
        self.item = EquipmentItem.objects.create(
            code="EQ-0001",
            name="テストタブレット",
            category=self.category,
            equipment_type="tablet",
            quality_rank="A",
            control_plan_no="CP-001",
            process_owner="QA",
            serial_no="00123",
            current_quantity=Decimal("2.00"),
            minimum_stock=Decimal("3.00"),
            next_inventory_check_date=timezone.localdate(),
            created_by=self.user,
        )

    def test_pages_render(self):
        for name in ["dashboard", "item_list", "equipment_list", "mold_list", "master_list", "ledger_list", "ledger_create"]:
            response = self.client.get(reverse(f"setsubi_zaiko:{name}"))
            self.assertEqual(response.status_code, 200, name)
        response = self.client.get(reverse("setsubi_zaiko:part_list"))
        self.assertRedirects(response, reverse("setsubi_zaiko:equipment_list"))

        detail_response = self.client.get(reverse("setsubi_zaiko:item_detail", args=[self.item.pk]))
        self.assertEqual(detail_response.status_code, 200)

        edit_response = self.client.get(reverse("setsubi_zaiko:item_edit", args=[self.item.pk]))
        self.assertEqual(edit_response.status_code, 200)

    def test_master_category_crud_uses_safe_delete(self):
        response = self.client.post(
            reverse("setsubi_zaiko:category_create"),
            {"code": "REAL-CAT", "name": "実運用分類", "group": EquipmentCategory.GROUP_SPARE, "parent": "", "description": "", "is_active": "on"},
        )
        self.assertEqual(response.status_code, 302)
        category = EquipmentCategory.objects.get(code="REAL-CAT")

        response = self.client.post(
            reverse("setsubi_zaiko:category_edit", args=[category.pk]),
            {"code": "REAL-CAT", "name": "実運用分類 更新", "group": EquipmentCategory.GROUP_SPARE, "parent": "", "description": "updated", "is_active": "on"},
        )
        self.assertEqual(response.status_code, 302)
        category.refresh_from_db()
        self.assertEqual(category.name, "実運用分類 更新")

        response = self.client.post(reverse("setsubi_zaiko:category_delete", args=[self.category.pk]))
        self.assertEqual(response.status_code, 302)
        self.category.refresh_from_db()
        self.assertFalse(self.category.is_active)

        response = self.client.post(reverse("setsubi_zaiko:category_delete", args=[category.pk]))
        self.assertEqual(response.status_code, 302)
        self.assertFalse(EquipmentCategory.objects.filter(pk=category.pk).exists())

    def test_master_catalog_crud_uses_safe_delete(self):
        node = EquipmentCatalogNode.objects.create(code="REAL-CATALOG", name="実運用カタログ", item_kind=EquipmentItem.KIND_MOLD)
        response = self.client.get(reverse("setsubi_zaiko:master_list"), {"type": "catalog", "item_kind": EquipmentItem.KIND_MOLD})
        self.assertContains(response, "REAL-CATALOG")

        response = self.client.post(
            reverse("setsubi_zaiko:catalog_edit", args=[node.pk]),
            {"code": "REAL-CATALOG", "name": "実運用カタログ 更新", "item_kind": EquipmentItem.KIND_MOLD, "parent": "", "sort_order": "10", "is_active": "on", "note": ""},
        )
        self.assertEqual(response.status_code, 302)
        node.refresh_from_db()
        self.assertEqual(node.name, "実運用カタログ 更新")

        response = self.client.post(reverse("setsubi_zaiko:catalog_delete", args=[node.pk]))
        self.assertEqual(response.status_code, 302)
        self.assertFalse(EquipmentCatalogNode.objects.filter(pk=node.pk).exists())

    def test_item_create_form_has_image_fields(self):
        response = self.client.get(reverse("setsubi_zaiko:item_create"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'name="item_image"')
        self.assertContains(response, 'name="nameplate_image"')
        self.assertContains(response, 'name="item_kind"')
        self.assertContains(response, 'name="quality_rank"')
        self.assertNotContains(response, 'name="control_plan_no"')
        self.assertContains(response, 'name="serial_no"')
        self.assertContains(response, 'name="equipment_group_name"')
        self.assertContains(response, 'name="equipment_document_root_path"')
        self.assertContains(response, "<summary")
        self.assertContains(response, "詳細情報・IATF管理項目を開く")
        self.assertContains(response, '<option value="枚">枚</option>')
        self.assertContains(response, '<option value="式">式</option>')
        self.assertContains(response, '<option value="本">本</option>')
        self.assertContains(response, '<option value="セット">セット</option>')
        self.assertContains(response, '<option value="その他">その他</option>')

    def test_item_edit_updates_master(self):
        response = self.client.post(
            reverse("setsubi_zaiko:item_edit", args=[self.item.pk]),
            {
                "code": self.item.code,
                "name": "更新タブレット",
                "category": self.category.pk,
                "equipment_type": "tablet",
                "item_kind": EquipmentItem.KIND_PART,
                "serial_no": self.item.serial_no,
                "quality_rank": "B",
                "supplier_name": "MISUMI",
                "minimum_stock": "1",
                "reorder_point": "2",
                "current_quantity": "2",
                "unit": "個",
                "status": "in_stock",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.item.refresh_from_db()
        self.assertEqual(self.item.name, "更新タブレット")
        self.assertEqual(self.item.quality_rank, "B")
        self.assertEqual(self.item.supplier_name, "MISUMI")
        self.assertEqual(self.item.control_plan_no, "CP-001")
        self.assertEqual(self.item.process_owner, "QA")
        self.assertEqual(self.item.serial_no, "00123")

    def test_mold_part_choices_and_categories_exist(self):
        response = self.client.get(reverse("setsubi_zaiko:item_create"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "金型入れ子")
        self.assertContains(response, "エジェクタピン")
        self.assertTrue(EquipmentCategory.objects.filter(code="MOLD-INSERT", parent__code="MOLD").exists())
        self.assertTrue(EquipmentCategory.objects.filter(code="MOLD-HOT-RUNNER", parent__code="MOLD").exists())

    def test_ledger_post_updates_quantity(self):
        response = self.client.post(
            reverse("setsubi_zaiko:ledger_create"),
            {
                "item": self.item.pk,
                "transaction_type": "OUT",
                "reason_code": "issue_to_use",
                "quantity": "1",
                "memo": "テスト払出",
                "operator_name": "テスト作業者",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.item.refresh_from_db()
        self.assertEqual(self.item.current_quantity, Decimal("1.00"))
        ledger = EquipmentStockLedger.objects.get()
        self.assertEqual(ledger.quantity_before, Decimal("2.00"))
        self.assertEqual(ledger.quantity_after, Decimal("1.00"))

    def test_ledger_workflow_pages_render(self):
        for name, label in [("ledger_in", "入庫ワークフロー"), ("ledger_out", "出庫ワークフロー"), ("ledger_adjust", "調整ワークフロー")]:
            response = self.client.get(reverse(f"setsubi_zaiko:{name}"))
            self.assertEqual(response.status_code, 200, name)
            self.assertContains(response, label)
            self.assertContains(response, "3段キーワード絞り込み")
            self.assertContains(response, "在庫 2.00")

    def test_ledger_out_workflow_updates_quantity(self):
        response = self.client.post(
            reverse("setsubi_zaiko:ledger_out"),
            {
                "item": self.item.pk,
                "transaction_type": "OUT",
                "reason_code": "issue_to_use",
                "quantity": "1",
                "memo": "workflow",
                "operator_name": "dev",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.item.refresh_from_db()
        self.assertEqual(self.item.current_quantity, Decimal("1.00"))

    def test_ledger_workflow_only_shows_part_master(self):
        asset = EquipmentItem.objects.create(
            code="TD-YS-RC70-001",
            name="取出し機",
            category=EquipmentCategory.objects.get(code="EQ-TD"),
            equipment_type="takeout_robot",
            item_kind=EquipmentItem.KIND_EQUIPMENT,
            current_quantity=Decimal("1.00"),
            unit="式",
            created_by=self.user,
        )
        response = self.client.get(reverse("setsubi_zaiko:ledger_out"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.item.code)
        self.assertNotContains(response, asset.code)

    def test_equipment_and_mold_pages_manage_part_inventory_groups(self):
        asset = EquipmentItem.objects.create(
            code="TD-YS-RC70-001",
            name="取出し機",
            category=EquipmentCategory.objects.get(code="EQ-TD"),
            equipment_type="takeout_robot",
            item_kind=EquipmentItem.KIND_EQUIPMENT,
            current_quantity=Decimal("1.00"),
            unit="式",
            created_by=self.user,
        )
        mold_part = EquipmentItem.objects.create(
            code="MOLD-INSERT-001",
            name="金型入れ子",
            category=EquipmentCategory.objects.get(code="MOLD-INSERT"),
            equipment_type="mold_insert",
            item_kind=EquipmentItem.KIND_PART,
            current_quantity=Decimal("5.00"),
            unit="個",
            created_by=self.user,
        )
        equipment_response = self.client.get(reverse("setsubi_zaiko:equipment_list"))
        self.assertEqual(equipment_response.status_code, 200)
        self.assertContains(equipment_response, "設備・機械部品")
        self.assertContains(equipment_response, self.item.code)
        self.assertNotContains(equipment_response, asset.code)
        self.assertNotContains(equipment_response, mold_part.code)

        mold_response = self.client.get(reverse("setsubi_zaiko:mold_list"))
        self.assertEqual(mold_response.status_code, 200)
        self.assertContains(mold_response, "金型部品")
        self.assertContains(mold_response, mold_part.code)
        self.assertNotContains(mold_response, self.item.code)

        part_response = self.client.get(reverse("setsubi_zaiko:part_list"))
        self.assertRedirects(part_response, reverse("setsubi_zaiko:equipment_list"))

    def test_ledger_list_filters_by_three_keywords(self):
        EquipmentStockLedger.objects.create(
            item=self.item,
            transaction_type="OUT",
            reason_code="issue_to_use",
            reason_label="使用",
            quantity=Decimal("1.00"),
            quantity_before=Decimal("2.00"),
            quantity_after=Decimal("1.00"),
            memo="13号機 スクリュー交換",
            operator_name="dev",
            created_by=self.user,
        )
        response = self.client.get(reverse("setsubi_zaiko:ledger_list"), {"q1": "EQ-0001", "q2": "スクリュー", "q3": "13号機"})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "EQ-0001")
        self.assertContains(response, "3段目")

    def test_csv_exports_keep_code_as_text(self):
        response = self.client.get(reverse("setsubi_zaiko:export_items_csv"))
        self.assertEqual(response.status_code, 200)
        body = response.content.decode("utf-8-sig")
        self.assertIn('=""EQ-0001""', body)
        self.assertIn("メーカー品番", body)
        self.assertIn("棚番", body)
        self.assertIn("品質ランク", body)
        self.assertIn("Control Plan No.", body)

    def test_iatf_alert_filters_render(self):
        response = self.client.get(reverse("setsubi_zaiko:item_list"), {"alert": "low_stock"})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "EQ-0001")
        self.assertContains(response, "A: 品質・安全重要")

    def test_dashboard_shows_iatf_alert_sections(self):
        response = self.client.get(reverse("setsubi_zaiko:dashboard"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "設備管理ボード")
        self.assertContains(response, "在庫アラート")

    def test_asset_can_link_to_part(self):
        asset_category = EquipmentCategory.objects.get(code="EQ-TD")
        part_category = EquipmentCategory.objects.get(code="MOLDING-ELECTRIC")
        asset = EquipmentItem.objects.create(
            code="TD-YS-RC70-001",
            name="取出し機 RC-70D-17",
            category=asset_category,
            equipment_type="takeout_robot",
            item_kind=EquipmentItem.KIND_EQUIPMENT,
            current_quantity=Decimal("1.00"),
            unit="式",
            created_by=self.user,
        )
        part = EquipmentItem.objects.create(
            code="SENSOR-001",
            name="確認センサー",
            category=part_category,
            equipment_type="sensor",
            item_kind=EquipmentItem.KIND_PART,
            current_quantity=Decimal("3.00"),
            unit="個",
            created_by=self.user,
        )
        response = self.client.post(
            reverse("setsubi_zaiko:part_link_create", args=[asset.pk]),
            {
                "asset": asset.pk,
                "part": part.pk,
                "usage_location": "チャック",
                "standard_quantity": "2",
                "criticality": "A",
                "replacement_cycle_days": "180",
                "note": "定期交換",
            },
        )
        self.assertEqual(response.status_code, 302)
        link = EquipmentPartLink.objects.get(asset=asset, part=part)
        self.assertEqual(link.usage_location, "チャック")
        detail = self.client.get(reverse("setsubi_zaiko:item_detail", args=[asset.pk]))
        self.assertContains(detail, "この設備・金型で使う部品")
        self.assertContains(detail, "SENSOR-001")

    def test_mold_drawing_folder_link_renders(self):
        mold = EquipmentItem.objects.create(
            code="MOLD-901-QMB",
            name="901 QMB",
            category=EquipmentCategory.objects.get(code="MOLD"),
            equipment_type="mold",
            item_kind=EquipmentItem.KIND_MOLD,
            applicable_mold_no="901",
            mold_customer_code="023",
            mold_customer_name="cty A",
            mold_product_code="901",
            mold_product_name="QMB",
            mold_component_name="runner lock",
            mold_drawing_root_path=r"O:\共有フォルダー\04_生産技術課\13_図面\13.1.金型図\023マグプロスト",
            mold_drawing_subfolder_path=r"901 QMB\runner lock",
            current_quantity=Decimal("1.00"),
            unit="式",
            created_by=self.user,
        )
        self.assertIn(r"023マグプロスト\901 QMB\runner lock", mold.mold_drawing_folder_path)
        self.assertEqual(mold.mold_hierarchy_label, "023 cty A > 901 QMB > runner lock")
        self.assertTrue(mold.mold_drawing_folder_uri.startswith("file:///"))

        detail = self.client.get(reverse("setsubi_zaiko:item_detail", args=[mold.pk]))
        self.assertContains(detail, "図面フォルダ")
        self.assertContains(detail, "runner lock")

    def test_sync_mold_folders_command_creates_nested_mold_records(self):
        with TemporaryDirectory() as tmpdir:
            import os

            root = f"{tmpdir}/13.1.金型図"
            os.makedirs(f"{root}/023 cty A/900 sản phẩm Z/runner lock")
            os.makedirs(f"{root}/023 cty A/900 sản phẩm Z/EP")

            out = StringIO()
            call_command("sync_mold_folders", root, stdout=out)

        mold = EquipmentItem.objects.get(mold_component_name="runner lock")
        self.assertEqual(mold.item_kind, EquipmentItem.KIND_MOLD)
        self.assertEqual(mold.equipment_type, "mold")
        self.assertEqual(mold.mold_customer_code, "023")
        self.assertEqual(mold.mold_customer_name, "cty A")
        self.assertEqual(mold.mold_product_code, "900")
        self.assertEqual(mold.mold_product_name, "sản phẩm Z")
        self.assertEqual(mold.mold_component_name, "runner lock")
        self.assertIn("runner lock", mold.mold_drawing_subfolder_path)
        self.assertIn("created=2", out.getvalue())

    def test_equipment_group_and_document_folder_link_renders(self):
        asset = EquipmentItem.objects.create(
            code="DR-MATSUI-MJ3-001",
            name="乾燥機 MJ3-50",
            category=EquipmentCategory.objects.get(code="EQ-KS"),
            equipment_type="dryer",
            item_kind=EquipmentItem.KIND_EQUIPMENT,
            equipment_group_name="乾燥機",
            equipment_series_name="ホッパードライヤー",
            maker="MATSUI",
            model_no="MJ3-50",
            serial_no="DR001",
            equipment_document_root_path=r"O:\共有フォルダー\04_生産技術課\06_設備管理\乾燥機",
            equipment_document_subfolder_path="MATSUI MJ3-50",
            current_quantity=Decimal("1.00"),
            unit="式",
            created_by=self.user,
        )
        self.assertIn(r"乾燥機\MATSUI MJ3-50", asset.equipment_document_folder_path)
        self.assertTrue(asset.equipment_document_folder_uri.startswith("file:///"))

        detail = self.client.get(reverse("setsubi_zaiko:item_detail", args=[asset.pk]))
        self.assertContains(detail, "設備グループ")
        self.assertContains(detail, "ホッパードライヤー")
        self.assertContains(detail, "資料フォルダ")

    def test_mold_page_filters_mold_part_inventory(self):
        mold = EquipmentItem.objects.create(
            code="MOLD-Z",
            name="linh kien Z",
            category=EquipmentCategory.objects.get(code="MOLD-INSERT"),
            equipment_type="mold_insert",
            item_kind=EquipmentItem.KIND_PART,
            current_quantity=Decimal("1.00"),
            unit="個",
            created_by=self.user,
        )

        response = self.client.get(reverse("setsubi_zaiko:mold_list"))
        self.assertContains(response, mold.code)
        self.assertContains(response, "linh kien Z")

        equipment_response = self.client.get(reverse("setsubi_zaiko:equipment_list"))
        self.assertNotContains(equipment_response, mold.code)

    def test_catalog_create_keeps_asset_catalog_form_available(self):
        group_d = EquipmentCatalogNode.objects.create(code="CAT-CUST-A-MOLD-B-C-D", name="nhom D", item_kind=EquipmentItem.KIND_MOLD)
        create_response = self.client.get(reverse("setsubi_zaiko:catalog_create"), {"item_kind": EquipmentItem.KIND_MOLD, "parent": group_d.pk})
        self.assertEqual(create_response.status_code, 200)
        self.assertContains(create_response, 'name="parent"')

    def test_import_equipment_list_upserts_from_excel(self):
        with TemporaryDirectory() as tmpdir:
            path = f"{tmpdir}/equipment.xlsx"
            workbook = Workbook()
            worksheet = workbook.active
            worksheet.title = "設備管理台帳"
            worksheet.append([])
            worksheet.append([])
            worksheet.append([])
            worksheet.append(["No.", "種類", "メーカー", "型式", "番号順", "管理番号", "成形号機", "材料名", "製品名", "製造番号", "製造年月", "電源（電圧）", "エアー", "備考"])
            worksheet.append([1, "取出し機", "Yushin ユーシン精機", "RC-70D-17", "001", "TD-YS-RC70-001", "13号機", "", "", "21003971-0010", "2021/05", "AC200V", "有る", "5軸昇降1段"])
            workbook.save(path)

            out = StringIO()
            call_command("import_equipment_list", path, stdout=out)

        imported = EquipmentItem.objects.get(code="TD-YS-RC70-001")
        self.assertEqual(imported.category.code, "EQ-TD")
        self.assertEqual(imported.equipment_type, "takeout_robot")
        self.assertEqual(imported.item_kind, EquipmentItem.KIND_EQUIPMENT)
        self.assertEqual(imported.unit, "式")
        self.assertEqual(imported.current_quantity, Decimal("1.00"))
        self.assertEqual(imported.applicable_machine_no, "13号機")
        self.assertIn("5軸昇降1段", imported.note)

    def test_import_equipment_list_keeps_existing_audit_fields(self):
        category = EquipmentCategory.objects.get(code="EQ-TD")
        item = EquipmentItem.objects.create(
            code="TD-YS-RC70-001",
            name="旧取出し機",
            category=category,
            equipment_type="takeout_robot",
            item_kind=EquipmentItem.KIND_EQUIPMENT,
            control_plan_no="CP-KEEP",
            process_owner="QA",
            current_quantity=Decimal("2.00"),
            unit="式",
            created_by=self.user,
        )

        with TemporaryDirectory() as tmpdir:
            path = f"{tmpdir}/equipment.xlsx"
            workbook = Workbook()
            worksheet = workbook.active
            worksheet.title = "設備管理台帳"
            worksheet.append([])
            worksheet.append([])
            worksheet.append([])
            worksheet.append(["No.", "種類", "メーカー", "型式", "番号順", "管理番号", "成形号機", "製造番号"])
            worksheet.append([1, "取出し機", "Yushin ユーシン精機", "RC-70D-17", "001", item.code, "13号機", "21003971-0010"])
            workbook.save(path)
            call_command("import_equipment_list", path, stdout=StringIO())

        item.refresh_from_db()
        self.assertEqual(item.control_plan_no, "CP-KEEP")
        self.assertEqual(item.process_owner, "QA")
        self.assertEqual(item.item_kind, EquipmentItem.KIND_EQUIPMENT)
        self.assertEqual(EquipmentCategory.objects.get(code="MOLD").parent_id, None)
