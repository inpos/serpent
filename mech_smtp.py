# -*- coding: utf-8 -*-

from serpent.config import conf
from serpent import rules
from serpent.queue import squeue


from email.header import Header
from zope.interface import implementer

from twisted.internet import defer, ssl
from twisted.mail import smtp
from twisted.mail.imap4 import LOGINCredentials, PLAINCredentials

from twisted.cred.portal import IRealm, Portal



@implementer(smtp.IMessageDelivery)
class SmtpMessageDelivery:
    def __init__(self, avatarId = None):
        self.avatarId = avatarId

    def receivedHeader(self, helo, origin, recipients):
        header = conf.smtp_header.format(
                                     sender_ip = helo[1],
                                     sender_host = helo[0],
                                     srv_host = conf.smtp_hostname,
                                     srv_info = conf.srv_version,
                                     sender = conf.smtp_email_delim.join([origin.local, origin.domain]),
                                     id = self.messageid,
                                     rcpt = conf.smtp_email_delim.join([recipients[0].dest.local, recipients[0].dest.domain]),
                                     date = smtp.rfc822date()
                                     )
        return 'Received: %s' % Header(header)
    
    def validateFrom(self, helo, origin):       # Надо воткнуть всякие проверки хоста по HELO
        try:
            rules.validateFrom(self, [origin.local, origin.domain])
        except:
            raise
        else:
            return origin
    
    def validateTo(self, user):
        self.messageid = smtp.messageid().split('@')[0].strip('<')
        try:
            rules.validateTo(self, user)
        except:
            raise
        else:
            msg = {
                       'from': [user.orig.local, user.orig.domain],
                       'rcpt': [user.dest.local, user.dest.domain],
                       'transaction_id': self.messageid,
                       'id': smtp.messageid().split('@')[0].strip('<')
                       }
            return lambda: SmtpMessage(msg)

@implementer(smtp.IMessage)
class SmtpMessage:
    def __init__(self, msg):
        self.lines = []
        self.size = 0
        self.msg = msg

    def lineReceived(self, line):
        self.lines.append(line)
    
    def eomReceived(self):
        self.lines.append('')
        self.msg['message'] = "\n".join(self.lines)
        self.lines = None
        return defer.succeed(squeue.add(self.msg))
    
    def connectionLost(self):
        # There was an error, throw away the stored lines
        self.lines = None

class SerpentESMTP(smtp.ESMTP):
    def ext_AUTH(self, rest):
        if self.canStartTLS and not self.startedTLS:
            self.sendCode(538, 'Unencrypted auth denied')
            return
        if self.authenticated:
            self.sendCode(503, 'Already authenticated')
            return
        parts = rest.split(None, 1)
        chal = self.challengers.get(parts[0].upper(), lambda: None)()
        if not chal:
            self.sendCode(504, 'Unrecognized authentication type')
            return
        self.mode = smtp.AUTH
        self.challenger = chal
        if len(parts) > 1:
            chal.getChallenge() # Discard it, apparently the client does not
                                # care about it.
            rest = parts[1]
        else:
            rest = None
        self.state_AUTH(rest)

class SerpentSMTPFactory(smtp.SMTPFactory):
    protocol = SerpentESMTP

    def __init__(self, *a, **kw):
        smtp.SMTPFactory.__init__(self, *a, **kw)
        self.delivery = SmtpMessageDelivery()

    def buildProtocol(self, addr):
        contextFactory = None
        if conf.tls:
            tls_data = open(conf.tls_pem, 'rb').read()
            cert = ssl.PrivateCertificate.loadPEM(tls_data)
            contextFactory = cert.options()
        p = smtp.SMTPFactory.buildProtocol(self, addr)
        p.ctx = contextFactory
        if conf.tls:
            p.canStartTLS = True
        p.host = conf.smtp_hostname
        p.delivery = self.delivery
        p.challengers = {"LOGIN": LOGINCredentials, "PLAIN": PLAINCredentials}
        return p


@implementer(IRealm)
class SmtpRealm:
    def requestAvatar(self, avatarId, mind, *interfaces):
        if smtp.IMessageDelivery in interfaces:
            return smtp.IMessageDelivery, SmtpMessageDelivery(avatarId), lambda: None
        raise NotImplementedError()



smtp_portal = Portal(SmtpRealm())
