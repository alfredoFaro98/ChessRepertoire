import os
import django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "chessrepertoire.settings")
django.setup()

from repertoire.models import OpeningRoot, OpeningLine

FILE_NAME = "carok"
ROOT_NAME = "Caro-Kann"

def clean_pgn(pgn):
    tokens = []
    for t in pgn.replace('.', '').split():
        if not t.isdigit() and t not in ["1-0", "0-1", "1/2-1/2", "*"]:
            tokens.append(t.strip())
    return " ".join(tokens)

root, _ = OpeningRoot.objects.get_or_create(
    nome=ROOT_NAME,
    defaults={
        "moves": "1. e4 c6 2. d4 d5",
        "descrizione": "",
        "difesa": True,
    },
)

with open(FILE_NAME, "r", encoding="utf-8") as f:
    raw_lines = [line.strip() for line in f if line.strip()]

unique_lines = []
for l in raw_lines:
    if l not in unique_lines:
        unique_lines.append(l)

existing = set(OpeningLine.objects.filter(root=root).values_list("pgn", flat=True))

inserted = 0
start_index = OpeningLine.objects.filter(root=root).count() + 1

for i, pgn in enumerate(unique_lines, start=start_index):
    if pgn not in existing:
        OpeningLine.objects.create(
            root=root,
            numero=i,
            titolo=" ".join(pgn.split()[:6]),
            pgn=pgn,
            flipped=root.difesa,
        )
        inserted += 1

print(f"[OK] Importazione completata per '{ROOT_NAME}'")
print(f"  Linee nel file: {len(raw_lines)}")
print(f"  Linee uniche: {len(unique_lines)}")
print(f"  Nuove linee inserite: {inserted}")

# Alberizzazione automatica
lines = list(root.linee.all())

for l in lines:
    l.parent = None
    l.save(update_fields=["parent"])

lines.sort(key=lambda l: len(clean_pgn(l.pgn).split()))

for child in lines:
    best_parent = None
    moves_child = clean_pgn(child.pgn)
    for potential_parent in lines:
        if potential_parent == child:
            continue
        moves_parent = clean_pgn(potential_parent.pgn)
        if moves_child.startswith(moves_parent) and len(moves_parent) < len(moves_child):
            if not best_parent or len(moves_parent) > len(clean_pgn(best_parent.pgn)):
                best_parent = potential_parent
    if best_parent:
        child.parent = best_parent
        child.save(update_fields=["parent"])

print(f"\n[TREE] Alberizzazione completata per '{ROOT_NAME}'")
print(f"  Totale linee: {len(lines)}")
