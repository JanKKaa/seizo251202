from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .forms import UserRegisterForm, UserUpdateForm, ProfileUpdateForm
from django.contrib.auth.models import User
from django.contrib.auth import login, logout
from .models import UserProfile
from django.db import IntegrityError
from news.models import NewsArticle
from django.core.paginator import Paginator  # Thêm dòng này để import Paginator

def index(request):
    articles_list = NewsArticle.objects.all().order_by('-created_at')
    paginator = Paginator(articles_list, 6)  # Hiển thị tối đa 6 bài viết mỗi trang

    page_number = request.GET.get('page')
    articles = paginator.get_page(page_number)

    return render(request, 'trang_chu/index.html', {'articles': articles})

@login_required
def profile(request):
    if request.method == 'POST':
        user_form = UserUpdateForm(request.POST, instance=request.user)
        profile_form = ProfileUpdateForm(request.POST, request.FILES, instance=request.user.userprofile)
        if user_form.is_valid() and profile_form.is_valid():
            user_form.save()
            profile_form.save()
            messages.success(request, 'プロフィールが更新されました!')
            return redirect('profile')
    else:
        user_form = UserUpdateForm(instance=request.user)
        profile_form = ProfileUpdateForm(instance=request.user.userprofile)
    return render(request, 'trang_chu/profile.html', {
        'user_form': user_form,
        'profile_form': profile_form
    })

def register(request):
    if request.method == 'POST':
        form = UserRegisterForm(request.POST)
        if form.is_valid():
            username = form.cleaned_data.get('username')
            if User.objects.filter(username=username).exists():
                form.add_error('username', 'ユーザー名は既に存在します。')
            else:
                try:
                    user = form.save()
                    position = form.cleaned_data.get('position')
                    # Kiểm tra xem hồ sơ người dùng đã tồn tại hay chưa
                    if not UserProfile.objects.filter(user=user).exists():
                        UserProfile.objects.create(user=user, position=position)
                    login(request, user)
                    messages.success(request, f'アカウントが作成されました! 今すぐログインできます。')
                    return redirect('register_success')
                except IntegrityError:
                    form.add_error(None, 'アカウント作成中にエラーが発生しました。もう一度お試しください。')
    else:
        form = UserRegisterForm()
    return render(request, 'trang_chu/register.html', {'form': form})

def register_success(request):
    return render(request, 'trang_chu/register_success.html')

@login_required
def delete_user(request):
    user = request.user
    if request.method == 'POST':
        user.delete()
        messages.success(request, 'アカウントが削除されました。')
        return redirect('index')
    return render(request, 'trang_chu/delete_user.html')

def custom_404(request, exception):
    return render(request, '404.html', status=404)

def custom_500(request):
    return render(request, '500.html', status=500)

def custom_logout(request):
    logout(request)
    return redirect('learn:index')