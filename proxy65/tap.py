from twisted.application import internet, service
from twisted.internet import interfaces
from twisted.python import usage
import proxy65

class Options(usage.Options):
    optParameters = [('jid', None, 'proxy65'),
                     ('secret', None, None),
                     ('rhost', None, '127.0.0.1'),
                     ('rport', None, '6000'),
                     ('proxyips', None, None)]


def makeService(config):
    return proxy65.makeService(config)
