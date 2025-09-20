from django.contrib import admin

from .models import Email
from .models import Group
from .models import Identity
from .models import Membership
from .models import Person
from cla.models import ICLA


class EmailInline(admin.TabularInline):
    model = Email
    extra = 0


class IdentityInline(admin.TabularInline):
    model = Identity
    extra = 0


class PersonMembershipInline(admin.TabularInline):
    model = Membership
    fk_name = "person"
    extra = 0
    fields = ("group", "since", "until")
    autocomplete_fields = ("group",)


class GroupMembershipInline(admin.TabularInline):
    model = Membership
    fk_name = "group"
    extra = 0
    fields = ("person", "since", "until")
    autocomplete_fields = ("person",)


class ICLAInline(admin.TabularInline):
    model = ICLA
    extra = 0
    fields = ("full_name", "email", "signed_at", "cla_pdf")
    readonly_fields = ("full_name", "email", "signed_at", "cla_pdf")
    show_change_link = True
    can_delete = False


@admin.register(Person)
class PersonModelAdmin(admin.ModelAdmin):
    list_display = ("name", "github", "ghe", "joined_at")
    inlines = [EmailInline, IdentityInline, PersonMembershipInline, ICLAInline]
    search_fields = ["name", "github", "ghe", "nick", "emails__email", "identities__identity"]
    ordering = ["name"]


@admin.register(Group)
class GroupAdmin(admin.ModelAdmin):
    inlines = [GroupMembershipInline]
    ordering = ["name"]
    search_fields = ["name"]
