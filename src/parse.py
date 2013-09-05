#!/usr/bin/python3
import lxml.html
import re
import requests
import json
import time
import sys
import os
from pygeocoder import Geocoder
from pygeolib import GeocoderError
from functools import lru_cache
from lxml import etree
from datetime import datetime, timedelta
from pprint import pprint

BASE_URL='https://news.ycombinator.com/'

def guess_type_of_position(text):
    '''
        Guess type of position from a piece of text

        Types of position:
            * Remote
            * H1B (and variations)
            * Intern 
    '''
    text_lower = text.lower()
    is_remote = False
    if 'remote' in text_lower:
        if 'no remote' not in text_lower:
            is_remote = True

    # Check if any of h1b_patterns exist in text but isn't 
    # prefixed by the word 'no'
    h1b_patterns = ['h1b', 'h1-b', 'h-1b']
    h1b = any(pattern in text_lower for pattern in h1b_patterns) and \
          not any('no ' + pattern in text_lower for pattern in h1b_patterns) 

    intern_ = False
    if re.search(r'\Wintern\W', text_lower):
        intern_ = True

    return (is_remote, h1b, intern_)

def guess_location(text, aggressive=True):
    '''
        Parse the location from a piece of text using some
        heuristics:
            * Match some common locations and their variations
            * Look for patterns like City Name, Two letter state/country code
            * If aggressive is true, look for patterns like City, State
    '''
    # Some commonly used locations and their oft used synonyms
    common_locations = {'San Francisco': ['SF', 'San Francisco', 
                                          'SoMa', 'SOMA', 'Bay Area',
                                          'SAN FRANCISCO'],
                        'Palo Alto': ['Palo Alto'],
                        'Mountain View': ['Mountain View'],
                        'New York': ['NYC', 'NY', 'New York'],
                        'London': ['London'],
                        'Berlin': ['Berlin'],
                        }

    
    # Look for a common location
    for location, names in common_locations.items():
        for name in names:
            if name in text:
                return location

    # Match for US locations like:
    #       Cambridge, MA
    # or even:
    #       Two Words, AB
    # Will also pickup locations like:
    #       London, UK
    match = re.search(r'(([A-Z][^ A-Z]{2,} ?){1,2}, [A-Z]{2})\W', text)
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
        Strip the first line from a comment, usually that is what
        stores the information about type of position and location

        Otherwise just reutrn the whole thing
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

def get_comment_objects(html):
    '''
        Parse the page with lxml and get the top level comments
    '''
    html = lxml.html.fromstring(html)
    
    # This is a complicated xpath because HN's html is terrible
    # Another reason is that we need only the top level comments, 
    # and ignore the children
    rows = html.xpath("//img[@width=0]/../..")

    for row in rows:
        if row.xpath(".//span[@class='comment']"):
            comment = row.xpath(".//span/font")[0]
            user = row.xpath('.//span/a[1]')[0].text_content()
            url = row.xpath('.//span/a[2]')[0].attrib['href']
            yield url, user, comment

    more = html.xpath(".//a[text()='More']")
    if len(more) == 1:
        time.sleep(30)
        for comment in get_comment_objects(fetch_page('http://news.ycombinator.com' + more[0].attrib['href'])):
            yield comment

def fetch_page(url):
    '''
        GET a url and return the response if status code is 200
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
    except GeocoderError:
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

def extract_text(node):
    '''
        Why extract_text and not .text_content()

        This one inserts '\n' for convenience
    '''
    text = ''
    for child in node.itertext():
        if is_url(child):
            text = text[:-1] + child
        else:
            text += child + '\n'
    return text

def is_duplicate(key, store):
    if store:
        return not key in store
    return True

def parse_and_write(start_html, currrent_file, previous_month_users):
    '''
        Parse the html, organize into objects and write to `current_file'
        as json
    '''
    results = []
    for url, user, comment in get_comment_objects(start_html):
        if not url:
            continue
        comment_text = extract_text(comment)
        comment_html = lxml.html.tostring(comment, encoding='utf-8')
        comment_html = comment_html.decode('utf-8')

        # The first line of comment usually contains the interesting info
        first_line = shorten_comment(comment_html)

        remote, h1b, intern_ = guess_type_of_position(first_line)

        # Try guessing location on first line, then on the whole thing
        location, lat, lon, formatted_address, country = [None]*5
        location = guess_location(first_line)
        if remote == False and location == None:
            location = guess_location(comment_text, False)

        if location:
            (lat, lon), formatted_address, country = geocode(location)
            if not lat or len(formatted_address) > 50:
                location, lat, lon, formatted_address, country = [None]*5

        result = dict(remote=remote, intern=intern_, h1b=h1b, 
                      short_desc=comment_text[:256], 
                      url=BASE_URL + url,
                      full_text=comment_text, full_html=comment_html,
                      user=user, freshness=is_duplicate(user, previous_month_users),
                      location=location,
                      lat=lat, lon=lon, country=country,
                      address=formatted_address,)
        results.append(result)
#    pprint(results)
    json.dump(results, open(currrent_file, 'w'), indent=4, sort_keys=True)


def main():
    url = 'https://news.ycombinator.com/item?id=' + sys.argv[1]
    year, month = sys.argv[2].split('-')

    date = datetime(year=int(year), month=int(month), day=1)
    previous_month = date - timedelta(days=30)

    current_file = './data/%s.json' % date.strftime('%Y-%m')
    previous_month_file = './data/%s.json' %  previous_month.strftime('%Y-%m')

    previous_month_users = None
    try:
        previous_month_data = json.load(open(previous_month_file))
        previous_month_users = [p['user'] for p in previous_month_data]
    except IOError:
        previous_month_data = False

    parse_and_write(fetch_page(url), current_file, previous_month_users)

    available_data = json.dumps(os.listdir('./data'))
    with open('data/months.js', 'w') as f:
        f.write('var available_data = %s;'%(available_data));
    
if __name__ == '__main__':
    main()
