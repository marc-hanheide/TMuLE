from setuptools import setup, find_packages

VERSION = '0.0.1'

setup(
    name='tmule',
    packages=find_packages(),
    scripts=['tmule.py'],
    version=VERSION,
    install_requires=['webnsock'],
    description='The TMux Launch Engine',
    author='Marc Hanheide',
    author_email='marc@hanheide.net',
    url='https://github.com/marc-hanheide/TMuLe',
    download_url='https://github.com/marc-hanheide/TMuLe/archive/%s.tar.gz'
        % VERSION,  # I'll explain this in a second
    keywords=['web.py', 'websockets', 'webserver', 'tmux'],
    classifiers=[],
    include_package_data=True,
    zip_safe=False
)
