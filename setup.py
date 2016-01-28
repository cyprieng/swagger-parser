#!/usr/bin/env python
# -*- coding: utf-8 -*-

from pip.req import parse_requirements
try:
    from setuptools import setup
except ImportError:
    from distutils.core import setup


with open('README.md') as readme_file:
    readme = readme_file.read()

with open('HISTORY.rst') as history_file:
    history = history_file.read()

requirements = [str(i.req) for i in parse_requirements('requirements.txt', session=False)]
test_requirements = [str(i.req) for i in parse_requirements('requirements_dev.txt', session=False)]

setup(
    name='swagger_parser',
    version='0.1',
    description="Swagger parser giving useful informations about your swagger files",
    long_description=readme + '\n\n' + history,
    author="Cyprien Guillemot",
    author_email='cyprien.guillemot@gmail.com',
    url='https://github.com/Trax-air/swagger-parser',
    packages=[
        'swagger_parser',
    ],
    package_dir={'swagger_parser':
                 'swagger_parser'},
    include_package_data=True,
    setup_requires=['pytest-runner'],
    install_requires=requirements,
    license="GPL",
    zip_safe=False,
    keywords='swagger, parser, API, REST, swagger-parser',
    classifiers=[
        'Development Status :: 2 - Pre-Alpha',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: ISC License (ISCL)',
        'Natural Language :: English',
        "Programming Language :: Python :: 2",
        'Programming Language :: Python :: 2.6',
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.3',
        'Programming Language :: Python :: 3.4',
        'Programming Language :: Python :: 3.5',
    ],
    test_suite='tests',
    tests_require=test_requirements
)
