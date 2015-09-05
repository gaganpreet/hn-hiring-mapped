#!/usr/bin/python3
import re
import requests
import json
import sys
import os
import concurrent.futures
from pygeocoder import Geocoder
from pygeolib import GeocoderError
from functools import lru_cache
from datetime import datetime, timedelta

BASE_URL = 'https://news.ycombinator.com'
ITEM_API_URL = 'https://hacker-news.firebaseio.com/v0/item/{0}.json'

def guess_type_of_position(text):
    '''
    Guess type of position from a piece of text

    Types of position:
        * Remote
        * H1B (and variations)
        * Intern (and variations)
    '''
    # Current version of re module doesn't support variable length look behinds
    # but the new regex module does, just in case someone wants to improve
    # this regex
    filters = {'h1b': r'(\W|^)(?<!no )(h1b|h-1b|h1-b)(\W|$)',
               'remote': r'(\W|^)(?<!no )remote(\W|$)',
               'intern': r'(\W|^)(?<!no )intern(s|ship)?(\W|$)'
               }

    text_lower = text.lower()
    h1b, remote, intern_ = [False]*3
    if re.search(filters['h1b'], text_lower):
        h1b = True
    if re.search(filters['remote'], text_lower):
        remote = True
    if re.search(filters['intern'], text_lower):
        intern_ = True

    return remote, h1b, intern_

def guess_location(text, aggressive=True):
    '''
    Parse the location from a piece of text using some heuristics:
        * Match some common locations and their variations
        * Look for patterns like City Name, Two letter state/country code
        * If aggressive is true, look for patterns like City, State
    '''
    # Some commonly used locations and their oft used synonyms
    common_locations = json.load(open('common_locations.json'))

    # Look for a common location
    for location in common_locations:
        for synonym in location['synonyms']:
            if synonym in text:
                return location['name']

    # Match for US locations like:
    #       Cambridge, MA
    # or even:
    #       Two Words, AB
    # Will also pickup locations like:
    #       London, UK
    # Tries to work with Unicode locations
    # TL;DR I tried to do NLP with a regex
    match = re.search(r'(([A-Z][^ A-Z\W]{2,} ?){1,2}, ?[A-Z]{2})(\W|$)', text, re.UNICODE)
    if match:
        return match.group(1)

    if aggressive:
        # Match locations like Munich, Germany
        # The aggressive bool is necessary otherwise there'll
        # be a lot of false positives, by default this will only be
        # evaluated for the first line of the comment
        match = re.search('(([A-Z][^ A-Z,]{2,} ?){1,2}?, [A-Z][^ ]+)', text)
        if match:
            return match.group(1)

    # Oops, we failed
    return None

def shorten_comment(comment_html):
    '''
    Strip the first line from a comment
    Usually that is what stores the information about type of position and location

    Otherwise just return the whole thing (if it can't be parsed)
    '''
    # First line either ends at a \n or starts at a new paragraph
    # Most of the comments (> 90%) should be parsed with this
    first_line = re.match(r'(.*?)(<p>|\n).*', comment_html)
    if first_line:
        line = first_line.group(1)
    else:
        # If our parsing fails, just return the whole thing
        # It's probably a single line comment
        line = comment_html

    # Strip all html tags
    line = re.sub('<.*?>', '', line)
    return line

def get_comment_objects(items):
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        for response in executor.map(fetch_item, items):
            if not response:
                continue
            if 'deleted' in response and response['deleted'] is True:
                continue
            yield response['id'], response['by'], response['text']


def fetch_page(url):
    '''
    GET a url and return the response text if status code is 200
    '''
    print('Fetching ' + url)
    response = requests.get(url)
    print(response.status_code)
    if response.status_code == 200:
        return response.text

@lru_cache(maxsize=200, typed=False)
def geocode(location):
    '''
    Geocode a location
    Results are cached
    '''
    location = location.encode('utf-8')

    try:
        results = Geocoder.geocode(location)
    except GeocoderError as e:
        print("Failed to geocode {0}, {1}".format(location, e))
        return ((None, None), None, None)
    lat, lon = results.coordinates
    formatted_address = results.formatted_address

    country = None
    for component in results.current_data['address_components']:
        if 'country' in component['types']:
            country = component['short_name']

    return ((lat, lon), formatted_address, country)

def is_url(text):
    '''
    Is the piece of text a URL
    '''
    return re.match('^https?://[^ ]*$', text)

def is_not_duplicate(key, store):
    if store:
        return not key in store
    return True

def location_and_geocode(comment, first_line):
    '''
    Guess location and geocode given a comment
    '''
    location, lat, lon, formatted_address, country = [None]*5

    # Try guessing location on first line, then on the whole thing
    location = guess_location(first_line)
    if location == None:
        location = guess_location(comment, False)

    if location:
        (lat, lon), formatted_address, country = geocode(location)
        if not lat or len(formatted_address) > 50:
            # 50 is a hard limit on the length of address
            lat, lon, formatted_address, country = [None]*4

    return (location, lat, lon, formatted_address, country)


def parse_and_write(post_id, currrent_file, previous_month_users):
    '''
    Parse the html, organize into objects and write to `current_file'
    as json
    '''
    results = []
    items = fetch_item(post_id)
    for url_path, user, comment_html in get_comment_objects(items['kids']):
        if not url_path:
            continue
        comment = comment_html

        first_line = shorten_comment(comment_html)
        remote, h1b, intern_ = guess_type_of_position(comment)

        location, lat, lon, formatted_address, country = location_and_geocode(comment, first_line)

        result = dict(remote=remote,
                      intern=intern_,
                      h1b=h1b,
                      url=(BASE_URL + '/item?id=' + str(url_path)),
                      full_html=comment_html,
                      user=user,
                      freshness=is_not_duplicate(user, previous_month_users),
                      location=location,
                      lat=lat,
                      lon=lon,
                      country=country,
                      address=formatted_address,)
        results.append(result)
    json.dump(results, open(currrent_file, 'w'), indent=4, sort_keys=True)


def fetch_item(item_id):
    url = ITEM_API_URL.format(item_id)
    response = requests.get(url)
    return response.json()


def main():
    item_id = sys.argv[1]

    date = datetime.strptime(sys.argv[2], '%Y-%m')
    previous_month = date - timedelta(days=1)

    current_file = './web/data/%s.json' % date.strftime('%Y-%m')
    previous_month_file = './web/data/%s.json' %  previous_month.strftime('%Y-%m')

    try:
        previous_month_data = json.load(open(previous_month_file))
        previous_month_users = [p['user'] for p in previous_month_data]
    except IOError:
        previous_month_users = False

    parse_and_write(item_id, current_file, previous_month_users)

    # Dump to a file the months for which data is available, ignoring hidden files
    available_data = [filename.split('.')[0]
                        for filename in os.listdir('./web/data')
                        if filename[0] is not '.']
    available_data.sort()
    available_data = json.dumps(available_data)
    with open('./web/js/months.js', 'w') as f:
        f.write('var available_data = %s;'%(available_data));

if __name__ == '__main__':
    main()
