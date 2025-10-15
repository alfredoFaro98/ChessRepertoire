from django.shortcuts import render, get_object_or_404
from .models import OpeningRoot, OpeningLine

from django.shortcuts import render
from .models import OpeningRoot
import chess
import chess.svg
import re

def opening_list(request):
    query = request.GET.get("q", "")
    filtro = request.GET.get("filtro", "tutti")

    # 🔍 Filtro base
    openings = OpeningRoot.objects.all()
    if filtro == "attacchi":
        openings = openings.filter(difesa=False)
    elif filtro == "difese":
        openings = openings.filter(difesa=True)

    if query:
        openings = openings.filter(nome__icontains=query)

    openings_data = []

    for opening in openings:
        board = chess.Board()
        try:
            if opening.moves:
                clean_moves = re.sub(r"\d+\.", "", opening.moves)
                tokens = clean_moves.split()
                for move in tokens:
                    if move not in ["1-0", "0-1", "1/2-1/2", "*"]:
                        board.push_san(move)
        except Exception:
            pass

        # 🧮 Conta le linee associate a questa apertura
        num_linee = opening.linee.count()

        openings_data.append({
            "obj": opening,
            "svg": chess.svg.board(
                board,
                size=220,
                flipped=getattr(opening, "difesa", False),
                colors={"square light": "#eeeed2", "square dark": "#769656"},
            ),
            "num_linee": num_linee,  # 👈 aggiunto
        })

    return render(request, "repertoire/opening_list.html", {
        "openings": openings_data,
        "all_openings": OpeningRoot.objects.all(),
        "query": query,
        "filtro": filtro,
    })


from django.shortcuts import render, get_object_or_404
from .models import OpeningRoot, OpeningLine

def opening_detail(request, opening_id):
    opening = get_object_or_404(OpeningRoot, id=opening_id)

    # Tutte le linee di questa apertura (root)
    all_lines = list(OpeningLine.objects.filter(root=opening).order_by("numero", "id"))

    # Mappa {line.id: posizione_reale}
    positions = {line.id: idx + 1 for idx, line in enumerate(all_lines)}

    # Linee principali per costruire l’albero
    main_lines = (
        opening.linee
        .filter(parent__isnull=True)
        .prefetch_related(
            "varianti",
            "varianti__varianti",
            "varianti__varianti__varianti",
            "varianti__varianti__varianti__varianti"
        )
    )

    return render(request, "repertoire/opening_detail.html", {
        "opening": opening,
        "main_lines": main_lines,
        "positions": positions,  # 👈 passiamo la mappa
    })




from django.shortcuts import render, get_object_or_404
from .models import OpeningRoot, OpeningLine

def line_detail(request, root_id, line_num):
    root = get_object_or_404(OpeningRoot, id=root_id)
    
    # Otteniamo tutte le linee della root ordinate realmente per 'numero' e poi per 'id'
    lines = list(OpeningLine.objects.filter(root=root).order_by('numero', 'id'))
    
    # Verifica che il numero richiesto esista come indice (1-based)
    if not (1 <= line_num <= len(lines)):
        return render(request, "404.html", status=404)
    
    # Recupera la linea in base alla posizione reale nella lista
    line = lines[line_num - 1]
    
    prev_line = lines[line_num - 2] if line_num > 1 else None
    next_line = lines[line_num] if line_num < len(lines) else None

    context = {
        "root": root,
        "line": line,
        "prev_line": prev_line,
        "next_line": next_line,
        "total_lines": len(lines),
        "line_position": line_num,
    }
    return render(request, "repertoire/line_detail.html", context)

from django.shortcuts import render

def analisi_domande(request):
    return render(request, 'repertoire/analisi_domande.html')


from django.http import HttpResponse
from .models import OpeningRoot

def download_opening_lines(request, pk):
    """Esporta tutte le linee di un'apertura in un file TXT scaricabile"""
    try:
        root = OpeningRoot.objects.get(pk=pk)
    except OpeningRoot.DoesNotExist:
        return HttpResponse("Apertura non trovata", status=404)

    # Recupera tutte le linee ordinate per numero
    lines = root.linee.all().order_by("numero")

    # Costruisce il contenuto del file
    content = ""
    for line in lines:
        # Rimuove qualsiasi newline presente nella stringa originale
        clean_pgn = " ".join(line.pgn.split())
        content += clean_pgn + "\r\n"


    # Crea la risposta HTTP come file TXT
    response = HttpResponse(content, content_type="text/plain; charset=utf-8")
    filename = f"{root.nome.replace(' ', '_').lower()}.txt"
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response

def line_training(request, root_id, numero):
    from .models import OpeningLine
    line = OpeningLine.objects.get(root_id=root_id, numero=numero)
    return render(request, "repertoire/line_training.html", {"line": line})

