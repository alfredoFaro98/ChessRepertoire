from django.shortcuts import render, get_object_or_404
from .models import OpeningRoot, OpeningLine

from django.shortcuts import render
from .models import OpeningRoot
import chess
import chess.svg

def opening_list(request):
    query = request.GET.get("q", "")
    openings = OpeningRoot.objects.all()
    if query:
        openings = openings.filter(nome__icontains=query)

    openings_data = []
    for opening in openings:
        board = chess.Board()
        try:
            if opening.moves:
                for move in opening.moves.split():
                    if "." not in move:  # ignora numeri tipo "1." "2."
                        board.push_san(move)
        except Exception:
            pass

        openings_data.append({
            "obj": opening,
            "svg": chess.svg.board(board, size=200)
        })

    return render(request, "repertoire/opening_list.html", {
        "openings": openings_data,
        "query": query,
    })


from django.shortcuts import render, get_object_or_404
from .models import OpeningRoot, OpeningLine

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





