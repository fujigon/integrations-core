# (C) Datadog, Inc. 2018
# All rights reserved
# Licensed under a 3-clause BSD style license (see LICENSE)

# Always prefer setuptools over distutils
from setuptools import setup
from codecs import open  # To use a consistent encoding
from os import path

HERE = path.abspath(path.dirname(__file__))

# Get the long description from the README file
with open(path.join(HERE, 'README.md'), encoding='utf-8') as f:
    long_description = f.read()

# Get version info
ABOUT = {}
with open(path.join(HERE, "datadog_checks", "activemq_xml", "__about__.py")) as f:
    exec(f.read(), ABOUT)


def get_requirements(fpath):
    with open(path.join(HERE, fpath), encoding='utf-8') as f:
        return f.readlines()


setup(
    name='datadog-activemq_xml',
    version=ABOUT["__version__"],
    description='The ActiveMQ XML check',
    long_description=long_description,
    keywords='datadog agent activemq_xml check',

    # The project's main homepage.
    url='https://github.com/DataDog/integrations-core',

    # Author details
    author='Datadog',
    author_email='packages@datadoghq.com',

    # License
    license='BSD',

    # See https://pypi.python.org/pypi?%3Aaction=list_classifiers
    classifiers=[
        'Development Status :: 5 - Production/Stable',
        'Intended Audience :: Developers',
        'Intended Audience :: System Administrators',
        'Topic :: System :: Monitoring',
        'License :: OSI Approved :: BSD License',
        'Programming Language :: Python :: 2',
        'Programming Language :: Python :: 2.7',
    ],

    # The package we're going to ship
    packages=['datadog_checks.activemq_xml'],

    # Run-time dependencies
    install_requires=get_requirements('requirements.in') + [
        'datadog_checks_base',
    ],
    tests_require=get_requirements('requirements-dev.txt'),

    # Extra files to ship with the wheel package
    include_package_data=True,
)
