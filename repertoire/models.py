from django.db import models

# Create your models here.
from django.db import models

class OpeningRoot(models.Model):
    nome = models.CharField(max_length=100, unique=True)       # es: "Caro-Kann"
    moves = models.CharField(max_length=50, blank=True, null=True)  # es: "1.e4 c6"
    descrizione = models.TextField(blank=True, null=True)

    class Meta:
        ordering = ['nome']

    def __str__(self):
        return self.nome


class OpeningLine(models.Model):
    root = models.ForeignKey(OpeningRoot, on_delete=models.CASCADE, related_name='linee')
    numero = models.PositiveIntegerField()  # Linea 1, 2, 3, ecc.
    titolo = models.CharField(max_length=200, blank=True, null=True)
    pgn = models.TextField()  # sequenza PGN o solo le mosse principali
    note = models.TextField(blank=True, null=True)

    class Meta:
        unique_together = ('root', 'numero')
        ordering = ['numero']

    def __str__(self):
        return f"{self.root.nome} - Linea {self.numero}"
