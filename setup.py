# -*- coding: utf-8 -*-

from setuptools import setup, find_packages

version = "0.0.1"

setup(
    name='taskarena',
    version=version,
    description='Adding collaborative functionality to TaskWarrior',
    author='Nikolai Nowaczyk',
    author_email='mail@nikno.de',
    license='GNU GPLv2',
    url='https://github.com/niknow/TaskArena/tree/master/tarenalib',
    packages=find_packages(),
    install_requires=['tasklib==0.10.0', 'click==5.1'],
    test_suite='tarenalib.tests',
    entry_points={
        'console_scripts': [
            'tarena=tarenalib.cli:cli'
        ]
    },
)
