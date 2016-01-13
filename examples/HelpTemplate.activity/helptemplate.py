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

from gi.repository import Gtk
from gi.repository import GObject

import logging
_logger = logging.getLogger('HelpTemplate')
_logger.setLevel(logging.DEBUG)

from sugar3.activity import activity
from sugar3.activity.widgets import StopButton
from sugar3.graphics.toolbutton import ToolButton
from sugar3.graphics.toolbarbox import ToolbarBox
from sugar3.graphics.toolbarbox import ToolbarButton

from help.help import Help

HOME = os.path.join(activity.get_bundle_path(), 'help/XO_Introduction.html')
#HOME = "http://website.com/something.html"
HELP_TAB = 1


class HelpTemplate(activity.Activity):

    def __init__(self, handle):
        activity.Activity.__init__(self, handle, create_jobject = False)

        #following are essential for interface to Help
        self.help_x11 = None
        self.handle = handle
        self.help = Help(self)

        self.toolbarbox = ToolbarBox()
        self.toolbarbox.show_all()

        toolbar = Gtk.Toolbar()
        toolbar.insert(ToolbarButton(page=toolbar, icon_name='help-about'), -1)
        toolbar.show()

        label = Gtk.Button('Help Template')
        label.show()
        self.set_canvas(label)

        self.set_toolbar_box(self.toolbarbox)

    def _toolbar_changed_cb(self,widget, tab_no):
        if tab_no == HELP_TAB:
            self.help_selected()
            
    def set_toolbar(self,tab):
        self.toolbox.set_current_toolbar(tab)
        
    def py_stop(self):
        self.__stop_clicked_cb(None)
        
    def __stop_clicked_cb(self,button):
        _logger.debug('caught stop clicked call back')
        self.close(skip_save = True)

    ################  Help routines
    def help_selected(self):
        """
        if help is not created in a gtk.mainwindow then create it
        else just switch to that viewport
        """
        self.help.activate_help()

