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
from hemp import jabber
import ConfigParser
import socks5

_config = None
_component = None
_proxy = None
_pendingConns = {}
_activeConns = {}

def onStreamAuthd(obj):
    global _proxy
    # Setup socks5 proxy class
    factory = protocol.Factory()
    factory.protocol = SOCKSv5Proxy
    _proxy = reactor.listenTCP(_config.getint("proxy", "port"),
                               factory,
                               interface = _config.get("proxy", "host"))

def onStreamEnd(obj):
    # Shutdown listening socket
    if _proxy != None:
        _proxy.loseConnection()

def onDiscoInfo(iq):
    iq.swapAttribs("to", "from")
    iq["type"] = "result"
    iq.query.children = []
    i = iq.query.addElement("identity")
    i["category"] = "proxy"
    i["type"] = "bytestreams"
    i["name"] = "JEP-65 Proxy"
    iq.query.addElement("feature")["var"] = "http://jabber.org/protocol/bytestreams"
    _component.send(iq)

def onIQGet(iq):
    iq.swapAttribs("to", "from")
    iq["type"] = "result"
    iq.query.children = []
    s = iq.query.addElement("streamhost")
    s["jid"] = _config.get("jabber", "id")
    s["host"] = _config.get("proxy", "host")
    s["port"] = _config.get("proxy", "port")
    _component.send(iq)


def hashSID(sid, initiator, target):
    import sha
    return sha.new("%s%s%s" % (sid, initiator, target)).hexdigest()

def onIQActivate(iq):
    sid = hashSID(iq.query["sid"], iq["from"], str(iq.query.activate))

    if sid in _pendingConns:
        # Get list of objects for this sid
        olist = _pendingConns[sid]

        # Remove sid from pending
        del _pendingConns[sid]

        # Ensure there are the correct # of participants
        if len(olist) != 2:
            # Send an error
            iq.swapAttribs("to", "from")
            iq["type"] = "error"
            iq.query.children = []
            iq.query.addElement("error")["code"] = "405"
            _component.send(iq)
            # Close all connected
            for c in olist: c.transport.loseConnection()
            return

        # Send iq result
        iq.swapAttribs("to", "from")
        iq["type"] = "result"
        iq.query.children = []
        _component.send(iq)

        # Remove sid from pending and mark as active
        assert sid not in _activeConns
        _activeConns[sid] = None
        
        # Complete connection
        olist[0].peersock = olist[1]
        olist[0].transport.registerProducer(olist[1], 0)
        olist[1].peersock = olist[0]
        olist[1].transport.registerProducer(olist[0], 0)
        olist[0].transport.startReading()
        olist[1].transport.startReading()

        print "Activated"
    else:
        # Send an error
        iq.swapAttribs("to", "from")
        iq["type"] = "error"
        iq.query.children = []
        iq.query.addElement("error")["code"] = "404"
        _component.send(iq)

class SOCKSv5Proxy(socks5.SOCKSv5):
    def __init__(self):
        socks5.SOCKSv5.__init__(self)
        self.supportedAuthMechs = [socks5.AUTHMECH_ANON]
        self.supportedAddrs = [socks5.ADDR_DOMAINNAME]
        self.enabledCommands = [socks5.CMD_CONNECT]
        self.addr = ""

    # ---------------------------------------------
    # Producer methods -- Not yet enabled
    # ---------------------------------------------
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
        print "Connect requested: ", addr
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
        if addr in _activeConns:
            self.sendErrorReply(socks5.REPLY_CONN_NOT_ALLOWED)
            return

        # Add this address to the pending connections
        olist = _pendingConns.get(addr, [])
        if len(olist) <= 1:
            olist.append(self)
            _pendingConns[addr] = olist
            self.connectCompleted(addr, 0)
            self.transport.stopReading()
        else:
            print "Already 2 pending conns"
            self.sendErrorReply(socks5.REPLY_CONN_REFUSED)

    def connectionLost(self, reason):
        if self.state == socks5.STATE_CONNECT_PENDING:
            # Remove this object from pending conns; and remove
            # the whole list from pending conns if this connection
            # is the only one there
            olist = _pendingConns[self.addr]
            if len(olist) == 1:
                del _pendingConns[self.addr]
            else:
                olist.remove(self)
                _pendingConns[self.addr] = olist
        else:
            if self.peersock != None:
                self.peersock.peersock = None
                self.peersock.transport.loseConnection()
                self.peersock = None
                del _activeConns[self.addr]
        

if __name__ == "__main__":
    _config = ConfigParser.ConfigParser()
    _config.readfp(open("proxy65.cfg"))

    # Ensure we have all the necessary options -- there's probably
    # a better way to do this?!
    assert _config.has_option("jabber", "id")
    assert _config.has_option("jabber", "secret")
    assert _config.has_option("jabber", "routerhost")
    assert _config.has_option("jabber", "routerport")
    assert _config.has_option("proxy", "host")
    assert _config.has_option("proxy", "port")

    # Setup a component
    _component = jabber.Component(_config.get("jabber", "routerhost"),
                                  _config.getint("jabber", "routerport"),
                                  _config.get("jabber", "id"),
                                  _config.get("jabber", "secret"))

    _component.addObserver(jabber.STREAM_AUTHD_EVENT, onStreamAuthd)
    _component.addObserver(jabber.STREAM_END_EVENT, onStreamEnd)
    _component.addObserver("/iq[@type='get']/query[@xmlns='http://jabber.org/protocol/bytestreams']",
                           onIQGet)    
    _component.addObserver("/iq[@type='set']/query[@xmlns='http://jabber.org/protocol/bytestreams']/activate",
                           onIQActivate)
    _component.addObserver("/iq[@type='get']/query[@xmlns='http://jabber.org/protocol/disco#info']",
                           onDiscoInfo)


    # Go!
    _component.run()




    
