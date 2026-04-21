import io
import math
import re
from datetime import timedelta

import chess
import chess.pgn
from django.utils import timezone

from .models import OpeningLine


RESULT_TOKENS = {"1-0", "0-1", "1/2-1/2", "*"}


def tokenize_pgn(pgn):
    text = pgn or ""
    text = re.sub(r"\{[^}]*\}", "", text)
    text = re.sub(r"\([^)]*\)", "", text)
    text = re.sub(r"\$\d+", "", text)
    text = re.sub(r"\d+\.(\.\.)?", " ", text)
    text = re.sub(r"[+#!?]", "", text)
    return [token for token in text.split() if token and token not in RESULT_TOKENS]


def canonical_pgn_from_moves(moves, start_fen=None):
    if not moves:
        return ""

    board = chess.Board(start_fen) if start_fen else chess.Board()
    parts = []
    for san_text in moves:
        move = board.parse_san(san_text)
        if board.turn == chess.WHITE:
            parts.append(f"{board.fullmove_number}.")
        parts.append(board.san(move))
        board.push(move)
    return " ".join(parts)


def normalize_pgn(pgn, start_fen=None):
    moves = tokenize_pgn(pgn)
    if not moves:
        return ""
    return canonical_pgn_from_moves(moves, start_fen=start_fen)


def pgn_preview(pgn, max_tokens=8):
    moves = tokenize_pgn(pgn)
    return " ".join(moves[:max_tokens])


def _collect_game_lines(node, board, path, include_variations, lines):
    variations = list(node.variations)
    if not variations:
        if path:
            lines.append(canonical_pgn_from_moves(path))
        return

    if not include_variations:
        variations = variations[:1]

    for child in variations:
        move = child.move
        san_text = board.san(move)
        board.push(move)
        path.append(san_text)
        _collect_game_lines(child, board, path, include_variations, lines)
        path.pop()
        board.pop()


def extract_pgn_lines(pgn_text, include_variations=False):
    parsed_lines = []
    pgn_io = io.StringIO(pgn_text or "")

    while True:
        game = chess.pgn.read_game(pgn_io)
        if game is None:
            break

        board = game.board()
        lines = []
        _collect_game_lines(game, board, [], include_variations, lines)
        parsed_lines.extend(lines)

    if not parsed_lines:
        normalized = normalize_pgn(pgn_text)
        if normalized:
            parsed_lines.append(normalized)

    unique_lines = []
    seen = set()
    for line in parsed_lines:
        if line and line not in seen:
            unique_lines.append(line)
            seen.add(line)
    return unique_lines


def comparable_moves(pgn):
    return tokenize_pgn(normalize_pgn(pgn) or pgn)


def trova_parent(linea: OpeningLine):
    """
    Trova la linea della stessa apertura (root) che è il prefisso più lungo
    del PGN della linea corrente.
    """
    if not linea.root or not linea.pgn:
        return None

    mosse = comparable_moves(linea.pgn)
    if len(mosse) < 2:
        return None

    candidates = []
    qs = OpeningLine.objects.filter(root=linea.root).exclude(id=linea.id)
    for altra in qs:
        seq = comparable_moves(altra.pgn)
        if len(seq) < len(mosse) and mosse[:len(seq)] == seq:
            candidates.append((len(seq), altra))

    if not candidates:
        return None

    candidates.sort(key=lambda item: item[0], reverse=True)
    return candidates[0][1]


def calculate_session_accuracy(correct_moves, wrong_attempts):
    total_answers = max(0, correct_moves) + max(0, wrong_attempts)
    if total_answers <= 0:
        return 0.0
    return round((max(0, correct_moves) / total_answers) * 100, 1)


def compute_next_review_at(difficulty, completions, session_accuracy, wrong_attempts):
    base_hours_by_difficulty = {
        "facile": 12,
        "media": 8,
        "difficile": 5,
    }

    base_hours = base_hours_by_difficulty.get(difficulty or "media", 8)
    growth = math.pow(1.7, max(0, completions - 1))
    confidence = 0.65 + (max(0.0, min(session_accuracy, 100.0)) / 100.0) * 0.9
    penalty = 1 + max(0, wrong_attempts) * 0.6

    hours = (base_hours * growth * confidence) / penalty
    hours = max(2.0, min(hours, 24 * 45))
    return timezone.now() + timedelta(hours=hours)


def update_review_fields(instance, wrong_attempts, correct_moves, total_moves):
    attempts_before = instance.review_attempts
    session_accuracy = calculate_session_accuracy(correct_moves, wrong_attempts)

    instance.review_attempts += 1
    instance.completamenti += 1
    instance.mistakes += max(0, wrong_attempts)
    instance.last_reviewed = timezone.now()
    instance.accuracy = (
        session_accuracy
        if attempts_before <= 0
        else round(((instance.accuracy * attempts_before) + session_accuracy) / (attempts_before + 1), 1)
    )
    instance.due_at = compute_next_review_at(
        getattr(instance, "difficolta", "media"),
        instance.completamenti,
        session_accuracy,
        wrong_attempts,
    )

    return {
        "session_accuracy": session_accuracy,
        "wrong_attempts": max(0, wrong_attempts),
        "correct_moves": max(0, correct_moves),
        "total_moves": max(0, total_moves),
        "due_at": instance.due_at,
    }


def is_due(reviewable, now=None):
    now = now or timezone.now()
    return reviewable.review_attempts == 0 or reviewable.due_at is None or reviewable.due_at <= now


def due_label(reviewable, now=None):
    now = now or timezone.now()
    if reviewable.review_attempts == 0:
        return "Nuova"
    if reviewable.due_at is None:
        return "Da pianificare"
    if reviewable.due_at <= now:
        delta = now - reviewable.due_at
        hours = max(1, int(delta.total_seconds() // 3600))
        return f"Scaduta da {hours}h"

    delta = reviewable.due_at - now
    hours = max(1, int(delta.total_seconds() // 3600))
    return f"Tra {hours}h"
