from django.urls import path
from . import views

urlpatterns = [
    path('', views.opening_list, name='opening_list'),
    path('opening/<int:opening_id>/', views.opening_detail, name='opening_detail'),
    path('opening/<int:root_id>/line/<int:line_num>/', views.line_detail, name='line_detail'),
]
