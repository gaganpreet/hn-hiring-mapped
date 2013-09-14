"""Location module."""

import re
from pygeocoder import Geocoder
from pygeolib import GeocoderError


class Location(object):
    """Representation of a location."""

    _location_synonyms = {
        'Berlin': 'Berlin',
        'London': 'London',
        'Mountain View': 'Mountain View',
        'New York': 'New York',
        'NY': 'New York',
        'NYC': 'New York',
        'San Francisco': 'San Francisco',
        'SF': 'San Francisco',
        'SOMA': 'San Francisco',
        'SoMa': 'San Francisco',
        'Bay Area': 'San Francisco',
        'SAN FRANCISCO': 'San Francisco',
    }

    def __init__(self, heading, text):
        self._location_data = {}
        location = self.guess_location(heading, aggressive_mode=True)
        if not location:
            location = self.guess_location(text)
        if location:
            self._location_data['location'] = location
            location = location.encode('UTF-8')
            try:
                results = Geocoder.geocode(location)
            except GeocoderError:
                return
            lat, lon = results.coordinates
            self._location_data['latitude'] = lat
            self._location_data['longitude'] = lon
            self._location_data['address'] = results.formatted_address
            for component in results.current_data['address_components']:
                if 'country' in component['types']:
                    self._location_data['country'] = component['short_name']

    def guess_location(self, text, aggressive_mode=False):
        """Guess the location from text."""
        # Start with commonly known locations.
        for synonym, location in self._location_synonyms:
            if synonym in text:
                return location
        # Match for words like Cambride, MA or San Francisco, CA
        match = re.search(r'(([A-Z][^ A-Z]{2,} ?){1,2}, [A-Z]{2})\W', text)
        if match:
            return match.group(1)
        if aggressive_mode:
            match = re.search('(([A-Z][^ A-Z,]{2,} ?){1,2}?, [A-Z][^ ]+)', text)
            if match:
                return match.group(1)
        return None

    @property
    def location(self):
        """Location."""
        return self._location_data.get('location')

    @property
    def latitute(self):
        """Latitude."""
        return self._location_data.get('latitude')

    @property
    def longitude(self):
        """Longitude."""
        return self._location_data.get('longitude')

    @property
    def address(self):
        """Formatted address of the place."""
        return self._location_data.get('address')

    @property
    def country(self):
        """Country."""
        return self._location_data.get('country')
