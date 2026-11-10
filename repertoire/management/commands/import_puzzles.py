"""Importa puzzle tattici da Lichess.

Esempi:
  # dall'API (pochi puzzle per tema, nessun file da scaricare)
  python manage.py import_puzzles --api --per-theme 20 --themes fork,skewer,pin

  # dal database completo (https://database.lichess.org/#puzzles)
  python manage.py import_puzzles --csv lichess_db_puzzle.csv.zst --per-theme 300 --min-rating 1200 --max-rating 2000
"""

from django.core.management.base import BaseCommand, CommandError

from repertoire import tactics
from repertoire.models import Puzzle


class Command(BaseCommand):
    help = "Importa puzzle tattici da Lichess (API o CSV del database puzzle)."

    def add_arguments(self, parser):
        source = parser.add_mutually_exclusive_group(required=True)
        source.add_argument("--api", action="store_true", help="Scarica dall'API Lichess.")
        source.add_argument("--csv", help="Percorso di lichess_db_puzzle.csv (o .csv.zst).")
        parser.add_argument("--themes", default="", help="Temi separati da virgola (default: tutti quelli del catalogo).")
        parser.add_argument("--per-theme", type=int, default=20, help="Puzzle per tema.")
        parser.add_argument("--difficulty", choices=tactics.DIFFICULTIES, default="normal", help="Solo per --api.")
        parser.add_argument("--min-rating", type=int, default=0, help="Solo per --csv.")
        parser.add_argument("--max-rating", type=int, default=4000, help="Solo per --csv.")
        parser.add_argument("--min-popularity", type=int, default=80, help="Solo per --csv (scarta puzzle poco apprezzati).")
        parser.add_argument("--min-plays", type=int, default=200, help="Solo per --csv.")

    def handle(self, *args, **opts):
        themes = [t.strip() for t in opts["themes"].split(",") if t.strip()] or list(tactics.THEMES)
        unknown = [t for t in themes if t not in tactics.THEMES]
        if unknown:
            raise CommandError(f"Temi sconosciuti: {', '.join(unknown)}. Validi: {', '.join(tactics.THEMES)}")

        if opts["api"]:
            self._from_api(themes, opts)
        else:
            self._from_csv(themes, opts)

    def _from_api(self, themes, opts):
        total = 0
        for theme in themes:
            try:
                added = tactics.download_theme_puzzles(theme, opts["per_theme"], opts["difficulty"])
            except tactics.LichessError as exc:
                raise CommandError(f"{theme}: {exc} (importati finora: {total})") from exc
            total += added
            self.stdout.write(f"{tactics.THEMES[theme]['nome']}: +{added}")
        self.stdout.write(self.style.SUCCESS(f"Importati {total} puzzle."))

    def _from_csv(self, themes, opts):
        wanted = set(themes)
        counts = {t: Puzzle.objects.filter(themes__contains=tactics.theme_filter_value(t)).count() for t in themes}
        cap = opts["per_theme"]
        existing = set(Puzzle.objects.values_list("lichess_id", flat=True))
        batch, total, scanned = [], 0, 0

        try:
            rows = tactics.iter_csv_rows(opts["csv"])
            for row in rows:
                scanned += 1
                if all(counts[t] >= cap for t in themes):
                    break
                try:
                    rating = int(row.get("Rating") or 0)
                    popularity = int(row.get("Popularity") or 0)
                    plays = int(row.get("NbPlays") or 0)
                except ValueError:
                    continue
                if not (opts["min_rating"] <= rating <= opts["max_rating"]):
                    continue
                if popularity < opts["min_popularity"] or plays < opts["min_plays"]:
                    continue
                row_themes = set((row.get("Themes") or "").split()) & wanted
                if not any(counts[t] < cap for t in row_themes):
                    continue
                if row["PuzzleId"] in existing:
                    continue
                batch.append(Puzzle(**tactics.puzzle_fields_from_csv(row)))
                existing.add(row["PuzzleId"])
                for t in row_themes:
                    counts[t] += 1
                if len(batch) >= 500:
                    Puzzle.objects.bulk_create(batch, ignore_conflicts=True)
                    total += len(batch)
                    batch = []
                    self.stdout.write(f"... {total} importati ({scanned} righe lette)")
        except (FileNotFoundError, tactics.LichessError) as exc:
            raise CommandError(str(exc)) from exc

        if batch:
            Puzzle.objects.bulk_create(batch, ignore_conflicts=True)
            total += len(batch)
        self.stdout.write(self.style.SUCCESS(f"Importati {total} puzzle ({scanned} righe lette)."))
