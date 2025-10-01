from django.contrib import admin

from .models import CCLA
from .models import CCLAAttachment
from .models import ICLA


@admin.register(ICLA)
class ICLAModelAdmin(admin.ModelAdmin):
    list_display = ("email", "full_name", "signed_date", "is_volunteer", "is_active")
    ordering = ["-signed_at"]
    search_fields = ["email", "full_name"]
    readonly_fields = ("is_volunteer",)
    exclude = ("_is_volunteer",)


class CCLAFileInline(admin.TabularInline):
    model = CCLAAttachment
    fields = ("file",)
    extra = 1
    min_num = 0
    can_delete = True


class ICLAInline(admin.TabularInline):
    model = ICLA
    extra = 0
    fields = ("full_name", "email", "in_schedule_a")
    ordering = ["-signed_at"]
    readonly_fields = ("full_name", "email")
    show_change_link = True
    can_delete = False


@admin.register(CCLA)
class CCLAAdmin(admin.ModelAdmin):
    inlines = [ICLAInline, CCLAFileInline]
    list_display = ("corporation_name", "signed_date")
    ordering = ["corporation_name"]
    search_fields = ["corporation_name"]
