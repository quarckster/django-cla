from django.contrib import admin

from .models import CCLA
from .models import ICLA


admin.site.site_header = "OpenSSL CLA Admin"
admin.site.site_title = "OpenSSL CLA Admin Portal"
admin.site.index_title = "Welcome to OpenSSL CLA Portal"


admin.site.register(CCLA)

@admin.register(ICLA)
class ICLAModelAdmin(admin.ModelAdmin):
    list_display = ("email", "full_name", "signed_at", "is_volunteer")

