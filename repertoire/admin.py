from django import forms
from django.contrib import admin
from django.utils.html import format_html
from .models import OpeningRoot, OpeningLine
from .utils import trova_parent


# === FILTRO PERSONALIZZATO PER FOGLIE ===
class LeafFilter(admin.SimpleListFilter):
    title = 'Tipo di linea'
    parameter_name = 'leaf'

    def lookups(self, request, model_admin):
        return [
            ('leaf', 'Solo linee foglia'),
            ('nonleaf', 'Solo linee con varianti'),
        ]

    def queryset(self, request, queryset):
        if self.value() == 'leaf':
            return queryset.filter(varianti__isnull=True)
        elif self.value() == 'nonleaf':
            return queryset.filter(varianti__isnull=False)
        return queryset


# === FORM PERSONALIZZATO PER AUTO-PARENT ===
class OpeningLineForm(forms.ModelForm):
    class Meta:
        model = OpeningLine
        fields = "__all__"

    def clean(self):
        cleaned = super().clean()
        if not cleaned.get("parent") and cleaned.get("pgn") and cleaned.get("root"):
            dummy = OpeningLine(
                id=self.instance.id,
                root=cleaned["root"],
                pgn=cleaned["pgn"]
            )
            cleaned["parent"] = trova_parent(dummy)
        return cleaned


# === ADMIN PER OPENINGROOT ===
@admin.register(OpeningRoot)
class OpeningRootAdmin(admin.ModelAdmin):
    list_display = ("nome", "moves", "difesa", "descrizione")
    list_filter = ("difesa",)
    search_fields = ("nome",)

    


# === ADMIN PER OPENINGLINE ===
@admin.register(OpeningLine)
class OpeningLineAdmin(admin.ModelAdmin):
    form = OpeningLineForm
    list_display = ("root", "numero", "titolo", "parent", "is_leaf", "pgn_display")
    list_filter = ("root", LeafFilter)
    search_fields = ("pgn", "titolo")

    def pgn_display(self, obj):
        """Mostra la PGN intera nella tabella (troncata graficamente ma visibile tutta con tooltip)."""
        if not obj.pgn:
            return ""
        text = obj.pgn.replace("\n", " ").strip()
        short = text if len(text) <= 120 else text[:120] + "…"
        return format_html("<span title='{}'>{}</span>", text, short)
    pgn_display.short_description = "Mosse (PGN)"

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "parent":
            # ✅ Limitiamo i parent alla stessa root (se stai modificando una linea esistente)
            if request.resolver_match.kwargs.get("object_id"):
                try:
                    current_line = OpeningLine.objects.get(pk=request.resolver_match.kwargs["object_id"])
                    kwargs["queryset"] = OpeningLine.objects.filter(root=current_line.root).exclude(pk=current_line.pk)
                except OpeningLine.DoesNotExist:
                    kwargs["queryset"] = OpeningLine.objects.none()
            else:
                # In caso di creazione nuova, mostriamo tutto (o nessuno finché non è scelta la root)
                kwargs["queryset"] = OpeningLine.objects.none()

            formfield = super().formfield_for_foreignkey(db_field, request, **kwargs)

            # ✅ Etichetta con indentazione e mosse complete
            def full_label(obj):
                indent = "— " * obj.depth() if hasattr(obj, "depth") else ""
                moves = obj.pgn.strip() if obj.pgn else "(vuoto)"
                if len(moves) > 200:
                    moves = moves[:200] + "..."
                return f"{indent}{moves}"

            formfield.label_from_instance = full_label
            return formfield

        return super().formfield_for_foreignkey(db_field, request, **kwargs)


