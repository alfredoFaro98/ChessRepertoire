import io
import json
import chess
import chess.svg
import chess.pgn
import re
from datetime import date, timedelta

from django.shortcuts import render, get_object_or_404
from django.http import HttpResponse
from django.db.models import Sum, Count
from django.db.models.functions import Length

from .models import OpeningRoot, OpeningLine, FinaleCapitolo, FinalePosizione, FinaleLine


# ── Move-tree helpers ──────────────────────────────────────────────────────────
def _pgn_to_moves(pgn):
    s = re.sub(r'\{[^}]*\}', '', pgn)
    s = re.sub(r'\$\d+', '', s)
    s = re.sub(r'\d+\.+', ' ', s)
    s = re.sub(r'(1-0|0-1|1/2-1/2|\*)', '', s)
    s = re.sub(r'[+#!?]', '', s)
    return [m for m in s.split() if m]


def _build_move_tree(lines):
    root = {'n': '', 'c': [], 'l': None}
    for line in lines:
        moves = _pgn_to_moves(line.pgn)
        node = root
        for move in moves:
            child = next((c for c in node['c'] if c['n'] == move), None)
            if child is None:
                child = {'n': move, 'c': [], 'l': None}
                node['c'].append(child)
            node = child
        if moves:
            node['l'] = {'id': line.root_id, 'num': line.numero}
    return root


# ── Lista aperture ─────────────────────────────────────────────────────────────
def opening_list(request):
    query  = request.GET.get("q", "")
    filtro = request.GET.get("filtro", "tutti")
    view_mode = request.GET.get("view", "card")
    sort_mode = request.GET.get("sort", "lines")

    openings = OpeningRoot.objects.annotate(num_linee=Count('linee'))
    if filtro == "attacchi":
        openings = openings.filter(difesa=False)
    elif filtro == "difese":
        openings = openings.filter(difesa=True)

    if query:
        openings = openings.filter(nome__icontains=query)

    openings = list(openings)
    if sort_mode == "name":
        openings.sort(key=lambda opening: opening.nome.lower())
    else:
        sort_mode = "lines"
        openings.sort(key=lambda opening: (-opening.num_linee, opening.nome.lower()))

    openings_data = []
    for opening in openings:
        board = chess.Board()
        try:
            if opening.moves:
                clean_moves = re.sub(r"\d+\.", "", opening.moves)
                for move in clean_moves.split():
                    if move not in ["1-0", "0-1", "1/2-1/2", "*"]:
                        board.push_san(move)
        except Exception:
            pass

        openings_data.append({
            "obj": opening,
            "svg": chess.svg.board(
                board, size=220,
                flipped=getattr(opening, "difesa", False),
                colors={"square light": "#eeeed2", "square dark": "#769656"},
            ),
            "num_linee": opening.num_linee,
            "studied_linee": opening.linee.filter(completamenti__gt=0).count(),
        })

    return render(request, "repertoire/opening_list.html", {
        "openings":     openings_data,
        "all_openings": list(
            OpeningRoot.objects
            .all()
            .order_by('nome')
            .values('nome', 'difesa')
        ),
        "query":        query,
        "filtro":       filtro,
        "view_mode":    view_mode if view_mode in {"card", "row"} else "card",
        "sort_mode":    sort_mode,
    })


# ── Dettaglio apertura ────────────────────────────────────────────────────────
def opening_detail(request, opening_id):
    opening = get_object_or_404(OpeningRoot, pk=opening_id)
    all_lines = list(
        OpeningLine.objects
        .filter(root=opening)
        .annotate(pgn_len=Length('pgn'))
        .order_by('pgn_len')
    )
    tree_json = json.dumps(_build_move_tree(all_lines))
    completed  = sum(1 for l in all_lines if l.completamenti > 0)
    return render(request, "repertoire/opening_detail.html", {
        "opening":        opening,
        "all_lines":      all_lines,
        "tree_json":      tree_json,
        "completed_lines": completed,
    })


# ── Dettaglio linea ────────────────────────────────────────────────────────────
def line_detail(request, root_id, line_num):
    root  = get_object_or_404(OpeningRoot, id=root_id)
    lines = list(OpeningLine.objects.filter(root=root).order_by('numero', 'id'))

    if not (1 <= line_num <= len(lines)):
        return render(request, "404.html", status=404)

    line      = lines[line_num - 1]
    prev_line = lines[line_num - 2] if line_num > 1 else None
    next_line = lines[line_num]     if line_num < len(lines) else None

    return render(request, "repertoire/line_detail.html", {
        "root":          root,
        "line":          line,
        "prev_line":     prev_line,
        "next_line":     next_line,
        "total_lines":   len(lines),
        "line_position": line_num,
    })


# ── Analisi domande ───────────────────────────────────────────────────────────
def analisi_domande(request):
    return render(request, 'repertoire/analisi_domande.html')


# ── Download TXT ──────────────────────────────────────────────────────────────
def download_opening_lines(request, pk):
    root = get_object_or_404(OpeningRoot, pk=pk)
    lines = root.linee.all().order_by("numero")
    content = ""
    for line in lines:
        content += " ".join(line.pgn.split()) + "\r\n"
    response = HttpResponse(content, content_type="text/plain; charset=utf-8")
    filename = f"{root.nome.replace(' ', '_').lower()}.txt"
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response


# ── Training ──────────────────────────────────────────────────────────────────
def line_training(request, root_id, numero):
    line      = get_object_or_404(OpeningLine, root_id=root_id, numero=numero)
    prev_line = OpeningLine.objects.filter(root_id=root_id, numero__lt=numero).order_by('-numero').first()
    next_line = OpeningLine.objects.filter(root_id=root_id, numero__gt=numero).order_by('numero').first()
    return render(request, "repertoire/line_training.html", {
        "line": line, "prev_line": prev_line, "next_line": next_line,
    })


# ── Import PGN ────────────────────────────────────────────────────────────────
def import_pgn(request):
    openings = OpeningRoot.objects.all().order_by('nome')

    if request.method != 'POST':
        return render(request, 'repertoire/import_pgn.html', {'openings': openings})

    # Leggi il testo PGN (da textarea o da file)
    pgn_text = request.POST.get('pgn_text', '').strip()
    if 'pgn_file' in request.FILES and not pgn_text:
        pgn_text = request.FILES['pgn_file'].read().decode('utf-8', errors='replace')

    if not pgn_text:
        return render(request, 'repertoire/import_pgn.html', {
            'openings': openings, 'error': 'Nessun PGN fornito.',
        })

    # Scegli / crea l'apertura
    new_root_name = request.POST.get('new_root_name', '').strip()
    root_id       = request.POST.get('root_id', '').strip()

    if new_root_name:
        root, _ = OpeningRoot.objects.get_or_create(nome=new_root_name)
    elif root_id:
        root = get_object_or_404(OpeningRoot, pk=root_id)
    else:
        return render(request, 'repertoire/import_pgn.html', {
            'openings': openings, 'error': "Seleziona o crea un'apertura di destinazione.",
        })

    # Parsing PGN: ogni game → una linea
    parsed_lines = []
    pgn_io = io.StringIO(pgn_text)
    while True:
        game = chess.pgn.read_game(pgn_io)
        if game is None:
            break
        board    = game.board()
        parts    = []
        move_num = board.fullmove_number
        for move in game.mainline_moves():
            if board.turn == chess.WHITE:
                parts.append(f"{move_num}.")
            parts.append(board.san(move))
            board.push(move)
            if board.turn == chess.WHITE:
                move_num += 1
        if parts:
            parsed_lines.append(' '.join(parts))

    if not parsed_lines:
        return render(request, 'repertoire/import_pgn.html', {
            'openings': openings, 'error': 'Nessuna linea trovata nel PGN.',
        })

    existing  = set(OpeningLine.objects.filter(root=root).values_list('pgn', flat=True))
    start_idx = OpeningLine.objects.filter(root=root).count() + 1
    inserted  = 0
    for i, pgn in enumerate(parsed_lines):
        if pgn not in existing:
            OpeningLine.objects.create(
                root=root, numero=start_idx + i,
                titolo=' '.join(pgn.replace('.', ' ').split()[:8]),
                pgn=pgn,
            )
            inserted += 1

    return render(request, 'repertoire/import_pgn.html', {
        'openings':      openings,
        'success':       f'Importate {inserted} nuove linee in "{root.nome}".',
        'root':          root,
        'inserted':      inserted,
        'total_parsed':  len(parsed_lines),
    })


# ── Dashboard Home ────────────────────────────────────────────────────────────
def home(request):
    filtro = request.GET.get('filtro', 'tutti')
    if filtro not in ('attacchi', 'difese'):
        filtro = 'tutti'

    total_lines       = OpeningLine.objects.count()
    lines_studied     = OpeningLine.objects.filter(completamenti__gt=0).count()
    total_completions = OpeningLine.objects.aggregate(t=Sum('completamenti'))['t'] or 0

    openings = OpeningRoot.objects.all()
    if filtro == 'attacchi':
        openings = openings.filter(difesa=False)
    elif filtro == 'difese':
        openings = openings.filter(difesa=True)

    openings_progress = []
    for op in openings:
        total   = op.linee.count()
        studied = op.linee.filter(completamenti__gt=0).count()
        pct     = round(studied / total * 100) if total else 0
        openings_progress.append({'obj': op, 'total': total, 'studied': studied, 'pct': pct})
    openings_progress.sort(key=lambda x: -x['pct'])

    return render(request, 'repertoire/home.html', {
        'total_lines':       total_lines,
        'lines_studied':     lines_studied,
        'total_completions': total_completions,
        'openings_progress': openings_progress,
        'filtro':            filtro,
    })


def _fen_pieces(fen):
    """Ritorna (pezzi_bianchi, pezzi_neri) come liste di simboli Unicode ordinati per valore."""
    W = {'K': '♔', 'Q': '♕', 'R': '♖', 'B': '♗', 'N': '♘', 'P': '♙'}
    B = {'k': '♚', 'q': '♛', 'r': '♜', 'b': '♝', 'n': '♞', 'p': '♟'}
    parts = (fen or '').split()
    placement = parts[0] if parts else ''
    wc = {p: 0 for p in 'KQRBNP'}
    bc = {p: 0 for p in 'kqrbnp'}
    for ch in placement:
        if ch in wc: wc[ch] += 1
        elif ch in bc: bc[ch] += 1
    white = [W[p] for p in 'KQRBNP' for _ in range(wc[p])]
    black = [B[p] for p in 'kqrbnp' for _ in range(bc[p])]
    return white, black


# ── Finali ────────────────────────────────────────────────────────────────────
def finali_list(request):
    capitoli = FinaleCapitolo.objects.prefetch_related('linee', 'posizioni').all()
    capitoli_data = []
    for cap in capitoli:
        fen = cap.fen_preview
        if not fen:
            first_line = cap.linee.first()
            if first_line:
                fen = first_line.fen_start
        white_pieces, black_pieces = _fen_pieces(fen)
        num_linee = cap.linee.count()
        linee_studiate = cap.linee.filter(completamenti__gt=0).count()
        capitoli_data.append({
            'obj': cap,
            'white_pieces': white_pieces,
            'black_pieces': black_pieces,
            'num_linee': num_linee,
            'linee_studiate': linee_studiate,
        })
    return render(request, 'repertoire/finali_list.html', {'capitoli': capitoli_data})


def errori(request):
    return render(request, 'repertoire/errori.html')


def finali_chapter_detail(request, capitolo_id):
    capitolo  = get_object_or_404(FinaleCapitolo, pk=capitolo_id)
    linee     = list(capitolo.linee.filter(parent__isnull=True))
    completed = sum(1 for l in linee if l.completamenti > 0)
    return render(request, 'repertoire/finali_chapter_detail.html', {
        'capitolo':        capitolo,
        'linee':           linee,
        'completed_lines': completed,
    })


def finale_line_detail(request, capitolo_id, line_num):
    capitolo = get_object_or_404(FinaleCapitolo, pk=capitolo_id)
    linee    = list(FinaleLine.objects.filter(capitolo=capitolo, parent__isnull=True).order_by('numero', 'id'))

    if not (1 <= line_num <= len(linee)):
        return render(request, '404.html', status=404)

    line      = linee[line_num - 1]
    prev_line = linee[line_num - 2] if line_num > 1 else None
    next_line = linee[line_num]     if line_num < len(linee) else None

    return render(request, 'repertoire/finale_line_detail.html', {
        'capitolo':      capitolo,
        'line':          line,
        'prev_line':     prev_line,
        'next_line':     next_line,
        'total_lines':   len(linee),
        'line_position': line_num,
    })


def finale_line_training(request, capitolo_id, numero):
    capitolo  = get_object_or_404(FinaleCapitolo, pk=capitolo_id)
    line      = get_object_or_404(FinaleLine, capitolo=capitolo, numero=numero)
    prev_line = FinaleLine.objects.filter(capitolo=capitolo, numero__lt=numero).order_by('-numero').first()
    next_line = FinaleLine.objects.filter(capitolo=capitolo, numero__gt=numero).order_by('numero').first()
    return render(request, 'repertoire/finale_line_training.html', {
        'capitolo': capitolo,
        'line':     line,
        'prev_line': prev_line,
        'next_line': next_line,
    })
