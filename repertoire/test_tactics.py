import json
import os
import tempfile
from datetime import timedelta
from io import StringIO
from unittest import mock

from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from . import tactics
from .models import Puzzle, PuzzleAttempt


def api_payload(puzzle_id="TEST1", last_move="g8f6", solution=("h5f7",)):
    return {
        "game": {"id": "abcd1234", "pgn": "e4 e5 Bc4 Nc6 Qh5 Nf6"},
        "puzzle": {
            "id": puzzle_id,
            "rating": 900,
            "solution": list(solution),
            "themes": ["mateIn1", "attackingF2F7", "opening", "oneMove"],
            "lastMove": last_move,
            "initialPly": 5,
        },
    }


def make_puzzle(lichess_id="P1", themes=("fork", "short"), rating=1500):
    # Il Nero ha appena giocato ...Nf6, il Bianco (giocatore) matta con Qxf7#
    return Puzzle.objects.create(
        lichess_id=lichess_id,
        fen="r1bqkbnr/pppp1ppp/2n5/4p2Q/2B1P3/8/PPPP1PPP/RNB1K1NR b KQkq - 3 3",
        moves="g8f6 h5f7",
        rating=rating,
        themes=tactics.pad_themes(themes),
    )


class PuzzleParsingTests(TestCase):
    def test_api_payload_becomes_fen_before_setup_move(self):
        fields = tactics.puzzle_fields_from_api(api_payload())
        self.assertEqual(fields["lichess_id"], "TEST1")
        self.assertEqual(fields["moves"], "g8f6 h5f7")
        self.assertTrue(fields["fen"].startswith("r1bqkbnr/pppp1ppp/2n5/4p2Q/2B1P3/8/PPPP1PPP/RNB1K1NR b"))
        self.assertIn(" attackingF2F7 ", fields["themes"])

    def test_inconsistent_payload_is_rejected(self):
        with self.assertRaises(tactics.LichessError):
            tactics.puzzle_fields_from_api(api_payload(last_move="g8h6"))
        with self.assertRaises(tactics.LichessError):
            tactics.puzzle_fields_from_api(api_payload(solution=("h5h8",)))

    def test_download_skips_duplicates(self):
        fetch = mock.Mock(return_value=api_payload())
        added = tactics.download_theme_puzzles("mateIn1", count=2, fetch=fetch)
        self.assertEqual(added, 1)
        self.assertEqual(Puzzle.objects.count(), 1)
        self.assertEqual(fetch.call_count, 6)

    def test_rate_limit_keeps_already_downloaded(self):
        fetch = mock.Mock(side_effect=[api_payload(), tactics.LichessRateLimited("stop")])
        self.assertEqual(tactics.download_theme_puzzles("mateIn1", count=5, fetch=fetch), 1)


class QuizAndScheduleTests(TestCase):
    def test_quiz_options_include_target_and_exclude_other_puzzle_themes(self):
        puzzle = make_puzzle(themes=("fork", "pin", "middlegame"))
        target, options = tactics.quiz_options(puzzle)
        self.assertEqual(target, "pin")  # "pin" viene prima di "fork" nel catalogo
        self.assertEqual(len(options), 4)
        self.assertEqual(len(set(options)), 4)
        self.assertIn("pin", options)
        self.assertNotIn("fork", options)

    def test_no_quiz_for_generic_puzzle(self):
        puzzle = make_puzzle(themes=("mateIn1", "short"))
        self.assertEqual(tactics.quiz_options(puzzle), (None, []))

    def test_review_schedule_until_mastered(self):
        puzzle = make_puzzle()
        now = timezone.now()
        tactics.apply_review_schedule(puzzle, False, now)
        self.assertEqual(puzzle.due_at, now + timedelta(days=1))
        for days in (3, 7, 21):
            tactics.apply_review_schedule(puzzle, True, now)
            self.assertEqual(puzzle.due_at, now + timedelta(days=days))
        tactics.apply_review_schedule(puzzle, True, now)
        self.assertIsNone(puzzle.due_at)

    def test_first_try_success_never_enters_review(self):
        puzzle = make_puzzle()
        tactics.apply_review_schedule(puzzle, True)
        self.assertIsNone(puzzle.due_at)


class TacticsApiTests(TestCase):
    def post(self, name, payload):
        return self.client.post(reverse(name), data=json.dumps(payload), content_type="application/json")

    def test_next_returns_unseen_puzzle_for_theme(self):
        make_puzzle("P1", themes=("fork",))
        make_puzzle("P2", themes=("pin",))
        data = self.client.get(reverse("tattica_api_next"), {"tema": "pin"}).json()
        self.assertEqual(data["puzzle"]["lichess_id"], "P2")
        self.assertEqual(data["puzzle"]["player_color"], "w")
        self.assertEqual(data["puzzle"]["moves"], ["g8f6", "h5f7"])

    def test_next_without_puzzles_returns_message(self):
        data = self.client.get(reverse("tattica_api_next")).json()
        self.assertIsNone(data["puzzle"])
        self.assertIn("scaricane", data["message"])

    def test_failed_attempt_goes_to_review_and_lowers_rating(self):
        puzzle = make_puzzle(rating=1500)
        resp = self.post("tattica_api_result", {
            "puzzle_id": puzzle.id, "success": False, "wrong_move": "Qxe5", "expected_move": "Qxf7#",
            "error_fen": puzzle.fen, "time_ms": 4000,
        })
        data = resp.json()
        self.assertTrue(data["ok"])
        self.assertLess(data["rating"], 1500)
        self.assertEqual([t["key"] for t in data["themes"]], ["fork"])
        puzzle.refresh_from_db()
        self.assertEqual(puzzle.fail_count, 1)
        self.assertIsNotNone(puzzle.due_at)

        # il ripasso non cambia il rating ma fa avanzare il ripasso dilazionato
        resp = self.post("tattica_api_result", {"puzzle_id": puzzle.id, "success": True})
        self.assertEqual(resp.json()["rating_delta"], 0)
        puzzle.refresh_from_db()
        self.assertEqual(puzzle.review_streak, 1)
        self.assertTrue(PuzzleAttempt.objects.filter(puzzle=puzzle, is_review=True, success=True).exists())

    def test_guess_is_checked_against_puzzle_themes(self):
        puzzle = make_puzzle(themes=("skewer", "endgame"))
        attempt_id = self.post("tattica_api_result", {"puzzle_id": puzzle.id, "success": True}).json()["attempt_id"]
        resp = self.post("tattica_api_guess", {"attempt_id": attempt_id, "guess": "pin", "target": "skewer"})
        self.assertFalse(resp.json()["correct"])
        stats, confusioni = tactics.theme_stats()
        self.assertEqual(stats["skewer"]["quiz_tot"], 1)
        self.assertEqual(confusioni[0]["tema"], "Infilata")
        self.assertEqual(confusioni[0]["scambiato_con"], "Inchiodatura")

    def test_download_endpoint_reports_rate_limit(self):
        with mock.patch.object(tactics, "download_theme_puzzles", side_effect=tactics.LichessRateLimited("piano")):
            resp = self.post("tattica_scarica", {"tema": "fork"})
        self.assertEqual(resp.status_code, 429)
        with mock.patch.object(tactics, "download_theme_puzzles", return_value=3):
            resp = self.post("tattica_scarica", {"tema": "fork", "count": 3})
        self.assertEqual(resp.json()["added"], 3)


class TacticsPagesTests(TestCase):
    def test_dashboard_without_puzzles_offers_download(self):
        resp = self.client.get(reverse("tattica"))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "scarica i primi puzzle")
        self.assertContains(resp, "Infilata")
        self.assertContains(resp, "Come riconoscerla")

    def test_dashboard_shows_weak_themes(self):
        puzzle = make_puzzle(themes=("skewer",))
        for _ in range(3):
            PuzzleAttempt.objects.create(puzzle=puzzle, success=False, wrong_move="Kd2", expected_move="Bb5+")
        resp = self.client.get(reverse("tattica"))
        self.assertContains(resp, "Temi più deboli")
        self.assertContains(resp, "Kd2 invece di Bb5+")

    def test_trainer_page_renders(self):
        resp = self.client.get(reverse("tattica_allena"), {"tema": "fork"})
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Che tema era?")

    def test_error_page_lists_failed_puzzles(self):
        puzzle = make_puzzle(themes=("pin",))
        puzzle.fail_count = 2
        puzzle.last_attempt_at = timezone.now()
        puzzle.save()
        PuzzleAttempt.objects.create(puzzle=puzzle, success=False, wrong_move="Nc3", expected_move="Qxf7#")
        resp = self.client.get(reverse("errori"), {"kind": "tattica"})
        self.assertContains(resp, "Inchiodatura")
        self.assertContains(resp, f"?puzzle={puzzle.id}")


class ImportCommandTests(TestCase):
    def test_csv_import_respects_filters_and_cap(self):
        header = "PuzzleId,FEN,Moves,Rating,RatingDeviation,Popularity,NbPlays,Themes,GameUrl,OpeningTags"
        fen = "8/8/8/8/8/8/8/K6k w - - 0 1"
        rows = [
            header,
            f"a1,{fen},a1a2 h1h2,1400,80,95,1000,fork short,https://lichess.org/x,",
            f"a2,{fen},a1a2 h1h2,1450,80,95,1000,fork long,https://lichess.org/y,",  # tetto fork raggiunto
            f"a3,{fen},a1a2 h1h2,2600,80,95,1000,pin,https://lichess.org/z,",  # rating troppo alto
            f"a4,{fen},a1a2 h1h2,1500,80,10,1000,pin,https://lichess.org/w,",  # poco popolare
            f"a5,{fen},a1a2 h1h2,1500,80,95,1000,pin,https://lichess.org/v,",
        ]
        fd, path = tempfile.mkstemp(suffix=".csv")
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write("\n".join(rows) + "\n")
        try:
            call_command("import_puzzles", csv=path, themes="fork,pin", per_theme=1, max_rating=2000, stdout=StringIO())
        finally:
            os.remove(path)
        self.assertEqual(sorted(Puzzle.objects.values_list("lichess_id", flat=True)), ["a1", "a5"])
