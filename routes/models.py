from django.db import models


class FuelStation(models.Model):
    station_name = models.CharField(max_length=255)
    address = models.CharField(max_length=255, blank=True)
    city = models.CharField(max_length=100, blank=True)
    state = models.CharField(max_length=10, db_index=True)
    price_per_gallon = models.DecimalField(max_digits=5, decimal_places=2)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('station_name', 'state')
        ordering = ['state', 'price_per_gallon']

    def __str__(self):
        return f"{self.station_name} ({self.state}) - ${self.price_per_gallon}"
