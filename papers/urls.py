from django.urls import path
from . import views

urlpatterns = [
    # Doctor Workspace
    path('doctor/dashboard/', views.doctor_dashboard, name='doctor_dashboard'),
    path('papers/submit/', views.paper_submit, name='paper_submit'),
    path('papers/<uuid:paper_id>/', views.paper_detail, name='paper_detail'),
    path('papers/<uuid:paper_id>/revision/', views.paper_revision, name='paper_revision'),
    path('papers/<uuid:paper_id>/review/', views.review_workspace, name='review_workspace'),
    path('papers/<uuid:paper_id>/viewer/', views.paper_pdf_viewer, name='paper_pdf_viewer'),
    path('papers/<uuid:paper_id>/round/<int:round_number>/pdf/', views.serve_protected_paper, name='serve_protected_paper'),
    path('reviews/<int:feedback_id>/annotated-pdf/', views.serve_annotated_pdf, name='serve_annotated_pdf'),
    path('papers/<uuid:paper_id>/request-access/', views.request_access, name='request_access'),

    # Coordinator Triage & Consolidation
    path('coordinator/triage/', views.coordinator_triage, name='coordinator_triage'),
    path('coordinator/papers/<uuid:paper_id>/assign/', views.coordinator_assign_reviewers, name='coordinator_assign_reviewers'),
    path('coordinator/papers/<uuid:paper_id>/consolidate/', views.coordinator_consolidation, name='coordinator_consolidation'),
    path('coordinator/papers/<uuid:paper_id>/publish/', views.coordinator_publish_paper, name='coordinator_publish_paper'),
    path('coordinator/papers/<uuid:paper_id>/retract/', views.coordinator_retract_paper, name='coordinator_retract_paper'),
    path('coordinator/access-requests/', views.coordinator_access_queue, name='coordinator_access_queue'),

    # Notifications Engine
    path('notifications/', views.notification_list, name='notification_list'),
    path('notifications/mark-read/<int:notification_id>/', views.mark_notification_read, name='mark_notification_read'),
    path('notifications/mark-all-read/', views.mark_all_notifications_read, name='mark_all_notifications_read'),

    # Executive Overview Dashboard
    path('executive/dashboard/', views.executive_dashboard, name='executive_dashboard'),

    # Public / Staff Catalog
    path('catalog/', views.catalog_view, name='catalog_view'),
]

