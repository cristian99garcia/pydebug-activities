# Copyright 2008 Paul Swartz
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

import os
import re
import sys
import mimetypes
from exceptions import *
from gettext import gettext as _

from gi.repository import Gtk
from gi.repository import Pango
from gi.repository import GObject
from gi.repository import GtkSource

import notebook
import hashlib
import shutil

# Initialize logging.
import logging
from sugar3 import logger
#Get the standard logging directory. 
std_log_dir = logger.get_logs_dir()
_logger = logging.getLogger('PyDebug')
_logger.setLevel(logging.DEBUG)


class S_WHERE:
    selection, file, multifile = range(3) #an enum


class GtkSourceviewEditor(notebook.Notebook):

    __gsignals__ = {
        'changed': (GObject.SIGNAL_RUN_FIRST, None, [])
    }

    def __init__(self, activity):
        notebook.Notebook.__init__(self, can_close_tabs=True)

        self._can_close_tabs = True #redundant, but above call broken for some reason
        self.activity = activity
        self.breakpoints_changed = False
        self.embeds_exist = False        
        self.set_size_request(900, 350)
        self.connect('page-removed', self._page_removed_cb)
        self.connect('switch-page', self._switch_page_cb)
        self.load_breakpoints = False

    def _page_removed_cb(self, notebook, page, n):
        pg_obj = self._get_page()
        _logger.debug('removing page %d. interactive_close:%r. Modified:%r'%(n,self.interactive_close,page.text_buffer.can_undo()))
    
    def _switch_page_cb(self, notebook, page_gptr, page_num):
        return  ## What?

        _logger.debug('got a switch page event')
        page = self.get_nth_page(page_num)
        line = page.text_buffer.set_cursor_visible()
        
    def set_to_page_like(self,eq_to_page):
        for n in range(self.get_n_pages()):
            page = self.get_nth_page(n)
            if page == eq_to_page:
                self.set_current_page(n)
                return True

        return False
        
    def load_object(self, fullPath, filename):
        if self.set_to_page_like(fullPath):
            return

        page = GtkSourceviewPage(fullPath, self.activity)
        label = filename
        page.text_buffer.connect('changed', self._changed_cb)
        self.add_page(label, page)
        #label object is passed back in Notebook object -- remember it
        page.label = self.tab_label
        page.label.set_tooltip_text(fullPath)
        self.set_current_page(-1)
        self._changed_cb(page.text_buffer)

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

        elif not self.activity.dirty:
            self.activity.set_dirty(True)

        self.emit('changed')

        if buffer.can_undo():
            self.set_changed_star()

    def _get_page(self):
        n = self.get_current_page()
        return self.get_nth_page(n)
    
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

    def copy(self, button = None):
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
            for n in range(self.get_n_pages()):
                page = self.get_nth_page(n)
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

            if page.find_next(ftext,s_opts, wrap=(s_opts.where != S_WHERE.multifile)):
                return True

            else:
                if (s_opts.where == S_WHERE.multifile):
                    current_page = self.get_current_page()
                    n_pages = self.get_n_pages() 
                    for i in range(1,n_pages):
                        page = self.get_nth_page((current_page + i) % n_pages)
                        if isinstance(page,SearchablePage):
                            if page.find_next(ftext,s_opts, wrap = True):
                                self.set_current_page((current_page + i) % n_pages)
                                return True

                    return False

                else:
                    return False #first file failed, not multifile

        else:
            return False #no open pages

    def get_all_filenames(self):
        for i in range(self.get_n_pages()):
            page = self.get_nth_page(i)
            if isinstance(page,GtkSourceviewPage):
                yield page.fullPath

    def get_all_breakpoints(self):
        break_list = []
        for i in range(self.get_n_pages()):
            page = self.get_nth_page(i)
            if isinstance(page, GtkSourceviewPage):
                iter = page.text_buffer.get_iter_at_line_offset(0, 0)
                while page.text_buffer.forward_iter_to_source_mark(iter,page.brk_cat):
                    break_list.append('%s:%s'%(page.fullPath, iter.get_line() + 1))

        return break_list

    def remove_all_embeds(self):
        for i in range(self.get_n_pages()):
            page = self.get_nth_page(i)

            if isinstance(page, GtkSourceviewPage):
                iter = page.text_buffer.get_iter_at_line_offset(0,0)

                while page.text_buffer.forward_iter_to_source_mark(iter, page.embed_cat):
                    embed_line = iter.copy()
                    embed_line.backward_line()
                    delete_candidate = self.text_buffer.get_text(embed_line, iter)
                    _logger.debug('delete candidate line:%s'%(delete_candidate,))

                    if delete_candidate.find('PyDebugTemp') > -1:
                        self.text_buffer.delete(embed_line,iter)
                        
    def get_list_of_embeded_files(self):
        file_list = []
        for i in range(self.get_n_pages()):
            page = self.get_nth_page(i)
            if isinstance(page,GtkSourceviewPage):
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
        _logger.info('save all %i Editor pages' % self.get_n_pages())
        for i in range(self.get_n_pages()):
            page = self.get_nth_page(i)
            if isinstance(page,GtkSourceviewPage):
                _logger.debug('%s' % page.fullPath)
                page.save()
                page.save_breakpoints()

        if self.breakpoints_changed:
            self.breakpoints_changed = False
            #the pdbrc file in home directory initializes breakpoints whenever pdb session starts
            self.write_pdbrc_file()
            
    def write_pdbrc_file(self):
        fn = os.path.join(os.environ['HOME'],'.pdbrc')
        break_list = self.get_all_breakpoints()
        _logger.debug("writing %d breakpoints" % len(break_list))

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
        for i in range(self.get_n_pages(),0,-1):
            self.remove_page(i-1)

    def reroot(self,olddir, newdir):
        _logger.info('reroot from %s to %s' % (olddir,newdir))
        for i in range(self.get_n_pages()):
            page = self.get_nth_page(i)
            if isinstance(page,GtkSourceviewPage):
                if page.reroot(olddir, newdir):
                    _logger.info('rerooting page %s failed' % page.fullPath)

                else:
                    _logger.info('rerooting page %s succeeded' % page.fullPath)

    def get_selected(self):
        return self._get_page().get_selected()
    
    def change_font_size(self,size):
        page = self._get_page()
        page.set_font_size(size)

    def toggle_breakpoint(self):
        page = self._get_page()
        page.break_at()


class SearchablePage(Gtk.ScrolledWindow):

    def get_selected(self):
        try:
            start, end = self.text_buffer.get_selection_bounds()
            return self.text_buffer.get_slice(start,end)

        except ValueError:
            return 0

    def get_text(self):
        """
        Return the text that's currently being edited.
        """
        start, end = self.text_buffer.get_bounds()
        return self.text_buffer.get_text(start, end)
        
    def get_offset(self):
        """
        Return the current character position in the currnet file.
        """
        insert = self.text_buffer.get_insert()
        _iter = self.text_buffer.get_iter_at_mark(insert)
        return _iter.get_offset()
    
    def get_iter(self):
        """
        Return the current character position in the currnet file.
        """
        insert = self.text_buffer.get_insert()
        _iter = self.text_buffer.get_iter_at_mark(insert)
        return _iter

    def copy(self):
        """
        Copy the currently selected text to the clipboard.
        """
        self.text_buffer.copy_clipboard(Gtk.Clipboard())
    
    def paste(self):
        """
        Cut the currently selected text the clipboard into the current file.
        """
        self.text_buffer.paste_clipboard(Gtk.Clipboard(), None, True)
        
    def cut(self):
        """
        Paste from the clipboard.
        """
        self.text_buffer.cut_clipboard(Gtk.Clipboard(), True)
        
    def _getMatches(self,buffertext,fpat,s_opts,offset):
        if s_opts.use_regex:
            while True:
                match = fpat.search(buffertext,re.I if s_opts.ignore_caps else 0)
                if match:
                    start,end = match.span()
                    yield (start+offset,end+offset,match)

                else:
                    return

                buffertext, offset = buffertext[end:],offset+end

        else:
            while True:
                if s_opts.ignore_caps:
                    #possible optimization: turn fpat into a regex by escaping, 
                    #then use re.i
                    buffertext = buffertext.lower()
                    fpat = fpat.lower()

                match = buffertext.find(fpat)

                if match >= 0:
                    end = match+len(fpat)
                    yield (offset + match, offset + end, None)

                else:
                    return

                buffertext, offset = buffertext[end:], offset + end

    def _match(self, pattern, text, s_opts):
        if s_opts.use_regex:
            return pattern.match(text,re.I if s_opts.ignore_caps else 0)

        else:
            if s_opts.ignore_caps:
                pattern = pattern.lower()
                text = text.lower()

            return pattern == text
    
    def _find_in(self, text, fpat, offset, s_opts, offset_add = 0):
        if s_opts.forward:
            matches = self._getMatches(text[offset:], fpat, s_opts, offset+offset_add)
            try:
                return matches.next()

            except StopIteration:
                return ()

        else:
            if offset != 0:
                text = text[:offset]

            matches = list(self._getMatches(text, fpat, s_opts, offset_add))
            if matches:
                return matches[-1]

            else:
                return ()
            
    def find_next(self, ftext, s_opts, wrap=True):
        """
        Scroll to the next place where the string text appears.
        If stay is True and text is found at the current position, stay where we are.
        """
        if s_opts.where == S_WHERE.selection:
            try:
                selstart, selend = self.text_buffer.get_selection_bounds()

            except (ValueError,TypeError):
                return False

            offsetadd = selstart.get_offset()
            buffertext = self.text_buffer.get_slice(selstart,selend)
            print buffertext

            try:
                start, end, match = self._find_in(buffertext, ftext, 0, s_opts, offsetadd)

            except (ValueError,TypeError):
                return False

        else:
            offset = self.get_offset() + (not s_opts.stay) #add 1 if not stay.
            text = self.get_text()
            try:
                start,end,match = self._find_in(text, ftext, offset, s_opts, 0)

            except (ValueError,TypeError):
                #find failed.
                if wrap:
                    try:
                        start,end,match = self._find_in(text, ftext, 0, s_opts, 0)

                    except (ValueError,TypeError):
                        return False

                else:
                    return False

        self._scroll_to_offset(start,end)
        self.text_view.grab_focus()
        return True

    def _scroll_to_offset(self, offset, bound):
        _iter = self.text_buffer.get_iter_at_offset(offset)
        _iter2 = self.text_buffer.get_iter_at_offset(bound)
        self.text_buffer.select_range(_iter,_iter2)
        mymark = self.text_buffer.create_mark('mymark',_iter)
        self.text_view.scroll_to_mark(mymark,0.0,True)
        
    def _scroll_to_line(self,line):
        _iter = self.text_buffer.get_iter_at_line(line)
        mark = self.text_buffer.get_mark('mymark')
        if not mark:
            mark = self.text_buffer.create_mark('mymark',_iter)

        else:
            self.text_buffer.move_mark(mark,_iter)

        self.text_view.scroll_to_mark(mark,0.0,True)
        mark_iter = self.text_buffer.get_iter_at_mark(mark)
        _logger.debug('scroll to line:%s mark is at line %s'%(line,mark_iter.get_line(),))

    def break_at(self):
        offset = self.get_offset()
        _logger.debug('breakpoint at character %s'%(offset,))

    def __eq__(self,other):
        if isinstance(other, GtkSourceviewPage):
            return self.fullPath == other.fullPath

        elif isinstance(other, basestring):
            return other == self.fullPath

        else:
            return False


class GtkSourceviewPage(SearchablePage):

    def __init__(self, fullPath, activity):
        """
        Do any initialization here.
        """
        Gtk.ScrolledWindow.__init__(self)

        self.breakpoints = {}
        self.embeds = {}

        self.fullPath = fullPath
        self.activity = activity
        #self.interactive_close = False

        self.text_buffer = GtkSource.Buffer()
        self.text_buffer.create_tag('breakpoint',background="#ffeeee")
        self.text_buffer.create_tag('embed_shell',background="#eeffee")
        self.text_view = GtkSource.View.new_with_buffer(self.text_buffer)
        self.text_view.connect('button_press_event',self._pd_button_press_cb)
        self.brk_cat = 'BREAKPOINT'
        self.embed_cat = 'EMBEDED_SHELL'
       
        self.text_view.set_size_request(900, 350)
        self.text_view.set_editable(True)
        self.text_view.set_cursor_visible(True)
        self.text_view.set_highlight_current_line(True)
        self.text_view.set_show_line_numbers(True)
        self.text_view.set_insert_spaces_instead_of_tabs(True)

        if hasattr(self.text_view, 'set_tabs_width'):
            self.text_view.set_tabs_width(4)

        else:
            self.text_view.set_tab_width(4)

        self.text_view.set_auto_indent(True)

        self.text_view.set_wrap_mode(Gtk.Warp.CHAR)
        self.set_font_size(self.activity.font_size)

        #build 650 doesn't seem to have the same means of specifying the search directory

        mgr = GtkSource.StyleSchemeManager()
        mgr.prepend_search_path(self.activity.pydebug_path)
        style_scheme = mgr.get_scheme('vibrant')

        if style_scheme:
            self.text_buffer.set_style_scheme(style_scheme)

        self.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        self.add(self.text_view)
        self.text_view.show()
        self.load_text()
        self.show()

    def set_font_size(self,font_size=None):
        if font_size == None:
            font_size = self.activity.font_size

        self.text_view.modify_font(Pango.FontDescription("Monospace %d" % font_size))
        _logger.debug('setting font size to %d'%font_size)

    def load_text(self, offset=None):
        """
        Load the text, and optionally scroll to the given offset in the file.
        """
        self.text_buffer.begin_not_undoable_action()

        if not os.path.basename(self.fullPath).startswith('Unsaved_Document'):
            _file = file(self.fullPath)
            self.text_buffer.set_text(_file.read())
            _file.close()
            self.save_hash()

        if offset is not None:
            self._scroll_to_offset(offset)
        
        if hasattr(self.text_buffer, 'set_highlight'):
            self.text_buffer.set_highlight(False)

        else:
            self.text_buffer.set_highlight_syntax(False)

        mime_type = mimetypes.guess_type(self.fullPath)[0]

        if mime_type and not os.path.basename(self.fullPath).startswith('Unsaved_Document'):
            lang_manager = GtkSource.LanguageManager.get_default()
            if hasattr(lang_manager, 'list_languages'):
               langs = lang_manager.list_languages()

            else:
                lang_ids = lang_manager.get_language_ids()
                langs = [lang_manager.get_language(i) for i in lang_ids]

            for lang in langs:
                for m in lang.get_mime_types():
                    if m == mime_type:
                        self.text_buffer.set_language(lang)
                        self.text_buffer.set_highlight_syntax(True)

        self.restore_breakpoints()
        self.text_buffer.end_not_undoable_action()
        self.text_buffer.set_modified(False)
        self.text_view.grab_focus()

    def restore_breakpoints(self):
        file_nickname = self.activity.glean_file_id_from_fullpath(self.fullPath)
        self.break_list = self.activity.debug_dict.get(file_nickname + '-breakpoints')
        if not self.break_list:
            return

        del self.activity.debug_dict[file_nickname + '-breakpoints']

        if not self.activity.editor.load_breakpoints:
            alert = self.activity.confirmation_alert(_('Chose OK to restore, Cancel to delete them.'), _('This Activity has Breakpoints!'), self._restore_brkpt_cb)

        else:
            self._restore_brkpt_cb(None, None)

    def _restore_brkpt_cb(self,alert,response):
        #callback not taken if not response ok
        self.activity.editor.load_breakpoints = True
        self.break_list = self.break_list.split(',')
        for line in self.break_list:
            line_start = self.text_buffer.get_iter_at_line(int(line) - 1)
            line_end = line_start.copy()
            line_end.forward_line()
            self.text_buffer.apply_tag_by_name('breakpoint', line_start, line_end)
            mark = self.text_buffer.create_source_mark(None, self.brk_cat, line_start)
            #breakpoints simulates a sparse array of marks stored in a dictionary by keyed by line number
            _logger.debug('set breakpoint on line:%s'%line)
                
    def save_hash(self):   
        self.md5sum = self.activity.md5sum(self.fullPath)

    def remove(self):
        self.save()
   
    def save(self,skip_md5 = False, interactive_close=False, new_file=None):
        if interactive_close:
            self.activity.remember_line_no(self.fullPath, self.get_iter().get_line())

        if os.path.basename(self.fullPath).startswith('Unsaved_Document') and self.text_buffer.can_undo():
            self.activity.save_cb(None)
            return

        if not new_file and (not self.text_buffer.can_undo() or self.activity.abandon_changes):
            if not self.text_buffer.can_undo():
                _logger.debug('no changes:%s for %s' % (self.text_buffer.can_undo(), os.path.basename(self.fullPath)))

            return  #only save if there's something to save

        if new_file:
            self.fullPath = new_file

        if not self.fullPath.startswith(self.activity.storage):
            _logger.debug('failed to save self.fullPath: %s, Checked for starting with %s' % (self.fullPath, self.activity.debugger_home))
            self.activity.confirmation_alert(_('Would you like to include %s in your project?'%os.path.basename(self.fullPath)),  _('This MODIFIED File is not in your package'),self.save_to_project_cb)
            return

        if interactive_close and self.text_buffer.can_undo():
            self.activity.confirmation_alert(_('Would you like to Save the file, or cancel and abandon the changes?'), _('This File Has Been Changed'),self.continue_save)

        self.continue_save(None, Gtk.ResponseType.OK)
    
    def save_to_project_cb(self,alert, response=None):
        basename = os.path.basename(self.fullPath)
        new_name = self.activity.non_conflicting(self.activity.child_path,basename)
        self.fullPath = new_name
        self.continue_save(None, Gtk.ResponseType.OK)
        #update the project treeview
        self.activity.manifest_class.set_file_sys_root(self.activity.child_path)

    def continue_save(self, alert, response = None):
        if response != Gtk.ResponseType.OK:
            return

        _logger.debug('saving %s'%os.path.basename(self.fullPath))
        text = self.get_text()
        _file = file(self.fullPath, 'w')

        try:
            _file.write(text)
            _file.close()
            self.save_hash()
            self.label.set_text(os.path.basename(self.fullPath))
            self.text_buffer.set_modified(False)
            msg = _("File saved: %{path}s md5sumn:%{md5}s")
            arg = {"path": os.path.basename(self.fullPath), "md5":self.md5sum))}
            _logger.debug(msg % arg)

        except IOError:
            msg = _("I/O error(%{0}s): %{1}s"%(IOError[0], IOError[1]))
            self.activity.alert(msg)

        except:
            msg = "Unexpected error:", sys.exc_info()[1]
            self.activity.alert(msg)

        if _file:
            _file.close()

    def underlying_change_cb(self,response):
        #remove the alert from the screen, since either a response button
        #was clicked or there was a timeout
        self.remove_alert(alert)

        #Do any work that is specific to the type of button clicked.
        if response_id is Gtk.ResponseType.OK:
            self.continue_save(response_id)

        elif response_id is Gt.ResponseType.CANCEL:
            return

    def save_breakpoints(self):
        """breakpoints saved in debug_dict {<activity folder> - <filename> : [<numeric list>]}"""
        break_list = ''
        file_nickname = self.activity.glean_file_id_from_fullpath(self.fullPath)
        iter = self.text_buffer.get_iter_at_line_offset(0, 0)
        while self.text_buffer.forward_iter_to_source_mark(iter, self.brk_cat):
            break_list += str(iter.get_line() + 1) + ','

        if len(break_list) > 0:
            #trim off last ','
            break_list = break_list[:-1]
            self.activity.debug_dict[file_nickname + '-breakpoints'] = break_list
            self.activity.log_dict(self.activity.debug_dict,'debug_dict showing breakpoints ==>:')

    def can_undo_redo(self):
        """
        Returns a two-tuple (can_undo, can_redo) with Booleans of those abilities.
        """
        return (self.text_buffer.can_undo(), self.text_buffer.can_redo())
        
    def undo(self):
        """
        Undo the last change in the file.  If we can't do anything, ignore.
        """
        self.text_buffer.undo()
        
    def redo(self):
        """
        Redo the last change in the file.  If we can't do anything, ignore.
        """
        self.text_buffer.redo()
            
    def replace(self, ftext, rtext, s_opts):
        """returns true if replaced (succeeded)"""
        selection = s_opts.where == S_WHERE.selection
        if s_opts.replace_all or selection:
            result = False
            if selection:
                try:
                    selstart, selend = self.text_buffer.get_selection_bounds()

                except (ValueError,TypeError):
                    return False

                offsetadd = selstart.get_offset()
                buffertext = self.text_buffer.get_slice(selstart,selend)

            else:
                offsetadd = 0
                buffertext = self.get_text()

            results = list(self._getMatches(buffertext,ftext,
                                            s_opts,offsetadd))
            if not s_opts.replace_all:
                results = [results[0]]

            else:
                results.reverse() #replace right-to-left so that 
                                #unreplaced indexes remain valid.

            self.text_buffer.begin_user_action()

            for start, end, match in results:
                start = self.text_buffer.get_iter_at_offset(start)
                end = self.text_buffer.get_iter_at_offset(end)
                self.text_buffer.delete(start,end)
                self.text_buffer.insert(start, self.makereplace(rtext,match,s_opts.use_regex))
                result = True

            self.text_buffer.end_user_action()

            return result

        else: #replace, the &find part handled by caller
            try:
                (start,end) = self.text_buffer.get_selection_bounds()

            except TypeError:
                return False

            match = self._match(ftext, self.text_buffer.get_slice(start,end), s_opts)
            if match:
                self.text_buffer.delete(start, end)
                rtext = self.makereplace(rtext,match,s_opts.use_regex)
                self.text_buffer.insert(start, rtext)
                return True

            else:
                return False
                
    def makereplace(self, rpat, match, use_regex):
        if use_regex:
            return match.expand(rpat)

        else:
            return rpat
        
    def reroot(self,olddir,newdir):
        """Returns False if it works"""
        oldpath = self.fullPath
        if oldpath.startswith(olddir):
            self.fullPath = os.path.join(newdir, oldpath[len(olddir):])
            return False

        else:
            return True
        
    def _pd_button_press_cb(self,widget,event):
        _logger.debug('got button press at x:%s y:%s'%(event.x,event.y))
        # was click in left gutter:
        if event.window == self.text_view.get_window(Gtk.TextWindowType.LEFT):
            x_buf, y_buf = self.text_view.window_to_buffer_coords(Gtk.TextWindowType.LEFT, int(event.x,),int(event.y))
            #get line
            line_start = self.text_view.get_line_at_y(y_buf)[0]
            line_end = line_start.copy()
            if event.button == 1: 
                self.activity.editor.breakpoints_changed = True
                if line_end.forward_line():
                    #get markers in this line
                    mark_list = self.text_buffer.get_source_marks_at_line(line_start.get_line(),self.brk_cat)
                    #search for brk_category mark
                    for m in mark_list:
                        if m.get_category() == self.brk_cat:
                            self.text_buffer.remove_tag_by_name('breakpoint',line_start,line_end)
                            self.text_buffer.delete_mark(m)
                            _logger.debug('clear breakpoint')
                            break

                    else:
                        self.text_buffer.apply_tag_by_name('breakpoint',line_start,line_end)
                        mark = self.text_buffer.create_source_mark(None,self.brk_cat,line_start)
                        #breakpoints simulates a sparse array of marks stored in a dictionary by keyed by line number
                        self.breakpoints[line_start.get_line()] = mark
                        _logger.debug('set breakpoint')

            else:  #the right button
                insertion = 'from IPython.frontend.terminal.embed import embed; embed() #PyDebugTemp\n'
                self.activity.editor.embeds_exist = True
                if line_end.forward_line():
                    #get markers in this line
                    current_line = self.text_buffer.get_text(line_start,line_end)
                    if current_line.find('PyDebugTemp') > -1:
                        line_start.forward_line()
                        line_end.forward_line()

                    _logger.debug('current line:%s'%(current_line,))
                    mark_list = self.text_buffer.get_source_marks_at_line(line_start.get_line(),self.embed_cat)
                    #search for embed_category mark

                    for m in mark_list:
                        if m.get_category() == self.embed_cat:
                            self.text_buffer.remove_tag_by_name('embed_shell',line_start,line_end)
                            self.text_buffer.delete_mark(m)
                            #now delete the embed code in the line preceedng the marker line
                            debug_start = line_start.copy()
                            debug_start.backward_line()
                            delete_candidate = self.text_buffer.get_text(debug_start,line_start)
                            _logger.debug('delete candidate line:%s'%(delete_candidate,))

                            if delete_candidate.find('PyDebugTemp') > -1:
                                self.text_buffer.delete(debug_start,line_start)
                            _logger.debug('clear embeded shell')
                            break

                    else:
                        self.text_buffer.apply_tag_by_name('embed_shell',line_start,line_end)
                        padding = self.get_indent(current_line)
                        indent = self.pad(padding)
                        self.text_buffer.insert(line_start,indent+insertion)
                        mark = self.text_buffer.create_source_mark(None,self.embed_cat,line_start)
                        #embeds simulates a sparse array of marks stored in a dictionary by keyed by line number
                        self.embeds[line_start.get_line()] = mark
                        _logger.debug('set embeded shell')

        return False

    def get_indent(self,line):
        i = 0
        for i in range(len(line)):
            if line[i] == ' ':
                i += 1

            else:
                break

        return i
    
    def pad(self,num_spaces):
        rtn = ''
        for i in range(num_spaces):
            rtn += ' '

        return rtn

