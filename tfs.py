#!/usr/bin/env python
# -*- coding: utf-8 -*-

import fuse
from lxml import html
import urllib2
import os
import stat
import time
import logging
import traceback
import sys
import errno

fuse.fuse_python_api = (0, 2)

class MyStat(fuse.Stat):
	def __init__(self):
		self.st_mode = stat.S_IFDIR | 0755
		self.st_ino = 0
		self.st_dev = 0
		self.st_nlink = 2
		self.st_uid = os.geteuid()
		self.st_gid = os.getegid()
		self.st_size = 4096
		self.st_atime = time.time()
		self.st_mtime = time.time()
		self.st_ctime = time.time()

class TFS(fuse.Fuse):

    class tdirentry(dict):
        pass
    
    def __init__(self, *args, **kw):
        fuse.Fuse.__init__(self, *args, **kw)

    def fsinit(self):
        self.dirs = self.tdirentry()
        self.dirs.mode = stat.S_IFDIR | 0755
        self.dirs.size = 0
        self.load_content(self.dirs, "http://tenshi.ru/anime-ost")
        self.cache = {}

    def load_content(self, curdir, url):
        if not curdir.size:
            logging.debug("Loading: %s" % url)
            curdir.size = 4096
            page = html.parse(url)
            for e in page.xpath('//img[@src="/icons/folder.gif"]/following-sibling::a[1]'):
                dirpath = e.text[:-1]
                dirurl = e.get('href')[:-1]
                logging.debug("dirpath: %s" % dirpath)
                if not dirpath in curdir:
                    curdir[dirpath] = self.tdirentry()
                    curdir[dirpath].mode = stat.S_IFDIR | 0755
                    curdir[dirpath].size = 0
                    curdir[dirpath].url = dirurl
            for e in page.xpath('//img[@src="/icons/sound2.gif"]/following-sibling::a[1]'):
                dirpath = e.text
                fileurl = e.get('href')
                logging.debug("File: %s url %s" % (dirpath, url))
                if not dirpath in curdir:
                    curdir[dirpath] = self.tdirentry()
                    curdir[dirpath].mode = stat.S_IFREG | 0444
                    curdir[dirpath].size = int(urllib2.urlopen(url + "/" + fileurl).info().getheader("Content-Length"))
                    curdir[dirpath].url = fileurl
        else:
            logging.debug("Skipping loading: %s" % url)
            return
        
        
    def dirlist(self, path, content):
        curdir = self.dirs
        url = "http://tenshi.ru/anime-ost"
        logging.debug("Dirlist: %s" % path)
        splitpath = path.split("/")
        logging.debug("Split: %s" % splitpath)
        cnt = len(splitpath) - 1
        for pathpart in splitpath:
            if pathpart != "":
                if not pathpart in curdir:
                    return None, ""
                curdir = curdir[pathpart]
                url += "/" + curdir.url
                if content or cnt:
                    self.load_content(curdir, url)
            cnt -= 1

        return curdir, url
                    
    def getattr(self, path):
        try:
            st = MyStat()
            logging.debug("Getting attrs for %s" % path)
            tentry, _ = self.dirlist(path[1:], False)
            if tentry == None:
                return -errno.ENOENT
            logging.debug("Got %d - %d" % (tentry.size, tentry.mode))
            st.st_mode = tentry.mode
            st.st_size = tentry.size
            return st
        except:
            logging.critical(str("".join(traceback.format_exception(*sys.exc_info()))))


    def readdir(self, path, offset):
        try:
            direntries = ['.', '..']
            tentry, _ = self.dirlist(path[1:], True)
            if tentry == None:
                return
            
            direntries.extend(tentry.keys())
            for r in direntries:
                yield fuse.Direntry(r)
        except:
            logging.critical(str("".join(traceback.format_exception(*sys.exc_info()))))

    def read(self, path, size, offset):
        try:
            tentry, url = self.dirlist(path[1:], False)
            if tentry == None:
                return -errno.ENOENT
            logging.debug("Read: %s [%d + %d]" % (url, offset, size))
            end = offset + size
            if path in self.cache:
                logging.debug("Pos: %d End: %d" % (self.cache[path]["pos"], end))
                if self.cache[path]["pos"] < end:
                    self.cache[path]["data"] += self.cache[path]["handle"].read(end - self.cache[path]["pos"])
                    self.cache[path]["pos"] = end
            else:
                self.cache[path] = {}
                self.cache[path]["handle"] = urllib2.urlopen(url)
                self.cache[path]["data"] = self.cache[path]["handle"].read(end)
                self.cache[path]["pos"] = end

            return self.cache[path]["data"][offset:end]
        
        except:
            logging.critical(str("".join(traceback.format_exception(*sys.exc_info()))))

logging.basicConfig(filename="tfsdebug.log", level=logging.DEBUG)

try:
    fs = TFS()
    fs.multithreaded = 0
    fs.parse(errex=1)
    fs.main()
except fuse.FuseError:
    raise
