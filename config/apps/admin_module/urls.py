from django.urls import path, include

urlpatterns = [

    path('', include(('apps.admin_module.project_urls', 'admin_project'), namespace='admin_project')),
    path('training/', include(('apps.admin_module.training_urls', 'admin_training'), namespace='admin_training')),
    path('internship/', include(('apps.admin_module.internship_urls', 'admin_internship'), namespace='admin_internship')),
]
