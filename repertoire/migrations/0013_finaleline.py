from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('repertoire', '0012_remove_srs_fields'),
    ]

    operations = [
        migrations.CreateModel(
            name='FinaleLine',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('numero', models.PositiveIntegerField(blank=True, default=0, null=True)),
                ('titolo', models.CharField(blank=True, max_length=200, null=True)),
                ('fen_start', models.TextField()),
                ('pgn', models.TextField()),
                ('note', models.TextField(blank=True, null=True)),
                ('flipped', models.BooleanField(default=False)),
                ('completamenti', models.PositiveIntegerField(default=0)),
                ('difficolta', models.CharField(
                    blank=True,
                    choices=[('facile', 'Facile'), ('media', 'Media'), ('difficile', 'Difficile')],
                    default='media',
                    max_length=20,
                )),
                ('capitolo', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='linee',
                    to='repertoire.finalecapitolo',
                )),
                ('parent', models.ForeignKey(
                    blank=True,
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='varianti',
                    to='repertoire.finaleline',
                )),
            ],
            options={
                'ordering': ['numero'],
            },
        ),
    ]
