# Generated by Django 4.1.9 on 2023-05-21 01:59

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('judge', '0169_alter_contest_name'),
    ]

    operations = [
        migrations.AlterField(
            model_name='contest',
            name='authors',
            field=models.ManyToManyField(help_text='These users will be able to edit the contest.', related_name='authors+', to='judge.profile'),
        ),
        migrations.AlterField(
            model_name='contest',
            name='curators',
            field=models.ManyToManyField(blank=True, help_text='These users will be able to edit the contest, but will not be listed as authors.', related_name='curators+', to='judge.profile'),
        ),
        migrations.AlterField(
            model_name='contest',
            name='private_contestants',
            field=models.ManyToManyField(blank=True, help_text='If private, only these users may see the contest', related_name='private_contestants+', to='judge.profile', verbose_name='private contestants'),
        ),
        migrations.AlterField(
            model_name='contest',
            name='rate_exclude',
            field=models.ManyToManyField(blank=True, related_name='rate_exclude+', to='judge.profile', verbose_name='exclude from ratings'),
        ),
        migrations.AlterField(
            model_name='contest',
            name='testers',
            field=models.ManyToManyField(blank=True, help_text='These users will be able to view the contest, but not edit it.', related_name='testers+', to='judge.profile'),
        ),
    ]
