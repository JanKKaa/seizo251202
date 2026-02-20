from django.urls import path
from . import views

urlpatterns = [
    path('', views.index, name='mente_index'),
    path('add/', views.add_product, name='add_product'),
    path('checksheet/<int:product_id>/', views.checksheet, name='checksheet'),
    path('checksheet/<int:product_id>/delete/<int:checksheet_id>/', views.delete_checksheet, name='delete_checksheet'),
    path('checksheet/<int:product_id>/update/', views.update_checksheet_fields, name='update_checksheet_fields'),
    path('lich-su-kiem-tra/<int:product_id>/', views.lichsukiemtra_list, name='lichsukiemtra_list'),
    path('lich-su-kiem-tra/xoa/<int:record_id>/', views.delete_lichsukiemtra, name='delete_lichsukiemtra'),
    path('delete_product/<int:product_id>/', views.delete_product, name='delete_product'),
    path('checker/', views.checker, name='checker'),  # Đường dẫn đến trang quản lý người kiểm tra
    path('checker/delete/<int:checker_id>/', views.delete_checker, name='delete_checker'),
]