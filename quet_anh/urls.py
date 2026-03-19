from django.urls import path
from . import views

urlpatterns = [
    path('', views.index_qa, name='index_qa'),
    path('upload/', views.upload_image, name='upload_image'),
    path('stock-in/start/', views.stock_in_start, name='stock_in_start'),
    path('history/', views.qa_history, name='qa_history'),
    path('history/delete/<int:pk>/', views.delete_qa_history, name='delete_qa_history'),

    path('device/', views.qa_device_list, name='qa_device_list'),
    path('device/add/', views.add_qa_device, name='add_qa_device'),
    path('device/edit/<int:pk>/', views.edit_qa_device, name='edit_qa_device'),
    path('device/delete/<int:pk>/', views.delete_qa_device, name='delete_qa_device'),
    path('material-master/', views.material_master_list, name='material_master_list'),
    path('material-master/add/', views.material_master_add, name='material_master_add'),
    path('material-master/edit/<int:pk>/', views.material_master_edit, name='material_master_edit'),
    path('material-master/delete/<int:pk>/', views.material_master_delete, name='material_master_delete'),

    path('dashboard/', views.dashboard_qa, name='dashboard_qa'),
    path('auto-input-ledger/', views.auto_input_ledger_list, name='auto_input_ledger_list'),
    path('auto-input-ledger/delete/<int:pk>/', views.auto_input_ledger_delete, name='auto_input_ledger_delete'),
    path('material-stock-ledger/', views.material_stock_ledger, name='material_stock_ledger'),
    path('material-stock-ledger/confirm/<int:pk>/', views.material_stock_ledger_confirm, name='material_stock_ledger_confirm'),
    path('material-stock-ledger/edit/<int:pk>/', views.material_stock_ledger_edit, name='material_stock_ledger_edit'),
    path('material-stock-ledger/delete/<int:pk>/', views.material_stock_ledger_delete, name='material_stock_ledger_delete'),
    path('material-out-stock-ledger/', views.material_out_stock_ledger, name='material_out_stock_ledger'),
    path('material-out-stock-ledger/confirm/<int:pk>/', views.material_out_stock_ledger_confirm, name='material_out_stock_ledger_confirm'),
    path('material-out-stock-ledger/edit/<int:pk>/', views.material_out_stock_ledger_edit, name='material_out_stock_ledger_edit'),
    path('material-out-stock-ledger/delete/<int:pk>/', views.material_out_stock_ledger_delete, name='material_out_stock_ledger_delete'),
    path("api/latest-events/", views.latest_vision_events, name="vision_latest_events"),
]
