# -*- coding: utf-8 -*-

userdb = {
         'user1': ['password1', 'local1', 'dom.lan'],
         'user2': ['password2', 'local2', 'dom.lan']
         }

class DictUDB(object):
    def __init__(self, userdb = userdb):
        self. userdb = userdb
    def username_by_email(self, email = None):
        if not email:
            return None
        for usr in self.userdb.keys():
            if email[0] == self.userdb[usr][1] and email[1] == self.userdb[usr][2]:
                return usr
        return False
    def check_pw(self, creds):
        usr = creds[0]
        pwd = creds[1]
        return usr in self.userdb.keys() and pwd == self.userdb[usr][0]
    def user_exist(self, username):
        return username in self.userdb.keys()
dbs = [DictUDB()]