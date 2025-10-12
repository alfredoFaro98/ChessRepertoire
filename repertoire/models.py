from django.db import models

class OpeningRoot(models.Model):
    nome = models.CharField(max_length=100, unique=True)
    moves = models.CharField(max_length=50, blank=True, null=True)
    descrizione = models.TextField(blank=True, null=True)

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
