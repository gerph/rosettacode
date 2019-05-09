#!/usr/bin/env python
"""
Fetch all the code for a given language into structures.
"""

import os.path
import requests

base_url = "http://rosettacode.org"
cache = 'no-backup'

def cache_page(url, name):
    cache_file = os.path.join(cache, name)
    if os.path.isfile(cache_file):
        with open(cache_file, 'r') as fh:
            page = fh.read().decode('utf-8')
    else:
        page = requests.get(url).text
        with open(cache_file, 'w') as fh:
            fh.write(page.encode('utf-8'))
    return page


class Task(object):
    """
    Read the details about a task.
    """
    def __init__(self, name):
        self.name = name
        url = '%s/mw/index.php?title=%s&action=edit' % (base_url, name)
        page = cache_page(url, 'page-%s' % (name,))
        self.page = page

eg = Task('100_doors')

try:
    # Python 2.6-2.7
    from HTMLParser import HTMLParser
except ImportError:
    # Python 3
    from html.parser import HTMLParser
html = HTMLParser()

from BeautifulSoup import BeautifulSoup
soup = BeautifulSoup(eg.page)
ta = soup.findAll('textarea')
edit = ta[0].contents[0]
edit = html.unescape(edit)
