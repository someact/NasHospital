from django.contrib import admin
from django.urls import path, include
from django.shortcuts import redirect
from accounts.views import redirect_user_by_role

def root_redirect(request):
    if request.user.is_authenticated:
        return redirect_user_by_role(request.user)
    return redirect('catalog_view')

urlpatterns = [
    path('admin/', admin.site.urls),
    path('accounts/', include('accounts.urls')),
    path('', root_redirect, name='root'),
    path('', include('papers.urls')),
]
