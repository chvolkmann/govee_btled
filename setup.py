#!/usr/bin/env python3
from setuptools import setup

setup(
    name='govee_btled',
    version='1.0',

    description='Govee Bluetooth RGB LED Controller',

    author='Christian Volkmann',
    author_email='ch.volkmann@gmail.com',

    packages=['govee_btled'],
    install_requires=[
        'pygatt[GATTTOOL]',
        'colour'
    ]
)