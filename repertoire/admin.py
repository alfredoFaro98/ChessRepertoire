from django import forms
from django.contrib import admin
from django.utils.html import format_html

from .models import (
    FinaleCapitolo,
    FinaleLine,
    FinaleLineMistake,
    FinalePosizione,
    OpeningLine,
    OpeningLineMistake,
    OpeningRoot,
    Puzzle,
    PuzzleAttempt,
)
from .utils import trova_parent


class LeafFilter(admin.SimpleListFilter):
    title = "Tipo di linea"
    parameter_name = "leaf"

    def lookups(self, request, model_admin):
        return [
            ("leaf", "Solo linee foglia"),
            ("nonleaf", "Solo linee con varianti"),
        ]

    def queryset(self, request, queryset):
        if self.value() == "leaf":
            return queryset.filter(varianti__isnull=True)
        if self.value() == "nonleaf":
            return queryset.filter(varianti__isnull=False)
        return queryset


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
                pgn=cleaned["pgn"],
            )
            cleaned["parent"] = trova_parent(dummy)
        return cleaned


@admin.register(OpeningRoot)
class OpeningRootAdmin(admin.ModelAdmin):
    list_display = ("nome", "moves", "difesa", "descrizione")
    list_filter = ("difesa",)
    search_fields = ("nome",)


@admin.register(OpeningLine)
class OpeningLineAdmin(admin.ModelAdmin):
    form = OpeningLineForm
    list_display = (
        "root",
        "numero",
        "titolo",
        "parent",
        "difficolta",
        "completamenti",
        "mistakes",
        "accuracy",
        "due_at",
        "pgn_display",
    )
    list_filter = ("root", "difficolta", LeafFilter)
    search_fields = ("pgn", "titolo")

    def pgn_display(self, obj):
        if not obj.pgn:
            return ""
        text = obj.pgn.replace("\n", " ").strip()
        short = text if len(text) <= 120 else text[:120] + "..."
        return format_html("<span title='{}'>{}</span>", text, short)

    pgn_display.short_description = "Mosse (PGN)"

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "parent":
            if request.resolver_match.kwargs.get("object_id"):
                try:
                    current_line = OpeningLine.objects.get(pk=request.resolver_match.kwargs["object_id"])
                    kwargs["queryset"] = OpeningLine.objects.filter(root=current_line.root).exclude(pk=current_line.pk)
                except OpeningLine.DoesNotExist:
                    kwargs["queryset"] = OpeningLine.objects.none()
            else:
                kwargs["queryset"] = OpeningLine.objects.none()

            formfield = super().formfield_for_foreignkey(db_field, request, **kwargs)

            def full_label(obj):
                indent = "- " * obj.depth() if hasattr(obj, "depth") else ""
                moves = obj.pgn.strip() if obj.pgn else "(vuoto)"
                if len(moves) > 200:
                    moves = moves[:200] + "..."
                return f"{indent}{moves}"

            formfield.label_from_instance = full_label
            return formfield

        return super().formfield_for_foreignkey(db_field, request, **kwargs)


class FinalePosizioneInline(admin.TabularInline):
    model = FinalePosizione
    extra = 1
    fields = ("titolo", "fen", "difficolta", "ordine", "note")


@admin.register(FinaleCapitolo)
class FinaleCapitoloAdmin(admin.ModelAdmin):
    list_display = ("nome", "ordine", "num_posizioni")
    fields = ("nome", "descrizione", "ordine", "fen_preview")
    inlines = [FinalePosizioneInline]

    def num_posizioni(self, obj):
        return obj.posizioni.count()

    num_posizioni.short_description = "Posizioni"


@admin.register(FinalePosizione)
class FinalePosizioneAdmin(admin.ModelAdmin):
    list_display = ("capitolo", "titolo", "difficolta", "completamenti")
    list_filter = ("capitolo", "difficolta")
    search_fields = ("titolo", "note")


@admin.register(FinaleLine)
class FinaleLineAdmin(admin.ModelAdmin):
    list_display = (
        "capitolo",
        "numero",
        "titolo",
        "difficolta",
        "completamenti",
        "mistakes",
        "accuracy",
        "due_at",
        "pgn_display",
    )
    list_filter = ("capitolo", "difficolta")
    search_fields = ("titolo", "pgn", "fen_start")

    def pgn_display(self, obj):
        if not obj.pgn:
            return ""
        text = obj.pgn.replace("\n", " ").strip()
        short = text if len(text) <= 80 else text[:80] + "..."
        return format_html("<span title='{}'>{}</span>", text, short)

    pgn_display.short_description = "Mosse (PGN)"


@admin.register(OpeningLineMistake)
class OpeningLineMistakeAdmin(admin.ModelAdmin):
    list_display = ("line", "wrong_move", "expected_move", "occurrence_count", "last_seen")
    list_filter = ("side_to_train", "line__root")
    search_fields = ("line__root__nome", "wrong_move", "expected_move", "fen")


@admin.register(FinaleLineMistake)
class FinaleLineMistakeAdmin(admin.ModelAdmin):
    list_display = ("line", "wrong_move", "expected_move", "occurrence_count", "last_seen")
    list_filter = ("side_to_train", "line__capitolo")
    search_fields = ("line__capitolo__nome", "wrong_move", "expected_move", "fen")


@admin.register(Puzzle)
class PuzzleAdmin(admin.ModelAdmin):
    list_display = ("lichess_id", "rating", "themes", "attempt_count", "fail_count", "due_at")
    search_fields = ("lichess_id", "themes")
    list_filter = ("source",)


@admin.register(PuzzleAttempt)
class PuzzleAttemptAdmin(admin.ModelAdmin):
    list_display = ("puzzle", "created_at", "success", "wrong_move", "expected_move", "guess_theme", "guess_correct")
    list_filter = ("success", "guess_correct")
