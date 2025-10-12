from django.core.management.base import BaseCommand
from django.db import transaction
from repertoire.models import OpeningRoot, OpeningLine

class Command(BaseCommand):
    help = "Riassegna i numeri delle linee seguendo la struttura gerarchica (DFS, più corte prima)"

    def handle(self, *args, **options):
        for opening in OpeningRoot.objects.all():
            self.stdout.write(f"\n🔄 Ricalcolo per {opening.nome}...")
            with transaction.atomic():
                # Passo 1️⃣ — azzera i numeri uno per volta
                for line in opening.linee.all():
                    line.numero = None
                    line.save(update_fields=["numero"])

                # Passo 2️⃣ — riassegna DFS
                counter = 1
                roots = opening.linee.filter(parent__isnull=True).order_by("id")
                for line in roots:
                    counter = self.assign_numbers(line, counter)

        self.stdout.write(self.style.SUCCESS("\n✅ Numerazione gerarchica completata."))

    def assign_numbers(self, line, counter):
        """Assegna numeri DFS: linea principale → varianti → sotto-varianti."""
        line.numero = counter
        line.save(update_fields=["numero"])
        self.stdout.write(f"{counter:>3}. {line.pgn[:60]}")
        counter += 1

        children = sorted(line.varianti.all(), key=lambda l: len(l.pgn.split()))
        for child in children:
            counter = self.assign_numbers(child, counter)
        return counter
