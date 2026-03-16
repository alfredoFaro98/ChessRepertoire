from django.urls import path
from . import views

urlpatterns = [
    path('', views.opening_list, name='home'),
    path('ripasso/', views.home, name='ripasso'),
    path('openings/', views.opening_list, name='opening_list'),
    path('opening/<int:opening_id>/', views.opening_detail, name='opening_detail'),
    path('opening/<int:root_id>/line/<int:line_num>/', views.line_detail, name='line_detail'),
    path('analisi-domande/', views.analisi_domande, name='analisi_domande'),
    path("opening/<int:pk>/download/", views.download_opening_lines, name="download_opening_lines"),
    path("opening/<int:root_id>/line/<int:numero>/train/", views.line_training, name="line_training"),
    path("linea/<int:line_id>/completata/", views.incrementa_completamenti, name="incrementa_completamenti"),
    path("import-pgn/", views.import_pgn, name="import_pgn"),
]
