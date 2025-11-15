from django.contrib import admin
from django.urls import path
from apps.project import views

app_name = 'project'

urlpatterns = [
    path('', views.home, name='home'),
    path('users/', views.users, name='users'),

    path('terms/', views.terms_view, name='terms'),
    path('terms_exist/', views.terms_exist, name='terms_exist'),
    path('registration_form/', views.registration_form_view, name='registration_form'),
    
    path('charge/', views.charge_view, name='charge_view'),
    path('success/<str:payment_id>/', views.success_view, name='success'),
    path('payment_update/', views.payment_update, name='payment_update'),

    path('existing-user/', views.existing_user_view, name='existing_user'),  

    
    path('send_otp/', views.send_otp, name='send_otp'),
    path('verify_otp/', views.verify_otp, name='verify_otp'),
    path('dashboard/', views.dashboard_view, name='dashboard'),

    path('payment_option/<int:registration_id>/', views.choose_payment_option, name='choose_payment_option'),
    path('cash/<int:registration_id>/<int:payment_id>/', views.cash_payment_view, name='cash_payment'),

    path('processing/', views.processing_view, name='processing_view'),
    path('payment-failure/', views.failure_view, name='payment_failure'),

    path('payment/failed/', views.payment_failed_view, name='payment_failed'),



    

    

    

]
