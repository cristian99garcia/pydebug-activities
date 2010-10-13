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

import os, os.path, ConfigParser, sys

from gettext import gettext as _

# Initialize logging.
import logging
_logger = logging.getLogger('PyDebug')

import gtk
import vte
import pango

from sugar.graphics.toolbutton import ToolButton
import sugar.graphics.toolbutton
import sugar.activity.activity
import sugar.env
import sugar.activity.bundlebuilder

from shutil import copy, copytree

MASKED_ENVIRONMENT = [
    'DBUS_SESSION_BUS_ADDRESS',
    'PPID'
]

class Terminal():
    
    def __init__(self,handle):
        pass
 
    def _get_terminal_canvas(self):
        self.terminal_notebook = gtk.Notebook()
        self.terminal_notebook.set_property("tab-pos", gtk.POS_BOTTOM)
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
        self.terminal_notebook.remove_page(index)
        if self.terminal_notebook.get_n_pages() == 0:
            self.close()
            
    def _tab_child_exited_cb(self, vt):
        for i in range(self.terminal_notebook.get_n_pages()):
            if self.terminal_notebook.get_nth_page(i).vt == vt:
                self._close_tab(i)
                return
    
    def _tab_title_changed_cb(self, vt):
        for i in range(self.terminal_notebook.get_n_pages()):
            if self.terminal_notebook.get_nth_page(i).vt == vt:
                label = self.terminal_notebook.get_nth_page(i).label
                label.set_text(vt.get_window_title())
                return
    
    def _drag_data_received_cb(self, widget, context, x, y, selection, target, time):
        widget.feed_child(selection.data)
        context.finish(True, False, time)
        return True
    
    def _create_tab(self, tab_state):
        vt = vte.Terminal()
        vt.connect("child-exited", self._tab_child_exited_cb)
        vt.connect("window-title-changed", self._tab_title_changed_cb)
    
        vt.drag_dest_set(gtk.DEST_DEFAULT_MOTION|gtk.DEST_DEFAULT_DROP,
               [('text/plain', 0, 0), ('STRING', 0, 1)],
               gtk.gdk.ACTION_DEFAULT|
               gtk.gdk.ACTION_COPY)
        vt.connect('drag_data_received', self._drag_data_received_cb)
        
        self._configure_vt(vt)
    
        vt.show()
    
        label = gtk.Label()
    
        scrollbar = gtk.VScrollbar(vt.get_adjustment())
        scrollbar.show()
    
        box = gtk.HBox()
        box.pack_start(vt)
        box.pack_start(scrollbar)
    
        box.vt = vt
        box.label = label
        
        index = self.terminal_notebook.append_page(box, label)
        if index == 0:
            vt.set_colors(gtk.gdk.color_parse('#000000'), gtk.gdk.color_parse('#FFFFCC'), [])            
        self.terminal_notebook.show_all()
    
        # Uncomment this to only show the tab bar when there is at least one tab.
        # I think it's useful to always see it, since it displays the 'window title'.
        #self.terminal_notebook.props.show_tabs = self.terminal_notebook.get_n_pages() > 1
    
        # Launch the default shell in the HOME directory.
        os.chdir(os.environ["HOME"])
    
        if tab_state:
            # Restore the environment.
            # This is currently not enabled.
            env = tab_state.get('env',[])
    
            filtered_env = []
            for e in env:
                var, sep, value = e.partition('=')
                if var not in MASKED_ENVIRONMENT:
                    filtered_env.append(var + sep + value)
    
            # TODO: Make the shell restore these environment variables, then clear out TERMINAL_ENV.
            #os.environ['TERMINAL_ENV'] = '\n'.join(filtered_env)
            
            # Restore the working directory.
            if tab_state.has_key('cwd'):
                os.chdir(tab_state['cwd'])
    
            # Restore the scrollback buffer.
            if tab_state.has_key('scrollback'):
                for l in tab_state['scrollback']:
                    vt.feed(l + '\r\n')
    
        box.pid = vt.fork_command()
    
        self.terminal_notebook.props.page = index
        vt.grab_focus()
    
        return index
    
    def feed_virtual_terminal(self,terminal,command):
        if terminal > len(self.terminal_notebook)-1 or terminal < 0:
            _logger.debug('in feed_virtual_terminal: terminal out of bounds %s'%terminal)
            return
        self.terminal_notebook.set_current_page(terminal)
        vt = self.terminal_notebook.get_nth_page(terminal).vt  
        vt.feed_child(command)
    
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
        if gtk.gdk.keyval_name(event.keyval) == 'Escape':
            vt = self.terminal_notebook.get_nth_page(self.terminal_notebook.get_current_page()).vt
            vt.event(event)
            return True
    
        return False
    
        
        
    def _get_conf(self, conf, var, default):
        if conf.has_option('terminal', var):
            if isinstance(default, bool):
                return conf.getboolean('terminal', var)
            elif isinstance(default, int):
                return conf.getint('terminal', var)
            else:
                return conf.get('terminal', var)
        else:
            conf.set('terminal', var, default)
    
            return default
    
    def _configure_vt(self, vt):
        conf = ConfigParser.ConfigParser()
        conf_file = os.path.join(os.environ['HOME'], 'terminalrc')
        
        if os.path.isfile(conf_file):
            f = open(conf_file, 'r')
            conf.readfp(f)
            f.close()
        else:
            conf.add_section('terminal')
        
        font = self._get_conf(conf, 'font', 'Monospace')
        vt.set_font(pango.FontDescription(font))
    
        fg_color = self._get_conf(conf, 'fg_color', '#000000')
        bg_color = self._get_conf(conf, 'bg_color', '#FFFFFF')
        vt.set_colors(gtk.gdk.color_parse(fg_color), gtk.gdk.color_parse(bg_color), [])
    
        blink = self._get_conf(conf, 'cursor_blink', False)
        vt.set_cursor_blinks(blink)
    
        bell = self._get_conf(conf, 'bell', False)
        vt.set_audible_bell(bell)
        
        scrollback_lines = self._get_conf(conf, 'scrollback_lines', 1000)
        vt.set_scrollback_lines(scrollback_lines)
    
        vt.set_allow_bold(True)
        
        scroll_key = self._get_conf(conf, 'scroll_on_keystroke', True)
        vt.set_scroll_on_keystroke(scroll_key)
    
        scroll_output = self._get_conf(conf, 'scroll_on_output', False)
        vt.set_scroll_on_output(scroll_output)
        
        emulation = self._get_conf(conf, 'emulation', 'xterm')
        vt.set_emulation(emulation)
    
        visible_bell = self._get_conf(conf, 'visible_bell', False)
        vt.set_visible_bell(visible_bell)
    
        conf.write(open(conf_file, 'w'))
        
    
    
