"""
Script per sostituire il contenuto del capitolo "Re e Pedone".
Eseguire con: python manage.py shell < seed_re_e_pedone.py
"""
import django, os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'chessrepertoire.settings')
django.setup()

from repertoire.models import FinaleCapitolo, FinaleLine, FinalePosizione

# ── Recupera il capitolo ──────────────────────────────────────────────────────
capitolo = FinaleCapitolo.objects.get(nome="Re e Pedone")

# ── Cancella tutto il vecchio contenuto ───────────────────────────────────────
FinaleLine.objects.filter(capitolo=capitolo).delete()
FinalePosizione.objects.filter(capitolo=capitolo).delete()
print("Vecchie linee e posizioni eliminate.")

# ── LINEE ─────────────────────────────────────────────────────────────────────

l1 = FinaleLine.objects.create(
    capitolo=capitolo,
    numero=1,
    titolo="La Regola del Quadrato",
    fen_start="8/8/8/8/P7/8/7k/8 w - - 0 1",
    pgn="1. a5 Kg3 2. a6 Kf4 3. a7 Ke5 4. a8=Q",
    note="Traccia una diagonale dal pedone fino all'ultima traversa per creare un quadrato immaginario. Se il Re difensore può entrare in questo quadrato al suo turno, catturerà il pedone. Qui il Nero è fuori dal quadrato.",
    difficolta="facile",
    flipped=False,
)
print(f"Creata linea: {l1}")

l2 = FinaleLine.objects.create(
    capitolo=capitolo,
    numero=2,
    titolo="Pedone davanti al Re (Patta)",
    fen_start="8/8/3k4/3P4/3K4/8/8/8 w - - 0 1",
    pgn="1. Kc4 Kd7 2. Kc5 Kc7 3. d6+ Kd7 4. Kd5 Kd8 5. Kc6 Kc8 6. d7+ Kd8 7. Kd6",
    note="Se il pedone si trova davanti al proprio Re, la posizione è patta (se il difensore non sbaglia). Il Nero si difende indietreggiando sempre sulla colonna del pedone per poi prendere l'opposizione, forzando lo stallo.",
    difficolta="facile",
    flipped=False,
)
print(f"Creata linea: {l2}")

l3 = FinaleLine.objects.create(
    capitolo=capitolo,
    numero=3,
    titolo="Re davanti al pedone e Aggiramento",
    fen_start="8/8/3k4/8/3K4/3P4/8/8 w - - 0 1",
    pgn="1. Kc4 Kc6 2. d4 Kd6 3. d5 Kd7 4. Kc5 Kc7 5. d6+ Kd7 6. Kd5 Kd8 7. Kc6 Kc8 8. d7+ Kd8 9. Kd6",
    note="Il Re è davanti al pedone, ma tocca al Bianco (il Nero ha l'opposizione). Il Bianco deve 'aggirare' (1.Kc4) minacciando di avanzare. La regola aurea: il Re fa strada, il pedone lo segue a distanza.",
    difficolta="media",
    flipped=False,
)
print(f"Creata linea: {l3}")

l4 = FinaleLine.objects.create(
    capitolo=capitolo,
    numero=4,
    titolo="Mantenere l'opposizione per vincere",
    fen_start="8/3k4/8/3K4/3P4/8/8/8 b - - 0 1",
    pgn="1... Ke7 2. Kc6 Kd8 3. Kd6 Kc8 4. d5 Kd8 5. Ke6 Ke8 6. d6 Kd8 7. d7 Kc7 8. Ke7",
    note="Tocca al Nero muovere, quindi il Bianco HA l'opposizione. Quando il Nero si sposta di lato (es. Ke7), il Bianco avanza in diagonale dalla parte opposta (Kc6) controllando le case di promozione.",
    difficolta="media",
    flipped=False,
)
print(f"Creata linea: {l4}")

l5 = FinaleLine.objects.create(
    capitolo=capitolo,
    numero=5,
    titolo="L'illusione del Pedone di Torre",
    fen_start="8/8/8/8/7P/6K1/8/6k1 b - - 0 1",
    pgn="1... Kg2 2. h5 Kg3 3. h6 Kg4 4. h7 Kg5 5. h8=Q",
    note="Se il Re nero riesce a mettersi davanti al pedone di torre (sulla colonna h o a), o a confinare il Re bianco nell'angolo, è sempre patta. Qui però il Nero è troppo lontano e il Bianco vince.",
    difficolta="facile",
    flipped=False,
)
print(f"Creata linea: {l5}")

# Variante della linea 5 (pedone di torre con patta)
l5v = FinaleLine.objects.create(
    capitolo=capitolo,
    numero=None,
    titolo="Pedone di Torre — Patta per angolo",
    fen_start="8/8/8/6k1/7P/6K1/8/8 b - - 0 1",
    pgn="1... Kh6 2. Kg4 Kg6 3. h5+ Kh6 4. Kh4 Kh7 5. Kg5 Kg7 6. h6+ Kh7 7. Kh5 Kh8 8. Kg6 Kg8 9. h7+ Kh8 10. Kh6",
    note="Qui il Re difensore è riuscito ad arrivare all'angolo. Non c'è modo di snidarlo senza causare uno stallo. Patta.",
    difficolta="facile",
    flipped=False,
    parent=l5,
)
print(f"Creata variante: {l5v}")

l6 = FinaleLine.objects.create(
    capitolo=capitolo,
    numero=6,
    titolo="La Spallata (Shouldering)",
    fen_start="8/8/8/8/1P6/3K4/5k2/8 w - - 0 1",
    pgn="1. Kd4 Ke2 2. Kc5 Kd3 3. b5",
    note="Il Re bianco non spinge subito il pedone (1.b5? Ke3 e il Nero entra nel quadrato) né va dritto dal pedone (1.Kc4? Ke3), ma usa il suo corpo con 1.Kd4! per 'dare una spallata' al Re nero e tagliarlo fuori, guadagnando il tempo decisivo.",
    difficolta="difficile",
    flipped=False,
)
print(f"Creata linea: {l6}")

# ── POSIZIONI ─────────────────────────────────────────────────────────────────

p1 = FinalePosizione.objects.create(
    capitolo=capitolo,
    titolo="Regola del quadrato - Riconoscimento",
    fen="8/8/8/p7/8/8/2K5/8 w - - 0 1",
    note="Mossa al Bianco. Il Re entra nel quadrato? Sì, il quadrato è a5-e5-e1-a1. Con 1. Kd3 (o Kd2) il Bianco entra e patta.",
    difficolta="facile",
    ordine=1,
)
print(f"Creata posizione: {p1}")

p2 = FinalePosizione.objects.create(
    capitolo=capitolo,
    titolo="Chi ha l'opposizione?",
    fen="8/8/8/3k4/8/3K4/8/8 w - - 0 1",
    note="Mossa al Bianco. I Re si guardano con una casa dispari di distanza. Chi deve muovere perde l'opposizione. Qui tocca al Bianco, quindi il Nero ha l'opposizione.",
    difficolta="facile",
    ordine=2,
)
print(f"Creata posizione: {p2}")

p3 = FinalePosizione.objects.create(
    capitolo=capitolo,
    titolo="Case Chiave - La sesta traversa",
    fen="8/3k4/8/3K4/3P4/8/8/8 w - - 0 1",
    note="Se il pedone non ha ancora superato la metà scacchiera, le case chiave sono 2 traverse davanti al pedone (c6, d6, e6). Se il Re le occupa, vince matematicamente, a prescindere dal tratto!",
    difficolta="media",
    ordine=3,
)
print(f"Creata posizione: {p3}")

p4 = FinalePosizione.objects.create(
    capitolo=capitolo,
    titolo="Trappola di Stallo",
    fen="8/3P4/3K4/8/3k4/8/8/8 b - - 0 1",
    note="Tocca al Nero. Se non ci rifletti, sembrerebbe finita. Ma la mossa corretta del difensore è 1... Kd8! costringendo il Bianco a giocare 2. Ke6 (abbandonando il pedone) o 2. Kc6, che è stallo immediato.",
    difficolta="difficile",
    ordine=4,
)
print(f"Creata posizione: {p4}")

print("\nDone! Capitolo 'Re e Pedone' aggiornato con successo.")
