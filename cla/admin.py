from django.conf import settings
from django.contrib import admin

from .models import CCLA
from .models import ICLA


admin.site.site_header = settings.ADMIN_SITE_HEADER
admin.site.site_title = settings.ADMIN_SITE_TITLE
admin.site.index_title = settings.ADMIN_SITE_INDEX_TITLE

admin.site.register(CCLA)


@admin.register(ICLA)
class ICLAModelAdmin(admin.ModelAdmin):
    list_display = ("email", "full_name", "signed_at", "is_volunteer", "is_active")
