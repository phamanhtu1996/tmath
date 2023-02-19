# Generated by Django 2.2.24 on 2022-02-25 10:02

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('emath', '0003_navigation'),
    ]

    operations = [
        migrations.CreateModel(
            name='Answer',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('description', models.CharField(max_length=100, verbose_name='Content')),
                ('is_correct', models.BooleanField(default=False, verbose_name='Correct answer')),
                ('problem', models.ForeignKey(null=True, on_delete=django.db.models.deletion.CASCADE, related_name='answers', to='emath.Problem', verbose_name='problem')),
            ],
            options={
                'unique_together': {('problem', 'is_correct')},
            },
        ),
    ]