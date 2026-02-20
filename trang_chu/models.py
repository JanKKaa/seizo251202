from django.db import models
from django.contrib.auth.models import User

class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    avatar = models.ImageField(upload_to='avatars/', null=True, blank=True)
    position = models.CharField(max_length=50, choices=[
        ('社員', '社員'),
        ('リーダー', 'リーダー'),
        ('係長', '係長'),
        ('課長', '課長'),
        ('部長', '部長'),
    ], default='社員')

    def __str__(self):
        return self.user.username
