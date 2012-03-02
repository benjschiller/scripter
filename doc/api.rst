.. scripter documentation master file, created by
   sphinx-quickstart on Thu Mar  1 16:51:12 2012.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.

scripter API
=============

.. toctree::
   :maxdepth: 2
 
.. warning:: Do not use private methods, they may change or disappear in future releases.


Classes
========
.. module:: scripter
.. autoclass:: Environment
   :members:
   :undoc-members:
   :private-members:
   
    .. automethod:: __init__

.. autoclass:: FilenameParser
   :members:
   :undoc-members:
   :private-members:
   
    .. automethod:: __init__

.. autoclass:: AnnounceExitFilter
   :members:
   :undoc-members:
   :private-members:
   
    .. automethod:: __init__


Exceptions
==========
.. autoclass:: InvalidFileException
    :show-inheritance:
.. autoclass:: Usage
    :show-inheritance:

Decorators
==========   
.. autofunction:: exit_on_Usage

Functions
=========
.. automodule:: scripter
   :members: assert_path, construct_target, extend_buffer, get_logger,
             is_valid_executable, leaves, path_to_executable, pformat_list,
             usage_info, valid_directories, valid_int

Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`

