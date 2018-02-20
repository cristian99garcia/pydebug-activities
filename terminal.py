# Copyright (C) 2007, Eduardo Silva <edsiper@gmail.com>.
# Copyright (C) 2008, One Laptop Per Child
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

# Initialize logging.
import logging
_logger = logging.getLogger('PyDebug')

from gi.repository import Gtk
from gi.repository import Gdk
from gi.repository import Vte
from gi.repository import GLib
from gi.repository import Pango

from sugar3.graphics.toolbutton import ToolButton
from sugar3.activity import activity
from sugar3 import env
from sugar3.activity import bundlebuilder


MASKED_ENVIRONMENT = [
    'DBUS_SESSION_BUS_ADDRESS',
    'PPID'
]


class Terminal:

    def __init__(self, activity):
        self.terminal_notebook = Gtk.Notebook()
        self._create_tab({'cwd' :self.sugar_bundle_path})
        self._create_tab({'cwd' :self.activity_playpen})

        go_cmd = _('go')
        alias_cmd = 'alias %s="%s/bin/ipython.py "\n' % (go_cmd, self.sugar_bundle_path)
        self.feed_virtual_terminal(0, alias_cmd)
        self.feed_virtual_terminal(0, 'clear\n%s/bin/ipython.py  \n' % self.sugar_bundle_path)

    def _get_terminal_canvas(self):
        self.terminal_notebook.set_property("tab-pos", Gtk.PositionType.TOP)
        self.terminal_notebook.set_scrollable(True)
        self.terminal_notebook.show()

        return self.terminal_notebook

    def _open_tab_cb(self, btn):
        index = self._create_tab(None)
        self.terminal_notebook.page = index

    def _close_tab_cb(self, btn):
        self._close_tab(self.terminal_notebook.props.page)

    def _prev_tab_cb(self, btn):
        if self.terminal_notebook.props.page == 0:
            self.terminal_notebook.props.page = self.terminal_notebook.get_n_pages() - 1

        else:
            self.terminal_notebook.props.page = self.terminal_notebook.props.page - 1

        vt = self.terminal_notebook.get_nth_page(self.terminal_notebook.get_current_page()).vt
        vt.grab_focus()

    def _next_tab_cb(self, btn):
        if self.terminal_notebook.props.page == self.terminal_notebook.get_n_pages() - 1:
            self.terminal_notebook.props.page = 0

        else:
            self.terminal_notebook.props.page = self.terminal_notebook.props.page + 1

        vt = self.terminal_notebook.get_nth_page(self.terminal_notebook.get_current_page()).vt
        vt.grab_focus()

    def _close_tab(self, index):
        num_pages = self.terminal_notebook.get_n_pages()
        if num_pages > 1:
            self.terminal_notebook.remove_page(index)
            for i in range(num_pages):
                self.terminal_notebook.set_tab_label(
                    self.terminal_notebook.get_nth_page(i),
                    Gtk.Label('Tab ' + str(i+1)))

    def _tab_child_exited_cb(self, vt):
        for i in range(self.terminal_notebook.get_n_pages()):
            if self.terminal_notebook.get_nth_page(i).vt == vt:
                self._close_tab(i)
                return

    def _tab_title_changed_cb(self, vt):
        for i in range(self.terminal_notebook.get_n_pages()):
            if self.terminal_notebook.get_nth_page(i).vt == vt:
                label = self.terminal_notebook.get_nth_page(i).label
                title = vt.get_window_title()
                label.set_text(title[title.rfind('/') + 1:])

                return

    def _drag_data_received_cb(self, widget, context, x, y, selection, target, time):
        widget.feed_child(selection.data)
        context.finish(True, False, time)
        return True

    def _create_tab(self, tab_state):
        vt = Vte.Terminal()
        vt.drag_dest_set(Gtk.DestDefaults.MOTION | Gtk.DestDefaults.DROP,
            [Gtk.TargetEntry.new('text/plain', 0, 0),
             Gtk.TargetEntry.new('STRING', 0, 1)],
            Gdk.DragAction.DEFAULT | Gdk.DragAction.COPY)

        vt.connect("child-exited", self._tab_child_exited_cb)
        vt.connect("window-title-changed", self._tab_title_changed_cb)
        vt.connect('drag_data_received', self._drag_data_received_cb)
        self._configure_vt(vt)
        vt.show()

        label = Gtk.Label('Tab ' + str(self.terminal_notebook.get_n_pages() + 1))

        scrollbar = Gtk.VScrollbar.new(vt.get_vadjustment())
        scrollbar.show()

        box = Gtk.HBox()
        box.pack_start(vt, True, True, 0)
        box.pack_start(scrollbar, False, False, 0)

        box.vt = vt
        box.label = label

        index = self.terminal_notebook.append_page(box, label)
        if index == 0:
            vt.set_colors(Gdk.RGBA.from_color(Gdk.Color.parse('#000000')[1]),
                          Gdk.RGBA.from_color(Gdk.Color.parse('#FFFFCC')[1]),
                          [])

        self.terminal_notebook.show_all()

        # Launch the default shell in the HOME directory.
        os.chdir(os.environ["HOME"])

        if tab_state:
            # Restore the environment.
            # This is currently not enabled.
            env = tab_state.get('env', [])

            filtered_env = []
            for e in env:
                var, sep, value = e.partition('=')
                if var not in MASKED_ENVIRONMENT:
                    filtered_env.append(var + sep + value)

            # Restore the working directory.
            if tab_state.has_key('cwd'):
                os.chdir(tab_state['cwd'])

            # Restore the scrollback buffer.
            if tab_state.has_key('scrollback'):
                for l in tab_state['scrollback']:
                    vt.feed(l + '\r\n')

        args = (Vte.PtyFlags.DEFAULT,
                os.environ["HOME"],
                ["/bin/bash"],
                [],
                GLib.SpawnFlags.DO_NOT_REAP_CHILD,
                None, None)

        if hasattr(vt, 'fork_command_full'):
            vt.fork_command_full(*args)
        else:
            vt.spawn_sync(*args)

        self.terminal_notebook.props.page = index

        vt.connect("realize", lambda vt: vt.grab_focus())

        return index

    def feed_virtual_terminal(self,terminal,command):
        if terminal > len(self.terminal_notebook)-1 or terminal < 0:
            _logger.debug('in feed_virtual_terminal: terminal out of bounds %s'%terminal)
            return

        self.terminal_notebook.set_current_page(terminal)
        vt = self.terminal_notebook.get_nth_page(terminal).vt
        vt.feed_child(command, len(command))

    def message_terminal(self,terminal,command):
        if terminal > len(self.terminal_notebook)-1 or terminal < 0:
            _logging.debug('in feed_virtual_terminal: terminal out of bounds %s'%terminal)
            return

        self.terminal_notebook.set_current_page(terminal)
        vt = self.terminal_notebook.get_nth_page(terminal).vt
        vt.feed(command)

    def _copy_cb(self, button):
        vt = self.terminal_notebook.get_nth_page(self.terminal_notebook.get_current_page()).vt
        if vt.get_has_selection():
            vt.copy_clipboard()

    def _paste_cb(self, button):
        vt = self.terminal_notebook.get_nth_page(self.terminal_notebook.get_current_page()).vt
        vt.paste_clipboard()

    def _become_root_cb(self, button):
        vt = self.terminal_notebook.get_nth_page(self.terminal_notebook.get_current_page()).vt
        vt.feed('\r\n')
        vt.fork_command("/bin/su", ('/bin/su', '-'))

    def set_terminal_focus(self):
        self.terminal_notebook.grab_focus()
        page = self.terminal_notebook.get_nth_page(self.terminal_notebook.get_current_page())
        page.grab_focus()
        vt = page.vt
        vt.grab_focus()
        _logger.debug('attemped to grab focus')
        return False

    def _fullscreen_cb(self, btn):
        self.fullscreen()

    def _key_press_cb(self, window, event):
        # Escape keypresses are routed directly to the vte and then dropped.
        # This hack prevents Sugar from hijacking them and canceling fullscreen mode.
        if Gdk.keyval_name(event.keyval) == 'Escape':
            vt = self.terminal_notebook.get_nth_page(self.terminal_notebook.get_current_page()).vt
            vt.event(event)
            return True

        return False

    def _configure_vt(self, vt):
        vt.set_font(Pango.FontDescription("Monospace"))

        vt.set_colors(Gdk.RGBA.from_color(Gdk.Color.parse("#000000")[1]),
                      Gdk.RGBA.from_color(Gdk.Color.parse("#FFFFFF")[1]),
                      [])

        vt.set_audible_bell(False)
        vt.set_scrollback_lines(1000)
        vt.set_allow_bold(True)
        vt.set_scroll_on_keystroke(True)
        vt.set_scroll_on_output(False)

