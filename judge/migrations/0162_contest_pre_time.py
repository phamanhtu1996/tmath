# Generated by Django 3.2.16 on 2023-02-22 10:35

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('judge', '0161_problem_public_description'),
    ]

    operations = [
        migrations.AddField(
            model_name='contest',
            name='pre_time',
            field=models.DateTimeField(blank=True, null=True, verbose_name='Pre-time'),
        ),
    ]
