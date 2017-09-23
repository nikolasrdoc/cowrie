# Copyright (c) 2017 Michel Oosterhof <michel@oosterhof.net>
# See the COPYRIGHT file for more information

"""
This module contains ...
"""

from __future__ import division, absolute_import

from twisted.internet import reactor, protocol
from twisted.python import log
from twisted.conch.ssh import session, common, keys
from twisted.conch.client.knownhosts import KnownHostsFile
from twisted.conch import endpoints

from cowrie.core.config import CONFIG

class _ProtocolFactory():
    """
    Factory to return the (existing) ssh session to pass to ssh command endpoint
    It does not actually function as a factory
    """

    def __init__(self, protocol):
        self.protocol = protocol


    def buildProtocol(self, addr):
        """
        """
        return self.protocol



class ProxyClient(object):
    """
    Dummy object because SSHSession expects a .client with an attached transport

    TODO: Forward ssh-exit-status
    """
    transport = None
    session = None

    def __init__(self, session):
        self.session = session
        self.transport = InBetween()
        self.transport.client = self.session



class InBetween(protocol.Protocol):
    """
    This is the glue between the SSH server one one side and the
    SSH client on the other side
    """

    transport = None # Transport is the back-end the ssh-server
    client = None # Client is the front-end, the ssh-client
    buf = "" # buffer to send to back-end

    def makeConnection(self, transport):
        log.msg( "IB:making connection")
        protocol.Protocol.makeConnection(self, transport)


    def connectionMade(self):
        log.msg(" IB: connection Made")


    def write(self, bytes):
        """
        """
        # This is data going from the end-user to the back-end
        if not self.transport:
            self.buf += bytes
            return
        elif len(self.buf) and self.transport != None:
            self.transport.dataReceived(self.buf)
            self.buf = None
        self.transport.dataReceived(bytes)


    def dataReceived(self, data):
        """
        """
        # This is data going from the back-end to the end-user
        self.client.write(data)


    def closed(self):
        """
        """
        log.msg("IB: closed")


    def closeReceived(self):
        """
        """
        log.msg("IB: closeRecieved")


    def loseConnection(self):
        """
        Frontend disconnected
        """
        log.msg("IB: loseConnection")


    def connectionLost(self, reason):
        """
        Backend has disconnected
        """
        log.msg("IB: ConnectionLost")
        self.client.loseConnection()


    def eofReceived(self):
        """
        """
        log.msg("IB: eofReceived")



class ProxySSHSession(session.SSHSession):
    """
    This is an SSH channel to proxy SSH session.
    """
    keys = []
    host = ""
    port = 22
    user = ""
    password = ""
    knownHosts = None

    def __init__(self, *args, **kw):
        session.SSHSession.__init__(self, *args, **kw)
        #self.__dict__['request_auth_agent_req@openssh.com'] = self.request_agent

        keyPath = CONFIG.get('proxy', 'private_key')
        self.keys.append(keys.Key.fromFile(keyPath))

        knownHostsPath = CONFIG.get('proxy', 'known_hosts')
        self.knownHosts = KnownHostsFile.fromPath(knownHostsPath)

        self.host = CONFIG.get('proxy', 'host')
        self.port = CONFIG.getint('proxy', 'port')
        self.user = CONFIG.get('proxy', 'user')
        self.password = CONFIG.get('proxy', 'password')

        log.msg( "host = "+self.host)
        log.msg( "port = "+str(self.port))
        log.msg( "user = "+self.user)
        log.msg( "known = "+str(self.knownHosts))


    def request_env(self, data):
        """
        """
        name, rest = getNS(data)
        value, rest = getNS(rest)
        if rest:
            raise ValueError("Bad data given in env request")
        log.msg(eventid='cowrie.client.var', format='request_env: %(name)s=%(value)s',
            name=name, value=value)
        # FIXME: This only works for shell, not for exec command
        if self.session:
            self.session.environ[name] = value
        return 0


    def request_exec(self, data):
        cmd, data = common.getNS(data)
        log.msg('request_exec "%s"' % cmd)
        self.client = ProxyClient(self)
        pf = _ProtocolFactory(self.client.transport)
        ep = endpoints.SSHCommandClientEndpoint.newConnection(reactor, cmd,
            self.user, self.host, port=self.port, password=self.password).connect(pf)
        #ep = endpoints.SSHCommandClientEndpoint.newConnection(reactor, cmd,
        #    self.user, self.host, port=self.port, keys=self.keys, knownHosts=self.knownHosts).connect(pf)
        #ep = endpoints.SSHCommandClientEndpoint.newConnection(reactor, cmd,
        #    USER, HOST, port=PORT, password=PASSWORD).connect(pf)
        return 1


    def request_agent(self, data):
        """
        """
        log.msg('request_agent: %s' % (repr(data),))
        return 0


    def request_x11_req(self, data):
        """
        """
        log.msg('request_x11: %s' % (repr(data),))
        return 0


    def closed(self):
        """
        This is reliably called on session close/disconnect and calls the avatar
        """
        session.SSHSession.closed(self)
        self.client = None


    def sendEOF(self):
        """
        Utility function to request to send EOF for this session
        """
        self.conn.sendEOF(self)


    def sendClose(self):
        """
        Utility function to request to send close for this session
        """
        self.conn.sendClose(self)


    def channelClosed(self):
        """
        """
        log.msg("Called channelClosed in SSHSession")

