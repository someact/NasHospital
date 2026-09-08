from django.urls import path
from . import views

urlpatterns = [
    path('login/', views.login_view, name='login'),
    path('login/2fa/', views.totp_login_challenge, name='totp_login_challenge'),
    path('logout/', views.logout_view, name='logout'),
    path('switch-role/<int:user_id>/', views.switch_role, name='switch_role'),
    path('security/2fa/', views.totp_setup_view, name='totp_setup'),

    # IT Admin Portal
    path('admin-portal/', views.admin_portal_dashboard, name='admin_portal_dashboard'),
    path('admin-portal/users/', views.admin_user_list, name='admin_user_list'),
    path('admin-portal/users/create/', views.admin_user_create, name='admin_user_create'),
    path('admin-portal/users/<int:user_id>/edit/', views.admin_user_edit, name='admin_user_edit'),
    path('admin-portal/users/<int:user_id>/reset-2fa/', views.admin_user_reset_2fa, name='admin_user_reset_2fa'),
    path('admin-portal/users/<int:user_id>/toggle-active/', views.admin_user_toggle_active, name='admin_user_toggle_active'),
    path('admin-portal/audit-logs/', views.admin_audit_logs, name='admin_audit_logs'),
]
