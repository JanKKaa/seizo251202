from django.urls import path
from . import views

urlpatterns = [
    path('', views.index_qa, name='index_qa'),
    path('upload/', views.upload_image, name='upload_image'),
    path('history/', views.qa_history, name='qa_history'),
    path('history/delete/<int:pk>/', views.delete_qa_history, name='delete_qa_history'),

    path('device/', views.qa_device_list, name='qa_device_list'),
    path('device/add/', views.add_qa_device, name='add_qa_device'),
    path('device/edit/<int:pk>/', views.edit_qa_device, name='edit_qa_device'),
    path('device/delete/<int:pk>/', views.delete_qa_device, name='delete_qa_device'),

    path('dashboard/', views.dashboard_qa, name='dashboard_qa'),
    path("api/latest-events/", views.latest_vision_events, name="vision_latest_events"),
]