from django.db import models
from datetime import date, timedelta

DIFFICOLTA_CHOICES = [
    ('facile',    'Facile'),
    ('media',     'Media'),
    ('difficile', 'Difficile'),
]

class OpeningRoot(models.Model):
    nome = models.CharField(max_length=100, unique=True)
    moves = models.CharField(max_length=50, blank=True, null=True)
    descrizione = models.TextField(blank=True, null=True)
    difesa = models.BooleanField(default=False)

    class Meta:
        ordering = ['nome']

    def __str__(self):
        return self.nome


class OpeningLine(models.Model):
    root = models.ForeignKey("OpeningRoot", on_delete=models.CASCADE, related_name="linee")
    numero = models.PositiveIntegerField(default=0, null=True, blank=True)
    titolo = models.CharField(max_length=200, blank=True, null=True)
    pgn = models.TextField()
    note = models.TextField(blank=True, null=True)
    flipped = models.BooleanField(default=False)

    completamenti = models.PositiveIntegerField(default=0)
    difficolta    = models.CharField(max_length=20, choices=DIFFICOLTA_CHOICES, default='media', blank=True)

    # SRS (Spaced Repetition System — algoritmo SM-2)
    srs_interval    = models.IntegerField(default=1)
    srs_easiness    = models.FloatField(default=2.5)
    srs_repetitions = models.IntegerField(default=0)
    srs_due_date    = models.DateField(null=True, blank=True)

    # ⬇️ gerarchia (varianti figlie)
    parent = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="varianti"
    )

    class Meta:
        ordering = ['numero']


    def __str__(self):
        return f"{self.root.nome} - Linea {self.numero}"

    # ✅ Conta le mosse reali nella PGN
    def count_moves(self):
        clean = self.pgn.replace('{', '').replace('}', '')
        return len([m for m in clean.split() if '.' not in m and m not in ['1-0', '0-1', '1/2-1/2', '*']])

    def mosse_chiave(self):
        return " ".join(self.pgn.split()[:6])

    def label_with_indent(self):
        indent = ""
        cur = self
        while cur.parent:
            indent += "— "
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

    def apply_sm2(self, quality):
        """Applica l'algoritmo SM-2. quality: 0-5 (0-2 = fail, 3-5 = pass)."""
        if quality < 3:
            self.srs_repetitions = 0
            self.srs_interval = 1
        else:
            if self.srs_repetitions == 0:
                self.srs_interval = 1
            elif self.srs_repetitions == 1:
                self.srs_interval = 6
            else:
                self.srs_interval = round(self.srs_interval * self.srs_easiness)
            self.srs_repetitions += 1
            self.srs_easiness = max(
                1.3,
                self.srs_easiness + 0.1 - (5 - quality) * (0.08 + (5 - quality) * 0.02)
            )
        self.srs_due_date = date.today() + timedelta(days=self.srs_interval)
        self.completamenti += 1
        self.save()


class LineSession(models.Model):
    """Singola sessione di allenamento su una linea."""
    line         = models.ForeignKey(OpeningLine, on_delete=models.CASCADE, related_name='sessioni')
    timestamp    = models.DateTimeField(auto_now_add=True)
    quality      = models.IntegerField()          # 0-5 (SM-2 quality)
    time_seconds = models.IntegerField(null=True, blank=True)

    class Meta:
        ordering = ['-timestamp']

    def __str__(self):
        return f"Sessione {self.line} — q={self.quality}"

