from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response


class FuelStationPagination(PageNumberPagination):
    page_size = 500

    def get_paginated_response(self, data):
        return Response(
            {
                'count': len(data),
                'page': self.page.number,
                'next': self.get_next_link(),
                'previous': self.get_previous_link(),
                'results': data,
            }
        )
