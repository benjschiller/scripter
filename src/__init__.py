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
# See `main_body' definition #
# for valid flags            #
import getopt
import sys
import os
import signal
import subprocess
import functools
from functools import partial

global NUM_CPUS
try:
    import multiprocessing
    NUM_CPUS = multiprocessing.cpu_count()
except ImportError:
    NUM_CPUS = 1

global PROGRAM_NAME
global CURRENT_PATH
global SOURCE_DIR
global TARGET_DIR
global ALLOWED_EXTENSIONS
PROGRAM_NAME = os.path.basename(sys.argv[0])
CURRENT_PATH = os.curdir + os.sep
SOURCE_DIR = None
TARGET_DIR = None
ALLOWED_EXTENSIONS = None
NEXT_SCRIPT = None

def _quote(s):
    return ''.join(["'",s,"'"])

def _documentation():
    try:
        doc = SCRIPT_DOC + __doc__
    except NameError:
        doc = __doc__
        pass
    finally:
        return doc

class Usage(Exception):
    def __init__(self, *args):
        self.msg = ''.join(args)

def print_debug(*args):
    statement = ' '.join(args)
    print >>sys.stderr, statement

def assert_path(path):
    '''if path does not exist, raise IOError'''
    if os.path.exists(path): return True
    else: raise IOError(' '.join(['File or directory', path, 'not found']))

class FilenameParser(object):
    def __init__(self, filename,
                 source_dir=None, target_dir=None,
                 verbose=False, debug=False,
                 is_dummy_file=False,
                 *args, **kwargs):

        self._debug = debug
        self.is_dummy_file = is_dummy_file

        self.additional_args = args
        self.__dict__.update(kwargs)

        if debug: print_debug('Parsing filename', filename)

        if not is_dummy_file:
            self.set_input_file(filename)
        else:
            if debug: print_debug('Using dummy file to gather information')
            self.input_file = filename

        if not is_valid_file(self.input_file) and not is_dummy_file:
            if debug: print_debug('Skipping file because it does not have',
                                  'a valid file extension')
            self.is_invalid = True
            return
        else:
            self.is_invalid = False

        self.input_dir = os.path.split(self.input_file)[0]
        self.file_extension = os.path.splitext(
                                self.input_file)[1].lstrip(os.extsep)


        self.source_dir = source_dir
        if self.source_dir is None and debug:
            print_debug('No source_dir specified')
        elif debug:
            print_debug('Using', self.source_dir, 'as source_dir')

        if target_dir is not None:
            self.target_dir = target_dir
        elif TARGET_DIR is not None:
            self.target_dir = TARGET_DIR
        else:
            raise Usage('Must specify an output directory with --target')
        if debug: print_debug('Using', self.target_dir, 'as target_dir')
    
        if self.source_dir is not None and not is_dummy_file:
            try:
                assert_path(source_dir)
                if debug: print_debug('Using', source_dir, 'as source_dir')

                fn_parts = filename.split(os.sep)
                source_dir_index = fn_parts.index(source_dir)
                
                self.output_dir = os.path.join(self.target_dir,
                                          *fn_parts[source_dir_index+1:-1])
            except IOError:
                source_dir = os.curdir
                if debug: print_debug('Using', source_dir, 'as source_dir')
                self.output_dir = self.target_dir
        else:
            self.output_dir = self.target_dir
       
        if debug: print_debug('Using', self.output_dir, 'as output_dir')
        if not self.is_dummy_file: self.check_output_dir(self.output_dir)

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

def find_files(filename_parser, verbose=False, debug=False, **kwargs):
    '''
    uses the filename_parser object (specifically the source_dir attribute)
    to attempt to find all files contained in the source directory

    and returns a list of filename_parser instances with those files
    '''
    # gather information about filename parser
    parsed_filenames = []
    dummy_instance = filename_parser('dummy', is_dummy_file=True)
    try:
        source_dir = dummy_instance.source_dir
    except AttributeError:
        raise Usage(''.join(['Filename parser must specify ',
                             'source_dir to use --find']))

    # find the files in source_dir
    leaves_in_source_dir = leaves(source_dir)
    for leaf in leaves_in_source_dir:
        if is_valid_file(leaf): parsed_filenames.append(filename_parser(leaf))
    return parsed_filenames

def is_valid_file(f):
    '''checks if a file is valid for processing'''
    if not os.path.isfile(f):
        return False
    elif f.startswith('.'):
        return False
    elif ALLOWED_EXTENSIONS is None:
        return True
    elif os.path.splitext(f)[1].lstrip(os.extsep) in ALLOWED_EXTENSIONS:
        return True
    else:
        return False

def leaves(dir_or_file, allow_symlinks = True, ignore_hidden_file = True):
    '''takes as input a VALID path and descends into all directories

    WARNING:
    this *will* get caught in an infinite loop if you have a symlink
    which references a node above itself in tree
    '''
    # Check sanity
    if not os.path.exists(dir_or_file):
        raise Usage(' '.join([source_dir, 'does not exist']))



    # Base case
    if os.path.isfile(dir_or_file) and not dir_or_file.startswith('.'):
        if debug: print_debug('Found file', dir_or_file)
        return dir_or_file

    # Recurse
    files = []
    for node in os.listdir(dir_or_file):
        node_path = os.path.join(dir_or_file, node)
        if os.path.isdir(node_path):
            files.extend(leaves(node_path))
        elif os.path.isfile(node_path) and not node_path.startswith('.'):
            files.append(node_path)
    return files

def with_exit(fnc):
    return sys.exit(fnc())

def version_info():
    if globals().has_key('SCRIPT_VERSION'):
        return ' '.join(['version', SCRIPT_VERSION])
    else:
        return 'version not specified'

def usage_info():
    return ' '.join(['Usage:', PROGRAM_NAME, '[OPTIONS]', 'FILE(S)'])

def perform(action, *args, **kwargs):
    '''wrapper function that calls the main_body function inside sys.exit'''
    return sys.exit(main_body(action, *args, **kwargs))

def check_script_options(options):
    script_options = {}
    # check some additional options
    # override this function in your script if you want to use it
    # return a dictionary with more options for action
    return script_options

def main_body(action, filename_parser=None, argv=None):
    SHORT_OPTS = "hvpr:"
    VERBOSITY_LEVELS = ['debug', 'verbose', 'quiet', 'silent']
    LONG_OPTS = ["help", "version", "find", "target=", 
                 "num-cpus=", "recursive"] + VERBOSITY_LEVELS 

    fp_kwargs = {}
    if argv is None:
        argv = sys.argv

    try: SHORT_OPTS += SCRIPT_SHORT_OPTS
    except NameError: pass
    try: LONG_OPTS.extend(SCRIPT_LONG_OPTS)
    except NameError: pass
    print SHORT_OPTS
    try:
        opts, args = getopt.gnu_getopt(argv[1:], SHORT_OPTS, LONG_OPTS)
        options = {}
        for k, v in opts:
            options[k.lstrip('-')] = v # with -'s stripped
    except getopt.error, msg:
        raise Usage(str(msg))

    try:
        # check script-specific options first
        script_options = check_script_options(options)
        fp_kwargs.update(script_options)

        # check for help
        if options.has_key('h') or options.has_key('help'):
            raise Usage(_documentation())
        # check for version info
        elif options.has_key('v') or options.has_key('version'):
            raise Usage(version_info())

        # check verbosity
        for verbosity in VERBOSITY_LEVELS:
            exec(''.join([verbosity,' = ', "options.has_key('",
                    verbosity, "')"]))

        if sum([locals()[verbosity] for verbosity in VERBOSITY_LEVELS]) > 1:
            raise Usage('can only specify at most one of ', 
                        ', '.join([''.join(['--',x])
                                   for x in VERBOSITY_LEVELS]))
        if debug: fp_kwargs['debug'] = True
        if debug: verbose = True

        verbose_kwargs = {'silent': silent, 'quiet': quiet,
                          'verbose': verbose, 'debug': debug}
        script_options.update(verbose_kwargs)
        fp_kwargs.update(verbose_kwargs)

        # Check num-cpus
        if options.has_key('p'):
            global NUM_CPUS
            NUM_CPUS = int(options['p'])
        elif options.has_key('num-cpus'):
            global NUM_CPUS
            NUM_CPUS = int(options['num-cpus'])

        fp_kwargs['source_dir'] = SOURCE_DIR

        # check if user specified a target_dir
        if options.has_key('target'):
            if len(options['target'].strip()) is not 0:
                if TARGET_DIR is not None and verbose:
                    print_debug('Using user-specified output directory',
                                options['target'], 'instead of',
                                TARGET_DIR)
                fp_kwargs['target_dir'] = options['target']

        # If a FilenameParser is not provided, use the built-in
        # and allow script to specify TARGET_DIR
        if filename_parser is None:
            filename_parser = FilenameParser
        filename_parser = partial(filename_parser, **fp_kwargs)

        # Check if we need to find the files or if any were specified
        # Also check if we have a proper filename parser
        if options.has_key('find') and filename_parser is None:
            raise Usage('Cannot use --find with a script that does not',
                        'specify how to parse filenames')
        elif len(args) == 0 and not options.has_key('find'):
            raise Usage('No input files specified')
        # Try to find more files if we are told to
        elif options.has_key('find') and filename_parser is not None:
            if debug:
                print_debug('Searching for valid files')
                if ALLOWED_EXTENSIONS is not None:
                    print_debug('Valid file extensions are',
                                ' '.join(ALLOWED_EXTENSIONS))
            sequence = find_files(filename_parser, **verbose_kwargs)
        else:
            sequence = []
        
        if debug:
            print_debug('Checking for user-specified files')
            if ALLOWED_EXTENSIONS is not None:
                print_debug('Valid file extensions are',
                            ' '.join(ALLOWED_EXTENSIONS))

        # Also includes explicitly mentioned files
        sequence += [filename_parser(pirate) for pirate in args]
        filtered_sequence = [x for x in sequence if not x.is_invalid]

    except Usage, err:
        print_debug(''.join([PROGRAM_NAME, ':']), str(err.msg))
        if locals().has_key('options'):
            if options.has_key('h') or options.has_key('help'): return 2
        print_debug("for help use --help")
        return 2
    
    spawn_workers(action, filtered_sequence, **script_options)

    if NEXT_SCRIPT is not None:
        if debug: print_debug('Launching the next script', NEXT_SCRIPT)
        # always proceed with --find
        next_script_args = ["--find"]
        # pass along verbosity level
        for verbosity in VERBOSITY_LEVELS:
            exec(''.join(["next_script_args.append('", verbosity, "')"]))
        os.execlp(NEXT_SCRIPT, "--find")

def debug_action(action):
    return lambda item: action(item, debug=True)

def spawn_workers(action, sequence, **kwargs):
   verbose = kwargs['verbose']
   debug = kwargs['debug']
   silent = kwargs['silent']
   if verbose: print >>sys.stdout, ' '.join(['Using', str(NUM_CPUS),
                                             'cpus...'])
   if debug: print_debug('Debugging mode enabled')

   if NUM_CPUS == 1:
       if debug: print_debug('multiprocessing disabled')
       for item in sequence:
           stdout = action(item, **kwargs)
           if not silent and stdout is not None: print >>sys.stdout, stdout
   else:
       if debug: print_debug('multiprocessing enabled')
       signal.signal(signal.SIGCHLD, signal.SIG_DFL)
       p = multiprocessing.Pool(processes=NUM_CPUS)
       stdouts = p.map(partial(action, **kwargs), sequence)
       stdouts = [x for x in stdouts if x is not None]
       if not silent and stdouts is not None:
           print >>sys.stdout, os.linesep.join(stdouts)
