#!/usr/bin/env python
# Setup script

"""Description:
Setup script for scripter
Copyright (c) 2010-2012 Benjamin Schiller <benjamin.schiller@ucsf.edu>
"""

import os, sys
from setuptools import setup
name = 'scripter'
version = '3.2.3'

def main():
	if not float(sys.version[:3])>=2.7:
		sys.stderr.write("CRITICAL: Python version must greater than or equal to 2.7! python 2.7.2 is recommended!\n")
		sys.exit(1)
	setup(name='scripter',
	      version=version,
	      description="""a tool for parallel execution of functions on many files""",
	      author='Benjamin Schiller',
	      author_email='benjamin.schiller@ucsf.edu',
	      requires = ['decorator'],
	      packages = ['scripter'],
	      package_dir = {'scripter': 'src' + os.sep},
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
