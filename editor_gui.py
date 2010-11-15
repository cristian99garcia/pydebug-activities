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

#major packages
import os,  shutil, sys
import gtk
from gettext import gettext as _

#sugar stuff
from sugar.graphics.toolbutton import ToolButton
import sugar.graphics.toolbutton

#application stuff
from terminal import Terminal
from editor import GtkSourceview2Editor
import pydebug
from page import SearchOptions, S_WHERE

#import logging
from  pydebug_logging import _logger, log_environment

class EditorGui(GtkSourceview2Editor):
    def __init__(self,activity):
        self._activity = activity

        GtkSourceview2Editor.__init__(self,activity)
        
        #set the default contents for edit,override fixed font size
        self.font_size = activity.debug_dict.get('font_size',8)                         
        self.find_window = None
        
        self.editbar = gtk.Toolbar()
        self.last_folder = None        
        editopen = ToolButton()
        editopen.set_stock_id('gtk-new')
        editopen.set_icon_widget(None)
        editopen.set_tooltip(_('New File'))
        editopen.connect('clicked', self._new_file_cb)
        editopen.add_accelerator('clicked',activity.accelerator,ord('N'),gtk.gdk.CONTROL_MASK,gtk.ACCEL_VISIBLE)
        #editopen.props.accelerator = '<Ctrl>O'
        editopen.show()
        self.editbar.insert(editopen, -1)
        
        editfile = ToolButton()
        editfile.set_stock_id('gtk-open')
        editfile.set_icon_widget(None)
        editfile.set_tooltip(_('Open File'))
        editfile.connect('clicked', self._read_file_cb)
        editfile.add_accelerator('clicked',activity.accelerator,ord('O'),gtk.gdk.CONTROL_MASK,gtk.ACCEL_VISIBLE)
        #editfile.props.accelerator = '<Ctrl>O'
        editfile.show()
        self.editbar.insert(editfile, -1)
        
        editsave = ToolButton()
        editsave.set_stock_id('gtk-save')
        editsave.set_icon_widget(None)
        editsave.set_tooltip(_('Save File'))
        editsave.add_accelerator('clicked',activity.accelerator,ord('S'),gtk.gdk.CONTROL_MASK,gtk.ACCEL_VISIBLE)
        #editsave.props.accelerator = '<Ctrl>S'
        editsave.connect('clicked', self.save_cb)
        editsave.show()
        self.editbar.insert(editsave, -1)
        
        editsaveas = ToolButton()
        editsaveas.set_stock_id('gtk-save-as')
        editsaveas.set_icon_widget(None)
        editsaveas.set_tooltip(_('Save As'))
        #editsaveas.props.accelerator = '<Ctrl>S'
        editsaveas.connect('clicked', self.save_file_cb)
        editsaveas.show()
        self.editbar.insert(editsaveas, -1)
        
        
        """
        editjournal = ToolButton(tooltip=_('Open Journal'))
        client = gconf.client_get_default()
        color = XoColor(client.get_string('/desktop/sugar/user/color'))
        journal_icon = Icon(icon_name='document-save', xo_color=color)
        editjournal.set_icon_widget(journal_icon)
        editjournal.connect('clicked', self._show_journal_object_picker_cb)
        #editjournal.props.accelerator = '<Ctrl>J'
        editjournal.show()
        self.editbar.insert(editjournal, -1)
        """
        
        separator = gtk.SeparatorToolItem()
        separator.set_draw(True)
        separator.show()
        self.editbar.insert(separator, -1)
        
        editundo = ToolButton('undo')
        editundo.set_tooltip(_('Undo'))
        editundo.connect('clicked', self.undo)
        editundo.add_accelerator('clicked',activity.accelerator,ord('Z'),gtk.gdk.CONTROL_MASK,gtk.ACCEL_VISIBLE)
        #editundo.props.accelerator = '<Ctrl>Z'
        editundo.show()
        self.editbar.insert(editundo, -1)

        editredo = ToolButton('redo')
        editredo.set_tooltip(_('Redo'))
        editredo.connect('clicked', self.redo)
        editredo.add_accelerator('clicked',activity.accelerator,ord('Y'),gtk.gdk.CONTROL_MASK,gtk.ACCEL_VISIBLE)
        #editredo.props.accelerator = '<Ctrl>Y'
        editredo.show()
        self.editbar.insert(editredo, -1)

        separator = gtk.SeparatorToolItem()
        separator.set_draw(True)
        separator.show()
        self.editbar.insert(separator, -1)
        
        editcut = ToolButton()
        editcut.set_stock_id('gtk-cut')
        editcut.set_icon_widget(None)
        editcut.set_tooltip(_('Cut'))
        self.edit_cut_handler_id = editcut.connect('clicked', self.cut)
        editcut.add_accelerator('clicked',activity.accelerator,ord('X'),gtk.gdk.CONTROL_MASK,gtk.ACCEL_VISIBLE)
        #editcut.props.accelerator = '<Ctrl>X'
        self.editbar.insert(editcut, -1)
        editcut.show()

        editcopy = ToolButton('edit-copy')
        editcopy.set_tooltip(_('Copy'))
        self.edit_copy_handler_id = editcopy.connect('clicked', self.copy_to_clipboard_cb)
        editcopy.add_accelerator('clicked',activity.accelerator,ord('C'),gtk.gdk.CONTROL_MASK,gtk.ACCEL_VISIBLE)
        #editcopy.props.accelerator = '<Ctrl>C'
        self.editbar.insert(editcopy, -1)
        editcopy.show()

        editpaste = ToolButton('edit-paste')
        editpaste.set_tooltip(_('Paste'))
        self.edit_paste_handler_id = editpaste.connect('clicked', self.paste)
        editpaste.add_accelerator('clicked',activity.accelerator,ord('V'),gtk.gdk.CONTROL_MASK,gtk.ACCEL_VISIBLE)
        #editpaste.props.accelerator = '<Ctrl>V'
        editpaste.show()
        self.editbar.insert(editpaste, -1)

        separator = gtk.SeparatorToolItem()
        separator.set_draw(True)
        separator.show()
        self.editbar.insert(separator, -1)
        
        editfind = ToolButton('viewmag1')
        editfind.set_tooltip(_('Find and Replace'))
        editfind.connect('clicked', self.show_find)
        editfind.add_accelerator('clicked',activity.accelerator,ord('F'),gtk.gdk.CONTROL_MASK,gtk.ACCEL_VISIBLE)
        #editfind.props.accelerator = '<Ctrl>F'
        editfind.show()
        self.editbar.insert(editfind, -1)

        separator = gtk.SeparatorToolItem()
        separator.set_draw(True)
        separator.show()
        self.editbar.insert(separator, -1)
        
        self.zoomout = ToolButton('zoom-out')
        self.zoomout.set_tooltip(_('Zoom out'))
        self.zoomout.connect('clicked', self.__zoomout_clicked_cb)
        self.editbar.insert(self.zoomout, -1)
        self.zoomout.show()

        self.zoomin = ToolButton('zoom-in')
        self.zoomin.set_tooltip(_('Zoom in'))
        self.zoomin.connect('clicked', self.__zoomin_clicked_cb)
        self.editbar.insert(self.zoomin, -1)
        self.zoomin.show()

        self.editbar.show_all()
        
        
    def get_editbar(self):
        """return reference for placing on the Sugar main menu notebook"""
        return self.editbar
        
    def _new_file_cb(self, widget):
        """create a new empty file, add a sequence number if default exists"""
        full_path = self._activity.util.non_conflicting(self._activity.child_path,'Unsaved_Document.py')
        self.load_object(full_path,os.path.basename(full_path))
        
    def _read_file_cb(self,widget):
        """open up a file selector"""
        _logger.debug('Reading a file into editor')
        dialog = gtk.FileChooserDialog("Open..",
                                       None,
                                       gtk.FILE_CHOOSER_ACTION_OPEN,
                                       (gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL,
                                        gtk.STOCK_OPEN, gtk.RESPONSE_OK))
        dialog.set_default_response(gtk.RESPONSE_OK)
        if self.last_folder == None:
            self.last_folder = self._activity.child_path
        if not self.last_folder:  
            self.last_folder = self.activity_playpen                 
        if self.last_folder:       
            dialog.set_current_folder(self.last_folder)      
        
        filter = gtk.FileFilter()
        filter.set_name("All files")
        filter.add_pattern("*")
        dialog.add_filter(filter)
        
        filter = gtk.FileFilter()
        filter.set_name("Python")
        filter.add_pattern("*.py")
        dialog.add_filter(filter)
        
        filter = gtk.FileFilter()
        filter.set_name("Activity")
        filter.add_pattern("*.xo")
        dialog.add_filter(filter)
        
        response = dialog.run()
        if response == gtk.RESPONSE_OK:
            _logger.debug(dialog.get_filename(), 'selected')
            fname = dialog.get_filename()
            self.last_folder = os.path.dirname(fname)
            self.load_object(fname,os.path.basename(fname))
            line = self.get_remembered_line_number(fname)
            if line:
                self.position_to(fname,line)
        elif response == gtk.RESPONSE_CANCEL:
            _logger.debug( 'File chooseer closed, no files selected')
        dialog.destroy()

    def save_file_cb(self, button):
        """
        impliments the SaveAs function
        """
        chooser = gtk.FileChooserDialog(title=None,action=gtk.FILE_CHOOSER_ACTION_SAVE,
                                        buttons=(gtk.STOCK_CANCEL,gtk.RESPONSE_CANCEL,gtk.STOCK_SAVE,
                                                 gtk.RESPONSE_OK))
        file_path = self.get_full_path()
        _logger.debug('Saving file %s'%(file_path))
        chooser.set_filename(file_path)
        response = chooser.run()
        new_fn = chooser.get_filename()
        chooser.destroy()
        if response == gtk.RESPONSE_CANCEL:
                return
        if response == gtk.RESPONSE_OK:
            self.save_cb(None,new_fn)
            
    def save_cb(self,button,new_fn=None):
        if new_fn:
            full_path = new_fn
        else:
            full_path = self.get_full_path()
        if os.path.basename(full_path).startswith('Unsaved_Document'): #force a choice to keep or change the name
            #fd = open(full_path,'w')
            #fd.close()
            self.save_file_cb(None)            
            return
        page = self._get_page()
        if  new_fn:
            page.fullPath = new_fn
            page.save(skip_md5 = True,new_file=new_fn)
        else:
            page.save()
        self.clear_changed_star()
        page.save_hash()
 
    def __zoomin_clicked_cb(self,button):
            self.font_size += 1
            self.change_font_size(self.font_size)
            self._activity.debug_dict['font_size'] = self.font_size
            
    def __zoomout_clicked_cb(self,botton):
            self.font_size -= 1
            self.change_font_size(self.font_size)
            self._activity.debug_dict['font_size'] = self.font_size
       
    ###   following routines are copied from develop_app for use with editor 
    def _replace_cb(self, button=None):
        ftext = self._search_entry.props.text
        rtext = self._replace_entry.props.text
        _logger.debug('replace %s with %s usiing options %r'%(ftext,rtext,self.s_opts))
        replaced, found = self.replace(ftext, rtext, 
                    self.s_opts)
        if found:
            self._replace_button.set_sensitive(True)

    def _search_entry_activated_cb(self, entry):
        text = self._search_entry.props.text
        if text:
            self._findnext_cb(None)       

    def _search_entry_changed_cb(self, entry):
        self.safe_to_replace = False
        text = self._search_entry.props.text
        if not text:
            self._findprev.set_sensitive(False)
            self._findnext.set_sensitive(False)
        else:
            self._findprev.set_sensitive(True)
            self._findnext.set_sensitive(True)
            if not self.s_opts.use_regex: #do not do partial searches for regex
                _logger.debug('finding:%s'%(text,))
                if self.find_next(text, 
                            SearchOptions(self.s_opts, 
                            stay=True, 
                            where = self.s_opts.where if self.s_opts.where != S_WHERE.multifile else S_WHERE.file)):
                    #no multifile, or focus gets grabbed
                    self._replace_button.set_sensitive(True)
                    
    def _replace_entry_changed_cb(self, entry):
        if self._replace_entry.props.text:
            self.safe_to_replace = True
            
    def _findprev_cb(self, button=None):
        ftext = self._search_entry.props.text
        if ftext:
            if self.find_next(ftext, SearchOptions(self.s_opts, forward=False)):
                self._replace_button.set_sensitive(True)
                        
    def _findnext_cb(self, button=None):
        ftext = self._search_entry.props.text
        _logger.debug('find next %s'%ftext)
        if ftext:
            if self.find_next(ftext, self.s_opts):
                self._replace_button.set_sensitive(True)
            self.set_focus()
    
    
    def show_find(self,button):
        """find_window is defined in project.glade"""
        if not self.find_window:
            self._find_width = 400
            self._find_height = 300
            self.find_window = self.wTree.get_widget("find")
            self.find_window.connect('destroy',self.close_find_window)
            self.find_window.connect('delete_event',self.close_find_window)
            self.find_connect()
            self.find_window.set_title(_('FIND OR REPLACE'))
            self.find_window.set_size_request(self._find_width,self._find_height)
            self.find_window.set_decorated(False)
            self.find_window.set_resizable(False)
            self.find_window.set_modal(False)
            self.find_window.connect('size_request',self._size_request_cb)
            self.find_window.set_transient_for(self._activity.window.get_toplevel())
        #if there is any selected text, put it in the find entry field, and grab focus
        selected = self.get_selected()
        _logger.debug('selected text is %s'%selected)
        self._search_entry.props.text = selected
        self._search_entry.grab_focus()
        self.find_window.show()
        
    def _size_request_cb(self, widget, req):
        x = gtk.gdk.screen_width() -self._find_width - 50
        self.find_window._width = req.width
        self.find_window._height = req.height
        self.find_window.move(x,150)       
        
    def find_connect(self):
        mdict = {
            'find_close_clicked_cb':self.close_find_window,
            #'find_entry_changed_cb':self.find_entry_changed_cb,
            #'replace_entry_changed_cb':self.replace_entry_changed_cb,
            'find_previous_clicked_cb':self._findprev_cb,
            'find_next_clicked_cb':self._findnext_cb,
            'find_entry_changed_cb':self._search_entry_changed_cb,
            'replace_entry_changed_cb':self._replace_entry_changed_cb,
            'replace_clicked_cb':self._replace_cb,
            #'replace_all_clicked_cb':self._findprev_cb,
             }
        self.wTree.signal_autoconnect(mdict)
        self._findnext = self.wTree.get_widget("find_next")
        self._findprev = self.wTree.get_widget("find_previous")
        self._search_entry = self.wTree.get_widget("find_entry")
        self._replace_entry = self.wTree.get_widget("replace_entry")
        self._replace_button = self.wTree.get_widget("replace")
        #self.replace_all = self.wTree.get_widget("replace_all")
        self.find_where = self.wTree.get_widget("find_where")

        
    def close_find_window(self,button):
        self.find_window.hide()
        return True
    
   