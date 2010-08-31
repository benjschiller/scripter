#!/usr/bin/env python
'''
Common Options:
-h, --help will display this menu
-v, --version will give the current package version
--verbose
--debug
--quiet (default)
--silent

--find                      (find files automatically)
--target=foo                output to directory foo
-p[#] or --num-cpus=[#]     Use at most [#] cpus
'''
import getopt
import sys
import os
import subprocess
import functools
from functools import partial
try:
    import multiprocessing
    NUM_CPUS = multiprocessing.cpu_count()
except ImportError:
    NUM_CPUS = 1

PROGRAM_NAME = os.path.basename(sys.argv[0])
CURRENT_PATH = os.curdir + os.sep

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

class FilenameParser:
    def __init__(self,
                 filename,
                 source_dir=None,
                 target_dir=None,
                 verbose=False,
                 debug=False,
                 *args,
                 **kwargs):

        self.additional_args = args
        self.__dict__.update(kwargs)

        if debug: print_debug('Checking for', filename, '...')
        self.assert_path(filename)
        self.input_file = filename

        if target_dir is None:
            raise Usage('Must specify target_dir (output directory)')
        else:
            self.target_dir = target_dir

        if source_dir is not None:
            self.assert_path(source_dir)
            self.source_dir = source_dir

            fn_parts = filename.split(os.sep)
            source_dir_index = fn_parts.index(source_dir)
            
            self.output_dir = os.path.join(target_dir,
                                fn_parts[source_dir_index+1:-1])
        else:
            self.output_dir = target_dir
        
        # Make the output directory, complain if we fail
        if os.path.exists(self.output_dir):
            if debug: print_debug('Output directory', 
                                    _quote(self.output_dir), 'already exists')
        else:
            if debug: print_debug('Creating directory', _quote(self.output_dir))
            os.makedirs(self.output_dir, mode=0755)
            if not os.path.exists(self.output_dir):
                raise IOError('Could not create directory ' + output_dir)

        self.protoname = os.path.splitext(
                            os.path.basename(self.input_file))[0]

    def assert_path(self, path):
        if os.path.exists(path): return True
        else: raise IOError(' '.join(['File or directory', 
                                        path, 'not found']))

    def with_extension(ext):
        '''Path to output file with extension'''
        os.extsep.join([self.protoname,ext])


def with_exit(fnc):
    return sys.exit(fnc())

def version_info():
    return ' '.join(['version', __version__])

def usage_info():
    return ' '.join(['Usage:', PROGRAM_NAME, '[OPTIONS]', 'FILE(S)'])

def perform(action, *args, **kwargs):
    '''wrapper function that calls the main_body function inside sys.exit'''
    return sys.exit(main_body(action, *args, **kwargs))

def main_body(action, filename_parser=None, argv=None):
    fp_kwargs = {}
    if argv is None:
        argv = sys.argv

    try:
        short_opts = "hvp:"
        verbosity_levels = ['debug', 'verbose', 'quiet', 'silent']
        long_opts = ["help", "version", "find", "target=",'num_cpus='] + verbosity_levels
        try:
            opts, args = getopt.gnu_getopt(argv[1:], short_opts, long_opts)
            options = {}
            for k, v in opts:
                options[k.lstrip('-')] = v # with -'s stripped
        except getopt.error, msg:
            raise Usage(msg)

        # check for help
        if options.has_key('h') or options.has_key('help'):
            raise Usage(_documentation())
        # check for version info
        elif options.has_key('v') or options.has_key('version'):
            raise Usage(version_info())

        # check verbosity
        for verbosity in verbosity_levels:
            #locals()[verbosity] = verbosity in options
            exec(''.join([verbosity,' = ', "options.has_key('",
                    verbosity, "')"]))

        if sum([locals()[verbosity] for verbosity in verbosity_levels]) > 1:
            raise Usage('can only specify at most one of ', ', '.join([''.join(['--',x]) 
                                                                        for x in verbosity_levels]))
        if debug: fp_kwargs['debug'] = True
        if debug: verbose = True


        # Check num_cpus
        if options.has_key('p'):
            NUM_CPUS = options['p']
        elif options.has_key('num_cpus'):
            NUM_CPUS = options['num_cpus']


        # Check if we need to find the files or if any were specified
        # Also check if we have a proper filename parser
        if options.has_key('find') and filename_parser is None:
            raise Usage('Cannot use --find with a script that does not' +
                        'specify how to parse filenames')
        elif len(args) == 0:
            raise Usage('No input files specified')
        # Try to find files if we need to
        elif options.has_key('find') and filename_parser is not None:
            sequence = find_files(filename_parser, verbose=verbose, debug=debug)
        else:
            # If a FilenameParser is not provided, use a generic one
            if options.has_key('target') and \
              len(options['target'].strip()) is not 0:
                fp_kwargs['target_dir'] = options['target']
            elif FilenameParser is None:
                raise Usage('must specify an output directory with --target')
            
            fp_kwargs['debug'] = debug
            fp_kwargs['verbose'] = verbose
            if filename_parser is None: filename_parser = FilenameParser
            filename_parser = partial(filename_parser, **fp_kwargs)
            sequence = [filename_parser(pirate)
                                                         for pirate in args]

    except Usage, err:
        print print_debug(PROGRAM_NAME, str(err.msg))
        print print_debug("for help use --help")
        return 2

    stdout = spawn_workers(action, sequence, verbose=verbose, debug=debug)
    if not silent: print >>sys.stdout, stdout

def debug_action(action):
    return lambda item: action(item, debug=True)

def spawn_workers(action, sequence, verbose=False, debug=False):
   if verbose: print >>sys.stdout, ' '.join(['Using', str(NUM_CPUS), 'cpus...'])
   if debug: print_debug('Debugging mode enabled')

   if NUM_CPUS == 1:
       if debug: print_debug('multiprocessing disabled')
       for item in sequence:
           print >>sys.stdout, action(item, debug=debug)
   else:
       if debug: print_debug('multiprocessing enabled')
       p = multiprocessing.Pool(processes=NUM_CPUS)
       stdouts = p.map(partial(action,debug=debug), sequence)
       return os.linesep.join(stdouts)
