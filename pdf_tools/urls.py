from django.urls import path
from . import views

app_name = 'pdf_tools'

urlpatterns = [
    path('', views.home, name='home'),
    path('merge/', views.merge_pdfs, name='merge_pdfs'),
    path('split/', views.split_pdf, name='split_pdf'),
    path('compress/', views.compress_pdf, name='compress_pdf'),
    path('images-to-pdf/', views.images_to_pdf, name='images_to_pdf'),
    path('rotate/', views.rotate_pdf, name='rotate_pdf'),
    path('download/<str:filename>/', views.download_file, name='download_file'),
    path('pdf-to-word/', views.pdf_to_word, name='pdf_to_word'),
    path('pdf-to-excel/', views.pdf_to_excel, name='pdf_to_excel'),
    path("remove-pdf-password/", views.remove_pdf_password, name="remove_pdf_password"),
    path("download/<str:filename>/", views.download_file, name="download_file"),
    path("pdf-to-ppt/", views.pdf_to_ppt, name="pdf_to_ppt"),
]