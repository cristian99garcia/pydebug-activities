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

import gtk
import gobject
#import gconf

from sugar.graphics.toolbox import Toolbox
from sugar.graphics.xocolor import XoColor
from sugar.graphics.icon import Icon
from sugar.graphics.toolcombobox import ToolComboBox
from sugar.graphics.toolbutton import ToolButton
from gettext import gettext as _

# Initialize logging.
import logging
from sugar import logger
#Get the standard logging directory. 
std_log_dir = logger.get_logs_dir()
_logger = logging.getLogger('PyDebug')

_logger.setLevel(logging.DEBUG)

class ActivityToolbar(gtk.Toolbar):
    """The Activity toolbar with the Journal entry title, sharing,
       Keep and Stop buttons
    
    All activities should have this toolbar. It is easiest to add it to your
    Activity by using the ActivityToolbox.
    """
    def __init__(self, activity):
        gtk.Toolbar.__init__(self)

        self._activity = activity
        self._updating_share = False
        """
        activity.connect('shared', self.__activity_shared_cb)
        activity.connect('joined', self.__activity_shared_cb)
        activity.connect('notify::max_participants',
                         self.__max_participants_changed_cb)
        """
        #if activity.metadata:
        if True:
            self.title = gtk.Entry()
            self.title.set_size_request(int(gtk.gdk.screen_width() / 6), -1)
            if activity.metadata:
                self.title.set_text(activity.metadata['title'])
                activity.metadata.connect('updated', self.__jobject_updated_cb)
            self.title.connect('changed', self.__title_changed_cb)
            self._add_widget(self.title)

        """
        separator = gtk.SeparatorToolItem()
        separator.props.draw = False
        separator.set_expand(True)
        self.insert(separator, -1)
        separator.show()
        """
        lookup = {'plain':0,'context':1,'verbose':2}
        traceback = ToolComboBox(label_text=_('Traceback:'))
        traceback.combo.append_item("plain", _('Plain'))
        traceback.combo.append_item('context', _('Context'))
        traceback.combo.append_item('verbose', _('Verbose'))
        index = self._activity.debug_dict.get('traceback',0)
        _logger.debug('retrieved traceback:%s'%(index,))
        traceback.combo.set_active(lookup.get(index,0))
        traceback.combo.connect('changed', self.__traceback_changed_cb)
        self.insert(traceback, -1)
        traceback.show()
        """
        self._update_share()
        
        self.keep = ToolButton(tooltip=_('Keep'))
        #client = gconf.client_get_default()
        #color = XoColor(client.get_string('/desktop/sugar/user/color'))
        #keep_icon = Icon(icon_name='document-save', xo_color=color)
        keep_icon = Icon(icon_name='document-save')
        self.keep.set_icon_widget(keep_icon)
        keep_icon.show()
        #self.keep.props.accelerator = '<Ctrl>S'
        self.keep.connect('clicked', self.__keep_clicked_cb)
        self.insert(self.keep, -1)
        self.keep.hide()
        """
        separator = gtk.SeparatorToolItem()
        separator.props.draw = False
        separator.set_expand(True)
        self.insert(separator, -1)
        separator.show()

        stop_button = ToolButton('activity-stop')
        stop_button.set_tooltip(_('Stop'))
        #stop_button.props.accelerator = '<Ctrl>Q'
        stop_button.connect('clicked', self.__stop_clicked_cb)
        self.insert(stop_button, -1)
        stop_button.show()

        self._update_title_sid = None

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
        it = combo.get_active_iter()
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
        self._activity.close()

    def __jobject_updated_cb(self, jobject):
        self.title.set_text(jobject['title'])

    def __title_changed_cb(self, entry):
        if not self._update_title_sid:
            self._update_title_sid = gobject.timeout_add(
                                                1000, self.__update_title_cb)

    def __update_title_cb(self):
        title = self.title.get_text()

        self._activity.metadata['title'] = title
        self._activity.metadata['title_set_by_user'] = '1'
        self._activity.save()
        """
        shared_activity = self._activity.get_shared_activity()
        if shared_activity:
            shared_activity.props.name = title
        """
        self._update_title_sid = None
        return False

    def _add_widget(self, widget, expand=False):
        tool_item = gtk.ToolItem()
        tool_item.set_expand(expand)

        tool_item.add(widget)
        widget.show()

        self.insert(tool_item, -1)
        tool_item.show()

    def __activity_shared_cb(self, activity):
        self._update_share()

    def __max_participants_changed_cb(self, activity, pspec):
        self._update_share()

class ActivityToolbox(Toolbox):
    """Creates the Toolbox for the Activity
    
    By default, the toolbox contains only the ActivityToolbar. After creating
    the toolbox, you can add your activity specific toolbars, for example the
    EditToolbar.
    
    To add the ActivityToolbox to your Activity in MyActivity.__init__() do:
    
        # Create the Toolbar with the ActivityToolbar: 
        toolbox = activity.ActivityToolbox(self)
        ... your code, inserting all other toolbars you need, like EditToolbar
        
        # Add the toolbox to the activity frame:
        self.set_toolbox(toolbox)
        # And make it visible:
        toolbox.show()
    """
    def __init__(self, activity):
        Toolbox.__init__(self)
        
        self._activity_toolbar = ActivityToolbar(activity)
        self.add_toolbar(_('Activity'), self._activity_toolbar)
        self._activity_toolbar.show()

    def get_activity_toolbar(self):
        return self._activity_toolbar


