.. scripter documentation master file, created by
   sphinx-quickstart on Thu Mar  1 16:51:12 2012.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.

Default command-line options
============================

.. toctree::
   :maxdepth: 2
   
A number of default command-line options are included with the default argument
parser in :class:`~scripter.Environment`.

.. seealso:: :meth:`~scripter.Environment.__init__`

Most importantly, we take a list of filenames to be acted on. This list accepts
wildcards using :mod:`glob <python:glob>`

Additionally, there are a number of optional arguments:

  -h, --help                            show this help message and exit
  -v, --version                         show version info and exit
  -p NUM_CPUS, --num-cpus NUM_CPUS      specify the number of maximum # CPUs to use
  --debug                               Sets logging level to DEBUG
  --info                                Sets logging level to INFO [default]
  --quiet                               Sets logging level to WARNING
  --silent                              Sets logging level to ERROR
  --target TARGET                       Specify the target directory
  --no-target                           Write new files in the current directory / do not preserve directory structure
  --recursive RECURSIVE, -r RECURSIVE   Recurse through any directories listed looking for valid files
  --no-action, --do-nothing, --dry-run  Don't act on files
  --config CONFIG                       Use configuration in file foo
