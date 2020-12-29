# -*- coding: utf-8 -*-
from setuptools import setup, find_packages

with open('requirements.txt') as f:
	install_requires = f.read().strip().split('\n')

# get version from __version__ variable in ddmrp/__init__.py
from ddmrp import __version__ as version

setup(
	name='ddmrp',
	version=version,
	description='Demand Driven Material Requirement Planning',
	author='Fisher',
	author_email='yuxinyong@163.com',
	packages=find_packages(),
	zip_safe=False,
	include_package_data=True,
	install_requires=install_requires
)
