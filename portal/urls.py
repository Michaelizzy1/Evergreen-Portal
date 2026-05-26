from django.urls import path
from . import views

urlpatterns = [
    path('',                         views.login_view,       name='login'),
    path('logout/',                  views.logout_view,      name='logout'),
    path('result/print/',            views.print_result,     name='print_result'),
    path('dashboard/',               views.dashboard_view,   name='dashboard'),
    path('results/<str:term>/',      views.term_result_view, name='term_result'),
    path('results/<str:term>/pdf/',  views.download_pdf_view,name='download_pdf'),
    path('health/', views.health_check),
]