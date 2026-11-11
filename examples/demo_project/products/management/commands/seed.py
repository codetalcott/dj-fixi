"""manage.py seed [--reset]: sample products, enough to page through."""

from django.core.management.base import BaseCommand

from products.models import Product

NAMES = [
    "Anvil", "Bolt", "Clamp", "Drill", "Easel", "File", "Gasket", "Hinge", "Ink", "Jack",
    "Knob", "Lathe", "Mallet", "Nail", "O-ring", "Pliers", "Quill", "Rasp", "Saw", "Trowel",
    "Union", "Vise", "Wrench", "X-brace", "Yoke",
]  # fmt: skip


class Command(BaseCommand):
    help = "Create sample products for the demo. Does nothing if products already exist."

    def add_arguments(self, parser):
        parser.add_argument("--reset", action="store_true", help="Delete every product first.")

    def handle(self, *args, reset, **options):
        if reset:
            Product.objects.all().delete()
        if Product.objects.exists():
            self.stdout.write("Products already exist; pass --reset to start over.")
            return
        for i, name in enumerate(NAMES):
            Product.objects.create(
                name=name,
                description=f"A dependable {name.lower()}.",
                price=f"{4 + i * 1.5:.2f}",
                stock=(i * 7) % 40,
                is_active=i % 6 != 5,
            )
        self.stdout.write(self.style.SUCCESS(f"Created {len(NAMES)} products."))
