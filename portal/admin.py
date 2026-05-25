from django.contrib import admin
from .models import *

# Register your models here.
# admin.site.register(Student)
# admin.site.register(Subject)
# admin.site.register(Result)
# admin.site.register(TermSummary)

class OwnedModelAdmin(admin.ModelAdmin):
    """Reusable mixin — restricts list/edit to records the user created."""

    exclude = ['created_by']

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs  # superuser sees everything
        return qs.filter(created_by=request.user)

    def save_model(self, request, obj, form, change):
        if not change:  # only set on creation, not on edit
            obj.created_by = request.user
        super().save_model(request, obj, form, change)

    def has_change_permission(self, request, obj=None):
        if obj is None:
            return True
        if request.user.is_superuser:
            return True
        return obj.created_by == request.user

    def has_delete_permission(self, request, obj=None):
        if obj is None:
            return True
        if request.user.is_superuser:
            return True
        return obj.created_by == request.user


@admin.register(Result)
class ResultAdmin(OwnedModelAdmin):
    list_display = ('student', 'subject', 'term', 'session', 'ca1', 'ca2', 'exam_score')
    list_filter  = ('term', 'session')
    search_fields = ('student__full_name', 'student__student_id')


@admin.register(TermSummary)
class TermSummaryAdmin(OwnedModelAdmin):
    list_display = ('student', 'term', 'session', 'class_position')
    list_filter  = ('term', 'session')
    search_fields = ('student__full_name',)


@admin.register(Student)
class StudentAdmin(OwnedModelAdmin):
    list_display  = ('student_id', 'full_name', 'class_name')
    search_fields = ('student_id', 'full_name')


@admin.register(Subject)
class SubjectAdmin(OwnedModelAdmin):
    list_display = ('name', 'icon')