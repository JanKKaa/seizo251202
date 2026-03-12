from django.urls import path
from . import views
from django.conf import settings
from django.conf.urls.static import static

app_name = 'learn'

urlpatterns = [
    path('', views.index, name='index'),
    path('courses/', views.course_list, name='course_list'),
    path('enroll/<int:course_id>/', views.enroll_course, name='enroll_course'),
    path('my-courses/', views.my_courses, name='my_courses'),
    path('dangnhap/', views.dangnhap_ma_nv, name='dangnhap'),
    path('logout/', views.logout_nv, name='logout_nv'),
    path('logout_admin/', views.logout_admin, name='logout_admin'),
    path('thumb/', views.external_thumb_proxy, name='external_thumb_proxy'),
]

urlpatterns += [
    path('nhanvien/', views.nhanvien_list, name='nhanvien_list'),
    path('nhanvien/create/', views.nhanvien_create, name='nhanvien_create'),
    path('nhanvien/<int:pk>/edit/', views.nhanvien_update, name='nhanvien_update'),
    path('nhanvien/<int:pk>/delete/', views.nhanvien_delete, name='nhanvien_delete'),
]

urlpatterns += [
    # Quản lý khóa học (admin)
    path('courses/create/', views.course_create, name='course_create'),
    path('courses/<int:pk>/edit/', views.course_edit, name='course_edit'),
    path('courses/<int:pk>/delete/', views.course_delete, name='course_delete'),
    
    # Báo cáo
    path('training-report/', views.training_report, name='training_report'),
    # Đánh dấu hoàn thành
    path('mark-completed/<int:enrollment_id>/', views.mark_completed, name='mark_completed'),
    path('login_admin/', views.login_admin, name='login_admin'),
    # Phê duyệt
    path('approval-history/', views.approval_history_list, name='approval_history_list'),
    path('approval-history/<int:enrollment_id>/', views.approval_history, name='approval_history'),
    # Phê duyệt báo cáo
    path('approve_report_supervisor/<int:enrollment_id>/', views.approve_report_supervisor, name='approve_report_supervisor'),
    path('approve_report_kanri/<int:enrollment_id>/', views.approve_report_kanri, name='approve_report_kanri'),
    # Xóa báo cáo
    path('delete-report/<int:enrollment_id>/', views.delete_report_file, name='delete_report_file'),
]

urlpatterns += [
    path('bangcap/', views.bangcap_list, name='bangcap_list'),
    path('bangcap/upload/', views.bangcap_upload, name='bangcap_upload'),
    path('bangcap/<int:pk>/edit/', views.bangcap_edit, name='bangcap_edit'),
    path('bangcap/<int:pk>/delete/', views.bangcap_delete, name='bangcap_delete'),
    path('bangcap/<int:pk>/', views.bangcap_detail, name='bangcap_detail'),
    path('quotes/', views.quote_list, name='quote_list'),
    path('quotes/delete/<int:pk>/', views.quote_delete, name='quote_delete'),
]

urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
