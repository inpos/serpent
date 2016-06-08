# -*- coding: utf-8 -*-

from twisted.cred.checkers import ICredentialsChecker
from twisted.cred import credentials, error
from twisted.python import failure
from twisted.internet import reactor, defer
from twisted.internet.task import LoopingCall

from zope.interface import implementer

from mech_smtp import SerpentSMTPFactory, smtp_portal
from mech_imap import SerpentIMAPFactory, imap_portal
from serpent.usrpwd import dbs
from serpent.queue import squeue
from serpent.config import conf

@implementer(ICredentialsChecker)
class CredChecker(object):
    '''Класс проверки данных авторизации.
Параметром в конструктор передаётся список (list()) объектов баз пользователей.'''
    credentialInterfaces = (credentials.IUsernamePassword,
                            credentials.IUsernameHashedPassword)
    
    def __init__(self, dbs):
        self.dbs = dbs
    
    def _cbPasswordMatch(self, matched, username):
        if matched:
            return username
        else:
            return failure.Failure(error.UnauthorizedLogin())
    
    def requestAvatarId(self, credentials):
        found_user = False
        for db in self.dbs:
            found_user = db.user_exist(credentials.username)
            if found_user:
                pwdfunc = db.check_pw
                break
        if found_user:
            return defer.maybeDeferred(
                pwdfunc, [credentials.username, credentials.password]).addCallback(
                self._cbPasswordMatch, str(credentials.username))
        else:
            return defer.fail(error.UnauthorizedLogin())

checker = CredChecker(dbs)
smtp_portal.registerChecker(checker)
smtp_factory = SerpentSMTPFactory(smtp_portal)
imap_portal.registerChecker(checker)
imap_factory = SerpentIMAPFactory(imap_portal)
    
reactor.listenTCP(2500, smtp_factory)
reactor.listenTCP(1430, imap_factory)

qtask = LoopingCall(squeue.run)
qtask.start(conf.smtp_queue_check_period)

reactor.run()