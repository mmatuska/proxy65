"""
License

Copyright (C) 
2008        Fabio Forno (xmpp:ff@jabber.bluendo.com)

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in
all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
THE SOFTWARE.

$Id:$
"""

from zope.interface import implements
from twisted.application import internet, service
from twisted.internet import interfaces
from twisted.python import usage
from twisted.plugin import IPlugin
from twisted.application.service import IServiceMaker
from proxy65 import proxy65

class Options(usage.Options):
    optParameters = [('jid', None, 'proxy65'),
                     ('secret', None, None),
                     ('rhost', None, '127.0.0.1'),
                     ('rport', None, '6000'),
                     ('proxyips', None, None)]


class Proxy65ServiceMaker(object):
    
    implements(IServiceMaker, IPlugin)
    tapname = "proxy65"
    description = "Prox65 Twisted Plugin"
    options = Options

    def makeService(self, config):
        return proxy65.makeService(config)

serviceMaker = Proxy65ServiceMaker()
