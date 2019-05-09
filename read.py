#!/usr/bin/env python
"""
Fetch all the code for a given language into structures.
"""

import os.path
import re

import requests

try:
    # Python 2.6-2.7
    from HTMLParser import HTMLParser
except ImportError:
    # Python 3
    from html.parser import HTMLParser
html = HTMLParser()

try:
    # Python 3
    from urllib.parse import unquote
except ImportError:
    # Python 2
    from urllib import unquote

from BeautifulSoup import BeautifulSoup


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


class CodeBlock(object):

    def __init__(self, code, syntax=None):
        self.syntax = syntax or None
        self.code = code
        self.output = None
        self.workswith = None

    def __repr__(self):
        return "<%s(length=%s lines, syntax=%s)>" % (self.__class__.__name__,
                                                     len(self.code.splitlines()),
                                                     self.syntax)


class Language(object):
    """
    Definition blocks for a language
    """
    chunk_re = re.compile(r"(\{\{out[^}]*}}\s*<pre>.*?</pre>|\{\{[^}]*}}|<lang.*?</lang>)", re.DOTALL)
    workswith_re = re.compile(r"\{\{works with\|([^}]*)}}", re.DOTALL)
    out_re = re.compile(r"\{\{out\|?([^}]*)}}\s*<pre>(.*?)</pre>", re.DOTALL)
    block_re = re.compile(r"<lang ?([^>]*)>(.*?)</lang>", re.DOTALL)

    def __init__(self, name, md):
        if '|' in name:
            # Eg 'F_Sharp|F#'
            parts = name.split('|')
            name = parts[1]
        self.name = name
        self.md = md
        self._blocks = None
        self._blockmatches = None

    def __repr__(self):
        return "<%s(name=%s, codeblocks=%s)>" % (self.__class__.__name__,
                                                 self.name.encode('ascii', 'replace'),
                                                 len(self.blocks))

    @property
    def blocks(self):
        if self._blocks is not None:
            return self._blocks

        blocks = []

        matches = self.chunk_re.findall(self.md)
        works_with = None
        code = None
        for string in matches:
            match = self.workswith_re.search(string)
            if match:
                parts = match.group(1).split('|')
                works_with = {
                        'wikiname': None,
                        'display': None,
                        'version': None,
                    }
                works_with['wikiname'] = parts[0]
                if len(parts) == 2:
                    works_with['version'] = parts[1]
                if len(parts) == 3:
                    works_with['display'] = parts[1]
                    works_with['version'] = parts[2]
                continue

            match = self.out_re.search(string)
            if match:
                params = match.group(1).split('|')
                output = match.group(2)
                label = 'Output'
                out = {
                    'case': None,
                    'input': None,
                    'note': None,
                    'text': None,
                }
                if params:
                    for i in params:
                        parts = i.split('=', 1)
                        if len(parts) == 2 and parts[0] in out:
                            out[parts[0]] = parts[1]
                        else:
                            label = parts[0]
                out['label'] = label
                out['output'] = output

                # Append to a code block
                code.output = out
                continue

            match = self.block_re.search(string)
            if match:
                code = CodeBlock(code=match.group(2),
                                 syntax=match.group(1))
                if works_with:
                    code.workswith = works_with
                blocks.append(code)
                continue

        self._blockmatches = matches  # For debugging, really.
        self._blocks = blocks
        return self._blocks


class Task(object):
    task_re = re.compile('^;Task:\n(.*?)^==', re.MULTILINE | re.DOTALL)
    intro_re = re.compile('^(.*?)\n;Task:\n', re.DOTALL)
    language_re = re.compile(r'\n==\{\{header\|(.*?)\}\}== *\n(.*?)(?=\n==\{|$)', re.DOTALL)
    language2_re = re.compile(r'\n==\{\{header\|([^}]*?)\}\} and \{\{header\|([^}]*?)\}\}== *\n(.*?)(?=\n==\{|$)', re.DOTALL)

    """
    Read the details about a task.
    """
    def __init__(self, wikiname):
        self.wikiname = wikiname
        self.name = unquote(wikiname)
        self.url = '%s/mw/index.php?title=%s&action=edit' % (base_url, self.wikiname)
        self._page = None
        self._edit = None
        self._languages = None
        self._byname = None

    @property
    def page(self):
        if not self._page:
            page = cache_page(self.url, 'page-%s' % (self.wikiname.replace('/', '_'),))
            self._page = page
        return self._page

    @property
    def fsname(self):
        return self.name.replace('/', '_').encode('utf-8')

    @property
    def edit(self):
        if not self._edit:
            soup = BeautifulSoup(self.page)
            ta = soup.findAll('textarea')
            area = ta[0].contents[0]
            self._edit = html.unescape(area)
        return self._edit

    def __repr__(self):
        if self._page:
            return "<%s(name=%s, languages=%s)>" % (self.__class__.__name__,
                                                    self.wikiname,
                                                    len(self.languages))
        else:
            return "<%s(name=%s, not loaded)>" % (self.__class__.__name__,
                                                  self.wikiname)

    @property
    def task(self):
        """
        Everything within the 'Task' block
        """
        match = self.task_re.search(self.edit)
        if match:
            return match.group(1)
        return ''

    @property
    def intro(self):
        """
        Everything up to the 'task' block.
        """
        match = self.intro_re.search(self.edit)
        if match:
            return match.group(1)
        return ''

    @property
    def languages(self):
        """
        All the language blocks.
        """
        if self._languages is not None:
            return self._languages
        matches = self.language_re.findall(self.edit)
        self._languages = [Language(name, md) for name, md in matches]

        # And those strange cases of 2 languages (we'll only pick the first)
        matches = self.language2_re.findall(self.edit)
        self._languages.extend([Language(name1, md) for name1, _, md in matches])
        self._byname = dict((lang.name, lang) for lang in self._languages)
        return self._languages

    @property
    def dict(self):
        if not self._languages:
            _ = self.languages
        return self._byname

    def __getitem__(self, index):
        if not isinstance(index, str):
            raise KeyError("Key for Task languages must be a string")
        return self.dict[index]

    def get(self, index, default):
        if not isinstance(index, str):
            raise KeyError("Key for Task languages must be a string")
        return self.dict.get(index, default)

    def keys(self):
        return self.dict.keys()

    def items(self):
        return self.dict.items()


class Category(object):
    """
    Fetch information about a category of data.
    """
    match_re = re.compile('^/wiki/([A-Za-z0-9_/%]+)$')

    def __init__(self, category):
        self.category = category
        self.url = '%s/wiki/Category:%s' % (base_url, self.category)
        self._page = None
        self._links = None
        self._tasks = None

    @property
    def page(self):
        if not self._page:
            page = cache_page(self.url, 'category-%s' % (self.category,))
            self._page = page
        return self._page

    @property
    def links(self):
        if self._links is not None:
            return self._links

        soup = BeautifulSoup(self.page)
        headings = soup.findAll('h2')
        for heading in headings:
            if heading.string and heading.string.startswith('Pages in'):
                ele = heading.nextSibling
                while ele and getattr(ele, 'name', None) != 'h2':
                    if getattr(ele, 'findAll', None):
                        atags = ele.findAll('a')
                        self._links = []
                        for atag in atags:
                            if atag.get('href', None):
                                match = self.match_re.search(atag['href'])
                                if match:
                                    self._links.append((atag['title'], match.group(1)))
                    ele = ele.nextSibling
        return self._links

    @property
    def tasks(self):
        if self._tasks is None:
            self._tasks = [Task(wikiname) for _, wikiname in self.links]
        return self._tasks

    def __repr__(self):
        if self._page:
            return "<%s(category=%s, tasks=%s)>" % (self.__class__.__name__,
                                                    self.category,
                                                    len(self.tasks))
        else:
            return "<%s(category=%s, not loaded)>" % (self.__class__.__name__,
                                                      self.category)


eg = Task('100_doors')
c = Category('C')

import random

def fetchall(category):
    tasks = category.tasks
    random.shuffle(tasks)
    for t in tasks:
        _ = t.edit
        print "%r" % (t,)


language = 'C'
extension = 'c'
layout = 'riscos'
code_dir = 'examples'
include_intro = True
include_task = True

for task in c.tasks:
    lang = task.get(language, None)
    if not lang:
        continue
    for index, code in enumerate(lang.blocks):
        variant = index + 1
        if len(lang.blocks) > 1:
            name = "%s__%s" % (task.fsname, variant)
        else:
            name = task.fsname
        if layout == 'riscos':
            filename = os.path.join(code_dir, extension, name)
        else:
            filename = os.path.join(code_dir, name + '.' + extension)

        #if os.path.isfile(filename):
        #    continue

        dirname = os.path.dirname(filename)
        if not os.path.isdir(dirname):
            os.makedirs(dirname)
        print("File: %s" % (filename,))
        with open(filename, 'w') as fh:
            if include_intro and task.intro:
                fh.write("/*\n%s\n*/\n\n" % (task.intro.encode('utf-8'),))
            if include_intro and task.task:
                fh.write("/* TASK:\n%s\n*/\n\n" % (task.task.encode('utf-8'),))
            fh.write(code.code.encode('utf-8'))
            # Ensure we always end on a newline
            fh.write("\n")
