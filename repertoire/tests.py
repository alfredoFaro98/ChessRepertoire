import json

import chess
from django.test import TestCase
from django.urls import reverse

from .models import FinaleCapitolo, FinaleLine, OpeningLine, OpeningLineMistake, OpeningRoot


class TrainingEventTests(TestCase):
    def setUp(self):
        self.root = OpeningRoot.objects.create(nome="Spagnola", difesa=False)
        self.line = OpeningLine.objects.create(
            root=self.root,
            numero=1,
            titolo="Linea principale",
            pgn="1. e4 e5 2. Nf3 Nc6 3. Bb5 a6",
        )

    def test_opening_training_event_tracks_mistakes_and_review_data(self):
        url = reverse("line_training_event", args=[self.root.id, self.line.numero])

        response = self.client.post(
            url,
            data=json.dumps(
                {
                    "event": "mistake",
                    "wrong_move": "d4",
                    "expected_move": "e4",
                    "fen": chess.STARTING_FEN,
                    "move_index": 0,
                    "side_to_train": "w",
                }
            ),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(OpeningLineMistake.objects.count(), 1)
        self.assertEqual(OpeningLineMistake.objects.first().occurrence_count, 1)

        response = self.client.post(
            url,
            data=json.dumps(
                {
                    "event": "mistake",
                    "wrong_move": "d4",
                    "expected_move": "e4",
                    "fen": chess.STARTING_FEN,
                    "move_index": 0,
                    "side_to_train": "w",
                }
            ),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(OpeningLineMistake.objects.count(), 1)
        self.assertEqual(OpeningLineMistake.objects.first().occurrence_count, 2)

        response = self.client.post(
            url,
            data=json.dumps(
                {
                    "event": "completed",
                    "wrong_attempts": 1,
                    "correct_moves": 3,
                    "total_moves": 4,
                }
            ),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)

        self.line.refresh_from_db()
        self.assertEqual(self.line.completamenti, 1)
        self.assertEqual(self.line.review_attempts, 1)
        self.assertEqual(self.line.mistakes, 1)
        self.assertEqual(self.line.accuracy, 75.0)
        self.assertIsNotNone(self.line.last_reviewed)
        self.assertIsNotNone(self.line.due_at)


class ImportPgnTests(TestCase):
    def test_import_pgn_can_expand_variations(self):
        root = OpeningRoot.objects.create(nome="Siciliana", difesa=True)
        url = reverse("import_pgn")
        pgn = """
[Event "Variation test"]

1. e4 e5 (1... c5 2. Nf3) 2. Nf3 Nc6 *
"""

        response = self.client.post(
            url,
            data={
                "root_id": root.id,
                "pgn_text": pgn,
                "include_variations": "on",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(OpeningLine.objects.filter(root=root).count(), 2)
        self.assertContains(response, "Prime linee riconosciute")


class DashboardAndErrorPageTests(TestCase):
    def setUp(self):
        self.root = OpeningRoot.objects.create(nome="Caro-Kann", difesa=True)
        self.line = OpeningLine.objects.create(
            root=self.root,
            numero=1,
            titolo="Avanzata",
            pgn="1. e4 c6 2. d4 d5 3. e5",
            mistakes=4,
            review_attempts=1,
            accuracy=62.5,
        )

        self.capitolo = FinaleCapitolo.objects.create(nome="Re e pedone", ordine=1)
        self.finale = FinaleLine.objects.create(
            capitolo=self.capitolo,
            numero=1,
            titolo="Opposizione",
            fen_start="8/8/8/8/8/8/4k3/4K3 w - - 0 1",
            pgn="1. Kf2 Kd3 2. Kf3",
        )

    def test_ripasso_page_shows_due_sections(self):
        response = self.client.get(reverse("ripasso"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Coda Aperture Di Oggi")
        self.assertContains(response, self.root.nome)
        self.assertContains(response, self.capitolo.nome)

    def test_error_page_lists_logged_errors(self):
        OpeningLineMistake.objects.create(
            line=self.line,
            fen=chess.STARTING_FEN,
            wrong_move="Nc3",
            expected_move="e4",
            move_index=0,
            side_to_train="w",
            occurrence_count=3,
        )

        response = self.client.get(reverse("errori"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Archivio Errori")
        self.assertContains(response, "Nc3")
        self.assertContains(response, "e4")

    def test_ripasso_page_ignores_lines_without_number(self):
        FinaleLine.objects.create(
            capitolo=self.capitolo,
            numero=None,
            titolo="Legacy line",
            fen_start="8/8/8/8/8/8/4k3/4K3 w - - 0 1",
            pgn="1. Kf2",
        )

        response = self.client.get(reverse("ripasso"))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "Linea None")

    def test_error_page_ignores_errors_for_lines_without_number(self):
        broken_line = OpeningLine.objects.create(
            root=self.root,
            numero=None,
            titolo="Senza numero",
            pgn="1. e4 c6",
        )
        OpeningLineMistake.objects.create(
            line=broken_line,
            fen=chess.STARTING_FEN,
            wrong_move="d4",
            expected_move="e4",
            move_index=0,
            side_to_train="w",
            occurrence_count=1,
        )

        response = self.client.get(reverse("errori"))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "Linea None")


class TrainingAndGamesPageTests(TestCase):
    def setUp(self):
        self.root = OpeningRoot.objects.create(nome="Inglese", difesa=False)
        self.line = OpeningLine.objects.create(
            root=self.root,
            numero=1,
            titolo="Sistema base",
            pgn="1. c4 e5 2. Nc3 Nc6 3. g3",
        )

    def test_training_page_shows_completion_panel(self):
        response = self.client.get(reverse("line_training", args=[self.root.id, self.line.numero]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Completamento linea")
        self.assertContains(response, "Accuratezza")

    def test_minigiochi_page_is_available(self):
        response = self.client.get(reverse("minigiochi"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Minigiochi")
        self.assertContains(response, "Coordinate Rush")
