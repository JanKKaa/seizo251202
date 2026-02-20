from django.urls import path
from . import views, views_devices, views_index, views_oee, views_esp32
from .views import edit_shot_total, manual_machine_add
from .views_devices import (
    api_device_realtime, component_replace_ajax, component_update_ajax, component_history_ajax, arduino_data, arduino_status_latest, arduino_status_page, arduino_status_all, arduino_status_all_page, api_device_raw, api_alarms_active, api_alarm_distribution
)
from .views_esp32 import esp32_data_api, esp32_status_proxy, esp32_status_processed
from .views_devices import api_devices_runtime
from . import views_csv
from .views_esp32 import esp32_alarm_popup
from . import viewsticker
from . import views_center2
from .views_weather import weather_minowa, jma_forecast_nagano
from .views_change4m import change4m_manage, change4m_updates_api
from .viewschatworks import chatwork_latest, chatwork_list_from_db, chatwork_grouped_by_date
from . import viewschatworks
from django.views.generic import TemplateView
from .views_csv import master_import, master_add, master_edit

app_name = 'iot'

urlpatterns = [
    # --- Trang chủ ---
    path('', views_index.index, name='index'),  # hoặc views.index nếu dùng views.py

    # --- Khuôn ---
    path('molding/', views.molding_list, name='molding'),
    path('molding/<int:pk>/edit/', views.molding_edit, name='molding_edit'),
    path('molding/create/', views.molding_create, name='molding_create'),
    path('molding/<int:pk>/delete/', views.molding_delete, name='molding_delete'),

    # --- Counter ---
    path('machine-counter/', views.machine_counter, name='machine_counter'),
    path('machine/<int:pk>/edit_shot_total/', edit_shot_total, name='edit_shot_total'),
    path('manual-machine/add/', manual_machine_add, name='manual_machine_add'),

    # --- Device CRUD ---
    path('devices/', views_devices.device_list, name='device_list'),
    path('devices/import/', views_devices.device_bulk_import, name='device_bulk_import'),
    path('devices/new/', views_devices.device_create, name='device_create'),
    path('devices/<int:pk>/', views_devices.device_detail, name='device_detail'),
    path('devices/<int:pk>/edit/', views_devices.device_update, name='device_update'),
    path('devices/<int:pk>/delete/', views_devices.device_delete, name='device_delete'),
    path('devices/<int:pk>/toggle/', views_devices.device_toggle_active, name='device_toggle_active'),

    # --- API/JSON ---
    path('api/devices/', views_devices.api_devices, name='api_devices'),
    path('api/devices/metrics/', views_devices.api_device_metrics, name='api_device_metrics'),
    path('api/devices/<int:pk>/', views_devices.api_device_detail, name='api_device_detail'),
    path('api/devices/<int:pk>/realtime/', api_device_realtime, name='api_device_realtime'),
    path('api/devices/runtime/', api_devices_runtime, name='api_devices_runtime'),

    # --- AJAX cho linh kiện ---
    path('components/<int:component_id>/replace/', component_replace_ajax, name='component_replace_ajax'),
    path('components/<int:component_id>/update/', component_update_ajax, name='component_update_ajax'),
    path('components/<int:component_id>/history/', component_history_ajax, name='component_history_ajax'),

    # --- Arduino ---
    path('arduino/data/', arduino_data, name='arduino_data'),

    # --- Arduino Status ---
    path('arduino/status/', arduino_status_latest, name='arduino_status_latest'),

    # --- Arduino Status Page ---
    path('arduino/status/page/', arduino_status_page, name='arduino_status_page'),

    # --- Arduino Status All ---
    path('arduino/status/all/', arduino_status_all, name='arduino_status_all'),

    # --- Arduino Status All Page ---
    path('arduino/status/all/page/', arduino_status_all_page, name='arduino_status_all_page'),

    # --- API Device Raw ---
    path('api/devices/raw/', api_device_raw, name='api_device_raw'),

    # --- API Alarms Active ---
    path('api/alarms/active/', api_alarms_active, name='api_alarms_active'),

    # --- API Alarm Distribution ---
    path('api/alarms/distribution/', api_alarm_distribution, name='api_alarm_distribution'),

    # --- Trang index ---
    path('index/', views_index.index, name='iot_index'),
    path('notification/<int:pk>/delete/', views_index.delete_notification, name='delete_notification'),
    path('dashboard/', views_index.dashboard, name='iot_dashboard'),
    path('dashboard_json/', views_index.dashboard_json, name='dashboard_json'),
    path('dashboard_notifications_json/', views.dashboard_notifications_json, name='dashboard_notifications_json'),

    # --- Alarm Count Per Machine Per Month ---
    # ...existing code...
    path('alarm_top5_machine_month/', views_index.alarm_top5_machine_month, name='alarm_top5_machine_month'),
   
    # --- OEE ---
    path('oee_today/', views_oee.oee_today, name='oee_today'),

    # --- ESP32 API ---
    path('api/esp32/', esp32_data_api, name='esp32_data_api'),
    path('api/esp32/status/', esp32_status_processed, name='esp32_status_processed'),
    path('api/esp32/status_raw/', esp32_status_proxy, name='esp32_status_proxy'),
    path('api/esp32/status_processed/', esp32_status_processed, name='esp32_status_processed'),
    path('api/esp32_machines/', views_esp32.esp32_status_processed_targets, name='esp32_machines'),

    # --- CSV Upload ---
    path('upload_plan/', views_csv.upload_production_plan, name='upload_production_plan'),
    path('upload_material_plan/', views_csv.upload_material_plan, name='upload_material_plan'),
    path('plan_status/', views_csv.production_plan_status, name='production_plan_status'),
    path('add_pallet_plan/', views_csv.add_pallet_plan, name='add_pallet_plan'),
    path('delete_pallet_plan/', views_csv.delete_pallet_plan, name='delete_pallet_plan'),

    # --- ESP32 Alarm Popup ---
    path('api/esp32_alarm_popup/', esp32_alarm_popup),
    path('api/ticker/', viewsticker.ticker_view, name='api_ticker'),  # <-- thêm dòng này
    path('ticker_view', viewsticker.ticker_view, name='ticker_view'),
    path('center_panel2_partial/', views_center2.center_panel2_partial, name='center_panel2_partial'),
    path('api/weather/minowa/', weather_minowa, name='weather_minowa'),
    path('api/weather/jma/nagano/', jma_forecast_nagano, name='jma_forecast_nagano'),

    # --- Change4M API & CRUD ---
    path('change-4m/manage/', change4m_manage, name='change4m-manage'),
    path('api/change-4m/', change4m_updates_api, name='change4m-updates'),

    # --- Trang chủ ---
    path('', views.index, name='iot_index'),  # Thêm dòng này
    path('add_pallet_plan/', views_csv.add_pallet_plan, name='add_pallet_plan'),

    # --- Chatwork ---
    path('api/chatwork/latest/', chatwork_latest, name='chatwork_latest'),
    path('api/chatwork/list/', chatwork_list_from_db, name='chatwork_list'),
    path('chatwork/', TemplateView.as_view(template_name='iot/chatwork.html'), name='chatwork_page'),

    # --- Chatwork Grouped by Date ---
    path('api/chatwork/grouped/', chatwork_grouped_by_date, name='chatwork_grouped_by_date'),

    # --- Xóa tin nhắn Chatwork ---
    path('api/chatwork/delete/', viewschatworks.chatwork_delete_message, name='chatwork_delete_message'),

    # --- Master Import ---
    path('master/import/', master_import, name='master_import'),
    path('master/add/', master_add, name='master_add'),
    path('master/edit/', master_edit, name='master_edit'),

    # --- Monthly Progress JSON ---
    path("monthly-progress-json/", views_index.monthly_progress_json, name="monthly_progress_json"),

    # --- Center2 ---
    path('center2/', views_index.center2, name='center2'),
    path('control-relay/<str:action>/', views.control_esp32_proxy, name='control_esp32_proxy'),
]

