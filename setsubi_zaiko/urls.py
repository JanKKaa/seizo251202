from django.urls import path

from . import views

app_name = "setsubi_zaiko"

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("items/", views.item_list, name="item_list"),
    path("equipment/", views.equipment_list, name="equipment_list"),
    path("molds/", views.mold_list, name="mold_list"),
    path("equipment-parts/", views.equipment_part_list, name="equipment_part_list"),
    path("mold-parts/", views.mold_part_list, name="mold_part_list"),
    path("parts/", views.part_list, name="part_list"),
    path("items/add/", views.item_create, name="item_create"),
    path("items/<int:pk>/", views.item_detail, name="item_detail"),
    path("items/<int:pk>/edit/", views.item_edit, name="item_edit"),
    path("items/<int:pk>/shot-source/", views.item_shot_source_edit, name="item_shot_source_edit"),
    path("items/<int:pk>/delete/", views.item_delete, name="item_delete"),
    path("items/<int:pk>/parts/add/", views.part_link_create, name="part_link_create"),
    path("part-links/add/", views.part_link_create, name="part_link_create_any"),
    path("part-links/<int:pk>/edit/", views.part_link_edit, name="part_link_edit"),
    path("part-links/<int:pk>/delete/", views.part_link_delete, name="part_link_delete"),
    path("part-links/<int:pk>/replace/", views.part_replacement_create, name="part_replacement_create"),
    path("masters/", views.master_list, name="master_list"),
    path("categories/add/", views.category_create, name="category_create"),
    path("categories/<int:pk>/edit/", views.category_edit, name="category_edit"),
    path("categories/<int:pk>/delete/", views.category_delete, name="category_delete"),
    path("catalogs/add/", views.catalog_create, name="catalog_create"),
    path("catalogs/<int:pk>/edit/", views.catalog_edit, name="catalog_edit"),
    path("catalogs/<int:pk>/delete/", views.catalog_delete, name="catalog_delete"),
    path("ledger/", views.ledger_list, name="ledger_list"),
    path("ledger/add/", views.ledger_create, name="ledger_create"),
    path("ledger/in/", views.ledger_create, {"mode": "in"}, name="ledger_in"),
    path("ledger/out/", views.ledger_create, {"mode": "out"}, name="ledger_out"),
    path("ledger/adjust/", views.ledger_create, {"mode": "adjust"}, name="ledger_adjust"),
    path("ledger/<int:pk>/edit/", views.ledger_edit, name="ledger_edit"),
    path("ledger/<int:pk>/delete/", views.ledger_delete, name="ledger_delete"),
    path("export/items.csv", views.export_items_csv, name="export_items_csv"),
    path("export/ledger.csv", views.export_ledger_csv, name="export_ledger_csv"),
]
