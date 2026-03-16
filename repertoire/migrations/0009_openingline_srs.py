from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('repertoire', '0008_openingline_completamenti'),
    ]

    operations = [
        migrations.AddField(
            model_name='openingline',
            name='srs_interval',
            field=models.IntegerField(default=1),
        ),
        migrations.AddField(
            model_name='openingline',
            name='srs_easiness',
            field=models.FloatField(default=2.5),
        ),
        migrations.AddField(
            model_name='openingline',
            name='srs_repetitions',
            field=models.IntegerField(default=0),
        ),
        migrations.AddField(
            model_name='openingline',
            name='srs_due_date',
            field=models.DateField(null=True, blank=True),
        ),
    ]
