#!/usr/bin/env python
'''
Common Options:
-h, --help          display this menu
-v, --version       give the current package version
--verbose           be verbose
--debug             be even more verbose
--quiet (default)   do not be verbose
--silent            do not output anything except errors

--find                      (find files automatically)
--target=foo                output to directory foo
-p[#], --num-cpus=[#]       Use at most [#] cpus
-r, --recursive                 continue with the next script, if available
'''
# See `Environment.__init__' definition #
# for valid flags            #
try: import multiprocessing
except ImportError: pass
import getopt
import sys
import os
import platform
import glob
import signal
import subprocess
import functools
import itertools
from functools import partial
import decorator
from decorator import decorator

global PROGRAM_NAME
PROGRAM_NAME = os.path.basename(sys.argv[0])

class InvalidFileException(ValueError):
    '''
    Exception for files that do not return a valid FilenameParser object
    '''
    def __init__(self, arg=None):
        super(InvalidFileException, self).__init__(arg)

@decorator
def exit_on_Usage(func, *args, **kargs):
    '''
    exit_on_Usage is a decorator
    that cause functions raising Usage to exit nicely
    '''
    try:
        return func(*args, **kargs)
    except Usage, err:
        print_debug(''.join([PROGRAM_NAME, ':']), str(err.msg))
        if locals().has_key('options'):
            if options.has_key('h') or options.has_key('help'): return 2
        print_debug("for help use --help")
        sys.exit(2)

class Environment(object):
    '''
    the base class for scripter
    
    provides an execution environment for jobs
    '''
    
    def __init__(self, short_opts='', long_opts=[], doc='',
                 version=''):
        self._script_version = version
        self._script_doc = doc
        self._unprocessed_sequence = []
        self._sequence = []
        self._script_kwargs = {}
        self._filename_parser = FilenameParser
        self._allow_action  = True
        self.source_dir = None
        self.target_dir = None
        self.allowed_extensions = None
        self.next_script = None
        self._is_first_time = True
        self.short_opts = "hvrp:" + short_opts
        self.verbosity_levels = ['debug', 'verbose', 'quiet', 'silent']
        self.long_opts = ["help", "version", "find", "target=", 
                          "num-cpus=", "recursive", "no-action"]
        self.long_opts.extend(self.verbosity_levels)
        self.long_opts.extend(long_opts)
        self._options = self.parse_argv()
        self._set_verbosity()
        self._exit_if_needed()
        self._set_initial_num_cpus()
        self._check_if_dry_run()
        return

    def _check_target_dir(self):
        '''
        check if user specified a target_dir
        '''
        if options.has_key('target'):
            if len(options['target'].strip()) is not 0:
                if self._target_dir is not None and verbose:
                    print_debug('Overriding target dir', self._target_dir,
                                'with user-specified output directory',
                                options['target'])
                self._target_dir = options['target']

    def get_target_dir(self):
        return self.target_dir

    def set_target_dir(self, target_dir):
        self.target_dir = target_dir
        return
        
    def get_source_dir(self):
        return self.source_dir

    def set_source_dir(self, source_dir):
        self.source_dir = source_dir
        return

    @exit_on_Usage
    def find_files(self):
        '''
        if --find, find any files that we can act upon
        uses the source_dir to find files to act upon
        returns a list of filename_parser instances with those files
        '''
        source_dir = self.get_source_dir()
        # Check if we need to find the files or if any were specified
        if source_dir is None:
            raise Usage('Cannot use --find without specifying a source',
                        'directory')
        if self.is_debug():
            print_debug('Searching for valid files')
            if self.allowed_extensions is not None:
                print_debug('Valid file extensions are',
                            ' '.join(self.allowed_extensions))
        filename_parser = self.get_filename_parser()
        parsed_filenames = []
        leaves_in_source_dir = leaves(source_dir)
        for leaf in leaves_in_source_dir:
            if self._is_valid_file(leaf):
                parsed_filenames.append(filename_parser(leaf))
        self._sequence.extend(parsed_filenames)
        return parsed_filenames

    def get_sequence(self):
        '''
        returns the sequence of FilenameParser objects for action
        '''
        options = self.get_options()
        # Always update the sequence before getting it
        if self._is_first_time:
            if self._options.has_key('find'):
                self.find_files()
            self._update_sequence()
            self._is_first_time = False
        sequence = self._sequence
        return sequence

    def _update_sequence(self, additional_sequence=[]):
        '''
        updates _sequence with additional_sequence and
        _unprocessed_sequence (if applicable)
        '''
        if self.is_debug():
            print_debug('Updating sequence...')
        if self.is_debug():
            print_debug('Checking for user-specified files')
            if self.allowed_extensions is not None:
                print_debug('Valid file extensions are',
                            ' '.join(self.allowed_extensions))
        filename_parser = self.get_filename_parser()
        # note, filenames get processed backward
        files = itertools.chain(_iter_except(self._unprocessed_sequence.pop,
                                             IndexError),
                                _iter_except(additional_sequence.pop,
                                             IndexError))
        for f in itertools.ifilter(self._is_valid_file, files):
            try:
                self._sequence.append(filename_parser(f))
            except InvalidFileException:
                continue
        return
            
    def _check_if_dry_run(self):
        '''check if this is a test run (no action)'''
        options = self._options
        self._allow_action = not options.has_key('no-action')
        return

    @exit_on_Usage
    def _exit_if_needed(self):
        '''
        exits if user requested help or version
        ''' 
        options = self._options
        # check for help
        if options.has_key('h') or options.has_key('help'):
            raise Usage(os.linesep.join([PROGRAM_NAME, __doc__,
                                         self._script_doc]))
        # check for version info
        elif options.has_key('v') or options.has_key('version'):
            raise Usage(PROGRAM_NAME, ': version ', self._script_version)
        return
    
    def _set_initial_num_cpus(self):
        '''
        set the number of cpus that we're going to use 
        '''
        # try to set number of cpus
        options = self._options
        num_cpus = 1
        try:
            if 'cpu_count' in dir(multiprocessing):
                num_cpus = multiprocessing.cpu_count()
        except NameError: pass
        # Check num-cpus/p
        if options.has_key('p'):
            num_cpus = int(options['p'])
        elif options.has_key('num-cpus'):
            num_cpus = int(options['num-cpus'])
        self._num_cpus = num_cpus
        return
        
    def get_options(self):
        '''
        returns a dictionary containing whose keys are the
        options as interpreted by parse_argv()
        and whose values are the corresponding values (or None)       
        '''
        return self._options

    def parse_any_opts(self, any_opts, short_to_long, update_script_kwargs=True,
                       replacement_value=True):
        """
        behaves like parse_long_opts
        
        but you must also provide a dictionary short_to_long which specifies
        the long variable names correspond to the single letter options
        i.e. {'a': 'apple', 'b': 'brain'}
        
        parse_any_opts will enforce "-" -> "_" name replacement
        and will also strip '=' or ':' from the end of names
        
        if a key is not in short_to_long, then we will leave it unchanged
        parse_short_opts(require_long = False) is equivalent to
        parse_any_opts()
        """
        return self.parse_short_opts(short_opts, short_to_long,
                                     require_long=False,
                                     
                                     update_script_kwargs=update_script_kwargs,
                                     replacement_value = replacement_value)

    def parse_short_opts(self, short_opts, short_to_long, require_long=True,
                         update_script_kwargs=True, replacement_value=True):
        """
        parse_short_opts behaves like parse_long_opts
        
        but you must also provide a dictionary short_to_long which specifies
        the long variable names correspond to the single letter options
        i.e. {'a': 'apple', 'b': 'brain'}
        
        parse_short_opts will enforce "-" -> "_" name replacement
        and will also strip '=' or ':' from the end of names
        
        if require_long = True, then any item in short_opts must be present
        as a key in short_to_long. if require_long is False, then we will leave
        keys unchanged when they are not present.
        parse_short_opts(require_long = False) is equivalent to
        parse_any_opts()
        """
        kwargs = self.parse_long_opts(short_opts, update_script_kwargs=False,
                                      replacement_value=replacement_value)
        real_kwargs = {}
        for k, v in kwargs:
            if require_long:
                option = short_to_long[k]
            else:
                if short_to_long.has_key(k): option = short_to_long[k]
                else: option = k
            pyoption = "_".join(option.split("-")).rstrip(':=')
            real_kwargs[option] = v
        if update_script_kwargs: self.update_script_kwargs(real_kwargs)
        return real_kwargs

    def parse_long_opts(self, long_opts, update_script_kwargs=True,
                        replacement_value = True):
        """
        parse_long_opts behaves like parse_boolean_opts, except that it assigns
        the argument for option to the dictionary of keywords,
        i.e --foo=boo --> {'foo': 'boo'}

        parse_long_opts will enforce "-" -> "_" name replacement
        and will also strip '=' or ':' from the end of names
        
        the exception is that '' is translated to True
        so parse_long_opts can still handle boolean options)
        You may override what value is used instead of True by setting
        replacement_value to something else
        
        by default, this method will also add the dictionary to the Environment
        instance's script_kwargs using update_script_kwargs
        this behavior can be disabled with update_script_kwargs = False
        
        e.g. if self.get_options() = {'help': '', 'flag': 'red'}, then
        >>> parse_boolean_opts(['flag', 'help'])
        {'flag': 'red', 'help': None}
        """
        kwargs = {}
        options = self.get_options()
        for option in boolean_opts:
            pyoption = "_".join(option.split("-")).rstrip(':=')
            if options[option] == '':
                kwargs[pyoption] = replacement_value
            else:
                kwargs[pyoption] = option[option]
        if update_script_kwargs: self.update_script_kwargs(kwargs)
        return kwargs
    
    def parse_boolean_opts(self, boolean_opts, update_script_kwargs=True):
        '''
        parse_boolean_opts takes a list of boolean options and
        returns a dictionary with whether those options were present in argv
        (changes "-" to "_" in variable names where appropriate)
        
        by default, this method will also add the dictionary to the Environment
        instance's script_kwargs using update_script_kwargs
        this behavior can be disabled with update_script_kwargs = False
        
        e.g. if self.get_options() = {'help': None}, then
        >>> parse_boolean_opts(['flag', 'help'])
        {'flag': True, 'help': False}
        '''
        kwargs = {}
        options = self.get_options()
        for option in boolean_opts:
            pyoption = "_".join(option.split("-")).rstrip(':=')
            kwargs[pyoption] = options.has_key(option)
        if update_script_kwargs: self.update_script_kwargs(kwargs)
        return kwargs

    @exit_on_Usage
    def parse_argv(self):
        '''
        launches getopt.gnu_getopt to validate options from sys.argv
        also adds any explicitly mentioned files to sequence, if needed
        
        uses self.short_opts and self.long_opts
        '''
        try:
            opts, args = getopt.gnu_getopt(sys.argv[1:],
                                           self.short_opts, self.long_opts)
        except getopt.error, msg:
            raise Usage(str(msg))
        options = {}
        for k, v in opts:
            options[k.lstrip('-')] = v # with -'s stripped
        # parse filenames too
        self._unprocessed_sequence.extend(args)
        return options

    @exit_on_Usage
    def _set_verbosity(self):
        options = self._options
        verbosity_levels = self.verbosity_levels
        # check verbosity
        for verbosity in verbosity_levels:
            setattr(self, '_' + verbosity, options.has_key(verbosity))

        if sum([getattr(self, '_' + verbosity) for
                verbosity in verbosity_levels]) > 1:
            raise Usage('can only specify at most one of ', 
                        ', '.join(['--' + x for x in verbosity_levels]))
        # debug implies verbose
        if self._debug: self._verbose = True
        return

    def get_verbose_kwargs(self):
        verbose_kwargs = {'silent': self.is_silent(),
                          'quiet': self.is_quiet(),
                          'verbose': self.is_verbose(),
                          'debug': self.is_debug()}
        return verbose_kwargs

    def disable_action(self):
        '''
        disables do_action (execution will return None)
        '''
        self._allow_action = False
        return
        
    def enable_action(self):
        '''
        enables do_action
        '''
        self._allow_action = True
        return

    def set_filename_parser(self, filename_parser):
        '''
        use the provided filename parser instead of the default one
        '''
        self._filename_parser = filename_parser
        return
    
    def get_filename_parser(self, with_args=True):
        '''
        returns the class being used as the filename parser
        
        if with_args is True, then partial is used to apply arguments as
        appropriate
        '''
        
        if with_args:
            if self.is_debug():
                print_debug('Using', str(self._filename_parser.__name__),
                            'with kwargs',
                            str(self.get_fp_kwargs()))
            return partial(self._filename_parser, **self.get_fp_kwargs())
        else:
            if self.is_debug():
                print_debug('Using', str(self._filename_parser.__name__),
                            'without kwargs')
            return self._filename_parser

    def set_num_cpus(self, num):
        '''
        return the number of cpus to be used
        if num is not None, set the number of cpus to be used before returning
        '''
        self._num_cpus = num
        return
    
    def get_num_cpus(self):
        '''
        return the number of cpus to be used
        if num is not None, set the number of cpus to be used before returning
        '''
        return self._num_cpus

    def is_silent(self):
        return self._silent
    
    def is_quiet(self):
        return self._verbose

    def is_verbose(self):
        return self._verbose

    def is_debug(self):
        return self._debug

    def get_action_kwargs(self):
        '''
        get the kwargs (a dictionary) for action
        '''
        kwargs_items = itertools.chain(self.get_verbose_kwargs().iteritems(),
                                       self.get_script_kwargs().iteritems())
        return dict((item for item in kwargs_items))

    def add_script_kwarg(self, key, value, override=True):
        '''
        update the script-level kwargs with provided dictionary
        with key, value pair
        (if override=False, do not override existing value if key exists)
        '''
        if override:
            self._script_kwargs.update({key: value})
        else:
            if not self._kwargs.has_key(key):
                self._kwargs[key] = value

    def update_script_kwargs(self, update_dict):
        '''
        update the script-level kwargs with provided dictionary
        used by both action and filename parser
        '''
        self._script_kwargs.update(update_dict)

    def get_script_kwargs(self):
        return self._script_kwargs

    def get_fp_kwargs(self):
        '''
        get the kwargs (a dictionary) for the filename parser
        '''
        source_dir_item = ('source_dir', self.get_source_dir())
        target_dir_item = ('target_dir', self.get_target_dir())
        kwargs_items = itertools.chain(self.get_verbose_kwargs().iteritems(),
                                       self.get_script_kwargs().iteritems(),
                                       (target_dir_item, source_dir_item))
        return dict((item for item in kwargs_items))
   
    def _is_valid_file(self, f):
        '''checks if a file is valid for processing'''
        if not os.path.isfile(f):
            if self.is_debug():
                print_debug('Skipping', _quote(f), '. It is not a file.')
            return False
        elif f.startswith('.'):
            print_debug('Skipping hidden file', _quote(f))
            return False
        elif self.allowed_extensions is None:
            return True
        else:
            file_ext = os.path.splitext(f)[1].lstrip(os.extsep)
            if file_ext in self.allowed_extensions:
                return True
            else:
                if self.is_debug():
                    print_debug('Skipping', _quote(f), 'because file',
                                'does not have a valid file extension')
                return False
    
    @exit_on_Usage 
    def do_action(self, action):
        '''
        executes an action
        
        actions should be functions that at least take FilenameParser objects
        '''
        sequence = list(self.get_sequence())
        if len(sequence) == 0:
            raise Usage('No input files specified. Nothing to do.')
        if not self._allow_action:
            print_debug('Test run. Nothing done.')
            print_debug('I would have acted on these files:',
                        ', '.join([str(f) for f in sequence]))
            return self.execute_next_script()
        
        kwargs = self.get_action_kwargs()

        max_cpus = len(sequence)
        if self.is_debug(): print_debug('Debugging mode enabled')
    
        used_cpus = min([self.get_num_cpus(), max_cpus])
    
        if used_cpus == 1:
            if self.is_debug(): print_debug('multiprocessing disabled')
            for item in sequence:
                stdout = action(item, **kwargs)
                if not self.is_silent() and stdout is not None:
                    print >>sys.stdout, stdout
        else:
            if self.is_debug():
                print_debug('WARNING: multiprocessing enabled', os.linesep,
                            'debug output may get mangeled')
            if self.is_verbose():
                print_debug('Using', str(used_cpus), 'cpu(s)...')
            if not platform.system() == 'Windows':
                signal.signal(signal.SIGCHLD, signal.SIG_DFL)
            p = multiprocessing.Pool(processes=used_cpus)
            results = [p.apply_async(action, (item,), kwargs) for
                       item in sequence]
            stdouts = (result.get() for result in results)
            stdouts_good = itertools.ifilter(lambda x: x is not None, stdouts)
            if not self.is_silent() and stdouts is not None:
                print >>sys.stdout, os.linesep.join(stdouts_good)
                
        return self.execute_next_script()
    
    def execute_next_script(self):
        '''
        execute the next script
        
        if there isn't one, then die
        '''
        if self.next_script is not None:
            if debug: print_debug('Launching the next script', NEXT_SCRIPT)
            # always proceed with --find
            next_script_args = ["--find"]
            # pass along verbosity level
            for verbosity in self.verbosity_levels:
                exec(''.join(["next_script_args.append('", verbosity, "')"]))
            os.execlp(self.next_script, "--find")
        else:
            sys.exit(0)
    
def _quote(s):
    return ''.join(["'", s ,"'"])

class Usage(Exception):
    def __init__(self, *args):
        self.msg = ''.join(args)

    def __str__(self):
        return self.msg

def print_debug(*args):
    statement = ' '.join(args)
    print >>sys.stderr, statement

def assert_path(path):
    '''if path does not exist, raise IOError'''
    if path is None: raise IOError('NoneType is not a valid path')
    if os.path.exists(path): return True
    else: raise IOError(' '.join(['File or directory', path, 'not found']))

class FilenameParser(object):
    @exit_on_Usage
    def __init__(self, filename,
                 source_dir=None, target_dir=None,
                 verbose=False, debug=False,
                 *args, **kwargs):

        self._debug = debug
        self.additional_args = args
        self.__dict__.update(kwargs)

        if debug: print_debug('Parsing filename', filename)

        self.set_input_file(filename)

        self.input_dir = os.path.split(self.input_file)[0]
        if self.input_dir == '': self.input_dir = os.curdir
        if debug: print_debug('Using', self.input_dir, 'as input_dir')
        self.file_extension = os.path.splitext(
                                self.input_file)[1].lstrip(os.extsep)

        if target_dir is not None: self.target_dir = target_dir
        else: raise Usage('Must specify an output directory with --target')
        if debug: print_debug('Using', self.target_dir, 'as target_dir')

        # Make sure we have the right output dir
        # Try to build target_dir/x/y/z from source_dir/x/y/z in input path
        # then resort to input_dir
        try:
            fn_parts = filename.split(os.sep)
            source_dir_index = fn_parts.index(source_dir)
            self.output_dir = os.path.join(self.target_dir,
                                           *fn_parts[source_dir_index+1:-1])
        except ValueError:
                self.output_dir = self.target_dir
       
        if debug: print_debug('Using', self.output_dir, 'as output_dir')
        self.check_output_dir(self.output_dir)

        self.protoname = os.path.splitext(
                            os.path.basename(self.input_file))[0]

    def __str__(self):
        return self.input_file

    def __repr__(self):
        return self.input_file

    def set_input_file(self, filename):
        if self._debug: print_debug('Checking for', filename, '...')
        assert_path(filename)
        self.input_file = filename

    def check_output_dir(self, output_dir):
        # Make the output directory, complain if we fail
        if os.path.exists(output_dir):
            if self._debug: print_debug('Output directory', 
                                    _quote(output_dir), 'already exists')
        else:
            if self._debug: print_debug('Creating directory',
                                        _quote(output_dir))
            os.makedirs(output_dir, mode=0755)
            if not os.path.exists(output_dir):
                raise IOError('Could not create directory ' + output_dir)

    def with_extension(self, ext):
        '''Path to output file with extension'''
        return os.extsep.join([self.protoname, ext])


@exit_on_Usage
def leaves(dir_or_file, allow_symlinks = True, ignore_hidden_files = True,
           max_depth = None):
    '''takes as input a VALID path and descends into all directories

    WARNING:
    this *will* get caught in an infinite loop if you have a symlink
    which references a node above itself in tree
    '''
    def is_hidden(node):
        return ignore_hidden_files and node.startswith('.')
    
    # Check sanity
    if not os.path.exists(dir_or_file):
        raise Usage(' '.join([dir_or_file, 'does not exist']))

    # Base case
    if os.path.isfile(dir_or_file) and not dir_or_file.startswith('.'):
        if debug: print_debug('Found file', dir_or_file)
        return dir_or_file

    # Recurse
    files = []
    for node in os.listdir(dir_or_file):
        node_path = os.path.join(dir_or_file, node)
        if os.path.isdir(node_path):
            if max_depth is None:
                files.extend(leaves(node_path, allow_symlinks=allow_symlinks,
                                    ignore_hidden_files=ignore_hidden_files,
                                    max_depth=max_depth))
            elif max_depth > 1:
                files.extend(leaves(node_path, allow_symlinks=allow_symlinks,
                                    ignore_hidden_files=ignore_hidden_files,
                                    max_depth=max_depth-1))
            elif max_depth == 1:
                if os.path.isfile(node_path) and not is_hidden(node):
                    files.append(node_path)
            else:
                break
        elif os.path.isfile(node_path) and not is_hidden(node_path):
            files.append(node_path)
    return files

def valid_directories(directory):
    '''wrapper for glob.glob, enforces that output must be a valid directory'''
    directories = [defir for dir in glob.glob(directory) if os.path.isdir(dir)]
    directories.reverse #to use the newest version, in case we have foo-version
    return directories

@exit_on_Usage
def path_to_executable(name, directories=None):
    """
    construct the path to the executable, search in order
    
    the directory specified (or any directory that matches with Unix
                             style pathname pattern expansion*)
    then env PATH
    then the current directory
    then give up

    *we reverse the order so that we will usually get the newest version
    """
    # if name is a list, iterate over it to find exe and catch errors
    if type(name) is list:
        for try_name in name:
            try: path_to = path_to_executable(try_name)
            except Usage: continue
            return path_to
    if type(name) is list:
        raise Usage("Could not find an executable with any of these names:",
                    ", ".join(name))

    if type(directories) is list:
       for d in directories:
           try: path_to = path_to_executable(name, directories)
           except Usage: continue 
           return path_to

    #try specified directory
    if directories is not None:
        for directory in valid_directories(directories):
            full_path = os.path.join(directory, name)
            if os.path.exists(full_path):
                if objects.access(full_path, os.X_OK):
                    return full_path
    #try PATH
    try: PATH = os.environ['PATH']
    except NameError:
        try: PATH = os.defpath
        except NameError: raise Usage("Could not determine PATH")
    for p in PATH.split(os.pathsep):
        full_path = os.path.join(p, name)
        if os.path.exists(full_path):
            if os.access(full_path, os.X_OK):
                return full_path
            
    # check if we're on Windows, and try a little harder
    if platform.system() == 'Windows':
        all_exes = itertools.ifilter(lambda f: f.endswith('exe'),
                    itertools.chain(
                        leaves(os.environ['PROGRAMFILES'], max_depth=2),
                        leaves(os.environ['PROGRAMFILES(X86)'], max_depth=2)
                    ))
        namex = name + os.extsep + 'exe'
        for exe in all_exes:
            exename = os.path.split(exe)[1]
            if (exename == name or exename == namex) and os.access(exe, os.X_OK):
                return exe # success
        
    #give up
    raise Usage("Could not find executable ", name)

def usage_info():
    return ' '.join(['Usage:', PROGRAM_NAME, '[OPTIONS]', 'FILE(S)'])

@exit_on_Usage
def valid_int(thing, msg, vmin, vmax):
    """
    checks if something is a valid integer
    and thing >= vmin and thing <= vmax

    returns the thing as an integer
    """
    try:
        int_thing = int(thing)
    except ValueError:
        try: raise Usage(msg)
        except NameError:
            raise Usage("Undefined variable is not a valid integer")

    if int_thing < vmin or int_thing > vmax:
        try: raise Usage(msg)
        except NameError:
            raise Usage("Undefined variable is not a valid integer")
    return int_thing


def extend_buffer(b, x, spacerlines=0):
    """extends buffer b with string x, ignores if x is None"""
    if b is None or x is None: return b
    else: return os.linesep.join([b] + [""]*spacerlines  + [x])

def _iter_except(func, exception, first=None):
    """
    Taken from http://docs.python.org/library/itertools.html
    This function is freely distributable and not covered by the license
    
    Call a function repeatedly until an exception is raised.

    Converts a call-until-exception interface to an iterator interface.
    Like __builtin__.iter(func, sentinel) but uses an exception instead
    of a sentinel to end the loop.

    Examples:
        bsddbiter = iter_except(db.next, bsddb.error, db.first)
        heapiter = iter_except(functools.partial(heappop, h), IndexError)
        dictiter = iter_except(d.popitem, KeyError)
        dequeiter = iter_except(d.popleft, IndexError)
        queueiter = iter_except(q.get_nowait, Queue.Empty)
        setiter = iter_except(s.pop, KeyError)

    """
    try:
        if first is not None:
            yield first()
        while 1:
            yield func()
    except exception:
        pass
