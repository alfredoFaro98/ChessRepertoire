import django.db.models.deletion
import django.utils.timezone
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("repertoire", "0016_add_preferito_to_openingroot"),
    ]

    operations = [
        migrations.CreateModel(
            name="Puzzle",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("lichess_id", models.CharField(max_length=16, unique=True)),
                ("fen", models.TextField()),
                ("moves", models.TextField()),
                ("rating", models.PositiveIntegerField(db_index=True, default=1500)),
                ("themes", models.CharField(blank=True, default="", max_length=400)),
                ("game_url", models.CharField(blank=True, default="", max_length=200)),
                ("opening_tags", models.CharField(blank=True, default="", max_length=200)),
                ("source", models.CharField(blank=True, default="", max_length=20)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("attempt_count", models.PositiveIntegerField(default=0)),
                ("success_count", models.PositiveIntegerField(default=0)),
                ("fail_count", models.PositiveIntegerField(default=0)),
                ("last_attempt_at", models.DateTimeField(blank=True, null=True)),
                ("review_streak", models.PositiveIntegerField(default=0)),
                ("due_at", models.DateTimeField(blank=True, db_index=True, null=True)),
            ],
            options={
                "ordering": ["rating", "id"],
            },
        ),
        migrations.CreateModel(
            name="PuzzleAttempt",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(db_index=True, default=django.utils.timezone.now)),
                ("success", models.BooleanField(default=False)),
                ("first_attempt", models.BooleanField(default=True)),
                ("is_review", models.BooleanField(default=False)),
                ("solution_shown", models.BooleanField(default=False)),
                ("hint_used", models.BooleanField(default=False)),
                ("time_ms", models.PositiveIntegerField(blank=True, null=True)),
                ("wrong_move", models.CharField(blank=True, default="", max_length=20)),
                ("expected_move", models.CharField(blank=True, default="", max_length=20)),
                ("error_fen", models.TextField(blank=True, default="")),
                ("move_index", models.PositiveIntegerField(default=0)),
                ("rating_after", models.IntegerField(blank=True, null=True)),
                ("guess_theme", models.CharField(blank=True, default="", max_length=40)),
                ("guess_target", models.CharField(blank=True, default="", max_length=40)),
                ("guess_correct", models.BooleanField(blank=True, null=True)),
                (
                    "puzzle",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="attempts",
                        to="repertoire.puzzle",
                    ),
                ),
            ],
            options={
                "ordering": ["-created_at", "-id"],
            },
        ),
    ]
