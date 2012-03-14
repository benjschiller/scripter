#!/usr/bin/env python
# Setup script

"""Description:
Setup script for scripter
Copyright (c) 2010-2012 Benjamin Schiller <benjamin.schiller@ucsf.edu>
"""

import os, sys
from distutils.core import setup
try: import py2exe
except ImportError: pass
try: import py2app
except ImportError: pass
cmdclass = {}
try:
    from sphinx.setup_command import BuildDoc
    cmdclass['build_sphinx'] = BuildDoc
except ImportError: pass
try:
    from sphinx_pypi_upload import UploadDoc
    cmdclass['upload_sphinx'] = UploadDoc
except ImportError: pass
name = 'scripter'
version = '3.1'

def main():
	if not float(sys.version[:3])>=2.7:
		sys.stderr.write("CRITICAL: Python version must greater than or equal to 2.7! python 2.7.2 is recommended!\n")
		sys.exit(1)
	setup(name='scripter',
	      version='3.1',
	      description="""a tool for parallel execution of functions on many files""",
	      author='Benjamin Schiller',
	      author_email='benjamin.schiller@ucsf.edu',
	      requires = ['decorator'],
	      packages = ['scripter'],
	      package_dir = {'scripter': 'src' + os.sep},
	      cmdclass=cmdclass,
		  command_options={
			  'project': ('setup.py', name),
			  'version': ('setup.py', version),
		  },
  	      classifiers = [
				'Development Status :: 4 - Beta',
				'License :: OSI Approved :: Artistic License',
				'Intended Audience :: Developers',
				'Intended Audience :: Science/Research',
				'Operating System :: MacOS :: MacOS X',
				'Operating System :: Microsoft :: Windows',
				'Operating System :: POSIX',
				'Programming Language :: Python :: 2.7',
				]
	      )
	
if __name__ == '__main__':
	main()
