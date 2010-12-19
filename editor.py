# Copyright 2008 Paul Swartz, George Hunt
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
      
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA  02110-1301  USA

import gtk, gobject
#import pango
import notebook
import gtksourceview2
import os.path
import sys
import re
import mimetypes
from exceptions import *
#import hashlib
from gettext import gettext as _
import shutil

from page import GtkSourceview2Page, BREAKPOINT_CAT, SearchOptions, S_WHERE

# Initialize logging.
from  pydebug_logging import _logger, log_environment, log_dict
"""
#constants for text_buffer marks
SHELL_CAT = 'SHELL'
TRACE_CAT = 'TRACE'
BREAKPOINT_COLOR = '#FFDDDD'
EMBEDED_SHELL_COLOR = '#DDFFDD'
EMBEDED_BREAKPOINT_COLOR = '#DDDDFF'
TRACE_INSERT = 'from ipy_sh import Tracer; debug = Tracer(); debug() #PyDebugTemp\n'
SHELL_INSERT = 'from IPython.Shell import IPShellEmbed; pdbshell = IPShellEmbed(banner="Nested shell"); pdbshell() #PyDebugTemp\n'
#following is for 0.11 ipython
#insertion = 'from IPython.frontend.terminal.embed import embed; embed() #PyDebugTemp\n'
#insertion = 'from IPython.Debugger import Tracer; debug = Tracer(); debug() #PyDebugTemp\n'
"""

class GtkSourceview2Editor:
    __gsignals__ = {
        'changed': (gobject.SIGNAL_RUN_FIRST, None, [])
    }

    def __init__(self, activity):
        self.edit_notebook = notebook.Notebook()
        self.edit_notebook._can_close_tabs = True
        self.edit_notebook.connect('do-close-page',self._remove_this_page_cb)
        self._activity = activity
        self.breakpoints_changed = False
        self.trace_outside_child_path = False
        self.embeds_exist = False        
        self.set_size_request(900, 350)
        self.edit_notebook.connect('page-removed', self._page_removed_cb)
        self.edit_notebook.connect('switch-page', self._switch_page_cb)
        self.load_breakpoints = False
        self.font_size = 8
        self.interactive_close = False
        
    def set_current_page(self,page):
        self.edit_notebook.set_current_page(page)
        
    def _remove_this_page_cb(self,widget):
        self.interactive_close = True
        self.save_page()
        n = self.edit_notebook.get_current_page()
        self.edit_notebook.remove_page(n)
               
    def _page_removed_cb(self, notebook, page, n):
        #pg_obj = self._get_page()
        if page.text_buffer.can_undo():
            page.save()
        _logger.debug('removing page %d. interactive_close:%r. Modified:%r'%
                      (n,self.interactive_close,page.text_buffer.can_undo()))
    
    def _switch_page_cb(self, notebook, page_gptr, page_num):
        pass
        return
        _logger.debug('got a switch page event')
        page = self.edit_notebook.get_nth_page(page_num)
        line = page.text_buffer.set_cursor_visible()
        
    def set_to_page_like(self,eq_to_page):
        for n in range(self.edit_notebook.get_n_pages()):
            page = self.edit_notebook.get_nth_page(n)
            if page == eq_to_page:
                self.edit_notebook.set_current_page(n)
                return True
        return False
        
    def load_object(self, fullPath, filename):
        if self.set_to_page_like(fullPath):
            return
        page = GtkSourceview2Page(fullPath, self._activity)
        label = filename
        page.text_buffer.connect('changed', self._changed_cb)
        self.edit_notebook.add_page(label, page)
        #label object is passed back in Notebook object -- remember it
        page.label = self.edit_notebook.tab_label
        page.tooltip = gtk.Tooltips()
        page.tooltip.set_tip(page.label,fullPath)
        #page.label.set_tooltip_text(fullPath)
        self.edit_notebook.set_current_page(-1)
        self._changed_cb(page.text_buffer)
        """
        #if we have visited this page before, return to the same place
        line = self._activity.get_remembered_line_number(fullPath)
        if line:
            page._scroll_to_line(line)
        """
        #_logger.debug('new label text: %s position to line:%s'%(page.label.get_text(),line,))
        
    def position_to(self, fullPath, line = 0, col = 0):
        self.load_object(fullPath, os.path.basename(fullPath))
        page = self._get_page()
        page._scroll_to_line(line)

    def save_page(self):        
        page = self._get_page()
        if self.interactive_close:
            self.interactive_close = False
            page.save(interactive_close=True)
            return
        page.save()

    def _changed_cb(self, buffer):
        if not buffer.can_undo():
            buffer.set_modified(False)
            self.clear_changed_star()
        elif not self._activity.dirty:
            self._activity.dirty = True
        #self.edit_notebook.emit('changed')
        if buffer.can_undo():
            self.set_changed_star()

    def _get_page(self):
        n = self.edit_notebook.get_current_page()
        return self.edit_notebook.get_nth_page(n)
    
    def get_full_path(self):
        page = self._get_page()
        return page.fullPath
        
    def set_changed_star(self, button = None):
        page = self._get_page()
        if page:
            current = page.label.get_text()
            if current.startswith('*'):return
            page.label.set_text('*' + current)
  
    def clear_changed_star(self, button = None):
        page = self._get_page()
        if page:
            current = os.path.basename(page.fullPath)
            page.label.set_text(current)
            
    def set_focus(self):
        page = self._get_page()
        if page:
            page.text_view.grab_focus()
        
    
    def can_undo_redo(self):
        page = self._get_page()
        if page is None:
            return (False, False)
        else:
            return page.can_undo_redo()

    def undo(self, button = None):
        page = self._get_page()
        if page:
            page.undo()

    def redo(self, button = None):
        page = self._get_page()
        if page:
            page.redo()

    def copy_to_clipboard_cb(self, button = None):
        page = self._get_page()
        if page:
            page.copy()

    def cut(self, button = None):
        page = self._get_page()
        if page:
            page.cut()

    def paste(self, button = None):
        page = self._get_page()
        if page:
            page.paste()

    def replace(self, ftext, rtext, s_opts):
        replaced = False
        if s_opts.use_regex and issubclass(type(ftext),basestring):
            ftext = re.compile(ftext)
        multifile = (s_opts.where == S_WHERE.multifile)
        if multifile and s_opts.replace_all:
            for n in range(self.edit_notebook.get_n_pages()):
                page = self.edit_notebook.get_nth_page(n)
                replaced = page.replace(ftext, rtext, 
                                s_opts) or replaced
            return (replaced, False) #not found-again
        
        page = self._get_page()
        if page:
            selection = s_opts.where == S_WHERE.selection
            replaced = page.replace(ftext, rtext, s_opts)
            if s_opts.replace_all:
                return (replaced, False)
            elif not selection:
                found = self.find_next(ftext,s_opts,page)
                return (replaced, found)
            else:
                #for replace-in-selection, leave selection unmodified
                return (replaced, replaced)
        
    def find_next(self, ftext, s_opts, page=None):
        if not page:
            page = self._get_page()
        if page:
            if s_opts.use_regex and issubclass(type(ftext),basestring):
                ftext = re.compile(ftext)
            if page.find_next(ftext,s_opts,
                                wrap=(s_opts.where != S_WHERE.multifile)):
                return True
            else:
                if (s_opts.where == S_WHERE.multifile):
                    current_page = self.edit_notebook.get_current_page()
                    n_pages = self.edit_notebook.get_n_pages() 
                    for i in range(1,n_pages):
                        page = self.edit_notebook.get_nth_page((current_page + i) % n_pages)
                        if isinstance(page,SearchablePage):
                            if page.find_next(ftext,s_opts,
                                        wrap = True):
                                self.edit_notebook.set_current_page((current_page + i) % 
                                        n_pages)
                                return True
                    return False
                else:
                    return False #first file failed, not multifile
        else:
            return False #no open pages

    def get_all_filenames(self):
        for i in range(self.edit_notebook.get_n_pages()):
            page = self.edit_notebook.get_nth_page(i)
            if isinstance(page,GtkSourceview2Page):
                yield page.fullPath

    def get_all_breakpoints(self):
        break_list = []
        for i in range(self.edit_notebook.get_n_pages()):
            page = self.edit_notebook.get_nth_page(i)
            if isinstance(page,GtkSourceview2Page):
                start, end = page.text_buffer.get_bounds()
                mark_list = page.get_marks_in_region_in_category(start, end, BREAKPOINT_CAT)
                for m in mark_list:
                    iter = page.text_buffer.get_iter_at_mark(m)
                    break_list.append('%s:%s'%(page.fullPath,iter.get_line()+1,))
        return break_list

    """
    Simplifying assumption: Breakpoints are stored only in marks in the text_buffer.
                             (and must therefore be put away in debug_dict)
                             Embeded lines are stored in file itself with comment
                                '#PyDebugTemp' and self identify their presence
    """
                                
    def save_all_breakpoints(self):
        for i in range(self.edit_notebook.get_n_pages()):
            page = self.edit_notebook.get_nth_page(i)
            if isinstance(page,GtkSourceview2Page):
                page.save_breakpoints()
    """
    def remove_all_embeds(self):
        for i in range(self.edit_notebook.get_n_pages()):
            page = self.edit_notebook.get_nth_page(i)
            if isinstance(page,GtkSourceview2Page):
                iter = page.text_buffer.get_iter_at_line_offset(0,0)
                while page.text_buffer.forward_iter_to_source_mark(iter,page.embed_cat):
                    embed_line = iter.copy()
                    embed_line.backward_line()
                    delete_candidate = self.text_buffer.get_text(embed_line,iter)
                    _logger.debug('delete candidate line:%s'%(delete_candidate,))
                    if delete_candidate.find('PyDebugTemp') > -1:
                        self.text_buffer.delete(embed_line,iter)
    """                   
    def get_list_of_embeded_files(self):
        file_list = []
        for i in range(self.edit_notebook.get_n_pages()):
            page = self.edit_notebook.get_nth_page(i)
            if isinstance(page,GtkSourceview2Page):
                if len(page.embeds) > 0:
                    file_list.append(page.fullPath)
        return file_list
                   
    def remove_embeds_from_file(self,fullPath):
        text = ''
        try:
            f = open(fullPath,"r")
            for line in f:
                if line.find('PyDebugTemp') == -1:
                    text += line
            _file = file(fullPath, 'w')
            _file.write(text)
            _file.close()
        except IOException,e:
            _logger.error('unable to rewrite%s Exception:%s'%(fullPath,e))
                         
    def clear_embeds(self):
        flist = self.get_list_of_embeded_files()
        for f in flist:
            self.remove_embeds_from_file(f)
        
    def save_all(self):
        _logger.info('save all %i Editor pages. write pdbrc: %s' % (self.edit_notebook.get_n_pages(),self.breakpoints_changed,))
        #if self._activity.is_foreign_dir():
            #_logger.info('save all aborting, still viewing in place')
            #return
        for i in range(self.edit_notebook.get_n_pages()):
            page = self.edit_notebook.get_nth_page(i)
            if isinstance(page,GtkSourceview2Page):
                _logger.debug('%s' % page.fullPath)
                page.save()
                page.save_breakpoints()
        if self.breakpoints_changed:
            self.breakpoints_changed = False
            #the pdbrc file in home directory initializes breakpoints whenever pdb session starts
            self.write_pdbrc_file()
        else:
            _logger.debug('breakpoints_changed:%s'%(self.breakpoints_changed))
            
    def write_pdbrc_file(self):
        fn = os.path.join(os.environ['HOME'],'.pdbrc')
        break_list = self.get_all_breakpoints()
        _logger.debug("writing %s breakpoints"%(len(break_list),))
        try:
            fd = file(fn,'w')
            fd.write('#Print instance variables (usage "pi classInstance")\n')
            fd.write('alias pi for k in %1.__dict__.keys(): print "%1",k,"=",%1.__dict__[k]\n')
            fd.write('#Print insance variables in self\n')
            fd.write('alias ps pi self\n')
            for break_line in break_list:
                fd.write('break %s\n'%(break_line,))
            fd.close()
        except Exception,e:
            _logger.error('unable to write to %s exception:%s'%(fn,e,))
            
    def remove_all(self):
        for i in range(self.edit_notebook.get_n_pages(),0,-1):
            self.edit_notebook.remove_page(i-1)
        """
            page = self.edit_notebook.get_nth_page(i)
            if isinstance(page,GtkSourceview2Page):
                self._close_page(None,page
        """
    def reroot(self,olddir, newdir):
        _logger.info('reroot from %s to %s' % (olddir,newdir))
        for i in range(self.edit_notebook.get_n_pages()):
            page = self.edit_notebook.get_nth_page(i)
            if isinstance(page,GtkSourceview2Page):
                if page.reroot(olddir, newdir): 
                    _logger.info('rerooting page %s failed' % 
                            page.fullPath)
                else:
                    _logger.info('rerooting page %s succeeded' % 
                            page.fullPath)
        
    def get_selected(self):
        return self._get_page().get_selected()
    
    def change_font_size(self,size):
        page = self._get_page()
        page.set_font_size(size)

    def toggle_breakpoint(self):
        page = self._get_page()
        page.break_at()

