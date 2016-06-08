# -*- coding: utf-8 -*-

import os
import pickle
from glob import iglob
from serpent.config import conf
from serpent.misc import IMAP_FLAGS

class SmtpFileStore(object):
    def __init__(self, dpath):
        self.path = dpath
        if not os.path.exists(dpath):
            os.makedirs(dpath)
    def read(self, fid):
        try:
            with open(os.path.join(self.path, fid), 'rb') as f, open(os.path.join(self.path, fid + '.i'), 'rb') as i:
                data = pickle.load(i)
                try:
                    data['message'] = f.read()
                except:
                    raise
            return data
        except:
            #return False
            raise
    def write(self, data):
        fid = data['id']
        try:
            with open(os.path.join(self.path, fid), 'wb') as f, open(os.path.join(self.path, fid + '.i'), 'wb') as i:
                m = data['message']
                data['message'] = ''
                try:
                    pickle.dump(data, i, 2)
                    f.write(m)
                except:
                    raise
            return True
        except:
            #return False
            raise
    def getinfo(self, fid):
        try:
            with open(os.path.join(self.path, fid + '.i'), 'rb') as i:
                data = pickle.load(i)
            return data
        except:
            return False
    def setinfo(self, data):
        try:
            with open(os.path.join(self.path, data['id'] + '.i'), 'wb') as i:
                pickle.dump(data, i, 2)
            return True
        except:
            return False
    def list(self):
        return [i.split('/')[-1].rstrip('\.i') for i in iglob(self.path + '*.i')]
    def delete(self, fid):
        os.remove(os.path.join(self.path, fid + '.i'))
        os.remove(os.path.join(self.path, fid))

class MailDirStore(object):
    def __init__(self):
        from serpent.imap import mailbox
        from mailbox import MaildirMessage
        self.mbox = mailbox
        self.mbox.MaildirMessage = MaildirMessage
    def deliver(self, user, message):
        mdir = os.path.join(conf.app_dir, conf.maildir_user_path % user)
        if not os.path.exists(mdir):
            os.makedirs(mdir)
        inbox = os.path.join(mdir, 'INBOX')
        mailbox = self.mbox.ExtendedMaildir(inbox)
        msg = self.mbox.MaildirMessage(message)
        try:
            mailbox.add(msg, [])
            return True
        except:
            raise
        