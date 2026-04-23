import json
import re

import chess
import chess.svg
from django.db import transaction
from django.db.models import Count, F, Max, Q, Sum
from django.db.models.functions import Length
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from .models import (
    FinaleCapitolo,
    FinaleLine,
    FinaleLineMistake,
    FinalePosizione,
    OpeningLine,
    OpeningLineMistake,
    OpeningRoot,
)
from .utils import (
    due_label,
    extract_pgn_lines,
    is_due,
    normalize_pgn,
    pgn_preview,
    tokenize_pgn,
    trova_parent,
    update_review_fields,
)


def _pgn_to_moves(pgn):
    return tokenize_pgn(pgn)


def _build_move_tree(lines):
    root = {"n": "", "c": [], "l": None}
    for line in lines:
        moves = _pgn_to_moves(line.pgn)
        node = root
        for move in moves:
            child = next((c for c in node["c"] if c["n"] == move), None)
            if child is None:
                child = {"n": move, "c": [], "l": None}
                node["c"].append(child)
            node = child
        if moves:
            node["l"] = {"id": line.root_id, "num": line.numero}
    return root


def _opening_due_filter(now):
    return Q(linee__review_attempts=0) | Q(linee__due_at__isnull=True) | Q(linee__due_at__lte=now)


def _finale_due_filter(now):
    return Q(linee__review_attempts=0) | Q(linee__due_at__isnull=True) | Q(linee__due_at__lte=now)


def _line_due_filter(now):
    return Q(review_attempts=0) | Q(due_at__isnull=True) | Q(due_at__lte=now)


def _numbered_related_line_filter(prefix):
    return Q(**{f"{prefix}numero__isnull": False}) & Q(**{f"{prefix}numero__gt": 0})


def _numbered_line_filter():
    return Q(numero__isnull=False) & Q(numero__gt=0)


def _has_valid_line_number(line):
    return line.numero is not None and line.numero > 0


def _serialize_due_opening_line(line):
    if not _has_valid_line_number(line):
        return None
    return {
        "kind": "opening",
        "kind_label": "Apertura",
        "title": line.root.nome,
        "subtitle": f"Linea {line.numero}",
        "preview": line.titolo or pgn_preview(line.pgn, 10),
        "status": due_label(line),
        "difficulty": line.difficolta,
        "mistakes": line.mistakes,
        "accuracy": line.accuracy,
        "train_url": reverse("line_training", args=[line.root_id, line.numero]),
        "detail_url": reverse("line_detail", args=[line.root_id, line.numero]),
        "due_at": line.due_at,
    }


def _serialize_due_finale_line(line):
    if not _has_valid_line_number(line):
        return None
    return {
        "kind": "finale",
        "kind_label": "Finale",
        "title": line.capitolo.nome,
        "subtitle": f"Linea {line.numero}",
        "preview": line.titolo or pgn_preview(line.pgn, 10),
        "status": due_label(line),
        "difficulty": line.difficolta,
        "mistakes": line.mistakes,
        "accuracy": line.accuracy,
        "train_url": reverse("finale_line_training", args=[line.capitolo_id, line.numero]),
        "detail_url": reverse("finale_line_detail", args=[line.capitolo_id, line.numero]),
        "due_at": line.due_at,
    }


def _sort_due_entries(entries):
    def sort_key(item):
        due_at = item["due_at"]
        return (due_at is not None, due_at or timezone.now(), -item["mistakes"], item["title"].lower())

    return sorted(entries, key=sort_key)


def opening_list(request):
    query = request.GET.get("q", "")
    filtro = request.GET.get("filtro", "tutti")
    view_mode = request.GET.get("view", "card")
    sort_mode = request.GET.get("sort", "lines")
    now = timezone.now()
    numbered_opening_lines = OpeningLine.objects.filter(_numbered_line_filter())
    numbered_related_lines = _numbered_related_line_filter("linee__")

    openings = OpeningRoot.objects.annotate(
        num_linee=Count("linee", filter=numbered_related_lines, distinct=True),
        studied_linee=Count(
            "linee",
            filter=numbered_related_lines & Q(linee__completamenti__gt=0),
            distinct=True,
        ),
        due_linee=Count(
            "linee",
            filter=numbered_related_lines & _opening_due_filter(now),
            distinct=True,
        ),
    )
    if filtro == "attacchi":
        openings = openings.filter(difesa=False)
    elif filtro == "difese":
        openings = openings.filter(difesa=True)

    if query:
        openings = openings.filter(nome__icontains=query)

    openings = list(openings)
    if sort_mode == "name":
        openings.sort(key=lambda opening: (not opening.preferito, opening.nome.lower()))
    else:
        sort_mode = "lines"
        openings.sort(key=lambda opening: (not opening.preferito, -opening.num_linee, -opening.due_linee, opening.nome.lower()))

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

        openings_data.append(
            {
                "obj": opening,
                "svg": chess.svg.board(
                    board,
                    size=220,
                    flipped=getattr(opening, "difesa", False),
                    colors={"square light": "#eeeed2", "square dark": "#769656"},
                ),
                "num_linee": opening.num_linee,
                "studied_linee": opening.studied_linee,
                "due_linee": opening.due_linee,
            }
        )

    return render(
        request,
        "repertoire/opening_list.html",
        {
            "openings": openings_data,
            "all_openings": list(OpeningRoot.objects.all().order_by("nome").values("nome", "difesa")),
            "query": query,
            "filtro": filtro,
            "view_mode": view_mode if view_mode in {"card", "row"} else "card",
            "sort_mode": sort_mode,
            "total_opening_lines": numbered_opening_lines.count(),
            "trained_opening_lines": numbered_opening_lines.filter(completamenti__gt=0).count(),
        },
    )


def opening_detail(request, opening_id):
    opening = get_object_or_404(OpeningRoot, pk=opening_id)
    all_lines = list(
        OpeningLine.objects.filter(root=opening)
        .filter(_numbered_line_filter())
        .annotate(pgn_len=Length("pgn"))
        .order_by("pgn_len", "numero", "id")
    )
    tree_json = json.dumps(_build_move_tree(all_lines))
    completed = sum(1 for line in all_lines if line.completamenti > 0)
    due_count = sum(1 for line in all_lines if is_due(line))
    return render(
        request,
        "repertoire/opening_detail.html",
        {
            "opening": opening,
            "all_lines": all_lines,
            "tree_json": tree_json,
            "completed_lines": completed,
            "due_lines": due_count,
        },
    )


def line_detail(request, root_id, line_num):
    root = get_object_or_404(OpeningRoot, id=root_id)
    lines = list(OpeningLine.objects.filter(root=root).filter(_numbered_line_filter()).order_by("numero", "id"))

    if not (1 <= line_num <= len(lines)):
        return render(request, "404.html", status=404)

    line = lines[line_num - 1]
    prev_line = lines[line_num - 2] if line_num > 1 else None
    next_line = lines[line_num] if line_num < len(lines) else None

    return render(
        request,
        "repertoire/line_detail.html",
        {
            "root": root,
            "line": line,
            "prev_line": prev_line,
            "next_line": next_line,
            "total_lines": len(lines),
            "line_position": line_num,
        },
    )


def analisi_domande(request):
    return render(request, "repertoire/analisi_domande.html")


def minigiochi(request):
    return render(request, "repertoire/minigiochi.html")


@require_POST
def toggle_opening_favorite(request, pk):
    opening = get_object_or_404(OpeningRoot, pk=pk)
    opening.preferito = not opening.preferito
    opening.save(update_fields=["preferito"])
    return JsonResponse({"preferito": opening.preferito})


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


def line_training(request, root_id, numero):
    line = get_object_or_404(OpeningLine, root_id=root_id, numero=numero)
    prev_line = OpeningLine.objects.filter(root_id=root_id, numero__lt=numero).order_by("-numero").first()
    next_line = OpeningLine.objects.filter(root_id=root_id, numero__gt=numero).order_by("numero").first()
    return render(
        request,
        "repertoire/line_training.html",
        {
            "line": line,
            "prev_line": prev_line,
            "next_line": next_line,
            "training_event_url": reverse("line_training_event", args=[root_id, numero]),
        },
    )


@require_POST
def line_training_event(request, root_id, numero):
    line = get_object_or_404(OpeningLine, root_id=root_id, numero=numero)
    return _handle_training_event(request, line, OpeningLineMistake)


def import_pgn(request):
    openings = OpeningRoot.objects.all().order_by("nome")

    if request.method != "POST":
        return render(request, "repertoire/import_pgn.html", {"openings": openings, "include_variations": False})

    pgn_text = request.POST.get("pgn_text", "").strip()
    if "pgn_file" in request.FILES and not pgn_text:
        pgn_text = request.FILES["pgn_file"].read().decode("utf-8", errors="replace")

    if not pgn_text:
        return render(
            request,
            "repertoire/import_pgn.html",
            {
                "openings": openings,
                "error": "Nessun PGN fornito.",
                "include_variations": request.POST.get("include_variations") == "on",
            },
        )

    new_root_name = request.POST.get("new_root_name", "").strip()
    root_id = request.POST.get("root_id", "").strip()
    include_variations = request.POST.get("include_variations") == "on"

    if new_root_name:
        root, _ = OpeningRoot.objects.get_or_create(nome=new_root_name)
    elif root_id:
        root = get_object_or_404(OpeningRoot, pk=root_id)
    else:
        return render(
            request,
            "repertoire/import_pgn.html",
            {
                "openings": openings,
                "error": "Seleziona o crea un'apertura di destinazione.",
                "include_variations": include_variations,
            },
        )

    parsed_lines = extract_pgn_lines(pgn_text, include_variations=include_variations)
    if not parsed_lines:
        return render(
            request,
            "repertoire/import_pgn.html",
            {
                "openings": openings,
                "error": "Nessuna linea trovata nel PGN.",
                "include_variations": include_variations,
            },
        )

    existing_lines = list(OpeningLine.objects.filter(root=root).order_by("numero"))
    existing_normalized = {normalize_pgn(line.pgn) or line.pgn: line for line in existing_lines}
    next_number = (OpeningLine.objects.filter(root=root).aggregate(max_num=Max("numero"))["max_num"] or 0) + 1
    inserted_lines = []
    duplicate_lines = []

    for pgn in parsed_lines:
        normalized = normalize_pgn(pgn) or pgn
        if normalized in existing_normalized:
            duplicate_lines.append(pgn)
            continue

        line = OpeningLine.objects.create(
            root=root,
            numero=next_number,
            titolo=pgn_preview(pgn, 8),
            pgn=normalized,
        )
        inserted_lines.append(line)
        existing_normalized[normalized] = line
        next_number += 1

    if inserted_lines:
        for line in sorted(inserted_lines, key=lambda item: len(tokenize_pgn(item.pgn))):
            line.parent = trova_parent(line)
        OpeningLine.objects.bulk_update(inserted_lines, ["parent"])

    if not root.moves:
        root.moves = pgn_preview(parsed_lines[0], 6)[:50]
        root.save(update_fields=["moves"])

    return render(
        request,
        "repertoire/import_pgn.html",
        {
            "openings": openings,
            "success": f'Importate {len(inserted_lines)} nuove linee in "{root.nome}".',
            "root": root,
            "inserted": len(inserted_lines),
            "total_parsed": len(parsed_lines),
            "duplicates_count": len(duplicate_lines),
            "preview_lines": parsed_lines[:6],
            "imported_lines_preview": [line.pgn for line in inserted_lines[:6]],
            "include_variations": include_variations,
        },
    )


def home(request):
    filtro = request.GET.get("filtro", "tutti")
    if filtro not in ("tutti", "attacchi", "difese"):
        filtro = "tutti"

    difficolta = request.GET.get("difficolta", "tutte")
    if difficolta not in ("tutte", "facile", "media", "difficile"):
        difficolta = "tutte"

    now = timezone.now()
    opening_lines = OpeningLine.objects.filter(_numbered_line_filter())
    numbered_related_lines = _numbered_related_line_filter("linee__")

    total_lines = opening_lines.count()
    lines_studied = opening_lines.filter(completamenti__gt=0).count()
    total_completions = opening_lines.aggregate(total=Sum("completamenti"))["total"] or 0
    due_opening_count = OpeningLine.objects.filter(_numbered_line_filter()).filter(_line_due_filter(now)).count()
    due_final_count = FinaleLine.objects.filter(_numbered_line_filter()).filter(_line_due_filter(now)).count()

    openings = OpeningRoot.objects.annotate(
        total=Count("linee", filter=numbered_related_lines, distinct=True),
        studied=Count(
            "linee",
            filter=numbered_related_lines & Q(linee__completamenti__gt=0),
            distinct=True,
        ),
        due=Count(
            "linee",
            filter=numbered_related_lines & _opening_due_filter(now),
            distinct=True,
        ),
    )
    if filtro == "attacchi":
        openings = openings.filter(difesa=False)
    elif filtro == "difese":
        openings = openings.filter(difesa=True)

    openings_progress = []
    for opening in openings:
        pct = round((opening.studied / opening.total) * 100) if opening.total else 0
        openings_progress.append(
            {
                "obj": opening,
                "total": opening.total,
                "studied": opening.studied,
                "due": opening.due,
                "pct": pct,
            }
        )
    openings_progress.sort(key=lambda item: (-item["due"], -item["pct"], item["obj"].nome.lower()))

    due_openings_qs = OpeningLine.objects.select_related("root").filter(_numbered_line_filter()).filter(_line_due_filter(now))
    if filtro == "attacchi":
        due_openings_qs = due_openings_qs.filter(root__difesa=False)
    elif filtro == "difese":
        due_openings_qs = due_openings_qs.filter(root__difesa=True)
    if difficolta != "tutte":
        due_openings_qs = due_openings_qs.filter(difficolta=difficolta)

    due_openings = _sort_due_entries(
        filter(None, [_serialize_due_opening_line(line) for line in due_openings_qs.order_by("due_at", "-mistakes", "numero")[:12]])
    )[:12]
    due_finals = _sort_due_entries(
        filter(
            None,
            [
                _serialize_due_finale_line(line)
                for line in FinaleLine.objects.select_related("capitolo")
                .filter(_numbered_line_filter())
                .filter(_line_due_filter(now))
                .order_by("due_at", "-mistakes", "numero")[:8]
            ],
        )
    )[:8]

    fragile_lines = list(
        OpeningLine.objects.select_related("root")
        .filter(_numbered_line_filter())
        .filter(mistakes__gt=0)
        .order_by("-mistakes", "due_at", "numero")[:8]
    )

    return render(
        request,
        "repertoire/home.html",
        {
            "total_lines": total_lines,
            "lines_studied": lines_studied,
            "total_completions": total_completions,
            "due_today_total": due_opening_count + due_final_count,
            "due_openings": due_openings,
            "due_finals": due_finals,
            "fragile_lines": fragile_lines,
            "openings_progress": openings_progress,
            "filtro": filtro,
            "difficolta": difficolta,
        },
    )


def _fen_pieces(fen):
    white_symbols = {"K": "♔", "Q": "♕", "R": "♖", "B": "♗", "N": "♘", "P": "♙"}
    black_symbols = {"k": "♚", "q": "♛", "r": "♜", "b": "♝", "n": "♞", "p": "♟"}
    parts = (fen or "").split()
    placement = parts[0] if parts else ""
    white_counts = {piece: 0 for piece in "KQRBNP"}
    black_counts = {piece: 0 for piece in "kqrbnp"}
    for char in placement:
        if char in white_counts:
            white_counts[char] += 1
        elif char in black_counts:
            black_counts[char] += 1
    white = [white_symbols[piece] for piece in "KQRBNP" for _ in range(white_counts[piece])]
    black = [black_symbols[piece] for piece in "kqrbnp" for _ in range(black_counts[piece])]
    return white, black


def finali_list(request):
    now = timezone.now()
    capitoli = FinaleCapitolo.objects.annotate(
        num_linee=Count("linee", distinct=True),
        linee_studiate=Count("linee", filter=Q(linee__completamenti__gt=0), distinct=True),
        due_linee=Count(
            "linee",
            filter=_numbered_related_line_filter("linee__") & _finale_due_filter(now),
            distinct=True,
        ),
    ).prefetch_related("linee", "posizioni")

    capitoli_data = []
    for capitolo in capitoli:
        prefetched_lines = list(capitolo.linee.all())
        first_line = prefetched_lines[0] if prefetched_lines else None
        fen = capitolo.fen_preview or (first_line.fen_start if first_line else "")
        white_pieces, black_pieces = _fen_pieces(fen)
        capitoli_data.append(
            {
                "obj": capitolo,
                "white_pieces": white_pieces,
                "black_pieces": black_pieces,
                "num_linee": capitolo.num_linee,
                "linee_studiate": capitolo.linee_studiate,
                "due_linee": capitolo.due_linee,
            }
        )
    return render(request, "repertoire/finali_list.html", {"capitoli": capitoli_data})


def errori(request):
    kind = request.GET.get("kind", "tutti")
    if kind not in {"tutti", "aperture", "finali"}:
        kind = "tutti"

    opening_errors = list(
        OpeningLineMistake.objects.select_related("line__root")
        .filter(line__numero__isnull=False, line__numero__gt=0)
        .order_by("-occurrence_count", "-last_seen")[:25]
    )
    final_errors = list(
        FinaleLineMistake.objects.select_related("line__capitolo")
        .filter(line__numero__isnull=False, line__numero__gt=0)
        .order_by("-occurrence_count", "-last_seen")[:25]
    )

    error_entries = []
    if kind in {"tutti", "aperture"}:
        for item in opening_errors:
            if not _has_valid_line_number(item.line):
                continue
            error_entries.append(
                {
                    "kind": "Apertura",
                    "title": item.line.root.nome,
                    "subtitle": f"Linea {item.line.numero}",
                    "wrong_move": item.wrong_move,
                    "expected_move": item.expected_move,
                    "fen": item.fen,
                    "occurrence_count": item.occurrence_count,
                    "last_seen": item.last_seen,
                    "train_url": reverse("line_training", args=[item.line.root_id, item.line.numero]),
                }
            )
    if kind in {"tutti", "finali"}:
        for item in final_errors:
            if not _has_valid_line_number(item.line):
                continue
            error_entries.append(
                {
                    "kind": "Finale",
                    "title": item.line.capitolo.nome,
                    "subtitle": f"Linea {item.line.numero}",
                    "wrong_move": item.wrong_move,
                    "expected_move": item.expected_move,
                    "fen": item.fen,
                    "occurrence_count": item.occurrence_count,
                    "last_seen": item.last_seen,
                    "train_url": reverse("finale_line_training", args=[item.line.capitolo_id, item.line.numero]),
                }
            )

    error_entries.sort(key=lambda item: (-item["occurrence_count"], -item["last_seen"].timestamp()))

    return render(
        request,
        "repertoire/errori.html",
        {
            "kind": kind,
            "error_entries": error_entries[:40],
            "opening_error_count": OpeningLineMistake.objects.filter(line__numero__isnull=False, line__numero__gt=0).count(),
            "final_error_count": FinaleLineMistake.objects.filter(line__numero__isnull=False, line__numero__gt=0).count(),
        },
    )


def finali_chapter_detail(request, capitolo_id):
    capitolo = get_object_or_404(FinaleCapitolo, pk=capitolo_id)
    linee = list(capitolo.linee.filter(parent__isnull=True).filter(_numbered_line_filter()).order_by("numero", "id"))
    completed = sum(1 for line in linee if line.completamenti > 0)
    due_count = sum(1 for line in linee if is_due(line))
    return render(
        request,
        "repertoire/finali_chapter_detail.html",
        {
            "capitolo": capitolo,
            "linee": linee,
            "completed_lines": completed,
            "due_lines": due_count,
        },
    )


def finale_line_detail(request, capitolo_id, line_num):
    capitolo = get_object_or_404(FinaleCapitolo, pk=capitolo_id)
    linee = list(
        FinaleLine.objects.filter(capitolo=capitolo, parent__isnull=True)
        .filter(_numbered_line_filter())
        .order_by("numero", "id")
    )

    if not (1 <= line_num <= len(linee)):
        return render(request, "404.html", status=404)

    line = linee[line_num - 1]
    prev_line = linee[line_num - 2] if line_num > 1 else None
    next_line = linee[line_num] if line_num < len(linee) else None

    return render(
        request,
        "repertoire/finale_line_detail.html",
        {
            "capitolo": capitolo,
            "line": line,
            "prev_line": prev_line,
            "next_line": next_line,
            "total_lines": len(linee),
            "line_position": line_num,
        },
    )


def finale_line_training(request, capitolo_id, numero):
    capitolo = get_object_or_404(FinaleCapitolo, pk=capitolo_id)
    line = get_object_or_404(FinaleLine, capitolo=capitolo, numero=numero)
    prev_line = FinaleLine.objects.filter(capitolo=capitolo, numero__lt=numero).order_by("-numero").first()
    next_line = FinaleLine.objects.filter(capitolo=capitolo, numero__gt=numero).order_by("numero").first()
    return render(
        request,
        "repertoire/finale_line_training.html",
        {
            "capitolo": capitolo,
            "line": line,
            "prev_line": prev_line,
            "next_line": next_line,
            "training_event_url": reverse("finale_line_training_event", args=[capitolo_id, numero]),
        },
    )


@require_POST
def finale_line_training_event(request, capitolo_id, numero):
    capitolo = get_object_or_404(FinaleCapitolo, pk=capitolo_id)
    line = get_object_or_404(FinaleLine, capitolo=capitolo, numero=numero)
    return _handle_training_event(request, line, FinaleLineMistake)


def _handle_training_event(request, line, mistake_model):
    try:
        payload = json.loads(request.body.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return JsonResponse({"ok": False, "error": "Payload non valido."}, status=400)

    event = payload.get("event")
    if event == "mistake":
        wrong_move = (payload.get("wrong_move") or "-").strip()[:30]
        expected_move = (payload.get("expected_move") or "").strip()[:30]
        fen = (payload.get("fen") or "").strip()
        move_index = int(payload.get("move_index") or 0)
        side_to_train = (payload.get("side_to_train") or "w").strip()[:1] or "w"

        if not expected_move or not fen:
            return JsonResponse({"ok": False, "error": "Fen e mossa attesa sono obbligatorie."}, status=400)

        with transaction.atomic():
            mistake, created = mistake_model.objects.get_or_create(
                line=line,
                fen=fen,
                wrong_move=wrong_move,
                expected_move=expected_move,
                move_index=move_index,
                side_to_train=side_to_train,
                defaults={"occurrence_count": 1},
            )
            if not created:
                mistake_model.objects.filter(pk=mistake.pk).update(
                    occurrence_count=F("occurrence_count") + 1,
                    last_seen=timezone.now(),
                )
                mistake.refresh_from_db(fields=["occurrence_count", "last_seen"])

        return JsonResponse({"ok": True, "occurrence_count": mistake.occurrence_count})

    if event == "completed":
        wrong_attempts = max(0, int(payload.get("wrong_attempts") or 0))
        correct_moves = max(0, int(payload.get("correct_moves") or 0))
        total_moves = max(0, int(payload.get("total_moves") or 0))

        with transaction.atomic():
            result = update_review_fields(line, wrong_attempts, correct_moves, total_moves)
            line.save(
                update_fields=[
                    "completamenti",
                    "last_reviewed",
                    "due_at",
                    "review_attempts",
                    "mistakes",
                    "accuracy",
                ]
            )

        return JsonResponse(
            {
                "ok": True,
                "completamenti": line.completamenti,
                "due_at": result["due_at"].isoformat() if result["due_at"] else None,
                "accuracy": line.accuracy,
                "mistakes": line.mistakes,
            }
        )

    return JsonResponse({"ok": False, "error": "Evento non supportato."}, status=400)
