# Generated by Django 3.2.16 on 2022-11-09 04:47

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('judge', '0158_problemdata_grader_args'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='problem',
            options={'ordering': ['-pk'], 'permissions': (('see_private_problem', 'See hidden problems'), ('edit_own_problem', 'Edit own problems'), ('edit_all_problem', 'Edit all problems'), ('edit_public_problem', 'Edit all public problems'), ('problem_full_markup', 'Edit problems with full markup'), ('clone_problem', 'Clone problem'), ('change_public_visibility', 'Change is_public field'), ('change_manually_managed', 'Change is_manually_managed field'), ('see_organization_problem', 'See organization-private problems')), 'verbose_name': 'problem', 'verbose_name_plural': 'problems'},
        ),
    ]
