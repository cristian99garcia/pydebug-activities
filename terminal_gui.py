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

#major packages
from terminal import Terminal
from gettext import gettext as _

from gi.repository import Gtk
from gi.repository import Gdk
from sugar3.graphics.toolbutton import ToolButton

#application stuff

from pydebug_logging import _logger


class TerminalGui(Terminal):

    def __init__(self,activity, top_level_toolbox):
        self._activity = activity
        self.toolbox = top_level_toolbox

        Terminal.__init__(self, self)

        #set up tool box/menu buttons
        activity_toolbar = self.toolbox.toolbar

        separator = Gtk.SeparatorToolItem()
        separator.set_draw(True)
        separator.show()
        activity_toolbar.insert(separator, 0)

        activity_go = ToolButton(stock_id=Gtk.STOCK_MEDIA_FORWARD)
        activity_go.set_icon_widget(None)
        activity_go.set_tooltip(_('Start Debugging'))
        activity_go.connect('clicked', self.project_run_cb)
        activity_go.add_accelerator('clicked', self.get_accelerator(), ord('O'), Gdk.ModifierType.CONTROL_MASK, Gtk.AccelFlags.VISIBLE)
        activity_go.show()
        activity_toolbar.insert(activity_go, 0)

        activity_copy_tb = ToolButton('edit-copy')
        activity_copy_tb.set_tooltip(_('Copy'))
        activity_copy_tb.connect('clicked', self._copy_cb)
        activity_toolbar.insert(activity_copy_tb, 3)
        activity_copy_tb.show()

        activity_paste_tb = ToolButton('edit-paste')
        activity_paste_tb.set_tooltip(_('Paste'))
        activity_paste_tb.connect('clicked', self._paste_cb)
        activity_paste_tb.add_accelerator('clicked', self.get_accelerator(), ord('V'), Gdk.ModifierType.CONTROL_MASK, Gtk.AccelFlags.VISIBLE)
        activity_toolbar.insert(activity_paste_tb, 4)
        activity_paste_tb.show()

        activity_tab_tb = ToolButton('list-add')
        activity_tab_tb.set_tooltip(_("Open New Tab"))
        activity_tab_tb.add_accelerator('clicked', self.get_accelerator(), ord('T'), Gdk.ModifierType.CONTROL_MASK, Gtk.AccelFlags.VISIBLE)
        activity_tab_tb.show()
        activity_tab_tb.connect('clicked', self._open_tab_cb)
        activity_toolbar.insert(activity_tab_tb, 5)

        activity_tab_delete_tv = ToolButton('list-remove')
        activity_tab_delete_tv.set_tooltip(_("Close Tab"))
        activity_tab_delete_tv.show()
        activity_tab_delete_tv.connect('clicked', self._close_tab_cb)
        activity_toolbar.insert(activity_tab_delete_tv, 6)

        activity_fullscreen_tb = ToolButton('view-fullscreen')
        activity_fullscreen_tb.set_tooltip(_("Fullscreen"))
        activity_fullscreen_tb.connect('clicked', self._activity._fullscreen_cb)
        activity_toolbar.insert(activity_fullscreen_tb, 7)
        activity_fullscreen_tb.hide()
        
        ###############################################################################
        
    def get_activity_toolbar(self):
        raise NotImplimentedError
        
    def get_accelerator(self):
        raise NotImplimentedError
        
    def project_run_cb(self,button):
        _logger.debug('entered project_run_cb')
        """
        start_script = ['python','import sys','from Rpyc import *','from Rpyc.Utils import remote_interpreter',
                        'c = SocketConnection("localhost")','remote_interpreter(c)']
        for l in start_script:
            self.feed_virtual_terminal(0,l+'\r\n')
        """
        self.start_debugging()
        
    def __keep_clicked_cb(self, button):
        self._keep_activity_info()

    def start_debugging(self): #check for a start up script in bundle root or bundle_root/bin
        command = self.activity_dict.get('command','')
        if command == '':
            self._activity.util.alert('No Activity Loaded')
            return

        _logger.debug("Command to execute:%s."%command)
        self.save_all()
        
        #try to restore a clean debugging environment
        #self.feed_virtual_terminal(0,'quit()\r\n\r\n')
        
        self._activity.set_visible_canvas(self.panes['TERMINAL'])
        #change the menus
        message = _('\n\n Use the HELP in the Ipython interpreter to learn to DEBUG your program.\n')
        self._activity.message_terminal(0,message)
        
        #get the ipython shell object
        """ this works but is not needed now
        ip = ipapi.get()
        arg_str = 'run -d -b %s %s'%(self.pydebug_path,self.child_path)
        ip.user_ns['go'] = arg_str
        _logger.debug('about to use "%s" to start ipython debugger\n'%(arg_str))
        """
        go_cmd = _('go')
        self.feed_virtual_terminal(0,'%s\n'%(go_cmd,))
        pass

