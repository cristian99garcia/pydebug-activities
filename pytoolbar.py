#!/usr/bin/env python
#
# Copyright (C) 2009, George Hunt <georgejhunt@gmail.com>
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

from gi.repository import Gtk
from gi.repository import Gdk

from sugar3.graphics.xocolor import XoColor
from sugar3.graphics.icon import Icon
from sugar3.graphics.toolcombobox import ToolComboBox
from sugar3.graphics.toolbutton import ToolButton
from sugar3.graphics.toolbarbox import ToolbarBox
from sugar3.activity.widgets import ActivityToolbarButton

from gettext import gettext as _

# Initialize logging.
import logging
from sugar3 import logger

#Get the standard logging directory.
std_log_dir = logger.get_logs_dir()
_logger = logging.getLogger('PyDebug')
_logger.setLevel(logging.DEBUG)


class ActivityToolbarBox(ToolbarBox):

    def __init__(self, activity):
        ToolbarBox.__init__(self)

        self._activity = activity
        self._updating_share = False

        self.title = Gtk.Entry()
        self.title.set_size_request(int(Gdk.Screen.width() / 6), -1)
        if activity.metadata:
            self.title.set_text(activity.metadata['title'])
            activity.metadata.connect('updated', self.__jobject_updated_cb)

        self.title.connect('changed', self.__title_changed_cb)
        self._add_widget(self.title)

        lookup = {'plain': 0, 'context': 1, 'verbose': 2}
        traceback = ToolComboBox(label_text=_('Traceback:'))
        traceback.combo.append_item("plain", _('Plain'))
        traceback.combo.append_item('context', _('Context'))
        traceback.combo.append_item('verbose', _('Verbose'))
        index = self._activity.debug_dict.get('traceback',0)
        _logger.debug('retrieved traceback:%s'%(index,))
        traceback.combo.set_active(lookup.get(index,0))
        traceback.combo.connect('changed', self.__traceback_changed_cb)
        self.toolbar.insert(traceback, -1)

        separator = Gtk.SeparatorToolItem()
        separator.props.draw = False
        separator.set_expand(True)
        self.toolbar.insert(separator, -1)

        stop_button = ToolButton('activity-stop')
        stop_button.set_tooltip(_('Stop'))
        stop_button.props.accelerator = '<Ctrl>Q'
        stop_button.connect('clicked', self.__stop_clicked_cb)
        self.toolbar.insert(stop_button, -1)

        self._update_title_sid = None

        self.show_all()

    def _update_share(self):
        self._updating_share = True

        if self._activity.props.max_participants == 1:
            self.share.hide()

        if self._activity.get_shared():
            self.share.set_sensitive(False)
            self.share.combo.set_active(1)

        else:
            self.share.set_sensitive(True)
            self.share.combo.set_active(0)

        self._updating_share = False
    
    def __traceback_changed_cb(self, combo):
        #it = combo.get_active_iter()
        value = combo.get_active()
        _logger.debug('combo box value:%s'%(value,))
        if value == 0:
            self._activity.traceback = 'plain'
            self._activity.debug_dict['traceback'] = 'plain'

        elif value == 1:
            self._activity.traceback = 'context'        
            self._activity.debug_dict['traceback'] = 'context'

        elif value == 2:
            self._activity.traceback = 'verbose'
            self._activity.debug_dict['traceback'] = 'verbose'

        self._activity.set_ipython_traceback()
        
    def __keep_clicked_cb(self, button):
        self._activity.save_icon_clicked = True
        self._activity.copy()

    def __stop_clicked_cb(self, button):
        self._activity.py_stop()

    def __jobject_updated_cb(self, jobject):
        self.title.set_text(jobject['title'])

    def __title_changed_cb(self, entry):
        if not self._update_title_sid:
            self._update_title_sid = GObject.timeout_add(1000, self.__update_title_cb)

    def __update_title_cb(self):
        title = self.title.get_text()

        self._activity.metadata['title'] = title
        self._activity.metadata['title_set_by_user'] = '1'
        self._activity.save()

        self._update_title_sid = None
        return False

    def _add_widget(self, widget, expand=False):
        tool_item = Gtk.ToolItem()
        tool_item.set_expand(expand)

        tool_item.add(widget)

        self.toolbar.insert(tool_item, -1)
        tool_item.show_all()

    def __activity_shared_cb(self, activity):
        self._update_share()

    def __max_participants_changed_cb(self, activity, pspec):
        self._update_share()

