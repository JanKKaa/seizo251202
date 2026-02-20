from django.urls import path
from . import views

app_name = "nhap_lieu"

urlpatterns = [
    path('', views.index, name='index'),
    path('mau-nhap-lieu/', views.mau_nhaplieu, name='mau_nhaplieu'),
    path('mau-list/', views.mau_list, name='mau_list'),
    path('mau-xoa/<str:ten_chuong_trinh>/', views.mau_xoa, name='mau_xoa'),
    path('quanly-may/', views.quanly_may, name='quanly_may'),
]