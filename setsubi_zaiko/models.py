from django.conf import settings
from django.db import models
from django.utils import timezone
from urllib.parse import quote


class EquipmentCategory(models.Model):
    GROUP_PRODUCTION = "production_equipment"
    GROUP_QA = "qa_equipment"
    GROUP_MAINTENANCE = "maintenance_tool"
    GROUP_IT = "it_device"
    GROUP_WAREHOUSE = "warehouse_tool"
    GROUP_SAFETY = "safety_device"
    GROUP_SPARE = "consumable_spare"
    GROUP_OTHER = "other"

    GROUP_CHOICES = [
        (GROUP_PRODUCTION, "生産設備"),
        (GROUP_QA, "品質確認機器"),
        (GROUP_MAINTENANCE, "保全工具"),
        (GROUP_IT, "IT端末"),
        (GROUP_WAREHOUSE, "倉庫備品"),
        (GROUP_SAFETY, "安全備品"),
        (GROUP_SPARE, "消耗品・予備品"),
        (GROUP_OTHER, "その他"),
    ]

    code = models.CharField("分類コード", max_length=50, unique=True)
    name = models.CharField("分類名", max_length=120)
    group = models.CharField("大分類", max_length=40, choices=GROUP_CHOICES, default=GROUP_OTHER)
    parent = models.ForeignKey(
        "self",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="children",
        verbose_name="親分類",
    )
    description = models.TextField("説明", blank=True)
    is_active = models.BooleanField("有効", default=True)
    created_at = models.DateTimeField("作成日時", auto_now_add=True)
    updated_at = models.DateTimeField("更新日時", auto_now=True)

    class Meta:
        ordering = ["group", "code"]
        verbose_name = "設備分類"
        verbose_name_plural = "設備分類"

    def full_name(self):
        if self.parent_id:
            return f"{self.parent.name} > {self.name}"
        return self.name

    def __str__(self):
        return f"{self.code} {self.full_name()}"


class EquipmentCatalogNode(models.Model):
    code = models.CharField("カタログコード", max_length=80, unique=True)
    name = models.CharField("カタログ名", max_length=160)
    item_kind = models.CharField(
        "管理区分",
        max_length=20,
        choices=[
            ("equipment", "設備台帳"),
            ("mold", "金型台帳"),
        ],
    )
    parent = models.ForeignKey(
        "self",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="children",
        verbose_name="親カタログ",
    )
    sort_order = models.PositiveIntegerField("表示順", default=100)
    is_active = models.BooleanField("有効", default=True)
    note = models.TextField("備考", blank=True)
    created_at = models.DateTimeField("作成日時", auto_now_add=True)
    updated_at = models.DateTimeField("更新日時", auto_now=True)

    class Meta:
        ordering = ["item_kind", "sort_order", "code"]
        verbose_name = "設備・金型カタログ"
        verbose_name_plural = "設備・金型カタログ"

    def full_name(self):
        names = [self.name]
        parent = self.parent
        while parent:
            names.append(parent.name)
            parent = parent.parent
        return " > ".join(reversed(names))

    def descendant_ids(self):
        ids = [self.id]
        children = list(self.children.filter(is_active=True))
        for child in children:
            ids.extend(child.descendant_ids())
        return ids

    def __str__(self):
        return f"{self.code} {self.full_name()}"


class EquipmentItem(models.Model):
    KIND_EQUIPMENT = "equipment"
    KIND_MOLD = "mold"
    KIND_PART = "part"
    ITEM_KIND_CHOICES = [
        (KIND_EQUIPMENT, "設備台帳"),
        (KIND_MOLD, "金型台帳"),
        (KIND_PART, "部品在庫"),
    ]

    TYPE_CHOICES = [
        ("injection_molding_machine", "射出成形機"),
        ("jsw_machine_part", "JSW成形機部品"),
        ("mold", "金型"),
        ("mold_part", "金型部品"),
        ("mold_insert", "金型入れ子"),
        ("mold_core_pin", "金型コアピン"),
        ("mold_ejector_pin", "エジェクタピン"),
        ("mold_slide_core", "スライドコア"),
        ("mold_guide_part", "金型ガイド部品"),
        ("mold_spring", "金型スプリング"),
        ("mold_cooling_part", "金型冷却部品"),
        ("mold_plate", "金型プレート"),
        ("mold_hot_runner_part", "ホットランナー部品"),
        ("takeout_robot", "取出し機"),
        ("crusher", "粉砕機"),
        ("dryer", "乾燥機"),
        ("vacuum_pump", "真空ポンプ"),
        ("compressor", "コンプレッサー"),
        ("mold_monitor_camera", "金型監視カメラ"),
        ("air_vent", "エアーベント"),
        ("washer", "洗浄機"),
        ("demagnetizer", "脱磁機"),
        ("automatic_machine", "自動機"),
        ("mixer", "混合機"),
        ("material_loader", "輸送システムローダ"),
        ("yushin_takeout_robot", "ユーシン取出機"),
        ("yushin_robot_part", "ユーシン取出機部品"),
        ("temperature_controller", "温調機"),
        ("hopper_dryer", "ホッパードライヤー"),
        ("conveyor", "コンベア"),
        ("hydraulic_part", "油圧部品"),
        ("electric_part", "電装部品"),
        ("pneumatic_part", "空圧部品"),
        ("tablet", "タブレット"),
        ("barcode_scanner", "バーコードスキャナ"),
        ("qr_reader", "QRリーダー"),
        ("camera", "カメラ"),
        ("pc", "PC"),
        ("printer", "プリンタ"),
        ("measuring_tool", "測定器"),
        ("jig", "治具"),
        ("sensor", "センサー"),
        ("network_device", "ネットワーク機器"),
        ("machine_part", "機械部品"),
        ("hand_tool", "手工具"),
        ("spare_part", "予備部品"),
        ("safety_item", "安全用品"),
        ("other", "その他"),
    ]
    STATUS_CHOICES = [
        ("in_stock", "在庫"),
        ("in_use", "使用中"),
        ("reserved", "予約中"),
        ("repair", "修理中"),
        ("stopped", "使用停止"),
        ("scrapped", "廃棄済"),
        ("lost", "紛失"),
    ]
    QUALITY_RANK_CHOICES = [
        ("A", "A: 品質・安全重要"),
        ("B", "B: 工程影響あり"),
        ("C", "C: 一般管理"),
    ]
    UNIT_CHOICES = [
        ("個", "個"),
        ("枚", "枚"),
        ("式", "式"),
        ("本", "本"),
        ("セット", "セット"),
        ("その他", "その他"),
    ]

    code = models.CharField("機器コード", max_length=60, unique=True)
    name = models.CharField("機器・部品名", max_length=160)
    category = models.ForeignKey(EquipmentCategory, on_delete=models.PROTECT, related_name="items", verbose_name="分類")
    catalog_node = models.ForeignKey(
        EquipmentCatalogNode,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="items",
        verbose_name="設備・金型カタログ",
    )
    equipment_type = models.CharField("機器種別", max_length=40, choices=TYPE_CHOICES, default="other")
    item_kind = models.CharField("管理区分", max_length=20, choices=ITEM_KIND_CHOICES, default=KIND_PART, db_index=True)
    iot_machine = models.ForeignKey(
        "iot.Machine",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="setsubi_assets",
        verbose_name="IoT成形機shot連携",
    )
    iot_esp32_machine = models.ForeignKey(
        "iot.Esp32CardSnapshot",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="setsubi_assets",
        verbose_name="ESP32成形機shot連携",
    )
    iot_mold_lifetime = models.ForeignKey(
        "iot.MoldLifetime",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="setsubi_assets",
        verbose_name="IoT金型shot連携",
    )
    internal_name = models.CharField("社内呼称", max_length=160, blank=True)
    maker_part_no = models.CharField("メーカー品番", max_length=120, blank=True)
    alternative_part_no = models.CharField("代替品番", max_length=120, blank=True)
    applicable_machine_no = models.CharField("適用機械No.", max_length=120, blank=True)
    applicable_mold_no = models.CharField("適用金型No.", max_length=120, blank=True)
    mold_customer_code = models.CharField("金型顧客コード", max_length=40, blank=True)
    mold_customer_name = models.CharField("金型顧客名", max_length=120, blank=True)
    mold_product_code = models.CharField("金型製品コード", max_length=40, blank=True)
    mold_product_name = models.CharField("金型製品名", max_length=160, blank=True)
    mold_component_name = models.CharField("金型部品・構成品名", max_length=160, blank=True)
    mold_drawing_root_path = models.CharField("金型図面親フォルダ", max_length=500, blank=True)
    mold_drawing_subfolder_path = models.CharField("金型図面サブフォルダ", max_length=500, blank=True)
    equipment_group_name = models.CharField("設備グループ", max_length=120, blank=True)
    equipment_series_name = models.CharField("設備シリーズ・型式分類", max_length=120, blank=True)
    equipment_document_root_path = models.CharField("設備資料親フォルダ", max_length=500, blank=True)
    equipment_document_subfolder_path = models.CharField("設備資料サブフォルダ", max_length=500, blank=True)
    shelf_no = models.CharField("棚番", max_length=80, blank=True)
    minimum_stock = models.DecimalField("最低在庫", max_digits=12, decimal_places=2, default=0)
    reorder_point = models.DecimalField("発注点", max_digits=12, decimal_places=2, default=0)
    quality_rank = models.CharField("品質ランク", max_length=1, choices=QUALITY_RANK_CHOICES, default="C")
    control_plan_no = models.CharField("Control Plan No.", max_length=80, blank=True)
    process_owner = models.CharField("管理責任者", max_length=120, blank=True)
    supplier_name = models.CharField("購入先", max_length=120, blank=True)
    supplier_part_url = models.URLField("購入先URL", blank=True)
    serial_no = models.CharField("シリアルNo.", max_length=100, blank=True)
    model_no = models.CharField("型式", max_length=100, blank=True)
    maker = models.CharField("メーカー", max_length=100, blank=True)
    location = models.CharField("保管場所", max_length=120, blank=True)
    department = models.CharField("使用部署", max_length=120, blank=True)
    received_date = models.DateField("購入・受入日", null=True, blank=True)
    calibration_due_date = models.DateField("校正期限", null=True, blank=True)
    last_inventory_check_date = models.DateField("最終棚卸日", null=True, blank=True)
    next_inventory_check_date = models.DateField("次回棚卸期限", null=True, blank=True)
    status = models.CharField("状態", max_length=30, choices=STATUS_CHOICES, default="in_stock")
    current_quantity = models.DecimalField("現在数量", max_digits=12, decimal_places=2, default=0)
    unit = models.CharField("単位", max_length=20, choices=UNIT_CHOICES, default="個")
    item_image = models.ImageField("外観写真", upload_to="setsubi_zaiko/items/", blank=True, null=True)
    nameplate_image = models.ImageField("銘板・ラベル写真", upload_to="setsubi_zaiko/nameplates/", blank=True, null=True)
    note = models.TextField("備考", blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="created_equipment_items")
    created_at = models.DateTimeField("作成日時", auto_now_add=True)
    updated_at = models.DateTimeField("更新日時", auto_now=True)

    class Meta:
        ordering = ["category__group", "category__code", "code"]
        verbose_name = "設備・部品マスター"
        verbose_name_plural = "設備・部品マスター"

    def __str__(self):
        return f"{self.code} {self.name}"

    @property
    def is_asset_master(self):
        return self.item_kind in {self.KIND_EQUIPMENT, self.KIND_MOLD}

    @property
    def is_part_master(self):
        return self.item_kind == self.KIND_PART

    @property
    def linked_current_shot(self):
        if self.item_kind == self.KIND_EQUIPMENT:
            if self.iot_machine_id:
                return self.iot_machine.shot_total
            if self.iot_esp32_machine_id:
                return self.iot_esp32_machine.total_shot
        if self.item_kind == self.KIND_MOLD and self.iot_mold_lifetime_id:
            return self.iot_mold_lifetime.total_shot
        return None

    @property
    def mold_drawing_folder_path(self):
        return join_windows_path(self.mold_drawing_root_path, self.mold_drawing_subfolder_path)

    @property
    def mold_drawing_folder_uri(self):
        return file_uri(self.mold_drawing_folder_path)

    @property
    def mold_hierarchy_label(self):
        parts = []
        customer = " ".join(value for value in [self.mold_customer_code, self.mold_customer_name] if value).strip()
        product = " ".join(value for value in [self.mold_product_code, self.mold_product_name] if value).strip()
        if customer:
            parts.append(customer)
        if product:
            parts.append(product)
        if self.mold_component_name:
            parts.append(self.mold_component_name)
        return " > ".join(parts)

    @property
    def equipment_document_folder_path(self):
        return join_windows_path(self.equipment_document_root_path, self.equipment_document_subfolder_path)

    @property
    def equipment_document_folder_uri(self):
        return file_uri(self.equipment_document_folder_path)


def join_windows_path(root, subfolder):
    root = (root or "").strip()
    subfolder = (subfolder or "").strip()
    if not root:
        return subfolder
    if not subfolder:
        return root
    if subfolder.startswith("\\\\") or (len(subfolder) >= 3 and subfolder[1:3] == ":\\"):
        return subfolder
    return root.rstrip("\\/") + "\\" + subfolder.lstrip("\\/")


def file_uri(path):
    if not path:
        return ""
    normalized = path.replace("\\", "/")
    if normalized.startswith("//"):
        return "file:" + quote(normalized)
    return "file:///" + quote(normalized)


class EquipmentPartLink(models.Model):
    CRITICALITY_CHOICES = [
        ("A", "A: 停止・品質に直結"),
        ("B", "B: 工程影響あり"),
        ("C", "C: 一般管理"),
    ]

    asset = models.ForeignKey(
        EquipmentItem,
        on_delete=models.CASCADE,
        related_name="linked_parts",
        verbose_name="設備・金型",
    )
    part = models.ForeignKey(
        EquipmentItem,
        on_delete=models.PROTECT,
        related_name="used_by_assets",
        verbose_name="使用部品",
    )
    usage_location = models.CharField("使用箇所", max_length=120, blank=True)
    standard_quantity = models.DecimalField("標準使用数", max_digits=10, decimal_places=2, default=1)
    criticality = models.CharField("重要度", max_length=1, choices=CRITICALITY_CHOICES, default="B")
    replacement_cycle_days = models.PositiveIntegerField("交換目安(日)", null=True, blank=True)
    lifetime_shots = models.PositiveBigIntegerField("交換目安(shot)", null=True, blank=True)
    shot_source_machine = models.ForeignKey(
        "iot.Machine",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="setsubi_part_links",
        verbose_name="成形機shot元",
    )
    shot_source_mold = models.ForeignKey(
        "iot.MoldLifetime",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="setsubi_part_links",
        verbose_name="金型shot元",
    )
    baseline_shot = models.PositiveBigIntegerField("交換時累積shot", default=0)
    last_replaced_at = models.DateTimeField("最終交換日", null=True, blank=True)
    note = models.TextField("備考", blank=True)
    created_at = models.DateTimeField("作成日時", auto_now_add=True)
    updated_at = models.DateTimeField("更新日時", auto_now=True)

    class Meta:
        ordering = ["asset__code", "criticality", "part__code"]
        unique_together = [("asset", "part", "usage_location")]
        verbose_name = "設備・金型 使用部品"
        verbose_name_plural = "設備・金型 使用部品"

    def __str__(self):
        return f"{self.asset.code} -> {self.part.code}"

    @property
    def current_shot(self):
        if self.shot_source_machine_id:
            return self.shot_source_machine.shot_total
        if self.shot_source_mold_id:
            return self.shot_source_mold.total_shot
        return self.asset.linked_current_shot

    @property
    def effective_shot_source_label(self):
        machine = self.shot_source_machine or self.asset.iot_machine
        if machine:
            return machine.name or machine.address
        if self.asset.iot_esp32_machine_id:
            return f"ESP32 {self.asset.iot_esp32_machine.address}"
        mold_lifetime = self.shot_source_mold or self.asset.iot_mold_lifetime
        if mold_lifetime:
            return mold_lifetime.mold.name
        return ""

    @property
    def uses_asset_shot_source(self):
        return not self.shot_source_machine_id and not self.shot_source_mold_id and (
            self.asset.iot_machine_id or self.asset.iot_esp32_machine_id or self.asset.iot_mold_lifetime_id
        )

    @property
    def used_shots(self):
        current = self.current_shot
        if current is None:
            return None
        return max(int(current) - int(self.baseline_shot or 0), 0)

    @property
    def remaining_shots(self):
        if not self.lifetime_shots:
            return None
        return max(int(self.lifetime_shots) - int(self.used_shots or 0), 0)

    @property
    def lifetime_percent(self):
        if not self.lifetime_shots:
            return None
        return min(round((self.used_shots or 0) / self.lifetime_shots * 100, 1), 100.0)


class EquipmentPartReplacementHistory(models.Model):
    link = models.ForeignKey(
        EquipmentPartLink,
        on_delete=models.PROTECT,
        related_name="replacement_histories",
        verbose_name="設備・金型 使用部品",
    )
    replaced_at = models.DateTimeField("今回交換日", default=timezone.now)
    previous_replaced_at = models.DateTimeField("前回交換日", null=True, blank=True)
    shot_at_replacement = models.PositiveBigIntegerField("交換時累積shot", null=True, blank=True)
    baseline_shot_before = models.PositiveBigIntegerField("前回基準shot", default=0)
    used_shots = models.PositiveBigIntegerField("使用shot数", null=True, blank=True)
    note = models.TextField("交換メモ", blank=True)
    operator_name = models.CharField("交換作業者", max_length=120, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="equipment_part_replacement_histories",
    )
    created_at = models.DateTimeField("記録日時", auto_now_add=True)

    class Meta:
        ordering = ["-replaced_at", "-id"]
        verbose_name = "部品交換履歴"
        verbose_name_plural = "部品交換履歴"

    def __str__(self):
        return f"{self.link} / {self.replaced_at:%Y-%m-%d}"


class EquipmentStockLedger(models.Model):
    TRANSACTION_CHOICES = [
        ("IN", "入庫"),
        ("OUT", "出庫"),
        ("ADJ+", "在庫調整増"),
        ("ADJ-", "在庫調整減"),
        ("RETURN", "返却"),
        ("SCRAP", "廃棄"),
    ]
    REASON_CHOICES = [
        ("new_purchase", "新規購入"),
        ("return_to_stock", "返却入庫"),
        ("repair_return", "修理完了"),
        ("transfer_in", "移動入庫"),
        ("issue_to_use", "使用払出"),
        ("transfer_out", "移動出庫"),
        ("send_repair", "修理出し"),
        ("scrap_disposal", "廃棄処理"),
        ("inventory_plus", "棚卸増"),
        ("inventory_minus", "棚卸減"),
        ("found_legacy", "未登録品発見"),
        ("lost_damage", "紛失・破損"),
        ("migration", "移行データ"),
        ("other", "その他"),
    ]

    item = models.ForeignKey(EquipmentItem, on_delete=models.PROTECT, related_name="ledgers", verbose_name="機器・部品")
    transaction_type = models.CharField("取引区分", max_length=12, choices=TRANSACTION_CHOICES)
    reason_code = models.CharField("理由コード", max_length=40, choices=REASON_CHOICES)
    reason_label = models.CharField("理由", max_length=120)
    memo = models.TextField("理由メモ", blank=True)
    quantity = models.DecimalField("数量", max_digits=12, decimal_places=2)
    quantity_before = models.DecimalField("調整前数量", max_digits=12, decimal_places=2, default=0)
    quantity_after = models.DecimalField("調整後数量", max_digits=12, decimal_places=2, default=0)
    lot_no = models.CharField("ロットNo.", max_length=100, blank=True)
    from_location = models.CharField("移動元", max_length=120, blank=True)
    to_location = models.CharField("移動先", max_length=120, blank=True)
    operator_name = models.CharField("作業者", max_length=120, blank=True)
    supervisor_confirmed = models.BooleanField("上長確認", default=False)
    supervisor_name = models.CharField("確認者", max_length=120, blank=True)
    confirmed_at = models.DateTimeField("確認日時", null=True, blank=True)
    system_no = models.CharField("システムNo.", max_length=80, unique=True, blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="equipment_stock_ledgers")
    created_at = models.DateTimeField("記録日時", auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        verbose_name = "設備在庫台帳"
        verbose_name_plural = "設備在庫台帳"

    def save(self, *args, **kwargs):
        if not self.reason_label:
            self.reason_label = dict(self.REASON_CHOICES).get(self.reason_code, self.reason_code)
        if not self.system_no:
            stamp = timezone.now().strftime("%Y%m%d%H%M%S%f")
            self.system_no = f"EQ-{stamp}"
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.system_no} {self.item.code} {self.transaction_type}"
