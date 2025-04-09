from django.contrib import admin
from .models import *

# Register your models here.
admin.site.register(Courses)
admin.site.register(Documents)
admin.site.register(Libraries)
admin.site.register(Admins)
admin.site.register(Members)

