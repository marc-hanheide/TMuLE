#!/usr/bin/env python
from setuptools import setup, find_packages

VERSION = '1.1.6'

setup(
    name='tmule',
    packages=find_packages(),
    entry_points={
    'console_scripts': [
        'tmule=tmule:main',
		    ],
		},
    #scripts=['tmule.py'],
    version=VERSION,
    install_requires=['webnsock', 'libtmux', 'psutil'],
    description='The TMux Launch Engine',
    author='Marc Hanheide',
    author_email='marc@hanheide.net',
    url='https://github.com/marc-hanheide/TMuLe',
    download_url='https://github.com/marc-hanheide/TMuLe/archive/%s.tar.gz'
        % VERSION,  # I'll explain this in a second
    keywords=['webnsock', 'libtmux'],
    classifiers=[],
    include_package_data=True,
    zip_safe=False
)
