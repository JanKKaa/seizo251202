# filepath: c:\seizo_web\seizo0\trang_chu\news\views.py
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .models import NewsArticle, NewsImage
from .forms import NewsArticleForm, NewsImageForm

def news_list(request):
    articles = NewsArticle.objects.all()
    return render(request, 'news/news_list.html', {'articles': articles})

@login_required
def news_create(request):
    if request.method == 'POST':
        form = NewsArticleForm(request.POST, request.FILES)
        if form.is_valid():
            article = form.save(commit=False)
            article.author = request.user
            article.save()
            # 小見出しの画像を保存
            for i in range(1, 5):  # 最大4枚の画像を選択
                image_field = f'image{i}'
                if image_field in request.FILES:
                    NewsImage.objects.create(article=article, image=request.FILES[image_field], order=i)
            messages.success(request, '投稿が正常に保存されました！')
            return redirect('news_list')
    else:
        form = NewsArticleForm()
    return render(request, 'news/news_form.html', {'form': form})

@login_required
def news_edit(request, pk):
    article = get_object_or_404(NewsArticle, pk=pk)
    if request.method == 'POST':
        form = NewsArticleForm(request.POST, request.FILES, instance=article)
        if form.is_valid():
            article = form.save(commit=False)
            article.save()
            # 小見出しの画像を保存
            for i in range(1, 5):  # 最大4枚の画像を選択
                image_field = f'image{i}'
                if image_field in request.FILES:
                    NewsImage.objects.create(article=article, image=request.FILES[image_field], order=i)
            messages.success(request, '投稿が正常に更新されました！')
            return redirect('news_list')
    else:
        form = NewsArticleForm(instance=article)
    return render(request, 'news/news_form.html', {'form': form, 'article': article})

@login_required
def news_delete(request, pk):
    article = get_object_or_404(NewsArticle, pk=pk)
    if request.method == 'POST':
        article.delete()
        messages.success(request, '投稿が正常に削除されました！')
        return redirect('news_list')
    return render(request, 'news/news_confirm_delete.html', {'article': article})

def news_xem(request, pk):
    article = get_object_or_404(NewsArticle, pk=pk)
    images = article.images.all()
    image1 = images.filter(order=1).first()
    image2 = images.filter(order=2).first()
    image3 = images.filter(order=3).first()
    image4 = images.filter(order=4).first()
    return render(request, 'news/news_xem.html', {
        'article': article,
        'image1': image1,
        'image2': image2,
        'image3': image3,
        'image4': image4,
    })