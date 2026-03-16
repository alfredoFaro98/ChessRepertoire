from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('repertoire', '0009_openingline_srs'),
    ]

    operations = [
        migrations.AddField(
            model_name='openingline',
            name='difficolta',
            field=models.CharField(
                blank=True,
                choices=[('facile', 'Facile'), ('media', 'Media'), ('difficile', 'Difficile')],
                default='media',
                max_length=20,
            ),
        ),
        migrations.CreateModel(
            name='LineSession',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('timestamp', models.DateTimeField(auto_now_add=True)),
                ('quality', models.IntegerField()),
                ('time_seconds', models.IntegerField(blank=True, null=True)),
                ('line', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='sessioni',
                    to='repertoire.openingline',
                )),
            ],
            options={
                'ordering': ['-timestamp'],
            },
        ),
    ]
