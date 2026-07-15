from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("app", "0084_shoppingitem_recurrence_next_due_date"),
    ]

    operations = [
        migrations.AddField(
            model_name="shoppinglist",
            name="category_order",
            field=models.JSONField(blank=True, default=list),
        ),
    ]
