from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone

class Comment(models.Model):
    document = models.ForeignKey('Document', on_delete=models.CASCADE, related_name='comments')
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    text = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f'Comment by {self.user.username} on {self.document.title}'

class Document(models.Model):
    title = models.CharField(max_length=255)
    file = models.FileField(upload_to='documents/')
    created_by = models.ForeignKey(User, related_name='created_documents', on_delete=models.CASCADE)
    recipient = models.ForeignKey(User, related_name='received_documents', on_delete=models.CASCADE, default=1)
    approved_by = models.ForeignKey(User, related_name='approved_documents', null=True, blank=True, on_delete=models.SET_NULL)
    approved_at = models.DateTimeField(null=True, blank=True)
    approved_file = models.FileField(upload_to='approved_files/', null=True, blank=True)
    submission_date = models.DateTimeField(auto_now_add=True)

    @property
    def is_approved(self):
        return self.approvals.filter(approved=True).exists()

    @property
    def is_rejected(self):
        return self.approvals.filter(rejected=True).exists()

    def __str__(self):
        return self.title

    def get_submission_date(self):
        local_time = timezone.localtime(self.submission_date)
        return local_time.strftime('%Y-%m-%d')

class Approval(models.Model):
    document = models.ForeignKey(Document, related_name='approvals', on_delete=models.CASCADE)
    approver = models.ForeignKey(User, related_name='approvals', on_delete=models.CASCADE)
    approved = models.BooleanField(default=False)
    approved_at = models.DateTimeField(null=True, blank=True)
    rejected = models.BooleanField(default=False)
    rejected_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = ('document', 'approver')

class Message(models.Model):
    sender = models.ForeignKey(User, related_name='phe_duyet_sent_messages', on_delete=models.CASCADE)
    recipient = models.ForeignKey(User, related_name='phe_duyet_received_messages', on_delete=models.CASCADE)
    subject = models.CharField(max_length=255)
    body = models.TextField()
    timestamp = models.DateTimeField(auto_now_add=True)
    read = models.BooleanField(default=False)

    def __str__(self):
        return f'Message from {self.sender} to {self.recipient} - {self.subject}'
