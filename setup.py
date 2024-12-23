from setuptools import setup, find_packages

with open('requirements.txt') as f:
	install_requires = f.read().strip().split('\n')

# get version from __version__ variable in semah/__init__.py
from semah import __version__ as version

setup(
	name='semah',
	version=version,
	description='App for semah v13 erpnext',
	author='Dconnex',
	author_email='cloud@avu.net.in',
	packages=find_packages(),
	zip_safe=False,
	include_package_data=True,
	install_requires=install_requires
)
