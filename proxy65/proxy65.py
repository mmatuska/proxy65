##============================================================================
##
##     License:
##
##     This library is free software; you can redistribute it and/or
##     modify it under the terms of the GNU General Public
##     License as published by the Free Software Foundation; either
##     version 2 of the License, or (at your option) any later version.
##
##     This library is distributed in the hope that it will be useful,
##     but WITHOUT ANY WARRANTY; without even the implied warranty of
##     MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
##     General Public License for more details.
##
##     You should have received a copy of the GNU General Public
##     License along with this library; if not, write to the Free Software
##     Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  021-1307
##     USA
##
##     Copyright (C) 2002-2003 Dave Smith (dizzyd@jabber.org)
##
## $Id$
##============================================================================

from twisted.internet import protocol, reactor
from twisted.python import usage, log
from twisted.protocols.jabber import component
import sys
import socks5

JEP65_GET      = "/iq[@type='get']/query[@xmlns='http://jabber.org/protocol/bytestreams']"
JEP65_ACTIVATE = "/iq[@type='set']/query[@xmlns='http://jabber.org/protocol/bytestreams']/activate"
DISCO_GET      = "/iq[@type='get']/query[@xmlns='http://jabber.org/protocol/disco#info']"


def hashSID(sid, initiator, target):
    import sha
    return sha.new("%s%s%s" % (sid, initiator, target)).hexdigest()

class JEP65Proxy(socks5.SOCKSv5):
    def __init__(self, service):
        socks5.SOCKSv5.__init__(self)
        self.service = service
        self.supportedAuthMechs = [socks5.AUTHMECH_ANON]
        self.supportedAddrs = [socks5.ADDR_DOMAINNAME]
        self.enabledCommands = [socks5.CMD_CONNECT]
        self.addr = ""

    def stopProducing(self):
        self.transport.loseConnection()

    def pauseProducing(self):
        self.transport.stopReading()

    def resumeProducing(self):
        self.transport.startReading()

    # ---------------------------------------------
    # SOCKSv5 subclass
    # ---------------------------------------------    
    def connectRequested(self, addr, port):
        # Check for special connect to the namespace -- this signifies that the client
        # is just checking to ensure it can connect to the streamhost
        if addr == "http://jabber.org/protocol/bytestreams":
            self.connectCompleted(addr, 0)
            self.transport.loseConnection()
            return
            
        # Save addr, for cleanup
        self.addr = addr
        
        # Check to see if the requested address is already
        # activated -- send an error if so
        if self.service.isActive(addr):
            self.sendErrorReply(socks5.REPLY_CONN_NOT_ALLOWED)
            return

        # Add this address to the pending connections
        if self.service.addConnection(addr, self):
            self.connectCompleted(addr, 0)
            self.transport.stopReading()
        else:
            self.sendErrorReply(socks5.REPLY_CONN_REFUSED)

    def connectionLost(self, reason):
        if self.state == socks5.STATE_CONNECT_PENDING:
            self.service.removePendingConnection(self.addr, self)
        else:
            self.transport.unregisterProducer()
            if self.peersock != None:
                self.peersock.peersock = None
                self.peersock.transport.unregisterProducer()
                self.peersock = None
                self.service.removeActiveConnection(self.addr)
        

class Service(component.Service, protocol.Factory):
    def __init__(self, serviceParent, config):
        component.Service.__init__(self, config["jid"], serviceParent)

        self.associateWithRouter(config["secret"], config["rhost"], int(config["rport"], 10))

        self.pendingConns = {}
        self.activeConns = {}

        # SOCKSv5 proxy objects
        self.proxy = None
        self.proxyPort = int(config["proxyport"])
        self.proxyIP = config["proxyip"]

    def buildProtocol(self, addr):
        return JEP65Proxy(self)

    def configureEvents(self, factory):
        factory.addBootstrap(JEP65_GET, self.onGetHostInfo)
        factory.addBootstrap(DISCO_GET, self.onDisco)        
        factory.addBootstrap(JEP65_ACTIVATE, self.onActivateStream)

    def componentConnected(self):
        self.proxy = reactor.listenTCP(self.proxyPort, self,
                                       interface = self.proxyIP)

    def componentDisconnected(self):
        if self.proxy != None:
            self.proxy.loseConnection()

    def onGetHostInfo(self, iq):
        iq.swapAttributeValues("to", "from")
        iq["type"] = "result"
        iq.query.children = []
        s = iq.query.addElement("streamhost")
        s["jid"] = self.jabberId
        s["host"] = self.proxyIP
        s["port"] = str(self.proxyPort)
        self.xmlstream.send(iq)

    def onDisco(self, iq):
        print iq.toXml()
        iq.swapAttributeValues("to", "from")
        iq["type"] = "result"
        iq.query.children = []
        i = iq.query.addElement("identity")
        i["category"] = "proxy"
        i["type"] = "bytestreams"
        i["name"] = "SOCKS5 Bytestreams Service"
        iq.query.addElement("feature")["var"] = "http://jabber.org/protocol/bytestreams"
        self.xmlstream.send(iq)


    def onActivateStream(self, iq):
        sid = hashSID(iq.query["sid"], iq["from"], str(iq.query.activate))
        log.msg("Activation requested for: ", sid)

        if sid in self.pendingConns:
            # Get list of objects for this sid
            olist = self.pendingConns[sid]

            # Remove sid from pending
            del self.pendingConns[sid]

            # Ensure there are the correct # of participants
            if len(olist) != 2:
                log.msg("Activation for %s failed: insufficient participants", sid)
                # Send an error
                iq.swapAttributeValues("to", "from")
                iq["type"] = "error"
                iq.query.children = []
                e = iq.addElement("error")
                e["code"] = "405"
                e["type"] = "cancel"
                c = e.addElement("condition")
                c["xmlns"] = "urn:ietf:params:xml:ns:xmpp-stanzas"
                c.addElement("not-allowed")
                self.xmlstream.send(iq)
                
                # Close all connected
                for c in olist: c.transport.loseConnection()
                return

            # Send iq result
            iq.swapAttributeValues("to", "from")
            iq["type"] = "result"
            iq.query.children = []
            self.xmlstream.send(iq)
            
            # Remove sid from pending and mark as active
            assert sid not in self.activeConns
            self.activeConns[sid] = None
        
            # Complete connection
            log.msg("Activating ", sid)
            olist[0].peersock = olist[1]
            olist[1].peersock = olist[0]
            olist[0].transport.registerProducer(olist[1], 0)
            olist[1].transport.registerProducer(olist[0], 0)
        else:
            # Send an error
            iq.swapAttributeValues("to", "from")
            iq["type"] = "error"
            iq.query.children = []
            e = iq.addElement("error")
            e["code"] = "404"
            e["type"] = "cancel"
            c = e.addElement("condition")
            c["xmlns"] = "urn:ietf:params:xml:ns:xmpp-stanzas"
            c.addElement("item-not-found")
            self.xmlstream.send(iq)

    def isActive(self, address):
        return address in self.activeConns

    def addConnection(self, address, connection):
        log.msg("Adding connection: ", address, connection)
        olist = self.pendingConns.get(address, [])
        if len(olist) <= 1:
            olist.append(connection)
            self.pendingConns[address] = olist
            return True
        else:
            return False

    def removePendingConnection(self, address, connection):
        olist = self.pendingConns[address]
        if len(olist) == 1:
            del self.pendingConns[address]
        else:
            olist.remove(connection)
            self.pendingConns[address] = olist


    def removeActiveConnection(self, address):
        del self.activeConns[address]
        

class Options(usage.Options):
    optParameters = [('jid', None, 'proxy65'),
                     ('secret', None, None),
                     ('rhost', None, '127.0.0.1'),
                     ('rport', None, '6000'),

                     ('proxyip', None, None),
                     ('proxyport', None, '7777')]



def updateApplication(ourApp, config):
    # Check for parameters...
    try:
        int(config["rport"], 10)
    except ValueError:
        print "Invalid router port (--rport) provided."
        sys.exit(-1)

    try:
        int(config["proxyport"], 10)
    except (ValueError, TypeError):
        print "Invalid proxy port (--proxyport) is required."
        sys.exit(-1)

    if config["secret"] == None:
        print "Component secret (--secret) is a REQUIRED parameter."
        sys.exit(-1)

    if config["proxyip"] == None:
        print "Proxy Network Address (--proxyip) is a REQUIRED parameter."
        sys.exit(-1)
        
    Service(ourApp, config)
    
    
