import json
import io
import chess
import chess.svg
import chess.pgn
import re
from datetime import date, timedelta

from django.shortcuts import render, get_object_or_404
from django.http import HttpResponse, JsonResponse
from django.views.decorators.http import require_POST
from django.db.models import Sum, Avg, Count
from django.db.models.functions import Length

from .models import OpeningRoot, OpeningLine, LineSession


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
    all_lines = (
        OpeningLine.objects
        .filter(root=opening)
        .annotate(pgn_len=Length('pgn'))
        .order_by('pgn_len')
    )
    return render(request, "repertoire/opening_detail.html", {
        "opening":   opening,
        "all_lines": all_lines,
    })


# ── Dettaglio linea (con statistiche) ─────────────────────────────────────────
def line_detail(request, root_id, line_num):
    root  = get_object_or_404(OpeningRoot, id=root_id)
    lines = list(OpeningLine.objects.filter(root=root).order_by('numero', 'id'))

    if not (1 <= line_num <= len(lines)):
        return render(request, "404.html", status=404)

    line      = lines[line_num - 1]
    prev_line = lines[line_num - 2] if line_num > 1 else None
    next_line = lines[line_num]     if line_num < len(lines) else None

    # Statistiche sessioni
    avg_quality = line.sessioni.aggregate(avg=Avg('quality'))['avg']
    avg_time    = line.sessioni.filter(time_seconds__isnull=False).aggregate(avg=Avg('time_seconds'))['avg']

    # Chart: ultimi 14 giorni
    today = date.today()
    chart_labels, chart_data = [], []
    for i in range(13, -1, -1):
        d = today - timedelta(days=i)
        chart_labels.append(d.strftime('%d/%m'))
        chart_data.append(line.sessioni.filter(timestamp__date=d).count())

    return render(request, "repertoire/line_detail.html", {
        "root":           root,
        "line":           line,
        "prev_line":      prev_line,
        "next_line":      next_line,
        "total_lines":    len(lines),
        "line_position":  line_num,
        "avg_quality":    round(avg_quality, 1) if avg_quality else None,
        "avg_time":       round(avg_time)        if avg_time    else None,
        "chart_labels":   chart_labels,
        "chart_data":     chart_data,
        "sessions_count": line.sessioni.count(),
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


# ── Completamento linea (SM-2 + sessione) ─────────────────────────────────────
@require_POST
def incrementa_completamenti(request, line_id):
    try:
        line = OpeningLine.objects.get(pk=line_id)
        try:
            body         = json.loads(request.body)
            quality      = int(body.get("quality", 3))
            time_seconds = body.get("time_seconds")
            if time_seconds is not None:
                time_seconds = int(time_seconds)
        except Exception:
            quality      = 3
            time_seconds = None

        quality = max(0, min(5, quality))
        line.apply_sm2(quality)
        LineSession.objects.create(line=line, quality=quality, time_seconds=time_seconds)

        return JsonResponse({
            "success":      True,
            "totale":       line.completamenti,
            "srs_due_date": str(line.srs_due_date),
            "srs_interval": line.srs_interval,
        })
    except OpeningLine.DoesNotExist:
        return JsonResponse({"success": False, "error": "Linea non trovata"}, status=404)


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
    today = date.today()
    filtro = request.GET.get('filtro', 'tutti')

    due_lines = (
        OpeningLine.objects
        .filter(srs_due_date__lte=today)
        .select_related('root')
        .order_by('srs_due_date', 'root__nome', 'numero')
    )
    if filtro == 'attacchi':
        due_lines = due_lines.filter(root__difesa=False)
    elif filtro == 'difese':
        due_lines = due_lines.filter(root__difesa=True)
    else:
        filtro = 'tutti'

    total_lines       = OpeningLine.objects.count()
    new_lines_count   = OpeningLine.objects.filter(srs_due_date__isnull=True).count()
    lines_studied     = OpeningLine.objects.filter(completamenti__gt=0).count()
    total_completions = OpeningLine.objects.aggregate(t=Sum('completamenti'))['t'] or 0

    openings_progress = []
    openings = OpeningRoot.objects.all()
    if filtro == 'attacchi':
        openings = openings.filter(difesa=False)
    elif filtro == 'difese':
        openings = openings.filter(difesa=True)

    for op in openings:
        total   = op.linee.count()
        studied = op.linee.filter(completamenti__gt=0).count()
        pct     = round(studied / total * 100) if total else 0
        openings_progress.append({'obj': op, 'total': total, 'studied': studied, 'pct': pct})
    openings_progress.sort(key=lambda x: -x['pct'])

    return render(request, 'repertoire/home.html', {
        'due_lines':         due_lines,
        'new_lines_count':   new_lines_count,
        'total_lines':       total_lines,
        'lines_studied':     lines_studied,
        'total_completions': total_completions,
        'openings_progress': openings_progress,
        'today':             today,
        'filtro':            filtro,
    })
