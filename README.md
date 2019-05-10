# Rosetta Code reading

## Introduction

The rosettacode.org site provides example code for a variety
for different tasks in many different languages. Because the
code is generally pretty self contained and simple - as the
point is to show the differences in the way languages do
things - it makes a good source of code to try things out
with.

I wanted to get the C code to test a compiler wasn't crashing
on simple stuff, but it's probably useful to others. So I've
tidied up code a little bit, and added a CLI interface, so
that others might use it.


## rosettacode.py

The main rosettacode.py library is able to be used to extract
information from the Task and Category pages, breaking down
the information into Languages and CodeBlocks. You can then
do what you want with that information.

It is expected that the code is used by accessing either a
Category(<name>) or a Task(<name>).

Basically:
  * a Category may list a number of Tasks.
  * Tasks may contain a number of Languages.
  * Languages may define multiple CodeBlocks.
  * CodeBlocks may have code, an output definition, and some
    other metadata.

For example:
    task = Task('100_doors')
    for lang in task.languages:
        for block in lang.blocks:
            print("Code length: {}".format(len(block.code)))
Or:
    category = Category('C')
    for task in category.tasks:
        print("Task: {}".format(task.name))

The layout of the pages is mostly structured to allow the
code blocks to be extracted, but some code blocks are not
structured consistently in the markdown.


## rccli.py

The CLI tool is intended to be used just to get the data out,
without needing to care about the API that does the data
processing. I didn't use it myself for the extraction of the
data I wanted - the nasty code I wrote was expanded into the
monstrosity that is this CLI tool.

If the tool isn't functional for you, there's always the API.
If the API isn't functional for you, well, you have the source...

Some examples:

Some example uses:

* `./rccli.py --task '100_doors'`

    list the languages in '100_doors'

* `./rccli.py --task '100_doors' --languages --count`

    list the languagse with counts of the code blocks

* `./rccli.py --task '100_doors' --code`

    list all the code in all the languages

* `./rccli.py --task '100_doors' --language 'C' --code`

    show the code blocks for C code in '100_doors'

* `./rccli.py --category 'C' --tasks`

    list all the tasks in the 'C' category

* `./rccli.py --catgeory 'C' --json`

    Dump JSON for the data in the 'C' category.

* `./rccli.py --category 'C' --json --file 'my.json'`

    Dump JSON for the data in the 'C' category to a file.

* `./rccli.py --task '100_doors' --dir 'code'`

    Extract all the code from the '100_doors' task in to a directory

* `./rccli.py --task '100_doors' --language 'C' --dir 'code'`

    Extract the C code from the '100_doors' task in to a directory

* `./rccli.py --category 'C' --language 'C' --dir 'code'`

    Extract the C code all tasks in the 'C' category in to a directory


## Notes

The API library uses a local cache in the 'no-backup'
directory. If that's not what you want, then it's simple
to change, but I was too lazy to add more functionality for
configuring it.
