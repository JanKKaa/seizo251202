from django.urls import path
from . import views

app_name = 'menu'

urlpatterns = [
    path('', views.MenuListView.as_view(), name='list'),
    path('them/', views.MenuCreateView.as_view(), name='create'),
    path('<int:pk>/sua/', views.MenuUpdateView.as_view(), name='update'),
    path('<int:pk>/xoa/', views.MenuDeleteView.as_view(), name='delete'),
    path('<int:pk>/dat-mon/', views.order_menu, name='order'),
    path('dangnhap/', views.dangnhap_ma_nv, name='dangnhap'),
    path('nhanvien/', views.nhanvien_list, name='nhanvien_list'),
    path('nhanvien/them/', views.nhanvien_create, name='nhanvien_create'),
    path('nhanvien/<int:pk>/sua/', views.nhanvien_update, name='nhanvien_update'),
    path('nhanvien/<int:pk>/xoa/', views.nhanvien_delete, name='nhanvien_delete'),
    path('logout_nv/', views.logout_nv, name='logout_nv'),
    # Holiday management
    path('holiday/', views.holiday_list, name='holiday_list'),
    path('holiday/delete/<int:pk>/', views.holiday_delete, name='holiday_delete'),
    path('order-history/', views.order_history, name='order_history'),
    path('order/<int:pk>/edit/', views.order_edit, name='order_edit'),
    path('order/<int:pk>/reorder/', views.order_reorder, name='order_reorder'),
    path('order/delete/<int:pk>/', views.order_delete, name='order_delete'),
    path('order/delete_all/<str:ma_nv>/', views.order_delete_all, name='order_delete_all'),
    path('order_kanri/', views.order_kanri, name='order_kanri'),
    path('order_kanri/csv/', views.order_kanri_csv, name='order_kanri_csv'),
    path('order_kanri/excel/', views.order_kanri_excel, name='order_kanri_excel'),
    path('order_kanri/pdf/', views.order_kanri_pdf, name='order_kanri_pdf'),
    path('order_detail/<int:year>/<int:month>/<int:day>/', views.order_detail, name='order_detail'),
    path('order_detail/<int:year>/<int:month>/<int:day>/fax-set/', views.fax_set, name='fax_set'),
    path('order_detail/<int:year>/<int:month>/<int:day>/fax-unset/', views.fax_unset, name='fax_unset'),
    path('order_detail/<int:year>/<int:month>/<int:day>/fax-printed/', views.fax_mark_printed, name='fax_mark_printed'),
    path('order_menu_year/<int:pk>/', views.order_menu_year, name='order_menu_year'),
    path('order/change_calamviec_multi/', views.change_calamviec_multi, name='change_calamviec_multi'),
    path('copy_order/', views.copy_order, name='copy_order'),
]