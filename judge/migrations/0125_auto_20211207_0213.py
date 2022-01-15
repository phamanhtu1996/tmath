# Generated by Django 2.2.24 on 2021-12-07 02:13

import django.core.validators
from django.db import migrations, models
import judge.models.problem_data
import judge.utils.problem_data


class Migration(migrations.Migration):

    dependencies = [
        ('judge', '0124_auto_20211205_0652'),
    ]

    operations = [
        migrations.AddField(
            model_name='problemdata',
            name='custom_checker',
            field=models.FileField(blank=True, null=True, storage=judge.utils.problem_data.ProblemDataStorage(), upload_to=judge.models.problem_data.problem_directory_file, validators=[django.core.validators.FileExtensionValidator(allowed_extensions=['py'])], verbose_name='custom checker file'),
        ),
        migrations.AddField(
            model_name='problemdata',
            name='custom_validator',
            field=models.FileField(blank=True, null=True, storage=judge.utils.problem_data.ProblemDataStorage(), upload_to=judge.models.problem_data.problem_directory_file, validators=[django.core.validators.FileExtensionValidator(allowed_extensions=['cpp'])], verbose_name='custom validator file'),
        ),
        migrations.AddField(
            model_name='profile',
            name='name',
            field=models.CharField(max_length=255, null=True),
        ),
        migrations.AlterField(
            model_name='problemdata',
            name='checker',
            field=models.CharField(blank=True, choices=[('standard', 'Standard'), ('floats', 'Floats'), ('floatsabs', 'Floats (absolute)'), ('floatsrel', 'Floats (relative)'), ('rstripped', 'Non-trailing spaces'), ('sorted', 'Unordered'), ('identical', 'Byte identical'), ('linecount', 'Line-by-line'), ('custom', 'Custom checker (PY)'), ('customval', 'Custom validator (CPP)')], max_length=10, verbose_name='checker'),
        ),
        migrations.AlterField(
            model_name='problemtestcase',
            name='checker',
            field=models.CharField(blank=True, choices=[('standard', 'Standard'), ('floats', 'Floats'), ('floatsabs', 'Floats (absolute)'), ('floatsrel', 'Floats (relative)'), ('rstripped', 'Non-trailing spaces'), ('sorted', 'Unordered'), ('identical', 'Byte identical'), ('linecount', 'Line-by-line'), ('custom', 'Custom checker (PY)'), ('customval', 'Custom validator (CPP)')], max_length=10, verbose_name='checker'),
        ),
    ]