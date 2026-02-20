from django.urls import path
from . import views

urlpatterns = [
    path('upload/', views.upload_image, name='upload_image'),
    path('', views.index_xla, name='index_xla'),  # Trang giao diện chính xử lý ảnh
   
    
    
   
    path('index-xla/', views.index_xla, name='index_xla'),
    path('device-info/', views.device_info_list, name='device_info_list'),
    path('device-info/add/', views.add_device_info, name='add_device_info'),
    path('device-info/edit/<int:pk>/', views.edit_device_info, name='edit_device_info'),
    path('device-info/delete/<int:pk>/', views.delete_device_info, name='delete_device_info'),
    path('lich-su/', views.lich_su, name='lich_su'),
]