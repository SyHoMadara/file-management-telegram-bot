# Generated by Django 5.2.4 on 2025-07-21 01:38

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('account', '0005_user_first_name_user_last_name_user_telegram_id'),
    ]

    operations = [
        migrations.AddField(
            model_name='user',
            name='premium_request_date',
            field=models.DateTimeField(blank=True, help_text='The date when the user requested premium access.', null=True, verbose_name='premium request date'),
        ),
        migrations.AddField(
            model_name='user',
            name='premium_requested',
            field=models.BooleanField(default=False, help_text='Designates whether this user has requested premium access.', verbose_name='premium requested'),
        ),
    ]
