# Generated by Django 2.2.24 on 2022-03-29 13:05

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('emath', '0008_organization_rate'),
    ]

    operations = [
        migrations.AlterField(
            model_name='organization',
            name='rate',
            field=models.IntegerField(choices=[(1000, 'Newbie'), (1300, 'Amateur'), (1600, 'Expert'), (1900, 'Candidate Master'), (2400, 'Master'), (3000, 'Grandmaster'), (4000, 'Target')], default=1000, verbose_name='Rate of Organization'),
        ),
    ]