from mailbox import Maildir
import os

class ExtendedMaildir(Maildir):
    def set_flags(self, key, flags):
        sflags = sorted(flags)
        if sflags == self.get_flags(key): return True
        subpath = self._lookup(key)
        info = '2,' + ''.join(sflags)
        oldpath = os.path.join(self._path, subpath)
        newsubdir = os.path.split(subpath)[0]
        newname = key + self.colon + info
        if 'S' not in sflags and newsubdir == 'new':
            newsubdir = 'cur'
        newpath = os.path.join(self._path, newsubdir, newname)
        if hasattr(os, 'link'):
            os.link(oldpath, newpath)
            os.remove(oldpath)
        else:
            os.rename(oldpath, newpath)
        self._toc[key] = os.path.join(newsubdir, newname)
    def get_flags(self, key):
        subpath = self._lookup(key)
        _, name = os.path.split(subpath)
        info = name.split(self.colon)[-1]
        if info.startswith('2,'):
            return info[2:]
        else:
            return ''
    def add_flag(self, flag):
        self.set_flags(''.join(set(self.get_flags()) | set(flag)))
    def remove_flag(self, flag):
        if self.get_flags():
            self.set_flags(''.join(set(self.get_flags()) - set(flag)))