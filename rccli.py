#!/usr/bin/env python
"""
Command line interface to access the Rosetta Code site.

Pretty rudimentary; just thrown together to make it
possible to invoke by anyone that doesn't want to use
the API directly.

Some example uses:

./rccli.py --task '100_doors'
  - list the languages in '100_doors'

./rccli.py --task '100_doors' --languages --count
  - list the languagse with counts of the code blocks

./rccli.py --task '100_doors' --code
  - list all the code in all the languages

./rccli.py --task '100_doors' --language 'C' --code
  - show the code blocks for C code in '100_doors'

./rccli.py --category 'C' --tasks
  - list all the tasks in the 'C' category

./rccli.py --catgeory 'C' --json
  - Dump JSON for the data in the 'C' category.

./rccli.py --category 'C' --json --file 'my.json'
  - Dump JSON for the data in the 'C' category to a file.

./rccli.py --task '100_doors' --dir 'code'
  - Extract all the code from the '100_doors' task in to a directory

./rccli.py --task '100_doors' --language 'C' --dir 'code'
  - Extract the C code from the '100_doors' task in to a directory

./rccli.py --category 'C' --language 'C' --dir 'code'
  - Extract the C code all tasks in the 'C' category in to a directory
"""

import argparse
import os
import sys

# Local libraries
from rosettacode import Task, Category
import json_funcs


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
    """
    Write out all the tasks in the list to a set of directories.

    Using the 'riscos' layout will write out as <dir>/<extension>/<name>.
    Using the 'unix' layout will write out as <dir>/<name>.<extension>.
    """
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
                    if include_task and task.task:
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
            fh = open(options.file, 'w')
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

        for chunk in json_funcs.json_iterable(result, pretty=True):
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
