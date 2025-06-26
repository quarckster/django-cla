from django.contrib import admin

from .models import CCLA
from .models import ICLA


admin.site.register(ICLA)
admin.site.register(CCLA)
