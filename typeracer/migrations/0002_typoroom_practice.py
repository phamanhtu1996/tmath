# Generated by Django 2.2.28 on 2022-09-02 03:14

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('typeracer', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='typoroom',
            name='practice',
            field=models.BooleanField(default=False, verbose_name='practice room'),
        ),
    ]