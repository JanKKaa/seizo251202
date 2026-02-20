from django.db import models
from django.contrib.auth.models import User

class NewsArticle(models.Model):
    title = models.CharField(max_length=200)
    content = models.TextField()
    author = models.ForeignKey(User, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    main_image = models.ImageField(upload_to='news_images/', blank=True, null=True)
    subtitle1 = models.CharField(max_length=200, blank=True)
    subcontent1 = models.TextField(blank=True)
    subtitle2 = models.CharField(max_length=200, blank=True)
    subcontent2 = models.TextField(blank=True)
    subtitle3 = models.CharField(max_length=200, blank=True)
    subcontent3 = models.TextField(blank=True)

    def __str__(self):
        return self.title

class NewsImage(models.Model):
    article = models.ForeignKey(NewsArticle, related_name='images', on_delete=models.CASCADE)
    image = models.ImageField(upload_to='news_images/')
    caption = models.CharField(max_length=200, blank=True)
    order = models.PositiveIntegerField(default=0)

    def __str__(self):
        return self.caption if self.caption else "Image for {}".format(self.article.title)
