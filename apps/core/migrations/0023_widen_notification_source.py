from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('core', '0022_seed_institutional_pages'),
    ]

    operations = [
        migrations.AlterField(
            model_name='notification',
            name='source',
            field=models.CharField(max_length=40, verbose_name='Origen'),
        ),
        migrations.AlterField(
            model_name='notificationpreference',
            name='source',
            field=models.CharField(max_length=40, verbose_name='Origen'),
        ),
    ]
