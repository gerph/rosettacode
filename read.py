#!/usr/bin/env python
"""
Fetch all the code for a given language into structures.
"""

import argparse
import json
import os.path
import re
import sys

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


def json_encode(obj):
    """
    Encoding function to use for objects which are not known to the standard JSON encoder.

    If the object contains a property '__jsonencode__', it is called to obtain the representation
    of the object.
    """

    def jsonspecial_datetime(obj):  # pylint: disable=unused-variable
        return obj.isoformat()

    if hasattr(obj, '__jsonencode__'):
        return obj.__jsonencode__()

    special_name = 'jsonspecial_%s' % (obj.__class__.__name__,)
    special_func = locals().get(special_name, None)
    if special_func:
        return special_func(obj)

    raise TypeError("Cannot serialise a '%s' object: %r" % (obj.__class__.__name__, obj))


def json_iterable(obj, pretty=False):
    if pretty:
        return json.JSONEncoder(default=json_encode,
                                sort_keys=True,
                                indent=2,
                                separators=(',', ': ')).iterencode(obj)
    else:
        return json.JSONEncoder(default=json_encode).iterencode(obj)


def write_json(filename, obj, pretty=False):
    with open(filename, 'w') as fh:
        for chunk in json_iterable(obj, pretty=pretty):
            fh.write(chunk)


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

    def __jsonencode__(self):
        return {
                'syntax': self.syntax,
                'code': self.code,
                'output': self.output,
                'workswith': self.workswith
            }


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

    def __jsonencode__(self):
        return {
                'name': self.name,
                'markdown': self.md,
                'code-blocks': self.blocks,
            }

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
                if code:
                    code.output = out
                else:
                    # We've defined an output without a recognised code block.
                    # Let's ignore for now.
                    pass
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
    intro_re = re.compile('^(.*?)\n(;Task:\n|==[^=])', re.DOTALL)
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
        self._language_filter = lambda _: True

    def __repr__(self):
        if self._page:
            return "<%s(name=%s, languages=%s)>" % (self.__class__.__name__,
                                                    self.wikiname,
                                                    len(self.languages))
        else:
            return "<%s(name=%s, not loaded)>" % (self.__class__.__name__,
                                                  self.wikiname)

    def __jsonencode__(self):
        return {
                'wikiname': self.wikiname,
                'name': self.name,
                'url': self.url,
                'languages': self.dict,
                'task': self.task,
                'intro': self.intro,
            }

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
            area = ''
            if ta:
                area = ta[0].contents[0]
            self._edit = html.unescape(area)
        return self._edit

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
    def language_filter(self):
        return self._language_filter

    @language_filter.setter
    def language_filter(self, value):
        self._language_filter = value
        self._languages = None

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
        languages = [Language(name, md) for name, md in matches]

        # And those strange cases of 2 languages (we'll only pick the first)
        matches = self.language2_re.findall(self.edit)
        languages.extend([Language(name1, md) for name1, _, md in matches])

        # Perform any requested filtering
        languages = [lang for lang in languages if self.language_filter(lang)]

        self._languages = languages
        self._byname = dict((lang.name, lang) for lang in self._languages)
        return self._languages

    @property
    def dict(self):
        if self._languages is None:
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

    def values(self):
        return self.languages


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
        self._task_filter = lambda _: True

    def __repr__(self):
        if self._page:
            return "<%s(category=%s, tasks=%s)>" % (self.__class__.__name__,
                                                    self.category,
                                                    len(self.tasks))
        else:
            return "<%s(category=%s, not loaded)>" % (self.__class__.__name__,
                                                      self.category)

    def __jsonencode__(self):
        return {
                'category': self.category,
                'url': self.url,
                'tasks': self.tasks,
            }

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
    def task_filter(self):
        return self._task_filter

    @task_filter.setter
    def task_filter(self, value):
        self._task_filter = value
        self._tasks = None

    @property
    def tasks(self):
        if self._tasks is None:
            tasks = [Task(wikiname) for _, wikiname in self.links]

            # Apply any filters
            tasks = [task for task in tasks if self.task_filter(task)]
            self._tasks = tasks
        return self._tasks


def list_task(task, options, fh=None, base_indent=''):
    if fh is None:
        fh = sys.stdout

    for lang in sorted(task.values()):
        indent = base_indent
        if options.languages:
            if options.count:
                fh.write("%s%s (%s)\n" % (indent, lang.name, len(lang.blocks)))
            else:
                fh.write("%s%s\n" % (indent, lang.name))
            indent += '  '
        if options.code:
            for index, block in enumerate(lang.blocks):
                fh.write("%s#%s:\n" % (indent, index))
                for line in block.code.splitlines():
                    fh.write("%s  %s\n" % (indent, line))


def comment(language, block):
    """
    Return a block of a comment for a given language.

    If we don't know the language, we'll use # prefix.
    """
    if language in ('C', 'C++'):
        return "/*%s\n*/\n" % (block,)

    prefix = "# "
    lines = [prefix + line + "\n" for line in block.splitlines()]
    return "".join(lines)


def write_tasks_dir(tasks, code_dir='code',
                    layout='unix',
                    include_task=False,
                    include_intro=False):
    for task in tasks:
        for lang in task.values():
            # This won't be right for many files, but let's be consistent
            extension = lang.name.lower().replace('/', '.')

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

                dirname = os.path.dirname(filename)
                if not os.path.isdir(dirname):
                    os.makedirs(dirname)

                # Report the progress...
                print("File: %s" % (filename,))
                with open(filename, 'w') as fh:
                    if include_intro and task.intro:
                        fh.write(comment(lang.name, "\n" + task.intro.encode('utf-8', 'replace')) + "\n")
                    if include_intro and task.task:
                        fh.write(comment(lang.name, "TASK:\n" + task.task.encode('utf-8', 'replace')) + "\n")
                    fh.write(code.code.encode('utf-8'))
                    # Ensure we always end on a newline
                    fh.write("\n")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--task', type=str, default=None,
                        help="Name of a Task to process")
    parser.add_argument('--category', type=str, default=None,
                        help="Name of a Category of process")
    parser.add_argument('--language', type=str, default=None,
                        help="Language to list")

    parser.add_argument('--tasks', action='store_true', default=False,
                        help='Report the tasks')
    parser.add_argument('--languages', action='store_true', default=False,
                        help='Report the languages')
    parser.add_argument('--count', action='store_true', default=False,
                        help='Report a count of the sub-resources')
    parser.add_argument('--code', action='store_true', default=False,
                        help='Report the code')

    parser.add_argument('--list', action='store_true', default=False,
                        help="Report the results as a list")
    parser.add_argument('--json', action='store_true', default=False,
                        help="Report the elements as JSON")
    parser.add_argument('--dir', type=str, default=None,
                        help="Report results to a directory structure")

    parser.add_argument('--file', type=str, default=None,
                        help="Report results to a file (for list, and json)")

    options = parser.parse_args()

    result = None

    if options.category:
        result = Category(options.category)
    elif options.task:
        result = Task(options.task)

    if result is None:
        print("No query requested; use --task or --category to select tasks")

    if options.language:
        if isinstance(result, Task):
            result.language_filter = lambda lang: lang.name == options.language
        if isinstance(result, Category):
            # They want all the tasks in the category, which have a given language
            def task_filter(task):
                task.language_filter = lambda lang: lang.name == options.language
                if task.get(options.language, None):
                    return True
                return False
            result.task_filter = task_filter

    # If they don't specify an output default to list
    if not options.list and not options.dir and not options.json:
        options.list = True

    if options.list:
        # They just want a plain list of what's there.
        if options.file:
            fh = open(options.file,'w')
        else:
            fh = sys.stdout

        # If they didn't request anything, default to languages
        if not options.tasks and not options.languages and not options.count and not options.code:
            options.languages = True

        if options.code:
            options.languages = True

        if isinstance(result, Task):
            if options.count and not options.languages:
                fh.write("%s\n" % (len(result.keys()),))
            else:
                list_task(result, options, fh, base_indent='')

        elif isinstance(result, Category):
            if options.count and not options.languages and not options.tasks:
                fh.write("%s\n" % (len(result.tasks),))
            else:
                for task in result.tasks:
                    if options.count and not options.tasks:
                        fh.write("%s (%s)\n" % (task.name, len(task.languages)))
                    else:
                        fh.write("%s\n" % (task.name,))
                    if options.languages:
                        list_task(task, options, base_indent='  ')

    elif options.json:
        # They want JSON output
        if options.file:
            fh = open(options.file, 'w')
        else:
            fh = sys.stdout

        for chunk in json_iterable(result, pretty=True):
            fh.write(chunk)

    elif options.dir:
        # They wanted a directory dump
        layout = 'unix'
        code_dir = options.dir

        tasks = []
        if isinstance(result, Task):
            tasks = [result]
        elif isinstance(result, Category):
            tasks = result.tasks

        write_tasks_dir(tasks, code_dir,
                        layout=layout,
                        include_task=True,
                        include_intro=True)

if __name__ == "__main__":
    main()
