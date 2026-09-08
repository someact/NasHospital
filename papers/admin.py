from django.contrib import admin
from .models import Paper, PaperRound, ReviewAssignment, ReviewFeedback, CoordinatorLetter, AccessRequest

@admin.register(Paper)
class PaperAdmin(admin.ModelAdmin):
    list_display = ('title', 'author', 'department', 'category', 'current_status', 'created_at', 'published_at')
    list_filter = ('current_status', 'department', 'category')
    search_fields = ('title', 'abstract', 'author__username', 'author__first_name', 'author__last_name')

admin.site.register(PaperRound)
admin.site.register(ReviewAssignment)
admin.site.register(ReviewFeedback)
admin.site.register(CoordinatorLetter)
admin.site.register(AccessRequest)
