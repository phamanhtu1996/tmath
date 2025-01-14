# Generated by Django 2.2.24 on 2022-03-24 03:51

import datetime
from django.db import migrations, models



class Migration(migrations.Migration):

    dependencies = [
        ('judge', '0137_auto_20220228_1508'),
    ]

    operations = [
        migrations.AddField(
            model_name='submissionsource',
            name='file',
            field=models.TextField(blank=True, max_length=65536, verbose_name='origin source'),
        ),
        migrations.AlterField(
            model_name='profile',
            name='last_change_name',
            field=models.DateTimeField(default=datetime.datetime(2022, 2, 22, 3, 51, 57, 317042, tzinfo=datetime.timezone.utc), verbose_name='last change fullname'),
        ),
    ]
