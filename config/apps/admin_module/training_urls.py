from django.urls import path
from apps.admin_module import training_view as views

app_name = 'admin_training'                                           

urlpatterns = [
    path('sales-dashboard/', views.sales_dashboard, name='sales_dashboard'),

    path('project/', views.project, name='project'),
    path('registration/', views.registration, name='registration'),
    path('payment/', views.payment, name='payment'),

    path('update-project/', views.update_project, name='update_project'),
    path('delete-project/', views.delete_project, name='delete_project'),

    
    path('payment-update/', views.update_payment, name='update_payment'),
    path('payment-delete/', views.delete_payment, name='delete_payment'),


    path('sales/accept-payment/', views.sales_accept_payment, name='sales_accept_payment'),
    path('sales/decline-payment/', views.sales_decline_payment, name='sales_decline_payment'),

    path('sales/edit/', views.sales_edit_payment, name='sales_edit_payment'),


    path('sales/projects/', views.sales_project, name='sales_project'),
    path('sales/registrations/', views.sales_registration, name='sales_registration'),
    path('sales/payments/', views.sales_payment, name='sales_payment'),

    path('payment-history/', views.payment_history_view, name='payment_history'),



    
]


