from django.urls import path

from . import views

app_name = "nhap_lieu"

urlpatterns = [
    path("", views.index, name="index"),
    path("mau-nhap-lieu/", views.mau_nhaplieu, name="mau_nhaplieu"),
    path("mau-list/", views.mau_list, name="mau_list"),
    path("mau-xoa/<str:ten_chuong_trinh>/", views.mau_xoa, name="mau_xoa"),
    path("quanly-may/", views.quanly_may, name="quanly_may"),
    path("api/cap-nhat-ket-qua/", views.api_cap_nhat_ket_qua, name="api_cap_nhat_ket_qua"),
    path("api/latest-result/", views.api_get_latest_result, name="api_get_latest_result"),
    path("api/latest-by-ip/", views.api_get_latest_by_ip, name="api_get_latest_by_ip"),
    path("api/sse-latest-result/", views.sse_latest_result, name="sse_latest_result"),
]
