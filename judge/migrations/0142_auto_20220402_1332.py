# Generated by Django 2.2.24 on 2022-04-02 13:32

import datetime
from django.db import migrations, models



class Migration(migrations.Migration):

    dependencies = [
        ('judge', '0141_auto_20220402_0751'),
    ]

    operations = [
        migrations.AlterField(
            model_name='profile',
            name='last_change_name',
            field=models.DateTimeField(default=datetime.datetime(2022, 3, 3, 13, 32, 17, 395545, tzinfo=datetime.timezone.utc), verbose_name='last change fullname'),
        ),
    ]
