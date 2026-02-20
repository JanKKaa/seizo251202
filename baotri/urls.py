from django.urls import path
from . import views

urlpatterns = [
    path('', views.index, name='baotri_index'),
    path('add/', views.add_task, name='add_task'),
    path('delete/<int:task_id>/', views.delete_task, name='delete_task'),  # Đường dẫn xóa nhiệm vụ
    path('<int:task_id>/', views.task_detail, name='task_detail'),
    path('<int:task_id>/delete/<int:detail_id>/', views.delete_task_detail, name='delete_task_detail'),
    path('task_code/', views.task_code, name='task_code'),
    path('start_task/<str:task_code>/', views.start_task, name='start_task'),
    path('task_code_list/', views.task_code_list, name='task_code_list'),
    path('task_code_detail/<int:task_code_id>/', views.task_code_detail, name='task_code_detail'),
    path('delete_task_code/<int:task_code_id>/', views.delete_task_code, name='delete_task_code'),
    path('list/', views.task_list, name='task_list'),  # Định nghĩa URL cho task_list
    path('edit_task/<int:task_id>/', views.edit_task, name='edit_task'),
    path('task_code/<int:pk>/edit_time/', views.edit_task_code_time, name='edit_task_code_time'),
    path('dashboard/', views.dashboard, name='baotri_dashboard'),
    path('export/pdf/', views.export_maintenance_pdf, name='export_maintenance_pdf'),
    path('export/csv/', views.export_maintenance_csv, name='export_maintenance_csv'),
    path('task_code/<int:pk>/confirm/', views.confirm_task_code, name='confirm_task_code'),
    path('task_code/<int:pk>/remove_confirm/', views.remove_supervisor_confirm, name='remove_supervisor_confirm'),
    
    # XÓA hoặc COMMENT các dòng này nếu không còn dùng:
    # path('mistake/list/', views.mistake_list, name='mistake_list'),
    # path('mistake/<int:pk>/', views.mistake_detail, name='mistake_detail'),
    path('mistake/manage/', views.mistake_manage, name='mistake_manage'),
    path('mistake/manage/<int:edit_pk>/', views.mistake_manage, name='mistake_edit'),
    path('quan-ly-shot/', views.shot_report, name='baotri_shot_report'),
]