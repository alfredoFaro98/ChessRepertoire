from .models import OpeningLine

def trova_parent(linea: OpeningLine):
    """
    Trova la linea della stessa apertura (root) che è prefisso più lungo del PGN della linea corrente.
    Esempio:
      A: 1.e4 c6 2.d4 d5 3.e5
      B: 1.e4 c6 2.d4 d5 3.e5 Bf5  -> parent = A
    """
    if not linea.root or not linea.pgn:
        return None

    mosse = linea.pgn.split()
    if len(mosse) < 2:
        return None

    candidates = []
    qs = OpeningLine.objects.filter(root=linea.root).exclude(id=linea.id)
    for altra in qs:
        seq = altra.pgn.split()
        if len(seq) < len(mosse) and mosse[:len(seq)] == seq:
            candidates.append(altra)

    if not candidates:
        return None

    # Prende il prefisso più lungo
    candidates.sort(key=lambda l: len(l.pgn.split()), reverse=True)
    return candidates[0]
