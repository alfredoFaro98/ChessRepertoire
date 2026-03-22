from django.db import models

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


# ── Finali ────────────────────────────────────────────────────────────────────

class FinaleCapitolo(models.Model):
    nome        = models.CharField(max_length=100, unique=True)
    descrizione = models.TextField(blank=True, null=True)
    ordine      = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['ordine', 'nome']

    def __str__(self):
        return self.nome


class FinaleLine(models.Model):
    capitolo    = models.ForeignKey(FinaleCapitolo, on_delete=models.CASCADE, related_name='linee')
    numero      = models.PositiveIntegerField(default=0, null=True, blank=True)
    titolo      = models.CharField(max_length=200, blank=True, null=True)
    fen_start   = models.TextField()
    pgn         = models.TextField()
    note        = models.TextField(blank=True, null=True)
    flipped     = models.BooleanField(default=False)
    completamenti = models.PositiveIntegerField(default=0)
    difficolta  = models.CharField(max_length=20, choices=DIFFICOLTA_CHOICES, default='media', blank=True)
    parent      = models.ForeignKey(
        'self', null=True, blank=True, on_delete=models.SET_NULL, related_name='varianti'
    )

    class Meta:
        ordering = ['numero']

    def __str__(self):
        return f"{self.capitolo.nome} - Linea {self.numero}"

    def count_moves(self):
        clean = self.pgn.replace('{', '').replace('}', '')
        return len([m for m in clean.split() if '.' not in m and m not in ['1-0', '0-1', '1/2-1/2', '*']])

    def is_leaf(self):
        return not self.varianti.exists()


class FinalePosizione(models.Model):
    capitolo    = models.ForeignKey(FinaleCapitolo, on_delete=models.CASCADE, related_name='posizioni')
    titolo      = models.CharField(max_length=200)
    fen         = models.TextField()
    note        = models.TextField(blank=True, null=True)
    difficolta  = models.CharField(max_length=20, choices=DIFFICOLTA_CHOICES, default='media')
    ordine      = models.PositiveIntegerField(default=0)

    completamenti = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['ordine', 'id']

    def __str__(self):
        return f"{self.capitolo.nome} – {self.titolo}"

