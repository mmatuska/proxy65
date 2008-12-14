#!/usr/bin/env python

# Copyright (c) 2008 Fabio Forno

from distutils.core import setup

setup(name='Proxy65',
      version='1.2.0',
      description='XEP 65 Bytestream Proxy Component',
      author='Dave Smith, Fabio Forno',
      author_email='fabio.forno@gmail.com',
      maintainer_email='fabio.forno@gmail.com',
      url='http://code.google.com/p/proxy65',
      license='MIT',
      packages=[
          'proxy65', 
          'twisted.plugins'
      ],
      package_data={'twisted.plugins': ['twisted/plugins/proxy65.py']}
)

# regenerate the plugin cache with the correct permissions
from twisted.plugin import getPlugins
from twisted.plugin import IPlugin

try:
    for plugin in getPlugins(IPlugin):
        pass
except:
    pass

