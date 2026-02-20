# filepath: c:\Users\Shin\seizo0\trang_chu\news\urls.py
from django.urls import path
from . import views

urlpatterns = [
    path('', views.news_list, name='news_list'),
    path('create/', views.news_create, name='news_create'),
    path('<int:pk>/edit/', views.news_edit, name='news_edit'),
    path('<int:pk>/delete/', views.news_delete, name='news_delete'),
    path('<int:pk>/', views.news_xem, name='news_xem'),  # Đường dẫn đến trang news_xem
]