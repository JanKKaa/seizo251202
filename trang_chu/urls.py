"""
URL configuration for trang_chu project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.1/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include
from django.contrib.auth import views as auth_views
from django.conf import settings
from django.conf.urls.static import static
from . import views
from django.conf.urls import handler403

urlpatterns = [
    path('admin/', admin.site.urls),
    path('login/', auth_views.LoginView.as_view(template_name='trang_chu/login.html'), name='login'),
    path('logout/', auth_views.LogoutView.as_view(next_page='login'), name='logout'),
    path('profile/', views.profile, name='profile'),
    path('delete_user/', views.delete_user, name='delete_user'),
    path('register/', views.register, name='register'),
    path('register_success/', views.register_success, name='register_success'),
    path('phe_duyet/', include('phe_duyet.urls')),
    path('news/', include('news.urls')),
    path('', views.index, name='index'),
    path('mente/', include('mente.urls')),
    path('baotri/', include('baotri.urls')),  # Thêm đường dẫn cho ứng dụng baotri
    path('quet_anh/', include('quet_anh.urls')),
    path('iot/', include(('iot.urls', 'iot'), namespace='iot')),  # cần dạng này
    path('nhap_lieu/', include('nhap_lieu.urls')),  # underscore route
    path('nhap-lieu/', include(('nhap_lieu.urls', 'nhap_lieu_alias'), namespace='nhap_lieu_alias')),  # alias route cho Flask callback
    path('menu/', include('menu.urls')),  # Đúng với cấu trúc của bạn
    path('learn/', include('learn.urls', namespace='learn')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

handler404 = 'trang_chu.views.custom_404'
handler500 = 'trang_chu.views.custom_500'
handler403 = 'menu.views.custom_permission_denied_view'
