from django.contrib import admin
from .models import OpeningRoot, OpeningLine

# alfredino98

@admin.register(OpeningRoot)
class OpeningRootAdmin(admin.ModelAdmin):
    list_display = ('nome', 'moves')
    search_fields = ('nome', 'moves')


@admin.register(OpeningLine)
class OpeningLineAdmin(admin.ModelAdmin):
    list_display = ('root', 'numero', 'titolo')
    list_filter = ('root',)
    search_fields = ('titolo', 'pgn')
