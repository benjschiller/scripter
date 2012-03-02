.. scripter documentation master file, created by
   sphinx-quickstart on Thu Mar  1 16:51:12 2012.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.

scripter: a tool for parallel execution of functions on many files
==================================================================

Licensed under Perl Artistic License 2.0

No warranty is provided, express or implied

.. toctree::
   :maxdepth: 2

   argparser
   api

==========
Philosophy
==========

:mod:`scripter` tries to make it easy to write scripts that
parallelize tasks by first parsing filenames and options, and
then executing an action (function) on the parsed filename objects.

Setting up the Environment
--------------------------


Its critical class is :class:`~scripter.Environment` which will generally be imported by ::

    import scripter
    e = scripter.Environment(version=VERSION, doc=__doc__)

Passing the version and documentation (usually __doc__) is recommended so that
users can use the expected "--help" and "--version" options

Attaching a FilenameParser
--------------------------

It is usually necessary to set a :class:`~scripter.FilenameParser`,
which acts of the
filenames given at the command
Your :class:`~scripter.FilenameParser` should inherit the class
:class:`~scripter.FilenameParser` from :mod:`scripter` and
should usually execute its :meth:`~scripter.FilenameParser.__init__` method
(either before or after yours, see the example below).
It is possible to use scripter's :class:`~scripter.FilenameParser`
directly if you don't need to customize it much. It is important that you allow
**kwargs in :meth:`~scripter.FilenameParser.__init__` for your custom
:class:`~scripter.FilenameParser` or it will almost certainly
fail to work. All options given at the command line and by :mod:`scripter` are passed
to both :class:`~scripter.FilenameParser` and the action.

.. _example-fp:
Here is an example :class:`~scripter.FilenameParser` hooked to :class:`~scripter.Environment` ::

    class ExampleFilenameParser(FilenameParser):
        def __init__(filename, number_of_apples=5, **kwargs):
             super(self, ExampleFilenameParser).__init__(self, **kwargs)
             self.tree = [filename + '_%d.txt' % num for num in range(number_of_apples)]

    e.set_filename_parser(ExampleFilenameParser)

Defining an action
------------------
The last thing you must for the script to run is to define the action and tell
the :class:`~scripter.Environment` to execute it. Like
:class:`~scripter.FilenameParser`, the action should accept
**kwargs or it will probably fail. Here is an example action which makes files
in the output directory for the specified number_of_apples::

    import os.path
    def example_function(filename_obj, **kwargs):
        tree = filename_obj.tree
        input = filename_obj.input_file
        output_dir = filename_obj.output_dir
        for f in tree:
            output_filename = os.path.join(output_dir, f) 
            fh = open(output_filename, 'wb')
            fh.write('This apple came from %s' % input)
        
    e.do_action(example_function) # this actually starts the script
    
Modifying the script options
----------------------------

You probably want to specify additional values at the command line besides the
:mod:`scripter` defaults. You can import the argument parser and modify it, see
:mod:`argparse <python:argparse>` for more information::

    parser = e.argument_parser
    parser.add_argument("--number-of-apples", type=int, nargs='?')
    
Options from the parser are converted into keywords that can be accessed either
from the kwargs directionary or by including the kwarg directly in the action
definition or the :meth:`~scripter.FilenameParser.__init__` method of the 
:class:`~scripter.FilenameParser`
(we did that above by include number_of_apples in our custom :ref:`__init__ <example-fp>` method)    

.. note: :mod:`scripter` will convert "-"s in long options to "_"s so that you may access those keyword arguments in the FilenameParser and action 
    
:mod:`scripter` includes a number of :doc:`default options <argparser>` that set
various script parameters

Dealing with errors/exceptions
------------------------------

If something goes wrong with :mod:`scripter`, it will usually raise a
:class:`scripter.Usage` exception. You may want to raise these too to avoid
users seeing python error codes.

The decorator :func:`scripter.exit_on_Usage` is provided for allowing
scripts to exit gracefully when errors occur. It is often a good idea to
decorate the main action for this purpose::

    from scripter import Usage, exit_on_Usage

    @exit_on_Usage
    def action(filename_obj, **kwargs):
        try:
            do_something()
        except NameError:
            raise Usage, 'could not do something'
            
    action()

This will cause the program to exit and tell the user "could not do something"




Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`

