#!/usr/bin/python3
"""Parser module."""

import lxml.html
import re
import requests
import json
import time
import sys
import os
from datetime import datetime, timedelta

from job_opening import JobOpening
from location import Location


BASE_URL = 'https://news.ycombinator.com/'


def guess_type_of_position(text):
    '''
        Guess type of position from a piece of text

        Types of position:
            * Remote
            * H1B (and variations)
            * Intern
    '''
    opening = JobOpening(text)
    return (opening.remote, opening.h1b, opening.intern)

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

def is_url(text):
    '''
        Is the piece of text a URL
    '''
    return re.match('^https?://[^ ]*$', text)

def extract_text(node):
    '''
        Why not .text_content() - This one inserts '\n' for convenience
    '''
    text = ''
    for child in node.itertext():
        if is_url(child):
            text = text[:-1] + child
        else:
            text += child + '\n'
    return text

def is_not_duplicate(key, store):
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
        comment_html = lxml.html.tostring(comment, encoding='utf-8')
        comment_html = comment_html.decode('utf-8')

        first_line = shorten_comment(comment_html)
        remote, h1b, intern_ = guess_type_of_position(first_line)

        loc = Location(first_line, extract_text(comment))
        location = loc.location
        lat = loc.latitude
        lon = loc.longitude
        formatted_address = loc.address
        country = loc.country

        result = dict(remote=remote, intern=intern_, h1b=h1b,
                      url=(BASE_URL + url),
                      full_html=comment_html,
                      user=user, freshness=is_not_duplicate(user, previous_month_users),
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

    current_file = './web/data/%s.json' % date.strftime('%Y-%m')
    previous_month_file = './web/data/%s.json' %  previous_month.strftime('%Y-%m')

    try:
        previous_month_data = json.load(open(previous_month_file))
        previous_month_users = [p['user'] for p in previous_month_data]
    except IOError:
        previous_month_users = False

    parse_and_write(fetch_page(url), current_file, previous_month_users)

    # Dump to a file the months for which data is available, ignoring hidden files
    available_data = [filename.split('.')[0] for filename in os.listdir('./web/data') if filename[0] is not '.']
    available_data.sort()
    available_data = json.dumps(available_data)
    with open('./web/js/months.js', 'w') as f:
        f.write('var available_data = %s;'%(available_data))

if __name__ == '__main__':
    main()
