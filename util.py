#!/usr/bin/env python
# Copyright (C) 2009, George Hunt <georgejhunt@gmail.com>
# Copyright (C) 2009, One Laptop Per Child
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA  02110-1301  USA

from __future__ import with_statement
import os
from subprocess import Popen, PIPE

from gettext import gettext as _

#major packages
import gtk
import hashlib
import time

#from jarabe.model import shell
#home_model = shell.get_model()

#sugar stuff
from sugar.graphics.alert import *

import logging
from  pydebug_logging import _logger

__pdb = None

class Utilities():
    def __init__(self,activity):
        self._activity = __pdb = activity
        self.home_model = None
        
    #####################            ALERT ROUTINES   ##################################
    
    def alert(self,msg,title=None):
        alert = NotifyAlert(0)
        if title != None:
            alert.props.title=_('There is no Activity file')
        alert.props.msg = msg
        alert.connect('response',self.no_file_cb)
        self._activity.add_alert(alert)
        return alert
        
    def no_file_cb(self,alert,response_id):
        self._activity.remove_alert(alert)

    from sugar.graphics.alert import ConfirmationAlert
  
    def confirmation_alert(self,msg,title=None,confirmation_cb = None):
        alert = ConfirmationAlert()
        alert.props.title=title
        alert.props.msg = msg
        alert.pydebug_cb = confirmation_cb
        alert.connect('response', self._alert_response_cb)
        self._activity.add_alert(alert)
        return alert

    #### Method: _alert_response_cb, called when an alert object throws a
                 #response event.
    def _alert_response_cb(self, alert, response_id):
        #remove the alert from the screen, since either a response button
        #was clicked or there was a timeout
        this_alert = alert  #keep a reference to it
        self._activity.remove_alert(alert)
        #Do any work that is specific to the type of button clicked.
        if response_id is gtk.RESPONSE_OK and this_alert.pydebug_cb != None:
            this_alert.pydebug_cb (this_alert, response_id)
            
        
    def set_dirty(self, dirty):
        self.dirty = dirty

    def md5sum_buffer(self, buffer, hash = None):
        if hash == None:
            hash = hashlib.md5()
        hash.update(buffer)
        return hash.hexdigest()

    def md5sum(self, filename, hash = None):
        """return hexdigest of single file"""
        h = self._md5sum(filename,hash)
        return h.hexdigest()
       
    def _md5sum(self, filename, hash = None):
        """return hash of single file"""
        if hash == None:
            hash = hashlib.md5()
        try:
            fd = None
            fd =  open(filename, 'rb')
            while True:
                block = fd.read(128)
                if not block: break
                hash.update(block)
        finally:
            if fd != None:
                fd.close()
        return hash
    
    def md5sum_tree(self, root):
        """return hexdigest of file tree under root"""
        if not (root and os.path.isdir(root)):
            return None
        h = hashlib.md5()
        for dirpath, dirnames, filenames in os.walk(root):
            for filename in filenames:
                abs_path = os.path.join(dirpath, filename)
                h = self._md5sum(abs_path, h)
                #print abs_path
        return h.hexdigest()
    
    def set_permissions(self,root, perms='664'):
        """walk a directory setting permissions"""
        if not os.path.isdir(root):
            return None
        for dirpath, dirnames, filenames in os.walk(root):
            for filename in filenames:
                abs_path = os.path.join(dirpath, filename)
                old_perms = os.stat(abs_path).st_mode
                if os.path.isdir(abs_path):
                    new_perms = int(perms,8) | int('771',8)
                else:
                    new_perms = old_perms | int(perms,8)
                os.chmod(abs_path,new_perms)
    
    def sugar_version(self):
        """return list with four elements (error=0) (major,minor,micro,release)"""
        cmd = 'rpm -q sugar'
        reply,err = self.command_line(cmd)
        if reply and reply.find('sugar') > -1:
            version = reply.split('-')[1]
            version_chunks = version.split('.')
            release_holder = reply.split('-')[2]
            release = release_holder.split('.')[0]
            return (int(version_chunks[0]),int(version_chunks[1]),\
                    int(version_chunks[2]),int(release),)
        return (0, 0, 0, 0)

    def command_line(self, cmd, alert_error=True):
        """send cmd line to shell, rtn (text,error code)"""
        _logger.debug('command_line cmd:%s'%cmd)
        p1 = Popen(cmd,stdout=PIPE, shell=True)
        output = p1.communicate()
        if p1.returncode != 0 :
            _logger.debug('error returned from shell command: %s was %s'%(cmd,output[0]))
            if alert_error: self.alert(_('%s Command returned non zero\n'%cmd+output[0]))
        return output[0],p1.returncode
        
    def non_conflicting(self,root,basename):
        """
        create a non-conflicting filename by adding '-<number>' to a filename before extension
        """
        ext = ''
        basename = basename.split('.')
        word = basename[0]
        if len(basename) > 1:
            ext = '.' + basename[1]
        adder = ''
        index = 0
        while (os.path.isfile(os.path.join(root, word + adder + ext)) or 
                                os.path.isdir(os.path.join(root, word + adder + ext))):
            index += 1
            adder = '-%s'%index
        _logger.debug('non conflicting:%s'%os.path.join(root, word + adder +  ext))
        return os.path.join(root, word + adder + ext)
    
    def get_home_model(self):
        """Use shell model to return home_model
           --the home_model code changed between .82 and .84 sugar
           --so do the lookup differently depending on sugar version
        """
        global home_model
        (major, minor, micro, release) = self.sugar_version() 
        _logger.debug('sugar version %s'%minor)
        
        if minor and minor >= 84:
            _logger.debug('using jarabe')
            from jarabe.model import shell
            home_model = shell.get_model()
        else:
            if not '/usr/share/sugar/shell/' in sys.path:
                sys.path.append('/usr/share/sugar/shell/')
            import view.Shell
            instance = view.Shell.get_instance()
            home_model = instance.get_model().get_home()
        if home_model:
            return home_model
        else:
            _logger.error('failed to retrieve home model')
            return None
        
        return home_model
        
    def get_activity_from_activity_id(self, activity_id):
        if not self.home_model:
            self.home_model = self.get_home_model()
        if self.home_model:
            return self.home_model._get_activity_by_id(activity_id)
        return None
    
    def get_wnck_window_from_activity_id(self, activity_id):
        """use sugar home_model to get X11 window specified by activity_id"""
        _logger.debug('entered get_wnck_window_from_activity_id. id:%s'%activity_id)
        activity = self.get_activity_from_activity_id()
        if activity:
            return activity.get_window()
        else:
            _logger.debug('wnck_window was none')
            return None
        
    def get_wnck_window_from_bundle_id(self, bundle_id):
        """get the window associated with bundle_id or None"""
        if not self.home_model:
            self.home_model = self.get_home_model()
        if self.home_model:
            activity_list = self.home_model._get_activities_with_window()
            _logger.debug('length of activity_list:%s'%(len(activity_list,)))
            if activity_list:
                for activity in activity_list:
                    if activity.get_type == bundle_id:
                        return activity.get_window()
            _logger.debug("failed to find %s"%(bundle_id,))
            return None
        
    def get_wnck_window_from_xid(self, xid):
        """select shell activity, get window, via xid"""
        if not self.home_model:
            self.home_model = self.get_home_model()
        if self.home_model:
            return self.home_model._get_activity_by_xid(xid).get_window()
        else:
            _logger.debug('failed to get window associated with xid:%s'%(xid,))
            return None
        
    def get_xid(self):
        """return the X11 window id of the main window"""
        screen = gtk.gdk.screen_get_default()
        root = screen.get_root_window()
        if root:
            return root.xid
        else:
            _logger.debug('failed to get xid')
            return None
        
    def activate_xid(self,xid):
        """ use the shell model to look up the window from xid, activat window"""
        window = self.get_wnck_window_from_xid(xid)
        if window:
            window.activate(gtk.get_current_event_time())
        else:
            _logger.debug('failed to get window from xid:%s'%(xid,))
            
    def activate_bundle_id(self, bundle_id):
        """get shell activity, look up window, and activate"""
        window = self.get_wnck_window_from_bundle_id(bundle_id)
        if window:
            window.activate(gtk.get_current_event_time())
        
        
    def get_current_activity(self):
        """returns the shell activity object for current window"""
        if not self.home_model:
            self.home_model = self.get_home_model()
        if self.home_model:
            return self.home_model.get_activity_by_xid(self.get_xid())
        else:
            return None
                
   
