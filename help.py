# Copyright (C) 2006, Red Hat, Inc.
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

import os
from gettext import gettext as _
from subprocess import Popen
from subprocess import PIPE

from gi.repository import Gtk
from gi.repository import GObject

from sugar3 import util

from jarabe.model import shell

from sugar3.activity import activity
from sugar3.graphics.window import Window
from sugar3.graphics.toolbutton import ToolButton
from sugar3.graphics.toolbarbox import ToolbarBox
from sugar3.activity.activityhandle import ActivityHandle
from sugar3.activity.widgets import ToolbarButton
from sugar3 import env

#from IPython.Debugger import Tracer
from pdb import *
from browser import Browser

GObject.threads_init()

HELP_PANE = 3

# Initialize logging.
import logging
_logger = logging.getLogger('PyDebug')


class Help(Window):

    def __init__(self, parent):
        self.pydebug = parent

        self.help_id = None
        self.handle = ActivityHandle()
        self.handle.activity_id = util.unique_id()

        Window.__init__(self)
        self.connect('realize',self.realize_cb)

        self._web_view = Browser()

        #determine which language we are going to be using
        help_root = self.get_help_root()
        self.HOME = os.path.join(help_root, 'PyDebug.htm')
    
        self.toolbarbox = ToolbarBox()
        self.set_toolbar_box(self.toolbarbox)
        self.toolbarbox.show()

        ##activitybar = Gtk.Toolbar()
        ##self.toolbarbox.add_toolbar(_('Activity'), activitybar)
        ##activitybar.show_all()

        editbar = Gtk.Toolbar()
        self.toolbarbox.toolbar.insert(ToolbarButton(page=editbar, icon_name='toolbar-edit'), -1)
        editbar.show_all()

        projectbar = Gtk.Toolbar()
        self.toolbarbox.toolbar.insert(ToolbarButton(page=self, icon_name='system-run'), -1)
        projectbar.show_all()

        self.help_toolbar = Toolbar(self, self._web_view)
        self.help_toolbar.show()
        self.toolbarbox.toolbar.insert(ToolbarButton(page=self.help_toolbar, icon_name="help-about"), -1)

        self.set_canvas(self._web_view)
        self._web_view.show()

        self._web_view.load_uri(self.HOME)
        self.pid = Popen(['/usr/bin/pydoc', '-p', '23432'])
        
    def close_pydoc(self):
        _logger.debug('closing pid %s' % (self.pid.pid,))
        self.killpid = Popen(['kill', str(self.pid.pid)])

    def get_help_toolbar(self):
        return self.help_toolbar

    def realize_help(self):
        _logger.debug('realize help called Version: %s pydebug activity id:%s' % (version, self.pydebug.handle.activity_id))
        #trial and error suggest the following pydebug activation is necesssary to return reliably to pydebug window
        self.pywin = self.get_wnck_window_from_activity_id(str(self.pydebug.handle.activity_id))
        if self.pywin:
            self.pywin.activate(Gtk.get_current_event_time())
            _logger.debug('pywin.activate called')

        self.show_all()

        return self

    def realize_cb(self, window):
        self.help_id = util.unique_id()
        ##wm.set_activity_id(window.window, self.help_id)
        self.help_window = window
            
    def activate_help(self):
        _logger.debug('activate_help called')
        self.help_window.show()
        window = self.get_wnck_window_from_activity_id(self.help_id)

        if window:
            window.activate(Gtk.get_current_event_time())

        else:
            _logger.debug('failed to get window')

    def goto_cb(self, page, tab):
        _logger.debug('current_toolbar_changed event called goto_cb. tab: %s'%tab)
        if tab == HELP_PANE:
            return

        if not self.help_id:
            return

        self.pydebug.set_toolbar(tab)
        self.help_window.hide()
        self.pywin = self.get_wnck_window_from_activity_id(str(self.pydebug.handle.activity_id))
        if self.pywin:
            self.pywin.activate(Gtk.get_current_event_time())

    def get_wnck_window_from_activity_id(self, activity_id):
        """Use shell model to look up the wmck window associated with activity_id
           --the home_model code changed between .82 and .84 sugar
           --so do the lookup differently depending on sugar version
        """
        _logger.debug('get_wnck_window_from_activity_id. id:%s' % activity_id)
        _logger.debug('sugar version %s' % version)

        if version and version >= 0.839:
            home_model = shell.get_model()
            activity = home_model.get_activity_by_id(activity_id)
        else:
            instance = view.Shell.get_instance()
            home_model = instance.get_model().get_home()
            activity = home_model._get_activity_by_id(activity_id)

        if activity:
            return activity.get_window()
        else:
            _logger.debug('wnck_window was none')
            return None
        
    def get_help_root(self):
        lang = os.environ.get('LANGUAGE')
        if not lang:
            lang = os.environ.get('LANG')

        if not lang:
            lang = 'en_US'

        if len(lang) > 1:
            two_char = lang[:2]

        root = os.path.join(os.environ['SUGAR_BUNDLE_PATH'], 'help', two_char)
        if os.path.isdir(root):
            return root

        root = os.path.join(os.environ['SUGAR_ACTIVITY_ROOT'], 'help', two_char)
        if os.path.isdir(root):
            return root

        #default to a non localized root
        root = os.path.join(os.environ['SUGAR_BUNDLE_PATH'], 'help')
        return root


class Toolbar(Gtk.Toolbar):

    def __init__(self, parent, web_view):
        GObject.GObject.__init__(self)
        
        self._help = parent
        self._web_view = web_view

        self._back = ToolButton('go-previous-paired')
        self._back.set_tooltip(_('Back'))
        self._back.props.sensitive = False
        self._back.connect('clicked', self._go_back_cb)
        self.insert(self._back, -1)
        self._back.show()

        self._forward = ToolButton('go-next-paired')
        self._forward.set_tooltip(_('Forward'))
        self._forward.props.sensitive = False
        self._forward.connect('clicked', self._go_forward_cb)
        self.insert(self._forward, -1)
        self._forward.show()

        home = ToolButton('zoom-home')
        home.set_tooltip(_('Home'))
        home.connect('clicked', self._go_home_cb)
        self.insert(home, -1)
        home.show()

        separator = Gtk.SeparatorToolItem()
        separator.set_draw(False)
        separator.set_expand(True)
        self.insert(separator, -1)
        separator.show()

        stop_button = ToolButton('activity-stop')
        stop_button.set_tooltip(_('Stop'))
        #stop_button.props.accelerator = '<Ctrl>Q'
        stop_button.connect('clicked', self.__stop_clicked_cb)
        self.insert(stop_button, -1)
        stop_button.show()

        ## FIXME
        ##progress_listener = self._web_view.progress
        ##progress_listener.connect('location-changed',
        ##                              self._location_changed_cb)
        ##progress_listener.connect('loading-stop', self._loading_stop_cb)

    def __stop_clicked_cb(self, button):
        self._help.pydebug.py_stop()

    def _location_changed_cb(self, progress_listener, uri):
        self.update_navigation_buttons()
        _logger.debug('location change cb')

    def _loading_stop_cb(self, progress_listener):
        self.update_navigation_buttons()

    def update_navigation_buttons(self):
        self._back.props.sensitive = self._web_view.can_go_back()
        self._forward.props.sensitive = self._web_view.can_go_forward()

    def _go_back_cb(self, button):
        self._web_view.go_back()
    
    def _go_forward_cb(self, button):
        self._web_view.go_forward()

    def _go_home_cb(self, button):
        self._web_view.load_uri(self._help.HOME)


class EarlyListener(object):

    def __init__(self, toolbar):
        self._toolbar = toolbar
    
    def onLocationChange(self, webProgress, request, location):
        self._toolbar.update_navigation_buttons()
        
    def onProgressChange(self, webProgress, request, curSelfProgress,
                         maxSelfProgress, curTotalProgress, maxTotalProgress):
        pass
    
    def onSecurityChange(self, webProgress, request, state):
        pass

    def onStateChange(self, webProgress, request, stateFlags, status):
        pass

    def onStatusChange(self, webProgress, request, status, message):
        pass


def command_line(cmd):
    _logger.debug('command_line cmd:%s' % cmd)
    p1 = Popen(cmd, stdout=PIPE, shell=True)
    output = p1.communicate()
    if p1.returncode != 0:
        return None

    return output[0]
    
def sugar_version():
    cmd = '/bin/rpm -q sugar'
    reply = command_line(cmd)
    if reply and reply.find('sugar') > -1:
        version = reply.split('-')[1]
        version_chunks = version.split('.')
        major_minor = version_chunks[0] + '.' + version_chunks[1]
        return float(major_minor)

    return None

