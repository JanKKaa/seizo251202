from decimal import Decimal
from io import StringIO
from tempfile import TemporaryDirectory

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone
from django.urls import reverse
from openpyxl import Workbook

from iot.models import Esp32CardSnapshot, Machine, Mold, MoldLifetime

from .models import EquipmentCatalogNode, EquipmentCategory, EquipmentItem, EquipmentPartLink, EquipmentPartReplacementHistory, EquipmentStockLedger


class SetsubiZaikoSmokeTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="dev", password="pw")
        self.admin = get_user_model().objects.create_superuser(username="admin", password="pw", email="admin@example.com")
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
        for name in ["dashboard", "item_list", "equipment_list", "mold_list", "equipment_part_list", "mold_part_list", "master_list", "ledger_list", "ledger_create"]:
            response = self.client.get(reverse(f"setsubi_zaiko:{name}"))
            self.assertEqual(response.status_code, 200, name)
        response = self.client.get(reverse("setsubi_zaiko:part_list"))
        self.assertRedirects(response, reverse("setsubi_zaiko:equipment_part_list"))

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
        self.assertContains(response, 'accept="image/*"')
        self.assertContains(response, 'capture="environment"')
        self.assertContains(response, 'data-camera-target="id_item_image"')
        self.assertContains(response, 'data-camera-target="id_nameplate_image"')
        self.assertContains(response, 'id="setsubi-camera-modal"')
        self.assertContains(response, "navigator.mediaDevices.getUserMedia")
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

    def test_master_and_part_pages_are_split_by_equipment_and_mold(self):
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
        mold_asset = EquipmentItem.objects.create(
            code="MOLD-ASSET-001",
            name="金型A",
            category=EquipmentCategory.objects.get(code="MOLD"),
            equipment_type="mold",
            item_kind=EquipmentItem.KIND_MOLD,
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
        self.assertContains(equipment_response, "設備・機械台帳")
        self.assertContains(equipment_response, asset.code)
        self.assertNotContains(equipment_response, self.item.code)
        self.assertNotContains(equipment_response, mold_part.code)

        mold_response = self.client.get(reverse("setsubi_zaiko:mold_list"))
        self.assertEqual(mold_response.status_code, 200)
        self.assertContains(mold_response, "金型台帳")
        self.assertContains(mold_response, mold_asset.code)
        self.assertNotContains(mold_response, self.item.code)
        self.assertNotContains(mold_response, mold_part.code)

        equipment_part_response = self.client.get(reverse("setsubi_zaiko:equipment_part_list"))
        self.assertEqual(equipment_part_response.status_code, 200)
        self.assertContains(equipment_part_response, self.item.code)
        self.assertNotContains(equipment_part_response, asset.code)
        self.assertNotContains(equipment_part_response, mold_part.code)

        mold_part_response = self.client.get(reverse("setsubi_zaiko:mold_part_list"))
        self.assertEqual(mold_part_response.status_code, 200)
        self.assertContains(mold_part_response, mold_part.code)
        self.assertNotContains(mold_part_response, self.item.code)
        self.assertNotContains(mold_part_response, mold_asset.code)

        part_response = self.client.get(reverse("setsubi_zaiko:part_list"))
        self.assertRedirects(part_response, reverse("setsubi_zaiko:equipment_part_list"))

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

    def test_item_list_pagination_keeps_search_filters(self):
        for index in range(12):
            EquipmentItem.objects.create(
                code=f"KEEP-{index:02d}",
                name="PAGEKEEP target",
                category=self.category,
                equipment_type="tablet",
                item_kind=EquipmentItem.KIND_PART,
                maker="KeepMaker",
                current_quantity=Decimal("1.00"),
                unit="個",
                created_by=self.user,
            )

        response = self.client.get(reverse("setsubi_zaiko:equipment_part_list"), {"q": "PAGEKEEP", "maker": "KeepMaker"})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "q=PAGEKEEP&amp;maker=KeepMaker&amp;page=2")

    def test_text_search_inputs_wait_for_enter_or_button(self):
        response = self.client.get(reverse("setsubi_zaiko:equipment_part_list"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'type="search" name="q"')
        self.assertNotContains(response, 'name="q" value="" placeholder="コード・品番・社内呼称・棚番・機械No." data-auto-submit-control')
        self.assertNotContains(response, 'name="maker" value="" placeholder="例: MISUMI" data-auto-submit-control')
        self.assertContains(response, 'type="submit">検索</button>')

    def test_category_choices_are_scoped_by_large_group(self):
        response = self.client.get(reverse("setsubi_zaiko:equipment_part_list"), {"group": "it_device"})
        self.assertEqual(response.status_code, 200)
        category_choices = list(response.context["category_choices"])
        self.assertTrue(category_choices)
        self.assertTrue(all(category.group == "it_device" for category in category_choices))

    def test_mold_master_filters_use_mold_catalog_hierarchy(self):
        root_023 = EquipmentCatalogNode.objects.create(code="MOLD-CUST-023", name="023", item_kind=EquipmentItem.KIND_MOLD, sort_order=1)
        root_999 = EquipmentCatalogNode.objects.create(code="MOLD-CUST-999", name="999", item_kind=EquipmentItem.KIND_MOLD, sort_order=2)
        child_023 = EquipmentCatalogNode.objects.create(code="MOLD-CUST-023-901", name="901", item_kind=EquipmentItem.KIND_MOLD, parent=root_023, sort_order=1)
        EquipmentCatalogNode.objects.create(code="MOLD-CUST-999-100", name="100", item_kind=EquipmentItem.KIND_MOLD, parent=root_999, sort_order=1)
        mold = EquipmentItem.objects.create(
            code="MOLD-901-QMB",
            name="901 QMB",
            category=EquipmentCategory.objects.get(code="MOLD"),
            catalog_node=child_023,
            equipment_type="mold",
            item_kind=EquipmentItem.KIND_MOLD,
            current_quantity=Decimal("1.00"),
            unit="式",
            created_by=self.user,
        )

        response = self.client.get(reverse("setsubi_zaiko:mold_list"), {"catalog_root": root_023.pk})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'name="catalog_root"')
        self.assertContains(response, 'name="catalog"')
        self.assertContains(response, mold.code)
        self.assertEqual(list(response.context["catalog_root_choices"]), [root_023, root_999])
        self.assertEqual(list(response.context["catalog_child_choices"]), [child_023])

        response = self.client.get(reverse("setsubi_zaiko:mold_list"), {"catalog_root": root_999.pk})
        self.assertNotContains(response, mold.code)

    def test_part_scope_follows_linked_asset_kind(self):
        equipment_asset = EquipmentItem.objects.create(
            code="LINK-EQ-ASSET",
            name="linked equipment",
            category=EquipmentCategory.objects.get(code="EQ-TD"),
            equipment_type="takeout_robot",
            item_kind=EquipmentItem.KIND_EQUIPMENT,
            current_quantity=Decimal("1.00"),
            created_by=self.user,
        )
        mold_asset = EquipmentItem.objects.create(
            code="LINK-MOLD-ASSET",
            name="linked mold",
            category=EquipmentCategory.objects.get(code="MOLD"),
            equipment_type="mold",
            item_kind=EquipmentItem.KIND_MOLD,
            current_quantity=Decimal("1.00"),
            created_by=self.user,
        )
        mold_linked_spare = EquipmentItem.objects.create(
            code="LINK-MOLD-SPARE",
            name="spare used by mold",
            category=self.category,
            equipment_type="spare_part",
            item_kind=EquipmentItem.KIND_PART,
            current_quantity=Decimal("1.00"),
            created_by=self.user,
        )
        equipment_linked_mold_type = EquipmentItem.objects.create(
            code="LINK-EQ-MOLDTYPE",
            name="mold type used by equipment",
            category=EquipmentCategory.objects.get(code="MOLD-INSERT"),
            equipment_type="mold_insert",
            item_kind=EquipmentItem.KIND_PART,
            current_quantity=Decimal("1.00"),
            created_by=self.user,
        )
        EquipmentPartLink.objects.create(asset=mold_asset, part=mold_linked_spare)
        EquipmentPartLink.objects.create(asset=equipment_asset, part=equipment_linked_mold_type)

        mold_response = self.client.get(reverse("setsubi_zaiko:mold_part_list"))
        self.assertContains(mold_response, mold_linked_spare.code)
        self.assertNotContains(mold_response, equipment_linked_mold_type.code)

        equipment_response = self.client.get(reverse("setsubi_zaiko:equipment_part_list"))
        self.assertContains(equipment_response, equipment_linked_mold_type.code)
        self.assertNotContains(equipment_response, mold_linked_spare.code)

    def test_part_list_filters_by_linked_asset_catalog(self):
        root = EquipmentCatalogNode.objects.create(code="EQ-CAT-ROOT", name="machine root", item_kind=EquipmentItem.KIND_EQUIPMENT, sort_order=1)
        child = EquipmentCatalogNode.objects.create(code="EQ-CAT-CHILD", name="machine child", item_kind=EquipmentItem.KIND_EQUIPMENT, parent=root, sort_order=1)
        other_root = EquipmentCatalogNode.objects.create(code="EQ-CAT-OTHER", name="other root", item_kind=EquipmentItem.KIND_EQUIPMENT, sort_order=2)
        asset = EquipmentItem.objects.create(
            code="CAT-EQ-ASSET",
            name="catalog equipment",
            category=EquipmentCategory.objects.get(code="EQ-TD"),
            catalog_node=child,
            equipment_type="takeout_robot",
            item_kind=EquipmentItem.KIND_EQUIPMENT,
            current_quantity=Decimal("1.00"),
            created_by=self.user,
        )
        part = EquipmentItem.objects.create(
            code="CAT-LINK-PART",
            name="catalog linked part",
            category=self.category,
            equipment_type="spare_part",
            item_kind=EquipmentItem.KIND_PART,
            current_quantity=Decimal("1.00"),
            created_by=self.user,
        )
        EquipmentPartLink.objects.create(asset=asset, part=part)

        response = self.client.get(reverse("setsubi_zaiko:equipment_part_list"), {"asset_catalog_root": root.pk})
        self.assertContains(response, part.code)
        self.assertContains(response, 'name="asset_catalog_root"')
        self.assertContains(response, 'name="asset_catalog"')
        self.assertEqual(list(response.context["asset_catalog_root_choices"]), [root, other_root])
        self.assertEqual(list(response.context["asset_catalog_child_choices"]), [child])

        response = self.client.get(reverse("setsubi_zaiko:equipment_part_list"), {"asset_catalog_root": other_root.pk})
        self.assertNotContains(response, part.code)

    def test_keyword_search_covers_linked_asset_information(self):
        asset = EquipmentItem.objects.create(
            code="SEARCH-ASSET-001",
            name="search target machine",
            category=EquipmentCategory.objects.get(code="EQ-TD"),
            equipment_type="takeout_robot",
            item_kind=EquipmentItem.KIND_EQUIPMENT,
            current_quantity=Decimal("1.00"),
            unit="式",
            created_by=self.user,
        )
        EquipmentPartLink.objects.create(asset=asset, part=self.item, usage_location="special chuck")

        response = self.client.get(reverse("setsubi_zaiko:equipment_part_list"), {"q": "SEARCH-ASSET-001"})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.item.code)

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

        other_asset = EquipmentItem.objects.create(
            code="TD-YS-RC70-002",
            name="取出し機 RC-70D-18",
            category=asset_category,
            equipment_type="takeout_robot",
            item_kind=EquipmentItem.KIND_EQUIPMENT,
            current_quantity=Decimal("1.00"),
            unit="式",
            created_by=self.user,
        )
        EquipmentPartLink.objects.create(asset=other_asset, part=part, usage_location="予備")
        self.assertEqual(part.used_by_assets.count(), 2)

    def test_equipment_part_lifetime_uses_machine_shot_and_keeps_replacement_history(self):
        asset = EquipmentItem.objects.create(
            code="SEIKEI-TEST-01",
            name="成形機テスト",
            category=EquipmentCategory.objects.get(code="EQ-TD"),
            equipment_type="injection_molding_machine",
            item_kind=EquipmentItem.KIND_EQUIPMENT,
            created_by=self.user,
        )
        machine = Machine.objects.create(address="test-machine", name="テスト成形機", shot_total=1000)
        response = self.client.post(
            reverse("setsubi_zaiko:part_link_create", args=[asset.pk]),
            {
                "asset": asset.pk,
                "part": self.item.pk,
                "usage_location": "油圧部",
                "standard_quantity": "1",
                "criticality": "A",
                "replacement_cycle_days": "",
                "lifetime_shots": "1000",
                "shot_source_machine": machine.pk,
                "shot_source_mold": "",
                "note": "shot管理",
            },
        )
        self.assertEqual(response.status_code, 302)
        link = EquipmentPartLink.objects.get(asset=asset, part=self.item)
        self.assertEqual(link.baseline_shot, 1000)

        machine.shot_total = 1250
        machine.save(update_fields=["shot_total"])
        detail = self.client.get(reverse("setsubi_zaiko:item_detail", args=[asset.pk]))
        self.assertContains(detail, "250 / 1000")

        response = self.client.post(
            reverse("setsubi_zaiko:part_replacement_create", args=[link.pk]),
            {"replaced_at": "2026-07-03T10:00", "operator_name": "担当者A", "note": "定期交換"},
        )
        self.assertRedirects(response, reverse("setsubi_zaiko:item_detail", args=[asset.pk]))
        link.refresh_from_db()
        history = EquipmentPartReplacementHistory.objects.get(link=link)
        self.assertEqual(history.shot_at_replacement, 1250)
        self.assertEqual(history.baseline_shot_before, 1000)
        self.assertEqual(history.used_shots, 250)
        self.assertIsNone(history.previous_replaced_at)
        self.assertEqual(link.baseline_shot, 1250)
        self.assertEqual(link.last_replaced_at, history.replaced_at)

        machine.shot_total = 1400
        machine.save(update_fields=["shot_total"])
        response = self.client.post(
            reverse("setsubi_zaiko:part_replacement_create", args=[link.pk]),
            {"replaced_at": "2026-07-10T09:00", "operator_name": "担当者B", "note": ""},
        )
        self.assertEqual(response.status_code, 302)
        latest = EquipmentPartReplacementHistory.objects.filter(link=link).first()
        self.assertEqual(latest.previous_replaced_at, history.replaced_at)
        self.assertEqual(latest.used_shots, 150)

    def test_mold_part_lifetime_uses_iot_mold_total_shot(self):
        asset = EquipmentItem.objects.create(
            code="MOLD-TEST-01",
            name="金型テスト",
            category=EquipmentCategory.objects.get(code="EQ-TD"),
            equipment_type="mold",
            item_kind=EquipmentItem.KIND_MOLD,
            created_by=self.user,
        )
        mold = Mold.objects.create(code="IOT-MOLD-01", name="IoT金型")
        source = MoldLifetime.objects.create(mold=mold, total_shot=5000, lifetime=100000)
        link = EquipmentPartLink.objects.create(
            asset=asset,
            part=self.item,
            lifetime_shots=10000,
            shot_source_mold=source,
            baseline_shot=4500,
        )
        self.assertEqual(link.current_shot, 5000)
        self.assertEqual(link.used_shots, 500)
        self.assertEqual(link.remaining_shots, 9500)

    def test_mold_shot_source_can_be_manually_mapped_when_names_differ(self):
        asset = EquipmentItem.objects.create(
            code="SETSUBI-MOLD-DIFFERENT",
            name="現場呼称 右側金型",
            category=EquipmentCategory.objects.get(code="EQ-TD"),
            equipment_type="mold",
            item_kind=EquipmentItem.KIND_MOLD,
            created_by=self.user,
        )
        link = EquipmentPartLink.objects.create(asset=asset, part=self.item, lifetime_shots=10000)
        iot_mold = Mold.objects.create(code="50171-API", name="IoT側の全く違う名称")
        source = MoldLifetime.objects.create(mold=iot_mold, condname="api-condition-x", total_shot=5000)

        response = self.client.post(
            reverse("setsubi_zaiko:item_shot_source_edit", args=[asset.pk]),
            {"iot_mold_lifetime": source.pk},
        )
        self.assertRedirects(response, reverse("setsubi_zaiko:item_detail", args=[asset.pk]))
        asset.refresh_from_db()
        link.refresh_from_db()
        self.assertEqual(asset.iot_mold_lifetime, source)
        self.assertEqual(link.baseline_shot, 5000)

        source.total_shot = 5400
        source.save(update_fields=["total_shot"])
        link.refresh_from_db()
        self.assertEqual(link.current_shot, 5400)
        self.assertEqual(link.used_shots, 400)
        detail = self.client.get(reverse("setsubi_zaiko:item_detail", args=[asset.pk]))
        self.assertContains(detail, "IoT側の全く違う名称")
        self.assertContains(detail, "400 / 10000")

    def test_equipment_shot_source_can_be_manually_mapped(self):
        asset = EquipmentItem.objects.create(
            code="SETSUBI-EQ-DIFFERENT",
            name="乾燥機の現場名",
            category=EquipmentCategory.objects.get(code="EQ-TD"),
            equipment_type="dryer",
            item_kind=EquipmentItem.KIND_EQUIPMENT,
            created_by=self.user,
        )
        machine = Machine.objects.create(address="manual-map-machine", name="IoT成形機36", shot_total=8000)
        response = self.client.post(
            reverse("setsubi_zaiko:item_shot_source_edit", args=[asset.pk]),
            {"iot_machine": machine.pk},
        )
        self.assertEqual(response.status_code, 302)
        asset.refresh_from_db()
        self.assertEqual(asset.iot_machine, machine)
        self.assertEqual(asset.linked_current_shot, 8000)

    def test_equipment_can_use_esp32_machine_total_shot(self):
        asset = EquipmentItem.objects.create(
            code="SETSUBI-ESP32-EQ",
            name="ESP32設備",
            category=EquipmentCategory.objects.get(code="EQ-TD"),
            equipment_type="automatic_machine",
            item_kind=EquipmentItem.KIND_EQUIPMENT,
            created_by=self.user,
        )
        link = EquipmentPartLink.objects.create(asset=asset, part=self.item, lifetime_shots=50000)
        snapshot = Esp32CardSnapshot.objects.create(address="ESP-SET-01", primary_product="製品A", total_shot=12000)
        response = self.client.post(
            reverse("setsubi_zaiko:item_shot_source_edit", args=[asset.pk]),
            {"iot_machine": "", "iot_esp32_machine": snapshot.pk},
        )
        self.assertEqual(response.status_code, 302)
        asset.refresh_from_db()
        link.refresh_from_db()
        self.assertEqual(asset.iot_esp32_machine, snapshot)
        self.assertEqual(link.baseline_shot, 12000)
        snapshot.total_shot = 12250
        snapshot.save(update_fields=["total_shot"])
        link.refresh_from_db()
        self.assertEqual(link.used_shots, 250)

    def test_new_part_from_asset_is_created_and_linked(self):
        asset = EquipmentItem.objects.create(
            code="DR-MATSUI-MJ3-001",
            name="乾燥機 MJ3-50",
            category=EquipmentCategory.objects.get(code="EQ-KS"),
            equipment_type="dryer",
            item_kind=EquipmentItem.KIND_EQUIPMENT,
            current_quantity=Decimal("1.00"),
            unit="式",
            created_by=self.user,
        )
        response = self.client.post(
            f"{reverse('setsubi_zaiko:item_create')}?item_kind=part&part_scope=equipment_parts&asset={asset.pk}",
            {
                "code": "DR-HEATER-001",
                "name": "heater",
                "category": EquipmentCategory.objects.get(code="MOLDING-ELECTRIC").pk,
                "catalog_node": "",
                "equipment_type": "spare_part",
                "item_kind": EquipmentItem.KIND_PART,
                "current_quantity": "1",
                "unit": "個",
                "minimum_stock": "0",
                "reorder_point": "0",
                "quality_rank": "C",
                "status": "in_stock",
            },
        )
        self.assertRedirects(response, reverse("setsubi_zaiko:item_detail", args=[asset.pk]))
        part = EquipmentItem.objects.get(code="DR-HEATER-001")
        self.assertEqual(part.applicable_machine_no, asset.code)
        self.assertTrue(EquipmentPartLink.objects.filter(asset=asset, part=part).exists())

    def test_admin_can_edit_and_delete_part_link(self):
        self.client.force_login(self.admin)
        asset = EquipmentItem.objects.create(
            code="TD-LINK-001",
            name="取出し機",
            category=EquipmentCategory.objects.get(code="EQ-TD"),
            equipment_type="takeout_robot",
            item_kind=EquipmentItem.KIND_EQUIPMENT,
            current_quantity=Decimal("1.00"),
            unit="式",
            created_by=self.user,
        )
        link = EquipmentPartLink.objects.create(asset=asset, part=self.item, usage_location="old")

        response = self.client.post(
            reverse("setsubi_zaiko:part_link_edit", args=[link.pk]),
            {
                "asset": asset.pk,
                "part": self.item.pk,
                "usage_location": "new",
                "standard_quantity": "3",
                "criticality": "A",
                "replacement_cycle_days": "90",
                "note": "admin edit",
            },
        )
        self.assertRedirects(response, reverse("setsubi_zaiko:item_detail", args=[asset.pk]))
        link.refresh_from_db()
        self.assertEqual(link.usage_location, "new")
        self.assertEqual(link.standard_quantity, Decimal("3.00"))

        response = self.client.post(reverse("setsubi_zaiko:part_link_delete", args=[link.pk]))
        self.assertRedirects(response, reverse("setsubi_zaiko:item_detail", args=[asset.pk]))
        self.assertFalse(EquipmentPartLink.objects.filter(pk=link.pk).exists())

    def test_admin_can_delete_item_without_ledgers(self):
        self.client.force_login(self.admin)
        asset = EquipmentItem.objects.create(
            code="TD-DELETE-001",
            name="削除テスト設備",
            category=EquipmentCategory.objects.get(code="EQ-TD"),
            equipment_type="takeout_robot",
            item_kind=EquipmentItem.KIND_EQUIPMENT,
            current_quantity=Decimal("1.00"),
            unit="式",
            created_by=self.user,
        )

        response = self.client.post(reverse("setsubi_zaiko:item_delete", args=[asset.pk]))
        self.assertRedirects(response, reverse("setsubi_zaiko:equipment_list"))
        self.assertFalse(EquipmentItem.objects.filter(pk=asset.pk).exists())

    def test_admin_ledger_edit_and_delete_recalculates_stock(self):
        self.client.force_login(self.admin)
        ledger_out = EquipmentStockLedger.objects.create(
            item=self.item,
            transaction_type="OUT",
            reason_code="issue_to_use",
            reason_label="使用払出",
            quantity=Decimal("1.00"),
            quantity_before=Decimal("2.00"),
            quantity_after=Decimal("1.00"),
            operator_name="dev",
            created_by=self.user,
        )
        ledger_in = EquipmentStockLedger.objects.create(
            item=self.item,
            transaction_type="IN",
            reason_code="new_purchase",
            reason_label="新規購入",
            quantity=Decimal("2.00"),
            quantity_before=Decimal("1.00"),
            quantity_after=Decimal("3.00"),
            operator_name="dev",
            created_by=self.user,
        )
        self.item.current_quantity = Decimal("3.00")
        self.item.save(update_fields=["current_quantity"])

        response = self.client.post(
            reverse("setsubi_zaiko:ledger_edit", args=[ledger_out.pk]),
            {
                "item": self.item.pk,
                "transaction_type": "OUT",
                "reason_code": "issue_to_use",
                "quantity": "2",
                "lot_no": "",
                "from_location": "",
                "to_location": "",
                "memo": "edited",
                "operator_name": "admin",
                "supervisor_name": "",
            },
        )
        self.assertRedirects(response, reverse("setsubi_zaiko:ledger_list"))
        ledger_out.refresh_from_db()
        ledger_in.refresh_from_db()
        self.item.refresh_from_db()
        self.assertEqual(ledger_out.quantity_after, Decimal("0.00"))
        self.assertEqual(ledger_in.quantity_before, Decimal("0.00"))
        self.assertEqual(ledger_in.quantity_after, Decimal("2.00"))
        self.assertEqual(self.item.current_quantity, Decimal("2.00"))

        response = self.client.post(reverse("setsubi_zaiko:ledger_delete", args=[ledger_out.pk]))
        self.assertRedirects(response, reverse("setsubi_zaiko:ledger_list"))
        ledger_in.refresh_from_db()
        self.item.refresh_from_db()
        self.assertFalse(EquipmentStockLedger.objects.filter(pk=ledger_out.pk).exists())
        self.assertEqual(ledger_in.quantity_before, Decimal("2.00"))
        self.assertEqual(ledger_in.quantity_after, Decimal("4.00"))
        self.assertEqual(self.item.current_quantity, Decimal("4.00"))

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

        response = self.client.get(reverse("setsubi_zaiko:mold_part_list"))
        self.assertContains(response, mold.code)
        self.assertContains(response, "linh kien Z")

        equipment_response = self.client.get(reverse("setsubi_zaiko:equipment_part_list"))
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
