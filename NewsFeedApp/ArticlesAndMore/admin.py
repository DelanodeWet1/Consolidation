"""Django admin registrations for ArticlesAndMore.

These are for maintenance/debugging only (e.g. fixing bad data). Regular
functionality — creating a Publisher, assigning editors/journalists to
one — is handled entirely in the app itself (see views.publisher_create,
publisher_assign_self, and publisher_assign_journalist), not here.
"""
from django.contrib import admin

from .models import Article, Newsletter, Publisher, User

admin.site.register(Publisher)
admin.site.register(Article)
admin.site.register(Newsletter)
admin.site.register(User)