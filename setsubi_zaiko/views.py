import csv
from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Count, F, Sum
from django.db.models import Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone

from .forms import EquipmentCatalogNodeForm, EquipmentCategoryForm, EquipmentItemForm, EquipmentPartLinkForm, EquipmentStockLedgerForm
from .models import EquipmentCatalogNode, EquipmentCategory, EquipmentItem, EquipmentPartLink, EquipmentStockLedger


MOLD_PART_TYPES = {
    "mold_part",
    "mold_insert",
    "mold_core_pin",
    "mold_ejector_pin",
    "mold_slide_core",
    "mold_guide_part",
    "mold_spring",
    "mold_cooling_part",
    "mold_plate",
    "mold_hot_runner_part",
}


def _operator_name(request):
    user = getattr(request, "user", None)
    if user and user.is_authenticated:
        full_name = user.get_full_name()
        return full_name or user.get_username()
    return ""


def _excel_text(value):
    value = "" if value is None else str(value)
    return f'="{value}"' if value else ""


def _catalog_descendant_ids(node):
    ids = [node.id]
    for child in node.children.filter(is_active=True):
        ids.extend(_catalog_descendant_ids(child))
    return ids


def _apply_part_scope(queryset, part_scope):
    if part_scope == "mold_parts":
        return queryset.filter(equipment_type__in=MOLD_PART_TYPES)
    if part_scope == "equipment_parts":
        return queryset.exclude(equipment_type__in=MOLD_PART_TYPES)
    return queryset


def _part_scope_type_choices(part_scope):
    choices = list(EquipmentItem.TYPE_CHOICES)
    if part_scope == "mold_parts":
        return [choice for choice in choices if choice[0] in MOLD_PART_TYPES]
    if part_scope == "equipment_parts":
        return [choice for choice in choices if choice[0] not in MOLD_PART_TYPES and choice[0] != "mold"]
    return choices


def _catalog_flat_tree(item_kind):
    roots = EquipmentCatalogNode.objects.filter(item_kind=item_kind, is_active=True, parent__isnull=True).order_by("sort_order", "code")
    rows = []

    def walk(node, depth):
        rows.append({"node": node, "depth": depth, "indent": "　" * depth, "item_count": node.items.count()})
        for child in node.children.filter(is_active=True).order_by("sort_order", "code"):
            walk(child, depth + 1)

    for root in roots:
        walk(root, 0)
    return rows


def _catalog_nested_tree(item_kind):
    roots = EquipmentCatalogNode.objects.filter(item_kind=item_kind, is_active=True, parent__isnull=True).order_by("sort_order", "code")

    def build(node):
        children = node.children.filter(is_active=True).order_by("sort_order", "code")
        return {
            "node": node,
            "item_count": node.items.count(),
            "children": [build(child) for child in children],
        }

    return [build(root) for root in roots]


def _csv_response(filename):
    response = HttpResponse(content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    response.write("\ufeff")
    return response


def _write_audit_header(writer, report_name, user):
    writer.writerow(["帳票名", report_name])
    writer.writerow(["管理区分", "設備・部品在庫トレーサビリティ"])
    writer.writerow(["出力者", user])
    writer.writerow(["出力日時", timezone.localtime().strftime("%Y-%m-%d %H:%M:%S")])
    writer.writerow(["確認印", ""])
    writer.writerow(["データ保全", "履歴データは削除せず、訂正は新規台帳で記録する。"])
    writer.writerow([])


@login_required
def dashboard(request):
    today = timezone.localdate()
    asset_filter = Q(item_kind__in=[EquipmentItem.KIND_EQUIPMENT, EquipmentItem.KIND_MOLD])
    part_filter = Q(item_kind=EquipmentItem.KIND_PART)
    group_labels = dict(EquipmentCategory.GROUP_CHOICES)
    group_rows = []
    for row in (
        EquipmentItem.objects.filter(part_filter)
        .values("category__group")
        .annotate(item_count=Count("id"), total_quantity=Sum("current_quantity"))
        .order_by("category__group")
    ):
        row["group_label"] = group_labels.get(row["category__group"], row["category__group"])
        group_rows.append(row)
    recent_ledgers = EquipmentStockLedger.objects.select_related("item", "item__category")[:10]
    total_items = EquipmentItem.objects.filter(part_filter).count()
    total_quantity = EquipmentItem.objects.filter(part_filter).aggregate(total=Sum("current_quantity"))["total"] or 0
    active_items = EquipmentItem.objects.filter(part_filter).exclude(status__in=["scrapped", "lost"]).count()
    ledger_count = EquipmentStockLedger.objects.count()
    asset_count = EquipmentItem.objects.filter(asset_filter).count()
    mold_count = EquipmentItem.objects.filter(item_kind=EquipmentItem.KIND_MOLD).count()
    part_count = EquipmentItem.objects.filter(part_filter).count()
    linked_part_count = EquipmentPartLink.objects.count()
    asset_cards = (
        EquipmentItem.objects.filter(asset_filter)
        .select_related("category")
        .annotate(part_link_count=Count("linked_parts"))
        .order_by("code")[:12]
    )
    low_stock_items = EquipmentItem.objects.filter(part_filter, minimum_stock__gt=0, current_quantity__lte=F("minimum_stock")).order_by("quality_rank", "code")[:8]
    calibration_due_items = EquipmentItem.objects.filter(calibration_due_date__isnull=False, calibration_due_date__lte=today).order_by("calibration_due_date", "code")[:8]
    inventory_due_items = EquipmentItem.objects.filter(next_inventory_check_date__isnull=False, next_inventory_check_date__lte=today).order_by("next_inventory_check_date", "code")[:8]
    unconfirmed_ledgers = EquipmentStockLedger.objects.filter(supervisor_confirmed=False).select_related("item").order_by("-created_at")[:8]
    status_labels = dict(EquipmentItem.STATUS_CHOICES)
    status_rows = []
    for row in (
        EquipmentItem.objects.filter(part_filter)
        .values("status")
        .annotate(item_count=Count("id"), total_quantity=Sum("current_quantity"))
        .order_by("status")
    ):
        row["status_label"] = status_labels.get(row["status"], row["status"])
        status_rows.append(row)
    context = {
        "group_rows": group_rows,
        "status_rows": status_rows,
        "status_labels": status_labels,
        "recent_ledgers": recent_ledgers,
        "dev_mode_notice": "開発テスト版です。本番Dockerには未展開です。",
        "current_operator": _operator_name(request),
        "total_items": total_items,
        "total_quantity": total_quantity,
        "active_items": active_items,
        "ledger_count": ledger_count,
        "asset_count": asset_count,
        "mold_count": mold_count,
        "part_count": part_count,
        "linked_part_count": linked_part_count,
        "asset_cards": asset_cards,
        "low_stock_items": low_stock_items,
        "calibration_due_items": calibration_due_items,
        "inventory_due_items": inventory_due_items,
        "unconfirmed_ledgers": unconfirmed_ledgers,
    }
    return render(request, "setsubi_zaiko/dashboard.html", context)


@login_required
def item_list(request, forced_item_kind=None, part_scope=None):
    items = EquipmentItem.objects.select_related("category", "catalog_node", "catalog_node__parent").order_by("code")
    item_kind = forced_item_kind or request.GET.get("item_kind") or EquipmentItem.KIND_PART
    is_asset_list = item_kind in {EquipmentItem.KIND_EQUIPMENT, EquipmentItem.KIND_MOLD}
    base_items = EquipmentItem.objects.filter(item_kind=item_kind).select_related("category", "catalog_node")
    if item_kind == EquipmentItem.KIND_PART:
        items = _apply_part_scope(items, part_scope)
        base_items = _apply_part_scope(base_items, part_scope)
    group = request.GET.get("group") or ""
    category_id = request.GET.get("category") or ""
    status = request.GET.get("status") or ""
    equipment_type = request.GET.get("equipment_type") or ""
    catalog_id = request.GET.get("catalog") or ""
    quality_rank = request.GET.get("quality_rank") or ""
    alert = request.GET.get("alert") or ""
    maker = request.GET.get("maker") or ""
    shelf = request.GET.get("shelf") or ""
    application = request.GET.get("application") or ""
    q = request.GET.get("q") or ""
    if item_kind:
        items = items.filter(item_kind=item_kind)
    if group:
        items = items.filter(category__group=group)
    if category_id:
        category_ids = [category_id]
        category_ids += list(EquipmentCategory.objects.filter(parent_id=category_id).values_list("id", flat=True))
        items = items.filter(category_id__in=category_ids)
    if catalog_id:
        catalog_node = EquipmentCatalogNode.objects.filter(id=catalog_id, item_kind=item_kind, is_active=True).first()
        if catalog_node:
            items = items.filter(catalog_node_id__in=_catalog_descendant_ids(catalog_node))
    if status:
        items = items.filter(status=status)
    if equipment_type:
        items = items.filter(equipment_type=equipment_type)
    if quality_rank:
        items = items.filter(quality_rank=quality_rank)
    if maker:
        items = items.filter(Q(maker__icontains=maker) | Q(supplier_name__icontains=maker))
    if shelf:
        items = items.filter(shelf_no__icontains=shelf)
    if application:
        items = items.filter(Q(applicable_machine_no__icontains=application) | Q(applicable_mold_no__icontains=application))
    if is_asset_list:
        alert = ""
        quality_rank = ""
        shelf = ""
    if alert == "low_stock":
        items = items.filter(minimum_stock__gt=0, current_quantity__lte=F("minimum_stock"))
    elif alert == "calibration_due":
        items = items.filter(calibration_due_date__isnull=False, calibration_due_date__lte=timezone.localdate())
    elif alert == "inventory_due":
        items = items.filter(next_inventory_check_date__isnull=False, next_inventory_check_date__lte=timezone.localdate())
    elif alert == "critical_missing_control":
        items = items.filter(quality_rank="A").filter(Q(control_plan_no="") | Q(process_owner=""))
    elif alert == "missing_photo":
        items = items.filter(Q(item_image__isnull=True) | Q(item_image=""))
    elif alert == "missing_shelf":
        items = items.filter(Q(shelf_no="") | Q(shelf_no__isnull=True))
    if q:
        items = items.filter(
            Q(code__icontains=q)
            | Q(name__icontains=q)
            | Q(internal_name__icontains=q)
            | Q(maker_part_no__icontains=q)
            | Q(alternative_part_no__icontains=q)
            | Q(control_plan_no__icontains=q)
            | Q(process_owner__icontains=q)
            | Q(supplier_name__icontains=q)
            | Q(applicable_machine_no__icontains=q)
            | Q(applicable_mold_no__icontains=q)
            | Q(shelf_no__icontains=q)
            | Q(serial_no__icontains=q)
            | Q(model_no__icontains=q)
            | Q(maker__icontains=q)
            | Q(department__icontains=q)
            | Q(equipment_group_name__icontains=q)
            | Q(equipment_series_name__icontains=q)
            | Q(equipment_document_root_path__icontains=q)
            | Q(equipment_document_subfolder_path__icontains=q)
            | Q(mold_drawing_root_path__icontains=q)
            | Q(mold_drawing_subfolder_path__icontains=q)
            | Q(mold_customer_code__icontains=q)
            | Q(mold_customer_name__icontains=q)
            | Q(mold_product_code__icontains=q)
            | Q(mold_product_name__icontains=q)
            | Q(mold_component_name__icontains=q)
        )
    result_count = items.count()
    page_obj = Paginator(items, 10).get_page(request.GET.get("page"))
    category_queryset = EquipmentCategory.objects.filter(is_active=True).select_related("parent").order_by("group", "parent__code", "code")
    if item_kind == EquipmentItem.KIND_EQUIPMENT:
        category_queryset = category_queryset.filter(Q(code="EQUIPMENT-LEDGER") | Q(parent__code="EQUIPMENT-LEDGER"))
    elif item_kind == EquipmentItem.KIND_MOLD:
        category_queryset = category_queryset.filter(Q(code="MOLD") | Q(parent__code="MOLD"))
    elif item_kind == EquipmentItem.KIND_PART:
        category_queryset = category_queryset.exclude(Q(code="EQUIPMENT-LEDGER") | Q(parent__code="EQUIPMENT-LEDGER"))
        if part_scope == "mold_parts":
            category_queryset = category_queryset.filter(Q(code="MOLD") | Q(parent__code="MOLD"))
        elif part_scope == "equipment_parts":
            category_queryset = category_queryset.exclude(Q(code="MOLD") | Q(parent__code="MOLD"))
    category_choices = list(category_queryset)
    group_labels = dict(EquipmentCategory.GROUP_CHOICES)
    group_sections = []
    for group_value, group_label in EquipmentCategory.GROUP_CHOICES:
        categories = [category for category in category_choices if category.group == group_value]
        if categories:
            group_sections.append({"value": group_value, "label": group_label, "categories": categories[:10]})
    category_tiles = []
    for category in category_choices:
        category_ids = [category.id]
        category_ids += [child.id for child in category.children.all() if child.is_active]
        category_items = base_items.filter(category_id__in=category_ids)
        item_count = category_items.count()
        if not item_count and category.parent_id:
            continue
        sample = category_items.filter(item_image__isnull=False).exclude(item_image="").first() or category_items.first()
        category_tiles.append({"category": category, "item_count": item_count, "sample": sample})
        if len(category_tiles) >= 12:
            break
    catalog_tree = _catalog_flat_tree(item_kind) if item_kind in {EquipmentItem.KIND_EQUIPMENT, EquipmentItem.KIND_MOLD} else []
    catalog_menu_tree = _catalog_nested_tree(item_kind) if item_kind in {EquipmentItem.KIND_EQUIPMENT, EquipmentItem.KIND_MOLD} else []
    catalog_tiles = []
    for row in catalog_tree:
        if row["depth"] > 1:
            continue
        node = row["node"]
        node_ids = _catalog_descendant_ids(node)
        node_items = base_items.filter(catalog_node_id__in=node_ids)
        item_count = node_items.count()
        if not item_count and row["depth"] > 0:
            continue
        sample = node_items.filter(item_image__isnull=False).exclude(item_image="").first() or node_items.first()
        catalog_tiles.append({"node": node, "item_count": item_count, "sample": sample})
        if len(catalog_tiles) >= 12:
            break
    part_items = _apply_part_scope(EquipmentItem.objects.filter(item_kind=EquipmentItem.KIND_PART), part_scope)
    quick_stats = {}
    maker_choices = []
    shelf_choices = []
    if item_kind == EquipmentItem.KIND_PART:
        quick_stats = {
            "low_stock": part_items.filter(minimum_stock__gt=0, current_quantity__lte=F("minimum_stock")).count(),
            "missing_photo": part_items.filter(Q(item_image__isnull=True) | Q(item_image="")).count(),
            "missing_shelf": part_items.filter(Q(shelf_no="") | Q(shelf_no__isnull=True)).count(),
            "critical_missing_control": part_items.filter(quality_rank="A").filter(Q(control_plan_no="") | Q(process_owner="")).count(),
        }
        maker_choices = list(
            part_items.exclude(maker="")
            .values_list("maker", flat=True)
            .distinct()
            .order_by("maker")[:20]
        )
        shelf_choices = list(
            part_items.exclude(shelf_no="")
            .values_list("shelf_no", flat=True)
            .distinct()
            .order_by("shelf_no")[:20]
        )
    return render(
        request,
        "setsubi_zaiko/item_list.html",
        {
            "page_obj": page_obj,
            "group_choices": EquipmentCategory.GROUP_CHOICES,
            "item_kind_choices": EquipmentItem.ITEM_KIND_CHOICES,
            "is_asset_list": is_asset_list,
            "lock_item_kind": bool(forced_item_kind),
            "list_title": {
                EquipmentItem.KIND_EQUIPMENT: "設備・機械台帳",
                EquipmentItem.KIND_MOLD: "金型台帳",
                EquipmentItem.KIND_PART: "部品在庫一覧",
            }.get(item_kind, "マスター一覧") if not part_scope else {
                "equipment_parts": "設備・機械部品",
                "mold_parts": "金型部品",
            }.get(part_scope, "部品在庫一覧"),
            "list_subtitle": {
                EquipmentItem.KIND_EQUIPMENT: "Excel設備リスト由来の設備・機械マスター。数量・在庫としては扱いません。",
                EquipmentItem.KIND_MOLD: "金型専用マスター。設備とは別の管理項目で扱います。",
                EquipmentItem.KIND_PART: "入庫・出庫・棚番・最低在庫を管理する部品だけの在庫一覧です。",
            }.get(item_kind, "") if not part_scope else {
                "equipment_parts": "成形機・周辺設備・電装品・機械部品など、設備側で使う交換部品を管理します。",
                "mold_parts": "入れ子、コアピン、エジェクタピン、スライド、スプリングなど、金型側で使う交換部品を管理します。",
            }.get(part_scope, ""),
            "category_choices": category_choices,
            "category_tiles": category_tiles,
            "catalog_tree": catalog_tree,
            "catalog_menu_tree": catalog_menu_tree,
            "catalog_tiles": catalog_tiles,
            "group_sections": group_sections,
            "group_labels": group_labels,
            "result_count": result_count,
            "quick_stats": quick_stats,
            "maker_choices": maker_choices,
            "shelf_choices": shelf_choices,
            "status_choices": EquipmentItem.STATUS_CHOICES,
            "type_choices": _part_scope_type_choices(part_scope),
            "quality_rank_choices": EquipmentItem.QUALITY_RANK_CHOICES,
            "alert_choices": [
                ("low_stock", "最低在庫以下"),
                ("calibration_due", "校正期限切れ"),
                ("inventory_due", "棚卸期限切れ"),
                ("critical_missing_control", "Aランク管理情報不足"),
                ("missing_photo", "写真未登録"),
                ("missing_shelf", "棚番未設定"),
            ],
            "filters": {"item_kind": item_kind, "part_scope": part_scope, "group": group, "category": category_id, "catalog": catalog_id, "status": status, "equipment_type": equipment_type, "quality_rank": quality_rank, "alert": alert, "maker": maker, "shelf": shelf, "application": application, "q": q},
        },
    )


@login_required
def equipment_list(request):
    return item_list(request, forced_item_kind=EquipmentItem.KIND_PART, part_scope="equipment_parts")


@login_required
def mold_list(request):
    return item_list(request, forced_item_kind=EquipmentItem.KIND_PART, part_scope="mold_parts")


@login_required
def part_list(request):
    return redirect("setsubi_zaiko:equipment_list")


@login_required
def item_create(request):
    form = EquipmentItemForm(request.POST or None, request.FILES or None)
    if request.method == "POST" and form.is_valid():
        item = form.save(commit=False)
        item.created_by = request.user
        item.save()
        messages.success(request, "機器・部品マスターを登録しました。")
        return redirect("setsubi_zaiko:item_list")
    return render(request, "setsubi_zaiko/form.html", {"form": form, "title": "機器・部品マスター登録", "form_kind": "item"})


@login_required
def item_detail(request, pk):
    item = get_object_or_404(EquipmentItem.objects.select_related("category", "category__parent", "catalog_node", "catalog_node__parent"), pk=pk)
    ledgers = item.ledgers.select_related("item").order_by("-created_at")[:20]
    linked_parts = item.linked_parts.select_related("part", "part__category").order_by("criticality", "part__code")
    used_by_assets = item.used_by_assets.select_related("asset", "asset__category").order_by("asset__code")
    is_asset = item.is_asset_master
    return render(
        request,
        "setsubi_zaiko/item_detail.html",
        {"item": item, "ledgers": ledgers, "linked_parts": linked_parts, "used_by_assets": used_by_assets, "is_asset": is_asset},
    )


@login_required
def part_link_create(request, pk=None):
    asset = get_object_or_404(EquipmentItem, pk=pk) if pk else None
    form = EquipmentPartLinkForm(request.POST or None, asset=asset)
    if request.method == "POST" and form.is_valid():
        link = form.save()
        messages.success(request, "使用部品をリンクしました。")
        return redirect("setsubi_zaiko:item_detail", pk=link.asset_id)
    title = "使用部品リンク登録"
    return render(request, "setsubi_zaiko/form.html", {"form": form, "title": title, "form_kind": "part_link", "item": asset})


@login_required
def item_edit(request, pk):
    item = get_object_or_404(EquipmentItem, pk=pk)
    form = EquipmentItemForm(request.POST or None, request.FILES or None, instance=item)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "機器・部品マスターを更新しました。")
        return redirect("setsubi_zaiko:item_detail", pk=item.pk)
    return render(
        request,
        "setsubi_zaiko/form.html",
        {"form": form, "title": "機器・部品マスター編集", "form_kind": "item", "item": item},
    )


@login_required
def master_list(request):
    master_type = request.GET.get("type") or "category"
    q = request.GET.get("q") or ""
    item_kind = request.GET.get("item_kind") or ""
    if master_type == "catalog":
        rows = EquipmentCatalogNode.objects.select_related("parent").annotate(item_count=Count("items", distinct=True), child_count=Count("children", distinct=True)).order_by("item_kind", "sort_order", "code")
        if item_kind in {EquipmentItem.KIND_EQUIPMENT, EquipmentItem.KIND_MOLD}:
            rows = rows.filter(item_kind=item_kind)
        if q:
            rows = rows.filter(Q(code__icontains=q) | Q(name__icontains=q) | Q(parent__name__icontains=q) | Q(note__icontains=q))
    else:
        master_type = "category"
        rows = EquipmentCategory.objects.select_related("parent").annotate(item_count=Count("items", distinct=True), child_count=Count("children", distinct=True)).order_by("group", "parent__code", "code")
        if q:
            rows = rows.filter(Q(code__icontains=q) | Q(name__icontains=q) | Q(parent__name__icontains=q) | Q(description__icontains=q))
    page_obj = Paginator(rows, 20).get_page(request.GET.get("page"))
    return render(
        request,
        "setsubi_zaiko/master_list.html",
        {
            "page_obj": page_obj,
            "master_type": master_type,
            "filters": {"type": master_type, "q": q, "item_kind": item_kind},
            "item_kind_choices": [(EquipmentItem.KIND_EQUIPMENT, "設備台帳"), (EquipmentItem.KIND_MOLD, "金型台帳")],
        },
    )


@login_required
def category_create(request):
    form = EquipmentCategoryForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "分類マスターを登録しました。")
        return redirect("setsubi_zaiko:master_list")
    return render(request, "setsubi_zaiko/form.html", {"form": form, "title": "分類マスター登録", "form_kind": "category", "cancel_url_name": "setsubi_zaiko:master_list"})


@login_required
def category_edit(request, pk):
    category = get_object_or_404(EquipmentCategory, pk=pk)
    form = EquipmentCategoryForm(request.POST or None, instance=category)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "分類マスターを更新しました。")
        return redirect("setsubi_zaiko:master_list")
    return render(request, "setsubi_zaiko/form.html", {"form": form, "title": "分類マスター編集", "form_kind": "category", "cancel_url_name": "setsubi_zaiko:master_list"})


@login_required
def category_delete(request, pk):
    category = get_object_or_404(EquipmentCategory.objects.annotate(item_count=Count("items", distinct=True), child_count=Count("children", distinct=True)), pk=pk)
    if request.method == "POST":
        if category.item_count or category.child_count:
            category.is_active = False
            category.save(update_fields=["is_active", "updated_at"])
            messages.warning(request, "使用中の分類のため、削除ではなく無効にしました。")
        else:
            category.delete()
            messages.success(request, "分類マスターを削除しました。")
        return redirect("setsubi_zaiko:master_list")
    return render(request, "setsubi_zaiko/confirm_delete.html", {"object": category, "title": "分類マスター削除", "cancel_url_name": "setsubi_zaiko:master_list", "has_dependencies": category.item_count or category.child_count})


@login_required
def catalog_create(request):
    initial = {}
    item_kind = request.GET.get("item_kind") or ""
    parent_id = request.GET.get("parent") or ""
    if item_kind in {EquipmentItem.KIND_EQUIPMENT, EquipmentItem.KIND_MOLD}:
        initial["item_kind"] = item_kind
    if parent_id:
        parent = EquipmentCatalogNode.objects.filter(pk=parent_id, is_active=True).first()
        if parent:
            initial["parent"] = parent
            initial["item_kind"] = parent.item_kind
    form = EquipmentCatalogNodeForm(request.POST or None, initial=initial)
    if request.method == "POST" and form.is_valid():
        node = form.save()
        messages.success(request, "カタログを登録しました。")
        return redirect(f"{reverse('setsubi_zaiko:master_list')}?type=catalog&item_kind={node.item_kind}")
    return render(request, "setsubi_zaiko/form.html", {"form": form, "title": "カタログ登録", "form_kind": "catalog", "cancel_url_name": "setsubi_zaiko:master_list"})


@login_required
def catalog_edit(request, pk):
    node = get_object_or_404(EquipmentCatalogNode, pk=pk)
    form = EquipmentCatalogNodeForm(request.POST or None, instance=node)
    if request.method == "POST" and form.is_valid():
        node = form.save()
        messages.success(request, "カタログを更新しました。")
        return redirect(f"{reverse('setsubi_zaiko:master_list')}?type=catalog&item_kind={node.item_kind}")
    return render(request, "setsubi_zaiko/form.html", {"form": form, "title": "カタログ編集", "form_kind": "catalog", "cancel_url_name": "setsubi_zaiko:master_list"})


@login_required
def catalog_delete(request, pk):
    node = get_object_or_404(EquipmentCatalogNode.objects.annotate(item_count=Count("items", distinct=True), child_count=Count("children", distinct=True)), pk=pk)
    if request.method == "POST":
        item_kind = node.item_kind
        if node.item_count or node.child_count:
            node.is_active = False
            node.save(update_fields=["is_active", "updated_at"])
            messages.warning(request, "使用中のカタログのため、削除ではなく無効にしました。")
        else:
            node.delete()
            messages.success(request, "カタログを削除しました。")
        return redirect(f"{reverse('setsubi_zaiko:master_list')}?type=catalog&item_kind={item_kind}")
    return render(request, "setsubi_zaiko/confirm_delete.html", {"object": node, "title": "カタログ削除", "cancel_url_name": "setsubi_zaiko:master_list", "has_dependencies": node.item_count or node.child_count})


@login_required
def ledger_list(request):
    ledgers = EquipmentStockLedger.objects.select_related("item", "item__category").order_by("-created_at")
    transaction_type = request.GET.get("transaction_type") or ""
    q1 = request.GET.get("q1") or ""
    q2 = request.GET.get("q2") or ""
    q3 = request.GET.get("q3") or ""
    if transaction_type:
        ledgers = ledgers.filter(transaction_type=transaction_type)
    for keyword in [q1, q2, q3]:
        if keyword:
            ledgers = ledgers.filter(
                Q(item__code__icontains=keyword)
                | Q(item__name__icontains=keyword)
                | Q(item__category__name__icontains=keyword)
                | Q(item__category__parent__name__icontains=keyword)
                | Q(item__equipment_type__icontains=keyword)
                | Q(item__maker_part_no__icontains=keyword)
                | Q(item__applicable_machine_no__icontains=keyword)
                | Q(item__applicable_mold_no__icontains=keyword)
                | Q(item__shelf_no__icontains=keyword)
                | Q(memo__icontains=keyword)
            )
    summary_rows = (
        ledgers.values("item__category__name", "transaction_type")
        .annotate(row_count=Count("id"), total_quantity=Sum("quantity"))
        .order_by("item__category__name", "transaction_type")[:12]
    )
    page_obj = Paginator(ledgers, 10).get_page(request.GET.get("page"))
    return render(
        request,
        "setsubi_zaiko/ledger_list.html",
        {
            "page_obj": page_obj,
            "summary_rows": summary_rows,
            "transaction_choices": EquipmentStockLedger.TRANSACTION_CHOICES,
            "filters": {"transaction_type": transaction_type, "q1": q1, "q2": q2, "q3": q3},
        },
    )


@login_required
@transaction.atomic
def ledger_create(request, mode=None):
    mode_map = {
        "in": {
            "transaction_type": "IN",
            "title": "入庫ワークフロー",
            "subtitle": "購入・返却・修理戻りを在庫へ戻します。",
            "accent": "emerald",
            "steps": ["部品を選ぶ", "入庫数を入力", "理由とロットを記録", "確認して登録"],
            "reason_presets": ["new_purchase", "return_to_stock", "repair_return", "transfer_in"],
        },
        "out": {
            "transaction_type": "OUT",
            "title": "出庫ワークフロー",
            "subtitle": "設備・金型の修理や交換で使用した部品を払い出します。",
            "accent": "rose",
            "steps": ["部品を選ぶ", "出庫数を入力", "使用先・理由を記録", "確認して登録"],
            "reason_presets": ["issue_to_use", "send_repair", "transfer_out"],
        },
        "adjust": {
            "transaction_type": None,
            "title": "調整ワークフロー",
            "subtitle": "棚卸差異、廃棄、修正を履歴として残します。",
            "accent": "amber",
            "steps": ["部品を選ぶ", "増減区分を選ぶ", "調整数を入力", "確認して登録"],
            "reason_presets": ["inventory_adjustment", "scrap", "lost", "other"],
        },
    }
    workflow = mode_map.get(mode)
    fixed_transaction_type = workflow["transaction_type"] if workflow else None
    initial = {"operator_name": _operator_name(request), "transaction_type": fixed_transaction_type}
    initial_item_id = request.GET.get("item")
    if request.method == "GET" and initial_item_id:
        initial_item = EquipmentItem.objects.filter(pk=initial_item_id, item_kind=EquipmentItem.KIND_PART).first()
        if initial_item:
            initial["item"] = initial_item
    form = EquipmentStockLedgerForm(
        request.POST or None,
        initial=initial,
        transaction_type=fixed_transaction_type,
    )
    if workflow:
        choices = list(form.fields["reason_code"].choices)
        preset = set(workflow["reason_presets"])
        form.fields["reason_code"].choices = [choice for choice in choices if choice[0] in preset] or choices
    if request.method == "POST" and form.is_valid():
        item = EquipmentItem.objects.select_for_update().get(pk=form.cleaned_data["item"].pk)
        transaction_type = form.cleaned_data["transaction_type"]
        quantity = form.cleaned_data["quantity"] or Decimal("0")
        before = item.current_quantity
        signed_quantity = quantity
        if transaction_type in ("OUT", "ADJ-", "SCRAP"):
            signed_quantity = -quantity
        after = before + signed_quantity
        if after < 0:
            form.add_error("quantity", "在庫数量がマイナスになります。数量を確認してください。")
        else:
            reason_code = form.cleaned_data["reason_code"]
            ledger = EquipmentStockLedger.objects.create(
                item=item,
                transaction_type=transaction_type,
                reason_code=reason_code,
                reason_label=dict(EquipmentStockLedger.REASON_CHOICES).get(reason_code, reason_code),
                memo=form.cleaned_data["memo"],
                quantity=quantity,
                quantity_before=before,
                quantity_after=after,
                lot_no=form.cleaned_data["lot_no"],
                from_location=form.cleaned_data["from_location"],
                to_location=form.cleaned_data["to_location"],
                operator_name=form.cleaned_data["operator_name"] or _operator_name(request),
                supervisor_confirmed=form.cleaned_data["supervisor_confirmed"],
                supervisor_name=form.cleaned_data["supervisor_name"],
                confirmed_at=timezone.now() if form.cleaned_data["supervisor_confirmed"] else None,
                created_by=request.user,
            )
            item.current_quantity = after
            if transaction_type in ("OUT", "ADJ-", "SCRAP") and after == 0:
                item.status = "in_use" if transaction_type == "OUT" else item.status
            if transaction_type in ("IN", "ADJ+", "RETURN") and item.status in ("scrapped", "lost"):
                item.status = "in_stock"
            item.save(update_fields=["current_quantity", "status", "updated_at"])
            messages.success(request, f"台帳を登録しました: {ledger.system_no}")
            return redirect("setsubi_zaiko:ledger_list")
    if workflow:
        return render(request, "setsubi_zaiko/ledger_workflow.html", {"form": form, "workflow": workflow, "mode": mode})
    return render(request, "setsubi_zaiko/form.html", {"form": form, "title": "入出庫・調整登録", "form_kind": "ledger"})


@login_required
def export_items_csv(request):
    response = _csv_response("equipment_inventory.csv")
    writer = csv.writer(response)
    _write_audit_header(writer, "設備・部品在庫一覧", _operator_name(request))
    writer.writerow([
        "機器コード",
        "機器名",
        "社内呼称",
        "メーカー品番",
        "代替品番",
        "適用機械No.",
        "適用金型No.",
        "棚番",
        "最低在庫",
        "発注点",
        "品質ランク",
        "Control Plan No.",
        "管理責任者",
        "購入先",
        "購入先URL",
        "大分類",
        "分類",
        "種別",
        "シリアルNo.",
        "型式",
        "保管場所",
        "使用部署",
        "校正期限",
        "最終棚卸日",
        "次回棚卸期限",
        "状態",
        "現在数量",
        "単位",
        "更新日時",
    ])
    for item in EquipmentItem.objects.select_related("category").filter(item_kind=EquipmentItem.KIND_PART).order_by("code"):
        writer.writerow([
            _excel_text(item.code),
            item.name,
            item.internal_name,
            _excel_text(item.maker_part_no),
            _excel_text(item.alternative_part_no),
            _excel_text(item.applicable_machine_no),
            _excel_text(item.applicable_mold_no),
            _excel_text(item.shelf_no),
            item.minimum_stock,
            item.reorder_point,
            item.get_quality_rank_display(),
            _excel_text(item.control_plan_no),
            item.process_owner,
            item.supplier_name,
            item.supplier_part_url,
            item.category.get_group_display(),
            item.category.name,
            item.get_equipment_type_display(),
            _excel_text(item.serial_no),
            _excel_text(item.model_no),
            item.location,
            item.department,
            item.calibration_due_date.strftime("%Y-%m-%d") if item.calibration_due_date else "",
            item.last_inventory_check_date.strftime("%Y-%m-%d") if item.last_inventory_check_date else "",
            item.next_inventory_check_date.strftime("%Y-%m-%d") if item.next_inventory_check_date else "",
            item.get_status_display(),
            item.current_quantity,
            item.unit,
            timezone.localtime(item.updated_at).strftime("%Y-%m-%d %H:%M:%S"),
        ])
    return response


@login_required
def export_ledger_csv(request):
    response = _csv_response("equipment_stock_ledger.csv")
    writer = csv.writer(response)
    _write_audit_header(writer, "設備・部品入出庫台帳", _operator_name(request))
    writer.writerow(["取引区分", "理由コード", "理由", "調整前→後", "数量", "機器コード", "機器名", "機器分類", "シリアルNo.", "ロットNo.", "移動元", "移動先", "作業者", "上長確認", "確認日時", "システムNo.", "記録日時"])
    for ledger in EquipmentStockLedger.objects.select_related("item", "item__category").order_by("-created_at"):
        writer.writerow([
            ledger.transaction_type,
            ledger.reason_code,
            ledger.reason_label,
            f"{ledger.quantity_before} -> {ledger.quantity_after}",
            ledger.quantity,
            _excel_text(ledger.item.code),
            ledger.item.name,
            ledger.item.category.name,
            _excel_text(ledger.item.serial_no),
            _excel_text(ledger.lot_no),
            ledger.from_location,
            ledger.to_location,
            ledger.operator_name,
            "済" if ledger.supervisor_confirmed else "未",
            timezone.localtime(ledger.confirmed_at).strftime("%Y-%m-%d %H:%M:%S") if ledger.confirmed_at else "",
            _excel_text(ledger.system_no),
            timezone.localtime(ledger.created_at).strftime("%Y-%m-%d %H:%M:%S"),
        ])
    return response
