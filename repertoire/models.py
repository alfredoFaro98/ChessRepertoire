from django.db import models
from django.utils import timezone


DIFFICOLTA_CHOICES = [
    ("facile", "Facile"),
    ("media", "Media"),
    ("difficile", "Difficile"),
]

SIDE_CHOICES = [
    ("w", "Bianco"),
    ("b", "Nero"),
]


class ReviewFieldsMixin(models.Model):
    completamenti = models.PositiveIntegerField(default=0)
    last_reviewed = models.DateTimeField(blank=True, null=True)
    due_at = models.DateTimeField(blank=True, null=True)
    review_attempts = models.PositiveIntegerField(default=0)
    mistakes = models.PositiveIntegerField(default=0)
    accuracy = models.FloatField(default=0)

    class Meta:
        abstract = True


class MistakeBase(models.Model):
    fen = models.TextField()
    wrong_move = models.CharField(max_length=30)
    expected_move = models.CharField(max_length=30)
    move_index = models.PositiveIntegerField(default=0)
    side_to_train = models.CharField(max_length=1, choices=SIDE_CHOICES, default="w")
    occurrence_count = models.PositiveIntegerField(default=1)
    first_seen = models.DateTimeField(auto_now_add=True)
    last_seen = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True
        ordering = ["-occurrence_count", "-last_seen"]


class OpeningRoot(models.Model):
    nome = models.CharField(max_length=100, unique=True)
    moves = models.CharField(max_length=50, blank=True, null=True)
    descrizione = models.TextField(blank=True, null=True)
    difesa = models.BooleanField(default=False)
    preferito = models.BooleanField(default=False)

    class Meta:
        ordering = ["nome"]

    def __str__(self):
        return self.nome


class OpeningLine(ReviewFieldsMixin, models.Model):
    root = models.ForeignKey("OpeningRoot", on_delete=models.CASCADE, related_name="linee")
    numero = models.PositiveIntegerField(default=0, null=True, blank=True)
    titolo = models.CharField(max_length=200, blank=True, null=True)
    pgn = models.TextField()
    note = models.TextField(blank=True, null=True)
    flipped = models.BooleanField(default=False)
    difficolta = models.CharField(max_length=20, choices=DIFFICOLTA_CHOICES, default="media", blank=True)
    parent = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="varianti",
    )

    class Meta:
        ordering = ["numero"]

    def __str__(self):
        return f"{self.root.nome} - Linea {self.numero}"

    def count_moves(self):
        clean = self.pgn.replace("{", "").replace("}", "")
        return len([m for m in clean.split() if "." not in m and m not in ["1-0", "0-1", "1/2-1/2", "*"]])

    def mosse_chiave(self):
        return " ".join(self.pgn.split()[:6])

    def label_with_indent(self):
        indent = ""
        cur = self
        while cur.parent:
            indent += "- "
            cur = cur.parent
        return f"{indent}{self.mosse_chiave()}"

    def is_leaf(self):
        return not self.varianti.exists()

    def depth(self):
        d = 0
        parent = self.parent
        while parent:
            d += 1
            parent = parent.parent
        return d


class FinaleCapitolo(models.Model):
    nome = models.CharField(max_length=100, unique=True)
    descrizione = models.TextField(blank=True, null=True)
    ordine = models.PositiveIntegerField(default=0)
    fen_preview = models.TextField(
        blank=True,
        null=True,
        help_text="FEN per la miniatura del capitolo. Se vuoto, usa la prima linea.",
    )

    class Meta:
        ordering = ["ordine", "nome"]

    def __str__(self):
        return self.nome


class FinaleLine(ReviewFieldsMixin, models.Model):
    capitolo = models.ForeignKey(FinaleCapitolo, on_delete=models.CASCADE, related_name="linee")
    numero = models.PositiveIntegerField(default=0, null=True, blank=True)
    titolo = models.CharField(max_length=200, blank=True, null=True)
    fen_start = models.TextField()
    pgn = models.TextField()
    note = models.TextField(blank=True, null=True)
    flipped = models.BooleanField(default=False)
    difficolta = models.CharField(max_length=20, choices=DIFFICOLTA_CHOICES, default="media", blank=True)
    parent = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="varianti",
    )

    class Meta:
        ordering = ["numero"]

    def __str__(self):
        return f"{self.capitolo.nome} - Linea {self.numero}"

    def count_moves(self):
        clean = self.pgn.replace("{", "").replace("}", "")
        return len([m for m in clean.split() if "." not in m and m not in ["1-0", "0-1", "1/2-1/2", "*"]])

    def is_leaf(self):
        return not self.varianti.exists()


class FinalePosizione(models.Model):
    capitolo = models.ForeignKey(FinaleCapitolo, on_delete=models.CASCADE, related_name="posizioni")
    titolo = models.CharField(max_length=200)
    fen = models.TextField()
    note = models.TextField(blank=True, null=True)
    difficolta = models.CharField(max_length=20, choices=DIFFICOLTA_CHOICES, default="media")
    ordine = models.PositiveIntegerField(default=0)
    completamenti = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["ordine", "id"]

    def __str__(self):
        return f"{self.capitolo.nome} - {self.titolo}"


class OpeningLineMistake(MistakeBase):
    line = models.ForeignKey(OpeningLine, on_delete=models.CASCADE, related_name="mistake_entries")

    class Meta(MistakeBase.Meta):
        constraints = [
            models.UniqueConstraint(
                fields=["line", "fen", "wrong_move", "expected_move", "move_index", "side_to_train"],
                name="uniq_opening_line_mistake",
            ),
        ]

    def __str__(self):
        return f"{self.line.root.nome} - {self.expected_move} vs {self.wrong_move}"


class FinaleLineMistake(MistakeBase):
    line = models.ForeignKey(FinaleLine, on_delete=models.CASCADE, related_name="mistake_entries")

    class Meta(MistakeBase.Meta):
        constraints = [
            models.UniqueConstraint(
                fields=["line", "fen", "wrong_move", "expected_move", "move_index", "side_to_train"],
                name="uniq_finale_line_mistake",
            ),
        ]

    def __str__(self):
        return f"{self.line.capitolo.nome} - {self.expected_move} vs {self.wrong_move}"


class Puzzle(models.Model):
    """Puzzle tattico in formato Lichess: `fen` è la posizione prima della mossa avversaria,
    `moves` (UCI) inizia con quella mossa e prosegue con la soluzione."""

    lichess_id = models.CharField(max_length=16, unique=True)
    fen = models.TextField()
    moves = models.TextField()
    rating = models.PositiveIntegerField(default=1500, db_index=True)
    themes = models.CharField(max_length=400, blank=True, default="")
    game_url = models.CharField(max_length=200, blank=True, default="")
    opening_tags = models.CharField(max_length=200, blank=True, default="")
    source = models.CharField(max_length=20, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    attempt_count = models.PositiveIntegerField(default=0)
    success_count = models.PositiveIntegerField(default=0)
    fail_count = models.PositiveIntegerField(default=0)
    last_attempt_at = models.DateTimeField(blank=True, null=True)
    review_streak = models.PositiveIntegerField(default=0)
    due_at = models.DateTimeField(blank=True, null=True, db_index=True)

    class Meta:
        ordering = ["rating", "id"]

    def __str__(self):
        return f"Puzzle {self.lichess_id} ({self.rating})"

    @property
    def lichess_url(self):
        return f"https://lichess.org/training/{self.lichess_id}"


class PuzzleAttempt(models.Model):
    puzzle = models.ForeignKey(Puzzle, on_delete=models.CASCADE, related_name="attempts")
    created_at = models.DateTimeField(default=timezone.now, db_index=True)
    success = models.BooleanField(default=False)
    first_attempt = models.BooleanField(default=True)
    is_review = models.BooleanField(default=False)
    solution_shown = models.BooleanField(default=False)
    hint_used = models.BooleanField(default=False)
    time_ms = models.PositiveIntegerField(blank=True, null=True)
    wrong_move = models.CharField(max_length=20, blank=True, default="")
    expected_move = models.CharField(max_length=20, blank=True, default="")
    error_fen = models.TextField(blank=True, default="")
    move_index = models.PositiveIntegerField(default=0)
    rating_after = models.IntegerField(blank=True, null=True)
    guess_theme = models.CharField(max_length=40, blank=True, default="")
    guess_target = models.CharField(max_length=40, blank=True, default="")
    guess_correct = models.BooleanField(blank=True, null=True)

    class Meta:
        ordering = ["-created_at", "-id"]

    def __str__(self):
        esito = "ok" if self.success else "errore"
        return f"{self.puzzle.lichess_id} - {esito}"
