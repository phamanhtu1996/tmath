# Generated by Django 2.2.7 on 2020-05-27 05:50

import django.core.validators
import django.db.models.deletion
from django.db import migrations, models

import judge.models.profile


class Migration(migrations.Migration):

    dependencies = [
        ('judge', '0108_bleach_problems'),
    ]

    operations = [
        migrations.AddField(
            model_name='profile',
            name='scratch_codes',
            field=models.CharField(blank=True, help_text='JSON array of 16 character base32-encoded codes for scratch codes', max_length=255, null=True, validators=[django.core.validators.RegexValidator(r'^(\[\])?$|^\[("[A-Z0-9]{16}", *)*"[A-Z0-9]{16}"\]$', 'Scratch codes must be empty or a JSON array of 16-character base32 codes')], verbose_name='scratch codes'),
        ),
    ]
