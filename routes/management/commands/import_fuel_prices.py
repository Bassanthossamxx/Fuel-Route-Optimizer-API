import csv
from django.core.management.base import BaseCommand
from routes.models import FuelStation


class Command(BaseCommand):
    help = "One-time import of fuel station prices (keeps highest price per station/state)"

    def add_arguments(self, parser):    
        parser.add_argument(
            '--file',
            type=str,
            default='fuel-prices.csv',
            help='Path to the fuel prices CSV file'
        )

    def handle(self, *args, **options):
        file_path = options['file']

        station_map = {}  # (station_name, state) -> FuelStation
        skipped_count = 0
        failed_count = 0

        self.stdout.write(self.style.NOTICE(
            f"Starting fuel stations import from: {file_path}"
        ))

        try:
            with open(file_path, newline='', encoding='utf-8') as csv_file:
                reader = csv.DictReader(csv_file)

                for row_number, row in enumerate(reader, start=1):
                    try:
                        station_name = row.get('Truckstop Name', '').strip()
                        state = row.get('State', '').strip()
                        price = row.get('Retail Price', '').strip()

                        if not station_name or not state or not price:
                            skipped_count += 1
                            continue

                        price = float(price)
                        key = (station_name, state)

                        # If station already exists, keep the HIGHEST price
                        if key in station_map:
                            if price > station_map[key].price_per_gallon:
                                station_map[key].price_per_gallon = price
                        else:
                            station_map[key] = FuelStation(
                                station_name=station_name,
                                state=state,
                                address=row.get('Address', '').strip(),
                                city=row.get('City', '').strip(),
                                price_per_gallon=price,
                            )

                    except Exception as row_error:
                        failed_count += 1
                        self.stderr.write(
                            self.style.ERROR(
                                f"Row {row_number} failed: {row_error}"
                            )
                        )

        except FileNotFoundError:
            self.stderr.write(
                self.style.ERROR(f"File not found: {file_path}")
            )
            return

        before_count = FuelStation.objects.count()

        FuelStation.objects.bulk_create(
            station_map.values(),
            batch_size=500,
            ignore_conflicts=True,
        )

        after_count = FuelStation.objects.count()

        self.stdout.write(self.style.SUCCESS("Fuel stations import completed"))
        self.stdout.write(f"Added records   : {after_count - before_count}")
        self.stdout.write(f"Skipped records : {skipped_count}")
        self.stdout.write(f"Failed records  : {failed_count}")
