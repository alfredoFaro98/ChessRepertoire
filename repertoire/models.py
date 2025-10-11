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


# models.py

class OpeningLine(models.Model):
    root = models.ForeignKey(OpeningRoot, on_delete=models.CASCADE, related_name='linee')
    numero = models.PositiveIntegerField()
    titolo = models.CharField(max_length=200, blank=True, null=True)
    pgn = models.TextField()
    note = models.TextField(blank=True, null=True)
    flipped = models.BooleanField(default=False)

    # 👇 nuovo campo opzionale
    parent = models.ForeignKey('self', null=True, blank=True, on_delete=models.SET_NULL, related_name='varianti')

    class Meta:
        unique_together = ('root', 'numero')
        ordering = ['numero']

    def __str__(self):
        return f"{self.root.nome} - Linea {self.numero}"

    def mosse_chiave(self):
        """Restituisce la sequenza sintetica di mosse (tipo '1.e4 c6 2.d4 d5')"""
        return " ".join(self.pgn.split()[:6])


