"""Logica della sezione Tattica: catalogo temi, import puzzle Lichess, statistiche e selezione."""

import csv
import io
import json
import random
from collections import defaultdict
from datetime import timedelta
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

import chess
from django.db.models import F
from django.db.models.functions import Abs
from django.utils import timezone

from .models import Puzzle, PuzzleAttempt
from .utils import tokenize_pgn


# ---------------------------------------------------------------------------
# Catalogo temi (chiavi = temi Lichess). L'ordine conta: i primi sono i più
# "specifici" e vengono scelti come risposta giusta nel quiz di riconoscimento.
# ---------------------------------------------------------------------------

GROUP_MOTIVI = "Motivi tattici"
GROUP_MATTI = "Schemi di matto"
GROUP_ALTRO = "Altro"

THEMES = {
    "skewer": {
        "nome": "Infilata",
        "gruppo": GROUP_MOTIVI,
        "descrizione": "Attacchi un pezzo di valore che sta davanti a un altro sulla stessa linea: "
        "quando si sposta, catturi quello che c'era dietro. È un'inchiodatura al contrario.",
        "segnali": [
            "Re o donna avversari allineati con un altro pezzo su colonna, traversa o diagonale",
            "Puoi dare scacco lungo quella linea con alfiere, torre o donna",
            "Nei finali: re e torre avversari sulla stessa traversa o colonna",
        ],
        "quiz": True,
    },
    "pin": {
        "nome": "Inchiodatura",
        "gruppo": GROUP_MOTIVI,
        "descrizione": "Un pezzo non può (o non dovrebbe) muoversi perché scoprirebbe il re o un pezzo "
        "più prezioso dietro di lui. Il pezzo inchiodato è un bersaglio: attaccalo ancora.",
        "segnali": [
            "Un pezzo avversario si trova tra il tuo pezzo a lungo raggio e il suo re o la sua donna",
            "Il pezzo inchiodato è anche l'unico difensore di qualcosa",
            "Puoi attaccarlo con un pedone o con un pezzo di valore minore",
        ],
        "quiz": True,
    },
    "fork": {
        "nome": "Forchetta (doppio attacco)",
        "gruppo": GROUP_MOTIVI,
        "descrizione": "Un solo pezzo attacca due o più bersagli nello stesso momento: l'avversario ne "
        "può salvare solo uno.",
        "segnali": [
            "Re e donna (o due torri) a distanza di salto di cavallo da una casa che puoi raggiungere",
            "Pezzi avversari indifesi o protetti male",
            "Uno scacco che attacca anche un altro pezzo",
        ],
        "quiz": True,
    },
    "discoveredAttack": {
        "nome": "Attacco di scoperta",
        "gruppo": GROUP_MOTIVI,
        "descrizione": "Sposti un pezzo che copriva la linea di un tuo pezzo a lungo raggio: si "
        "aprono due minacce, quella del pezzo mosso e quella del pezzo scoperto.",
        "segnali": [
            "Un tuo alfiere, torre o donna \"dietro\" un tuo pezzo, puntato verso re o donna avversaria",
            "Il pezzo davanti può muovere dando scacco o catturando qualcosa",
            "Se lo scacco viene dal pezzo scoperto è uno scacco di scoperta: fortissimo",
        ],
        "quiz": True,
    },
    "doubleCheck": {
        "nome": "Scacco doppio",
        "gruppo": GROUP_MOTIVI,
        "descrizione": "Due pezzi danno scacco contemporaneamente: l'unica difesa è muovere il re. "
        "Spesso porta al matto anche con pezzi in presa.",
        "segnali": [
            "Uno scacco di scoperta in cui anche il pezzo che si sposta dà scacco",
            "Il re avversario ha poche case di fuga",
        ],
        "quiz": True,
    },
    "deflection": {
        "nome": "Deviazione",
        "gruppo": GROUP_MOTIVI,
        "descrizione": "Costringi un difensore ad abbandonare il suo compito (difendere una casa o un "
        "pezzo), di solito con una cattura o uno scacco che deve accettare.",
        "segnali": [
            "Un pezzo avversario difende due cose insieme (è sovraccarico)",
            "Se quel difensore sparisse, avresti matto o vinceresti materiale",
        ],
        "quiz": True,
    },
    "attraction": {
        "nome": "Attrazione (adescamento)",
        "gruppo": GROUP_MOTIVI,
        "descrizione": "Sacrifichi per attirare il re o un pezzo avversario su una casa dove subirà "
        "una forchetta, un'infilata o un matto.",
        "segnali": [
            "Esiste una casa \"perfetta\" per una forchetta o un matto, ma il pezzo avversario non c'è ancora",
            "Un sacrificio di scacco che il re è costretto a prendere",
        ],
        "quiz": True,
    },
    "capturingDefender": {
        "nome": "Eliminazione del difensore",
        "gruppo": GROUP_MOTIVI,
        "descrizione": "Catturi (anche sacrificando) il pezzo che difende un altro pezzo o una casa "
        "chiave, poi incassi il bersaglio rimasto senza protezione.",
        "segnali": [
            "Conta attaccanti e difensori: se ne togli uno, il conto cambia?",
            "Un cavallo che difende la casa di matto, ad esempio f6/f3 o h7/h2",
        ],
        "quiz": True,
    },
    "clearance": {
        "nome": "Sgombero",
        "gruppo": GROUP_MOTIVI,
        "descrizione": "Liberi una casa, una colonna o una diagonale muovendo un tuo pezzo (spesso con "
        "tempo), così un altro tuo pezzo può usarla.",
        "segnali": [
            "Un tuo pezzo occupa proprio la casa di cui avresti bisogno per un altro pezzo",
            "Una tua linea d'attacco è bloccata da un tuo pezzo",
        ],
        "quiz": True,
    },
    "interference": {
        "nome": "Interferenza",
        "gruppo": GROUP_MOTIVI,
        "descrizione": "Metti un pezzo tra un pezzo avversario e la casa o il pezzo che deve "
        "difendere, interrompendo il collegamento.",
        "segnali": [
            "Due pezzi avversari si difendono a vicenda lungo una linea",
            "Una casa d'incrocio dove puoi piazzare un pezzo e tagliare la difesa",
        ],
        "quiz": True,
    },
    "xRayAttack": {
        "nome": "Attacco ai raggi X",
        "gruppo": GROUP_MOTIVI,
        "descrizione": "Un pezzo attacca o difende \"attraverso\" un altro pezzo sulla stessa linea: "
        "dopo una cattura, la linea si apre e il pezzo dietro entra in gioco.",
        "segnali": [
            "Due pezzi pesanti allineati, i tuoi o quelli dell'avversario",
            "Una serie di catture sulla stessa casa: conta anche i pezzi dietro",
        ],
        "quiz": True,
    },
    "intermezzo": {
        "nome": "Mossa intermedia",
        "gruppo": GROUP_MOTIVI,
        "descrizione": "Invece della mossa \"ovvia\" (spesso una ricattura) giochi prima una minaccia "
        "più forte, come uno scacco o un attacco alla donna, e solo dopo ricatturi.",
        "segnali": [
            "Stai per ricatturare in automatico: fermati e cerca scacchi o catture",
            "L'avversario ha appena lasciato qualcosa di attaccabile",
        ],
        "quiz": True,
    },
    "trappedPiece": {
        "nome": "Pezzo intrappolato",
        "gruppo": GROUP_MOTIVI,
        "descrizione": "Un pezzo avversario non ha case sicure: lo attacchi e non può scappare.",
        "segnali": [
            "Un alfiere o un cavallo sul bordo o in fondo al campo avversario",
            "Una donna che ha mangiato un pedone \"avvelenato\"",
        ],
        "quiz": True,
    },
    "hangingPiece": {
        "nome": "Pezzo indifeso",
        "gruppo": GROUP_MOTIVI,
        "descrizione": "Un pezzo è in presa o difeso troppo poco: va semplicemente catturato. Sembra "
        "banale, ma è l'errore che decide più partite.",
        "segnali": [
            "Dopo ogni mossa avversaria chiediti: cosa è rimasto senza difesa?",
            "Conta attaccanti e difensori di ogni pezzo",
        ],
        "quiz": True,
    },
    "quietMove": {
        "nome": "Mossa tranquilla",
        "gruppo": GROUP_MOTIVI,
        "descrizione": "La mossa vincente non è uno scacco né una cattura: prepara una minaccia "
        "imparabile o toglie una difesa.",
        "segnali": [
            "Gli scacchi e le catture non funzionano, ma la posizione \"puzza\" di tattica",
            "L'avversario non ha mosse utili: aumenta la pressione con calma",
        ],
        "quiz": True,
    },
    "attackingF2F7": {
        "nome": "Attacco su f2/f7",
        "gruppo": GROUP_MOTIVI,
        "descrizione": "f2 e f7 sono difese solo dal re all'inizio della partita: bersaglio classico "
        "di alfiere, cavallo e donna.",
        "segnali": [
            "Alfiere su c4/c5 e cavallo che può saltare su g5/g4",
            "Il re non ha ancora arroccato",
        ],
        "quiz": True,
    },
    "backRankMate": {
        "nome": "Matto sulla traversa",
        "gruppo": GROUP_MATTI,
        "descrizione": "Il re è chiuso dai propri pedoni sull'ultima traversa: una torre o la donna "
        "danno matto lungo la riga.",
        "segnali": [
            "Re arroccato senza \"finestra\" (nessun pedone mosso davanti)",
            "L'ultima traversa è difesa da un solo pezzo: deviarlo!",
        ],
        "quiz": True,
    },
    "smotheredMate": {
        "nome": "Matto affogato",
        "gruppo": GROUP_MATTI,
        "descrizione": "Il re è circondato dai propri pezzi e un cavallo gli dà matto. Spesso preceduto "
        "da un sacrificio di donna per chiudere l'ultima casa.",
        "segnali": [
            "Re in angolo (g8/h8) con torre e pedoni attorno",
            "Un cavallo che arriva in f7 o g6",
        ],
        "quiz": True,
    },
    "arabianMate": {
        "nome": "Matto arabo",
        "gruppo": GROUP_MATTI,
        "descrizione": "Torre e cavallo collaborano: la torre dà matto accanto al re in angolo, il "
        "cavallo la protegge e copre l'ultima casa di fuga.",
        "segnali": ["Re nell'angolo", "Il tuo cavallo controlla la casa vicina in diagonale al re"],
        "quiz": True,
    },
    "anastasiaMate": {
        "nome": "Matto di Anastasia",
        "gruppo": GROUP_MATTI,
        "descrizione": "Un cavallo chiude il re sul bordo e una torre o la donna danno matto lungo la colonna.",
        "segnali": ["Re su h7/h8 con un pedone in g7", "Cavallo in e7 e colonna h apribile"],
        "quiz": True,
    },
    "hookMate": {
        "nome": "Matto a uncino",
        "gruppo": GROUP_MATTI,
        "descrizione": "Torre protetta da un cavallo, a sua volta protetto da un pedone, danno matto al re vicino.",
        "segnali": ["Catena pedone-cavallo-torre vicino al re avversario"],
        "quiz": True,
    },
    "bodenMate": {
        "nome": "Matto di Boden",
        "gruppo": GROUP_MATTI,
        "descrizione": "Due alfieri su diagonali incrociate danno matto a un re (spesso arroccato lungo) "
        "bloccato dai suoi pezzi.",
        "segnali": ["Re arroccato lungo con pezzi su c7/d7", "Due alfieri che puntano verso a6 e f4"],
        "quiz": True,
    },
    "doubleBishopMate": {
        "nome": "Matto dei due alfieri",
        "gruppo": GROUP_MATTI,
        "descrizione": "Due alfieri su diagonali vicine danno matto al re che non ha case libere.",
        "segnali": ["Re senza case di fuga e due alfieri che controllano diagonali adiacenti"],
        "quiz": True,
    },
    "dovetailMate": {
        "nome": "Matto a coda di rondine",
        "gruppo": GROUP_MATTI,
        "descrizione": "La donna dà matto accanto al re in diagonale; le due case di fuga dietro il re "
        "sono occupate dai suoi pezzi.",
        "segnali": ["Pezzi avversari diagonalmente dietro al re", "La donna può arrivare a contatto protetta"],
        "quiz": True,
    },
    "mateIn1": {"nome": "Matto in 1", "gruppo": GROUP_ALTRO, "descrizione": "Trova lo scacco matto immediato.",
                "segnali": ["Controlla tutti gli scacchi, uno per uno"], "quiz": False},
    "mateIn2": {"nome": "Matto in 2", "gruppo": GROUP_ALTRO, "descrizione": "Matto forzato in due mosse.",
                "segnali": ["Scacchi, catture, minacce: in quest'ordine"], "quiz": False},
    "mateIn3": {"nome": "Matto in 3", "gruppo": GROUP_ALTRO, "descrizione": "Matto forzato in tre mosse.",
                "segnali": ["Restringi le case del re prima di dare matto"], "quiz": False},
    "sacrifice": {"nome": "Sacrificio", "gruppo": GROUP_ALTRO,
                  "descrizione": "Cedi materiale per ottenere qualcosa di più: matto, materiale o attacco.",
                  "segnali": ["Il re avversario è esposto o i suoi pezzi sono scoordinati"], "quiz": False},
    "exposedKing": {"nome": "Re esposto", "gruppo": GROUP_ALTRO,
                    "descrizione": "Il re avversario ha perso la protezione dei pedoni: attaccalo con scacchi.",
                    "segnali": ["Pedoni dell'arrocco avanzati o mancanti"], "quiz": False},
    "advancedPawn": {"nome": "Pedone avanzato", "gruppo": GROUP_ALTRO,
                     "descrizione": "Un pedone vicino alla promozione cambia tutti i calcoli.",
                     "segnali": ["Pedone in settima: cerca deviazioni dei pezzi che lo bloccano"], "quiz": False},
    "defensiveMove": {"nome": "Mossa difensiva", "gruppo": GROUP_ALTRO,
                      "descrizione": "L'unica mossa che salva la posizione o evita di perdere materiale.",
                      "segnali": ["Prima di attaccare, guarda cosa minaccia l'avversario"], "quiz": False},
}

# Temi proposti per il pacchetto iniziale (i più utili a livello club)
STARTER_THEMES = [
    "fork", "pin", "skewer", "discoveredAttack", "hangingPiece", "deflection",
    "capturingDefender", "backRankMate", "attraction", "intermezzo", "trappedPiece", "mateIn2",
]

DIFFICULTIES = ["easiest", "easier", "normal", "harder", "hardest"]
REVIEW_INTERVALS_DAYS = [3, 7, 21]
START_RATING = 1500


def theme_keys(puzzle_or_str):
    raw = puzzle_or_str.themes if hasattr(puzzle_or_str, "themes") else puzzle_or_str
    return [t for t in (raw or "").split() if t]


def known_theme_keys(puzzle):
    keys = set(theme_keys(puzzle))
    return [k for k in THEMES if k in keys]


def pad_themes(keys):
    return " " + " ".join(k for k in keys if k) + " "


def theme_filter_value(key):
    return f" {key} "


def theme_payload(key):
    info = THEMES.get(key)
    if not info:
        return None
    return {
        "key": key,
        "nome": info["nome"],
        "gruppo": info["gruppo"],
        "descrizione": info["descrizione"],
        "segnali": info["segnali"],
    }


# ---------------------------------------------------------------------------
# Import puzzle
# ---------------------------------------------------------------------------


class LichessError(Exception):
    pass


class LichessRateLimited(LichessError):
    pass


def puzzle_fields_from_api(data):
    """Converte la risposta di /api/puzzle/next nel formato del DB (stile CSV Lichess).

    fen = posizione PRIMA della mossa avversaria; moves = [mossa avversaria] + soluzione (UCI).
    """
    try:
        game = data["game"]
        puzzle = data["puzzle"]
        san_moves = tokenize_pgn(game["pgn"])
        solution = list(puzzle["solution"])
    except (KeyError, TypeError) as exc:
        raise LichessError(f"Risposta Lichess inattesa: {exc}") from exc

    if not san_moves or not solution:
        raise LichessError("Puzzle senza mosse.")

    board = chess.Board()
    try:
        for san in san_moves[:-1]:
            board.push_san(san)
        fen_before = board.fen()
        setup = board.parse_san(san_moves[-1])
        board.push(setup)
        for uci in solution:
            move = chess.Move.from_uci(uci)
            if move not in board.legal_moves:
                raise ValueError(uci)
            board.push(move)
    except ValueError as exc:
        raise LichessError(f"Puzzle {puzzle.get('id')} non valido: {exc}") from exc

    last_move = puzzle.get("lastMove")
    if last_move and last_move != setup.uci():
        raise LichessError(f"Puzzle {puzzle.get('id')}: mossa iniziale incoerente.")

    return {
        "lichess_id": str(puzzle["id"]),
        "fen": fen_before,
        "moves": " ".join([setup.uci()] + solution),
        "rating": int(puzzle.get("rating") or START_RATING),
        "themes": pad_themes(puzzle.get("themes") or []),
        "game_url": f"https://lichess.org/{game.get('id', '')}" if game.get("id") else "",
        "source": "lichess-api",
    }


def fetch_lichess_puzzle(theme, difficulty="normal", timeout=15):
    params = {"angle": theme}
    if difficulty in DIFFICULTIES:
        params["difficulty"] = difficulty
    req = Request(
        "https://lichess.org/api/puzzle/next?" + urlencode(params),
        headers={"Accept": "application/json", "User-Agent": "ChessRepertoire/1.0 (personal trainer)"},
    )
    try:
        with urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except HTTPError as exc:
        if exc.code == 429:
            raise LichessRateLimited("Lichess sta limitando le richieste: aspetta un minuto e riprova.") from exc
        raise LichessError(f"Lichess ha risposto con errore {exc.code}.") from exc
    except (URLError, TimeoutError, OSError) as exc:
        raise LichessError(f"Impossibile contattare Lichess: {exc}") from exc


def download_theme_puzzles(theme, count=10, difficulty="normal", fetch=fetch_lichess_puzzle):
    """Scarica `count` puzzle nuovi per un tema. Restituisce il numero di puzzle aggiunti."""
    added = 0
    misses = 0
    max_requests = count * 3
    for _ in range(max_requests):
        if added >= count:
            break
        try:
            data = fetch(theme, difficulty)
        except LichessRateLimited:
            if added:
                break  # teniamo quelli già salvati
            raise
        try:
            fields = puzzle_fields_from_api(data)
        except LichessError:
            misses += 1
            continue
        _, created = Puzzle.objects.get_or_create(lichess_id=fields.pop("lichess_id"), defaults=fields)
        if created:
            added += 1
        else:
            misses += 1
    return added


def iter_csv_rows(path):
    """Legge il CSV Lichess (anche .zst se è installato `zstandard`)."""
    if str(path).endswith(".zst"):
        try:
            import zstandard
        except ImportError as exc:
            raise LichessError(
                "Per leggere il .zst installa `pip install zstandard` oppure decomprimi il file."
            ) from exc
        fh = open(path, "rb")
        reader = zstandard.ZstdDecompressor().stream_reader(fh)
        text = io.TextIOWrapper(reader, encoding="utf-8")
    else:
        fh = None
        text = open(path, encoding="utf-8", newline="")
    try:
        yield from csv.DictReader(text)
    finally:
        text.close()
        if fh:
            fh.close()


def puzzle_fields_from_csv(row):
    themes = (row.get("Themes") or "").split()
    return {
        "lichess_id": row["PuzzleId"],
        "fen": row["FEN"],
        "moves": row["Moves"],
        "rating": int(row.get("Rating") or START_RATING),
        "themes": pad_themes(themes),
        "game_url": row.get("GameUrl") or "",
        "opening_tags": (row.get("OpeningTags") or "")[:200],
        "source": "csv",
    }


# ---------------------------------------------------------------------------
# Rating e statistiche
# ---------------------------------------------------------------------------


def current_rating():
    last = (
        PuzzleAttempt.objects.filter(rating_after__isnull=False)
        .order_by("-created_at", "-id")
        .values_list("rating_after", flat=True)
        .first()
    )
    return last if last is not None else START_RATING


def updated_rating(user_rating, puzzle_rating, success, rated_count):
    k = 32 if rated_count < 30 else 16
    expected = 1 / (1 + 10 ** ((puzzle_rating - user_rating) / 400))
    return round(user_rating + k * ((1 if success else 0) - expected))


def suggested_difficulty(rating):
    if rating < 1200:
        return "easiest"
    if rating < 1400:
        return "easier"
    if rating < 1650:
        return "normal"
    if rating < 1850:
        return "harder"
    return "hardest"


def theme_stats():
    """Statistiche per tema: disponibilità, risoluzione, riconoscimento, confusioni."""
    stats = {
        key: {
            "key": key,
            **theme_payload(key),
            "totale": 0,
            "nuovi": 0,
            "tentativi": 0,
            "risolti": 0,
            "falliti": 0,
            "falliti_recenti": 0,
            "quiz_tot": 0,
            "quiz_ok": 0,
            "da_ripassare": 0,
        }
        for key in THEMES
    }
    now = timezone.now()
    recent_cutoff = now - timedelta(days=30)

    for themes_str, attempts, due_at in Puzzle.objects.values_list("themes", "attempt_count", "due_at"):
        for key in theme_keys(themes_str):
            if key in stats:
                stats[key]["totale"] += 1
                if attempts == 0:
                    stats[key]["nuovi"] += 1
                if due_at and due_at <= now:
                    stats[key]["da_ripassare"] += 1

    confusioni = defaultdict(int)
    attempts = PuzzleAttempt.objects.select_related("puzzle").only(
        "success", "created_at", "guess_theme", "guess_target", "guess_correct", "puzzle", "puzzle__themes"
    )
    for att in attempts:
        for key in theme_keys(att.puzzle.themes):
            if key in stats:
                s = stats[key]
                s["tentativi"] += 1
                if att.success:
                    s["risolti"] += 1
                else:
                    s["falliti"] += 1
                    if att.created_at >= recent_cutoff:
                        s["falliti_recenti"] += 1
        if att.guess_target in stats and att.guess_correct is not None:
            stats[att.guess_target]["quiz_tot"] += 1
            if att.guess_correct:
                stats[att.guess_target]["quiz_ok"] += 1
            elif att.guess_theme in THEMES:
                confusioni[(att.guess_target, att.guess_theme)] += 1

    for s in stats.values():
        s["successo_pct"] = round(100 * s["risolti"] / s["tentativi"]) if s["tentativi"] else None
        s["quiz_pct"] = round(100 * s["quiz_ok"] / s["quiz_tot"]) if s["quiz_tot"] else None

    confusion_list = [
        {
            "tema": THEMES[target]["nome"],
            "scambiato_con": THEMES[guess]["nome"],
            "volte": n,
        }
        for (target, guess), n in sorted(confusioni.items(), key=lambda kv: -kv[1])
    ]
    return stats, confusion_list


def weak_themes(stats, min_attempts=3, limit=3):
    candidates = [s for s in stats.values() if s["tentativi"] >= min_attempts]
    candidates.sort(key=lambda s: (s["successo_pct"], -s["falliti"]))
    return [s for s in candidates if s["successo_pct"] < 85][:limit]


# ---------------------------------------------------------------------------
# Selezione puzzle e SRS
# ---------------------------------------------------------------------------


def due_puzzles(theme=None):
    qs = Puzzle.objects.filter(due_at__isnull=False, due_at__lte=timezone.now())
    if theme:
        qs = qs.filter(themes__contains=theme_filter_value(theme))
    return qs.order_by("due_at", "id")


def _closest_unseen(theme, rating, exclude_ids):
    qs = Puzzle.objects.filter(attempt_count=0).exclude(id__in=exclude_ids)
    if theme:
        qs = qs.filter(themes__contains=theme_filter_value(theme))
    pool = list(qs.annotate(dist=Abs(F("rating") - rating)).order_by("dist", "id")[:15])
    return random.choice(pool) if pool else None


def _weighted_weak_theme(stats):
    keys, weights = [], []
    for key, s in stats.items():
        if s["nuovi"] == 0:
            continue
        if s["tentativi"] >= 3:
            weight = (1 - s["risolti"] / s["tentativi"]) + 0.1
        else:
            weight = 0.5
        keys.append(key)
        weights.append(weight)
    if not keys:
        return None
    return random.choices(keys, weights=weights, k=1)[0]


def select_next_puzzle(mode="misto", theme=None, exclude_ids=()):
    """Restituisce (puzzle, mode_effettivo)."""
    exclude_ids = [i for i in exclude_ids if i]
    if mode == "ripasso":
        puzzle = due_puzzles(theme).exclude(id__in=exclude_ids).first()
        return puzzle, "ripasso"

    rating = current_rating()
    if mode == "deboli" and not theme:
        stats, _ = theme_stats()
        chosen = _weighted_weak_theme(stats)
        puzzle = _closest_unseen(chosen, rating, exclude_ids) if chosen else None
        if puzzle:
            return puzzle, "deboli"

    puzzle = _closest_unseen(theme, rating, exclude_ids)
    if puzzle:
        return puzzle, mode
    puzzle = due_puzzles(theme).exclude(id__in=exclude_ids).first()
    if puzzle:
        return puzzle, "ripasso"
    return None, mode


def quiz_options(puzzle, n_options=4):
    """Opzioni per il quiz "che tema è?": (target, [chiavi]) oppure (None, [])."""
    present = set(theme_keys(puzzle))
    candidates = [k for k in THEMES if THEMES[k]["quiz"] and k in present]
    if not candidates:
        return None, []
    target = candidates[0]
    group = THEMES[target]["gruppo"]
    same_group = [k for k, v in THEMES.items() if v["quiz"] and k not in present and v["gruppo"] == group]
    other = [k for k, v in THEMES.items() if v["quiz"] and k not in present and v["gruppo"] != group]
    random.shuffle(same_group)
    random.shuffle(other)
    distractors = (same_group + other)[: n_options - 1]
    options = [target] + distractors
    random.shuffle(options)
    return target, options


def apply_review_schedule(puzzle, success, now=None):
    now = now or timezone.now()
    if not success:
        puzzle.review_streak = 0
        puzzle.due_at = now + timedelta(days=1)
        return
    if puzzle.due_at is None:
        return  # risolto subito: nessun ripasso
    if puzzle.review_streak >= len(REVIEW_INTERVALS_DAYS):
        puzzle.due_at = None
        puzzle.review_streak = 0
        return
    puzzle.due_at = now + timedelta(days=REVIEW_INTERVALS_DAYS[puzzle.review_streak])
    puzzle.review_streak += 1


def serialize_puzzle(puzzle, mode):
    board = chess.Board(puzzle.fen)
    moves = puzzle.moves.split()
    target, options = quiz_options(puzzle)
    player_color = "b" if board.turn == chess.WHITE else "w"
    return {
        "id": puzzle.id,
        "lichess_id": puzzle.lichess_id,
        "fen": puzzle.fen,
        "moves": moves,
        "player_color": player_color,
        "rating": puzzle.rating,
        "mode": mode,
        "is_review": puzzle.attempt_count > 0,
        "quiz_target": target,
        "quiz_options": [{"key": k, "nome": THEMES[k]["nome"]} for k in options],
        "lichess_url": puzzle.lichess_url,
    }
