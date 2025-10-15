# import_from_txt.py
from repertoire.models import OpeningRoot, OpeningLine

# Nome del file di testo (una linea PGN per riga)
FILE_NAME = "linee_alberizzate.txt"

# Nome del root principale
ROOT_NAME = "Gioco Italiano"

# 1️⃣ Crea o recupera il root
root, created = OpeningRoot.objects.get_or_create(
    nome=ROOT_NAME,
    defaults={
        "moves": "1.e4 e5 2.Nf3 Nc6 3.Bc4",
        "descrizione": "Apertura classica italiana: sviluppo rapido e pressione su f7.",
        "difesa": False,
    },
)

# 2️⃣ Legge le righe dal file
try:
    with open(FILE_NAME, "r", encoding="utf-8") as f:
        raw_lines = [line.strip() for line in f if line.strip()]
except FileNotFoundError:
    print(f"❌ File '{FILE_NAME}' non trovato. Assicurati che sia nella stessa cartella dello script.")
    raise SystemExit

# 3️⃣ Rimuove duplicati (mantiene l'ordine)
unique_lines = []
for l in raw_lines:
    if l not in unique_lines:
        unique_lines.append(l)

# 4️⃣ Controlla linee già presenti nel DB
existing = set(OpeningLine.objects.filter(root=root).values_list("pgn", flat=True))

# 5️⃣ Inserisce solo le nuove linee
inserted = 0
start_index = OpeningLine.objects.filter(root=root).count() + 1

for i, pgn in enumerate(unique_lines, start=start_index):
    if pgn not in existing:
        OpeningLine.objects.create(
            root=root,
            numero=i,
            titolo=" ".join(pgn.split()[:6]),
            pgn=pgn,
        )
        inserted += 1

# 6️⃣ Messaggi di riepilogo
print(f"\n✅ Importazione completata per '{ROOT_NAME}'")
print(f"➡️ Righe totali nel file: {len(raw_lines)}")
print(f"➡️ Righe uniche (filtrate): {len(unique_lines)}")
print(f"➡️ Nuove linee inserite: {inserted}")
print(f"➡️ Totale linee ora nel DB: {OpeningLine.objects.filter(root=root).count()}")
