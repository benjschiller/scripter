#!/usr/bin/env python
# See `Environment.__init__' definition for valid flags #
import multiprocessing
import argparse
import sys
try: import sysconfig
except ImportError: pass
import os
import platform
import glob
import signal
import subprocess
import time
import getpass
import pprint
import functools
import itertools
from functools import partial
import decorator
from decorator import decorator
from errno import ENOENT
import logging
global PROGRAM_NAME
PROGRAM_NAME = os.path.basename(sys.argv[0])
from pkg_resources import get_distribution
VERSION = get_distribution('scripter').version
__version__ = VERSION

# set up the module-level logger
LOGGER = multiprocessing.log_to_stderr()
LOGGER.setLevel(logging.CRITICAL)

debug = LOGGER.debug
info = LOGGER.info
warning = LOGGER.warning
error = LOGGER.error
critical = LOGGER.critical
log = LOGGER.log
exception = LOGGER.exception

def pformat_list(L):
    """
    Takes a list and turns each item into a str
    then returns the pretty-printed version of that list
    """
    return pprint.pformat([str(itm) for itm in L])

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
        sys.stderr.write('%s: %s\n' % (PROGRAM_NAME, err.msg))
        sys.stderr.write("for help use --help\n")
        sys.exit(2)

class Environment(object):
    '''
    the base class for scripter
    
    provides an execution environment for jobs
    '''
    def __init__(self, doc=None, version='', handle_files=True):
        self._script_version = version
        self._unprocessed_sequence = []
        self._sequence = []
        self._script_kwargs = {}
        self._filename_parser = FilenameParser
        self._num_cpus = None
        self._config_reader = None
        self._config_writer = None
        self.allowed_extensions = None
        self.next_script = None
        self._is_first_time = True
        parser = argparse.ArgumentParser(description=doc)
        self.argument_parser = parser
        version_str = '%(prog)s {0!s} (scripter {1!s})'.format(version,
                                                               __version__)
        parser.add_argument('-v', '--version',
                            help='show version info and exit',
                            action='version', version=version_str)
        parser.add_argument('-p', '--num-cpus', nargs='?',
                            help='specify the number of maximum # CPUs to use',
                            default=multiprocessing.cpu_count())
        vgroup = parser.add_mutually_exclusive_group()
        vgroup.add_argument('--debug', help='Sets logging level to DEBUG',
                           dest='logging_level', action='store_const',
                           const=logging.DEBUG)
        vgroup.add_argument('--info', default=logging.INFO,
                           help='Sets logging level to INFO [default]',
                           dest='logging_level', action='store_const',
                           const=logging.INFO)
        vgroup.add_argument('--quiet', help='Sets logging level to WARNING',
                           dest='logging_level', action='store_const',
                           const=logging.WARNING)
        vgroup.add_argument('--silent', help='Sets logging level to ERROR',
                           dest='logging_level', action='store_const',
                           const=logging.ERROR)
        parser.set_defaults(logging_level=logging.INFO)
        parser.add_argument('--target', dest='target', nargs='?')
        parser.add_argument('--no-target', action='store_true',
                            help='Write new files in the current directory / do not preserve directory structure')
        parser.add_argument('--recursive', '-r',
                            help='Recurse through any directories listed looking for valid files')
        parser.add_argument('--no-action', '--do-nothing', '--dry-run',
                            dest='allow_action', default=True,
                            action='store_false', help="Don't act on files")
        parser.add_argument('--config', help='Use configuration in file foo')
        if handle_files:
            parser.add_argument('files', nargs='+',
                                help='A list of files to act upon (wildcards ok)')
        return

    def set_config_reader(self, reader):
        """
        will be called as reader(vars(parser.parse_args())['config'])
        """
        self._config_reader = reader

    def set_config_writer(self, writer):
        """
        will be called as writer(**parser.parse_args())
        """
        self._config_writer = writer

    def get_sequence(self, **kwargs):
        '''
        returns the sequence of FilenameParser objects for action
        
        Running this more than once will not do anything
        '''
        if self._is_first_time:
            self._update_sequence(**kwargs)
            self._is_first_time = False
        sequence = self._sequence
        return sequence

    def _update_sequence(self, files=[], recursive=False, **kwargs):
        '''
        updates _sequence with files specified at command line (wildcards ok)
        '''
        debug('Updating sequence of files...')
        debug('Checking for user-specified files...')
        # process wildcards as needed
        unprocessed_files = []
        for item in _iter_except(files.pop, IndexError):
            files = glob.glob(item)
            if len(files) == 1: unprocessed_files.append(files[0])
            elif len(files) > 1: unprocessed_files.extend(files)
        if self.allowed_extensions is not None:
            debug('Valid file extensions are %s',
                  ' '.join(self.allowed_extensions))
        if len(unprocessed_files) > 0:
            debug('Found the following files:')
            debug(pformat_list(unprocessed_files))
        filename_parser = self.get_filename_parser(**kwargs)
        # note, filenames get processed backward
        files = itertools.chain(_iter_except(unprocessed_files.pop, IndexError))
        sequence = self._sequence
        for f in files:
            if recursive and self._is_valid_dir(f):
                debug('Searching for valid files in f')
                for leaf in leaves(f):
                    if self._is_valid_file(leaf):
                        try:
                            appendable = filename_parser(leaf)
                            sequence.append(appendable)
                        except InvalidFileException:
                            pass
            elif self._is_valid_file(f):
                try: sequence.append(filename_parser(f))
                except InvalidFileException: pass
        return
        
    def set_filename_parser(self, filename_parser):
        '''
        use the provided filename parser instead of the default one
        '''
        self._filename_parser = filename_parser
        return
    
    def get_filename_parser(self, **kwargs):
        '''
        returns the class being used as the filename parser
        
        if with_args is True, then partial is used to apply arguments as
        appropriate
        '''
        if kwargs is not None:
            debug('Using %s with the following kwargs:',
                  self._filename_parser.__name__)
            debug('\n%s', pprint.pformat(kwargs))
            return partial(self._filename_parser, **kwargs)
        else:
            debug('Using %s', self._filename_parser.__name__)
            return self._filename_parser

    def override_num_cpus(self, num):
        """
        override the number of processes we're going to start
        """
        self._num_cpus = num
        return
   
    @staticmethod 
    def _is_valid_dir(f):
        '''
        checks if a directory is valid
        '''
        if not os.access(f, os.F_OK + os.R_OK + os.X_OK):
            return False
        else:
            return os.path.isdir(f)
        
    def _is_valid_file(self, f):
        '''
        checks if a file is valid for processing
        '''
        if not os.abort()path.isfile(f):
            debug('Skipping %s. It is not a file.', _quote(f))
            return False
        elif f.startswith('.'):
            debug('Skipping hidden file %s', _quote(f))
            return False
        elif self.allowed_extensions is None:
            return True
        else:
            file_ext = os.path.splitext(f)[1].lstrip(os.extsep)
            if file_ext in self.allowed_extensions:
                return True
            else:
                debug('Skipping %s because file does not have a valid file '
                      'extension', _quote(f))
                return False
    
    @exit_on_Usage 
    def do_action(self, action, stay_open=False):
        '''
        executes an action
        
        actions should be functions that at least take FilenameParser objects
        '''
        args = self.argument_parser.parse_args()
        context = vars(args)
        # read config if user supplies method
        if context['config'] is not None:
            if self._config_reader is None: raise NotImplementedError ### FINISH
            cfg_opts = self._config_reader(context['config'])
            context.update(cfg_opts)
        
        self._options = context
        LOGGER.setLevel(context['logging_level'])
        
        num_cpus = self._num_cpus or context['num_cpus']
        allow_action = context['allow_action']
        
        sequence = self.get_sequence(**context)
        
        if len(sequence) == 0:
            raise Usage('No input files specified or found. Nothing to do.')
        if not allow_action:
            info('Test run. Nothing done.')
            info('I would have acted on the following files:') 
            info(pformat_list(sequence))
            sys.exit(0)
        
        max_cpus = len(sequence)
        debug('Debugging mode enabled')
    
        used_cpus = min([num_cpus, max_cpus])
    
        # write config if user supplies method
        if self._config_writer is not None:
            self._config_writer(**context)
        
        # Create output directory if it doesn't exist
        for item in sequence:
            item.check_output_dir(item.output_dir)
        
        if used_cpus == 1:
            debug('multiprocessing disabled')
            for item in sequence:
                stdout = action(item, **context)
                if not LOGGER.getEffectiveLevel() >= 50 and stdout is not None:
                    print >>sys.stdout, stdout
        else:
            signal.signal(signal.SIGCHLD, signal.SIG_DFL)
            debug('multiprocessing enabled')
            p = multiprocessing.Pool(processes=used_cpus)
            debug('Initialized pool of %d workers', used_cpus)
            results = [p.apply_async(action, (item,), context) for
                       item in sequence]
            stdouts = (result.get() for result in results)
            stdouts_good = filter(lambda x: type(x) is str, stdouts)
            if not LOGGER.getEffectiveLevel() >= 50 and stdouts_good is not None:
                print >>sys.stdout, os.linesep.join(stdouts_good)

        if self.next_script is not None:
            return self.execute_next_script()
        if not stay_open:
            sys.exit(0)
    
    def execute_next_script(self):
        '''
        execute the next script
        '''
        raise NotImplementedError
        os.execlp(self.next_script, "--find")
    
def _quote(s):
    return ''.join(["'", s ,"'"])

class Usage(Exception):
    def __init__(self, *args):
        self.msg = ''.join(map(str, args))

    def __str__(self):
        return self.msg

def assert_path(path):
    '''if path does not exist, raise IOError'''
    if path is None: raise IOError('NoneType is not a valid path')
    if os.path.exists(path): return True
    else:
        raise IOError(ENOENT, os.strerror(ENOENT), path)

def construct_target(name=None):
    if name is None: name = PROGRAM_NAME
    try: name = name[0:name.index('.py')]
    except ValueError: pass
    date = time.strftime("%m-%d-%Y", time.localtime())
    user = getpass.getuser()
    t = '_'.join([name, date, user])
    i = 0
    while True:
        target = '%s.%s' % (t, i)
        if os.path.exists(target): i += 1
        else: break
    return target

class FilenameParser(object):
    """
    The default FilenameParser class included with scripter
    
    its one mandatory argument is a filename
    it must accept arbitrary **kwargs or it will be very unhappy
    
    It is recommend you customize this class for parsing filenames as needed
    """
    @exit_on_Usage
    def __init__(self, filename, drop_parent_name=True,
                 target=None, no_target=False, *args, **kwargs):
        self.additional_args = args
        self.__dict__.update(kwargs)

        debug('Parsing filename %s', filename)

        self.set_input_file(filename)

        input_dir = os.path.relpath(os.path.split(self.input_file)[0] or '.')
        self.input_dir = input_dir
        debug('Using %s as input_dir', input_dir)
        self.file_extension = os.path.splitext(self.input_file)[1][1:]

        if no_target:
            output_dir = '.'
        else:
            target_dir = construct_target(target)
            if drop_parent_name:
                path_by_folder = input_dir.split(os.sep)
                if len(path_by_folder) == 1:
                    if path_by_folder[0] in ['.', '..']:
                        output_dir = target_dir
                    else:
                        output_dir = os.path.join(target_dir, input_dir)
                else:
                    while True:
                        try: folder = path_by_folder.pop(0)
                        except IndexError:
                            output_dir = target_dir
                            break
                        if folder == '..': continue
                        else:
                            more_dirs = os.path.join(folder, *path_by_folder)
                            output_dir = os.path.join(target_dir, more_dirs)
            else:
                output_dir = os.path.join(target_dir, input_dir)
        self.output_dir = output_dir
        debug('Using %s as output_dir', self.output_dir)

        self.protoname = os.path.splitext(
                            os.path.basename(self.input_file))[0]

    def __str__(self):
        return self.input_file

    def __repr__(self):
        return self.input_file

    def set_input_file(self, filename):
        debug('Checking for %s ...', filename)
        assert_path(filename)
        self.input_file = filename

    def check_output_dir(self, output_dir):
        # Make the output directory, complain if we fail
        if os.path.exists(output_dir):
            debug('Output directory %s already exists', _quote(output_dir))
        else:
            debug('Creating directory "%s"', output_dir)
            os.makedirs(output_dir, mode=0755)
            if not os.path.exists(output_dir):
                raise IOError('Could not create directory %s' % output_dir)

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
        debug('Found file %s', dir_or_file)
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
    directories = [dir for dir in glob.glob(directory) if os.path.isdir(dir)]
    directories.reverse #to use the newest version, in case we have foo-version
    return directories

def path_to_executable(name, directories=None, max_depth=2):
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
    # bug workaround
    if type(name) is list:
        for try_name in name:
            try:
                path_to = _path_to_executable(try_name,
                                              directories=directories,
                                              max_depth=max_depth)
            except StandardError: continue
            return path_to
        error("Could not find an executable with any of these names: %s",
                    ", ".join(name))
        return
    else:
        try: path_to = _path_to_executable(name,
                                           directories=directories,
                                           max_depth=max_depth)
        except StandardError:
            error("Could not find executable %s", name)
            return
        return path_to
        
def _path_to_executable(name, directories=None, max_depth=2):
    using_windows = platform.system() == 'Windows'

    #try specified directory
    if directories is not None:
        if type(directories) is not list: directories = [directories]
        for d in directories:
            for directory in valid_directories(d):
                full_path = os.path.join(directory, name)
                if is_valid_executable(full_path):
                    return full_path
                if using_windows and is_valid_executable(full_path + '.exe'):
                    return full_path + '.exe'
            
    #try PATH
    try: PATH = os.environ['PATH']
    except NameError:
        try: PATH = os.defpath
        except NameError: raise Usage("Could not determine PATH")
    for p in PATH.split(os.pathsep):
        full_path = os.path.join(p, name)
        if is_valid_executable(full_path):
            return full_path
        if using_windows and is_valid_executable(full_path + '.exe'):
            return full_path + '.exe'
            
    #try python scripts
    try:
        script_path = sysconfig.get_path('scripts')
        full_path = os.path.join(script, name)
        if is_valid_executable(full_path):
            return full_path
        if using_windows and is_valid_executable(full_path + '.exe'):
            return full_path + '.exe'
    except NameError, AttributeError: pass
        
    # check if we're on Windows, and try a little harder
    if using_windows:
        all_exes = itertools.ifilter(lambda f: f.endswith('exe'),
                    itertools.chain(
                                    leaves(os.environ['PROGRAMFILES'],
                                           max_depth=max_depth),
                                    leaves(os.environ['PROGRAMFILES(X86)'],
                                           max_depth=max_depth)
                    ))
        namex = name + '.exe'
        for exe in all_exes:
            exename = os.path.split(exe)[1]
            if (exename == name or exename == namex) and \
                is_valid_executable(exe):
                    return exe # success
    
    # give up
    raise StandardError

def is_valid_executable(filename):
    """
    checks if a filename is a valid executable
    """
    if os.path.exists(filename):
        if os.access(filename, os.X_OK):
            return filename
    return False

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

def get_logger(level=logging.WARNING):
    """
    get_logger(level=WARNING) wraps multiprocessing.get_logger()
    
    adds an AnnounceExitFilter to prevent output from getting very garbled
    at program exit
    """
    logger = multiprocessing.get_logger()
    logger.addFilter(AnnounceExitFilter(False))
    logger.setLevel(level)
    return logger

class AnnounceExitFilter(object):
    """
    rejects messages announcing thread exit iff the initial condition is False

    looks for specific messages hardcoded into multiprocessing/pool.py
    see source for more details
    """
    def __init__(self, announce_exit):
        self._announce_exit = announce_exit
        super(AnnounceExitFilter, self).__init__()

    def filter(self, record):
        if record.getMessage().startswith('worker got sentinel') or \
           record.getMessage().startswith('worker exiting') or \
           record.getMessage().startswith('recreated blocker') or \
           record.getMessage().startswith('process shutting down') or \
           record.getMessage().startswith('running all "atexit"') or \
           record.getMessage().endswith('closing conn') or \
           record.getMessage().startswith('DECREF'):
            return self._announce_exit
        else:
            return True