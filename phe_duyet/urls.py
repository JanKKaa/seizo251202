from django.urls import path
from . import views

app_name = 'phe_duyet'

urlpatterns = [
    path('', views.index, name='index'),
    path('approve_document/<int:document_id>/', views.approve_document, name='approve_document'),
    path('rejection_notice/<int:document_id>/', views.rejection_notice, name='rejection_notice'),
    path('upload_approved_file/<int:document_id>/', views.upload_approved_file, name='upload_approved_file'),
    path('create_document/', views.create_document, name='create_document'),
    path('download_document/<int:document_id>/', views.download_document, name='download_document'),
    path('send_message/', views.send_message, name='send_message'),
    path('inbox/', views.inbox, name='inbox'),
    path('manage_messages/', views.manage_messages, name='manage_messages'),
    path('delete_message/<int:message_id>/', views.delete_message, name='delete_message'),
    path('delete_document/<int:document_id>/', views.delete_document, name='delete_document'),
    path('send-reminder-email/<int:document_id>/', views.send_reminder_email, name='send_reminder_email'),
    path('export/csv/', views.export_csv, name='export_csv'),
    path('export/pdf/', views.export_pdf, name='export_pdf'),
    path('update-file/<int:document_id>/', views.update_document_file, name='update_document_file'),
]