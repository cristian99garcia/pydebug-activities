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
import pango
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

# Initialize logging.
from  pydebug_logging import _logger, log_environment, log_dict

#constants for text_buffer marks
BREAKPOINT_CAT = 'BREAKPOINT'
SHELL_CAT = 'SHELL'
TRACE_CAT = 'TRACE'
BREAKPOINT_COLOR = '#FFDDDD'
EMBEDED_SHELL_COLOR = '#DDFFDD'
EMBEDED_BREAKPOINT_COLOR = '#DDDDFF'
TRACE_INSERT = 'from IPython.Debugger import Tracer; debug = Tracer(); debug() #PyDebugTemp\n'
SHELL_INSERT = 'from IPython.Shell import IPShellEmbed; pdbshell = IPShellEmbed([],banner="%s"); pdbshell() #PyDebugTemp\n'
#following is for 0.11 ipython
#insertion = 'from IPython.frontend.terminal.embed import embed; embed() #PyDebugTemp\n'
#insertion = 'from IPython.Debugger import Tracer; debug = Tracer(); debug() #PyDebugTemp\n'

class SearchablePage(gtk.ScrolledWindow):
    def get_selected(self):
        try:
            start,end = self.text_buffer.get_selection_bounds()
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
        self.text_buffer.copy_clipboard(gtk.Clipboard())
    
    def paste(self):
        """
        Cut the currently selected text the clipboard into the current file.
        """
        self.text_buffer.paste_clipboard(gtk.Clipboard(), None, True)
        
    def cut(self):
        """
        Paste from the clipboard.
        """
        self.text_buffer.cut_clipboard(gtk.Clipboard(), True)
        
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
            matches = self._getMatches(text[offset:],fpat,s_opts,
                    offset+offset_add)
            try:
                return matches.next()
            except StopIteration:
                return ()
        else:
            if offset != 0:
                text = text[:offset]
            matches = list(self._getMatches(text,fpat,s_opts,
                    offset_add))
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
                start, end, match = self._find_in(buffertext, ftext, 0,
                                            s_opts, offsetadd)
            except (ValueError,TypeError):
                return False
        else:
            offset = self.get_offset() + (not s_opts.stay) #add 1 if not stay.
            text = self.get_text()
            try:
                start,end,match = self._find_in(text, ftext, offset,
                                            s_opts, 0)
            except (ValueError,TypeError):
                #find failed.
                if wrap:
                    try:
                        start,end,match = self._find_in(text, ftext, 0, 
                                                        s_opts, 0)
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
        self.text_buffer.select_range(_iter,_iter)
        self.thismark = thismark = self.text_buffer.create_mark('mymark',_iter)
        self.text_view.scroll_to_mark(thismark,0.0,True)
        mark_iter = self.text_buffer.get_iter_at_mark(thismark)
        _logger.debug('scroll to line:%s mark is at line %s'%(line,mark_iter.get_line(),))
        gobject.idle_add(self.scroll_cb)
        
    def scroll_cb(self):
        self.text_view.scroll_to_mark(self.thismark,0.0,True)        

    def break_at(self):
        offset = self.get_offset()
        _logger.debug('breakpoint at character %s'%(offset,))
        
    
    def __eq__(self,other):
        if isinstance(other,GtkSourceview2Page):
            return self.fullPath == other.fullPath
        #elif isinstance(other,type(self.fullPath)):
        #    other = other.metadata['source']
        if isinstance(other,basestring):
            return other == self.fullPath
        else:
            return False
        
class GtkSourceview2Page(SearchablePage):

    def __init__(self, fullPath, activity):
        """
        Do any initialization here.
        """
        self.fullPath = fullPath
        self._activity = activity
        self.breakpoints = {}
        self.embeds = {}
        
        gtk.ScrolledWindow.__init__(self)
        self.text_buffer = gtksourceview2.Buffer()
        self.text_buffer.create_tag(BREAKPOINT_CAT, background = BREAKPOINT_COLOR)
        self.text_buffer.create_tag(SHELL_CAT, background = EMBEDED_SHELL_COLOR)
        self.text_buffer.create_tag(TRACE_CAT, background = EMBEDED_BREAKPOINT_COLOR)

        self.text_view = gtksourceview2.View(self.text_buffer)
        self.text_view.connect('button_press_event',self._pd_button_press_cb)
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

        self.text_view.set_wrap_mode(gtk.WRAP_CHAR)
        #self.text_view.modify_font(pango.FontDescription("Monospace 6.5"))
        self.set_font_size(self._activity.font_size)

        # We could change the color theme here, if we want to.
        """ folowing does not work on build 650
        mgr = gtksourceview2.StyleSchemeManager()
        mgr.prepend_search_path(self._activity.pydebug_path)
        _logger.debug('search path for gtksourceview is %r'%mgr.get_search_path())
        """
        #build 650 doesn't seem to have the same means of specifying the search directory
        info = self._activity.util.sugar_version()
        if len(info)>0:
            (major,minor,micro,release) = info
            _logger.debug('sugar version major:%s minor:%s micro:%s release:%s'%info)
        else:
            _logger.debug('sugar version failure')
            minor = 70
        if minor > 80:
            mgr = gtksourceview2.StyleSchemeManager()
        else:
            mgr = gtksourceview2.StyleManager()
        mgr.prepend_search_path(self._activity.pydebug_path)
        style_scheme = mgr.get_scheme('vibrant')
        if style_scheme:
            self.text_buffer.set_style_scheme(style_scheme)
        
        self.set_policy(gtk.POLICY_AUTOMATIC,
                      gtk.POLICY_AUTOMATIC)
        self.add(self.text_view)
        self.text_view.show()
        self.load_text()
        self.show()

    def set_font_size(self,font_size=None):
        if font_size == None: font_size = self._activity.font_size
        self.text_view.modify_font(pango.FontDescription("Monospace %d"%font_size))
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
            lang_manager = gtksourceview2.language_manager_get_default()
            if hasattr(lang_manager, 'list_languages'):
               langs = lang_manager.list_languages()
            else:
                lang_ids = lang_manager.get_language_ids()
                langs = [lang_manager.get_language(i) for i in lang_ids]
            for lang in langs:
                for m in lang.get_mime_types():
                    if m == mime_type:
                        self.text_buffer.set_language(lang)
                        if hasattr(self.text_buffer, 'set_highlight'):
                            self.text_buffer.set_highlight(True)
                        else:
                            self.text_buffer.set_highlight_syntax(True)
        self.restore_breakpoints()
        self.text_buffer.end_not_undoable_action()
        self.text_buffer.set_modified(False)
        self.text_view.grab_focus()
    
    def restore_breakpoints(self):
        file_nickname = self._activity.glean_file_id_from_fullpath(self.fullPath)
        self.break_list = self._activity.debug_dict.get(file_nickname + '-breakpoints')
        if not self.break_list: return
        del self._activity.debug_dict[file_nickname + '-breakpoints']
        if not self._activity.load_breakpoints:
            alert = self._activity.util.confirmation_alert(_('Chose OK to restore, Cancel to delete them.'),
                                                      _('This Activity has Breakpoints!'),
                                                      self._restore_brkpt_cb)
        else:
            self._restore_brkpt_cb(None,None)

    def _restore_brkpt_cb(self,alert,response):
        #callback not taken if not response ok
        self._activity.load_breakpoints = True
        self.break_list = self.break_list.split(',')
        for line in self.break_list:
            line_start = self.text_buffer.get_iter_at_line(int(line) - 1)
            line_end = line_start.copy()
            line_end.forward_line()
            self.text_buffer.apply_tag_by_name(BREAKPOINT_CAT,line_start,line_end)
            mark = self.text_buffer.create_source_mark(None,BREAKPOINT_CAT,line_start)
            #breakpoints simulates a sparse array of marks stored in a dictionary by keyed by line number
            _logger.debug('set breakpoint on line:%s'%line)
                
    def save_hash(self):   
        self.md5sum = self._activity.util.md5sum(self.fullPath)

    def remove(self):
        self.save()
   
    def save(self,skip_md5 = False, interactive_close=False,new_file=None):
        if interactive_close:
            self._activity.remember_line_no(self.fullPath,self.get_iter().get_line())
        if os.path.basename(self.fullPath).startswith('Unsaved_Document') and \
                            self.text_buffer.can_undo():
            self._activity.save_cb(None)
            return
        if not new_file and (not self.text_buffer.can_undo() or self._activity.abandon_changes): 
            if not self.text_buffer.can_undo():
                _logger.debug('no changes:%s for %s'%(self.text_buffer.can_undo(),os.path.basename(self.fullPath),))
            return  #only save if there's something to save
        if new_file:
            self.fullPath = new_file
        
        """
        if not skip_md5:
            hash = self._activity.util.md5sum(self.fullPath)
            if self.md5sum != hash: #underlying file has changed
                _logger.warning('md5sum stored:%s. Calculated:%s'%(self.md5sum,hash))
                _logger.warning('md5sum changed outside editor for %s. Save file questioned'
                                %os.path.basename(self.fullPath))
                self._activity.confirmation_alert(_('Would you like to overwrite the changes in %s?'%os.path.basename(self.fullPath)),
                                                 _('The Underlying File Has Been Changed By Another Application'),
                                                 self.continue_save)
                return
        """
        if not self.fullPath.startswith(self._activity.storage):
            _logger.debug('failed to save self.fullPath: %s, Checked for starting with %s'%(self.fullPath, \
                                                                                            self._activity.debugger_home))
            self._activity.util.confirmation_alert(_('Would you like to include %s in your project?'%os.path.basename(self.fullPath)),\
                                             _('This MODIFIED File is not in your package'),self.save_to_project_cb)
            return
        if interactive_close and self.text_buffer.can_undo():
            self._activity.util.confirmation_alert(_('Would you like to Save the file, or cancel and abandon the changes?'),
                                            _('This File Has Been Changed'),self.continue_save)
                                           
        self.continue_save(None,gtk.RESPONSE_OK)
    
    def save_to_project_cb(self,alert, response=None):
        basename = os.path.basename(self.fullPath)
        new_name = self._activity.util.non_conflicting(self._activity.child_path,basename)
        self.tooltip.set_tip(self.label,new_name)
        self.fullPath = new_name
        self.continue_save(None,gtk.RESPONSE_OK)
        #update the project treeview
        self._activity.manifest_class.set_file_sys_root(self._activity.child_path)
                   
    def continue_save(self, alert, response = None):
        if response != gtk.RESPONSE_OK: return
        _logger.debug('saving %s'%os.path.basename(self.fullPath))
        text = self.get_text()
        _file = file(self.fullPath, 'w')
        try:
            _file.write(text)
            _file.close()
            self.save_hash()
            self.label.set_text(os.path.basename(self.fullPath))
            self.text_buffer.set_modified(False)
            msg = _("File saved: %s md5sumn:%s"%(os.path.basename(self.fullPath),self.md5sum))
            _logger.debug(msg)
        except IOError:
            msg = _("I/O error(%s): %s"%(IOError[0], IOError[1]))
            self._activity.alert(msg)
        except:
            msg = "Unexpected error:", sys.exc_info()[1]
            self._activity.alert(msg)
        if _file:
            _file.close()

    def underlying_change_cb(self,response):
        #remove the alert from the screen, since either a response button
        #was clicked or there was a timeout
        self.remove_alert(alert)

        #Do any work that is specific to the type of button clicked.
        if response_id is gtk.RESPONSE_OK:
            self.continue_save(response_id)
        elif response_id is gtk.RESPONSE_CANCEL:
            return
        
    def save_breakpoints(self):
        """breakpoints saved in debug_dict {<activity folder> - <filename> : [<numeric list>]}"""
        break_list = ''
        file_nickname = self._activity.glean_file_id_from_fullpath(self.fullPath)
        iter = self.text_buffer.get_iter_at_line_offset(0,0)
        while self.text_buffer.forward_iter_to_source_mark(iter,BREAKPOINT_CAT):
            break_list += str(iter.get_line()+1) + ','
        if len(break_list) > 0:
            #trim off last ','
            break_list = break_list[:-1]
            self._activity.debug_dict[file_nickname + '-breakpoints'] = break_list
            log_dict(self._activity.debug_dict,'debug_dict j ==>:')
        
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
            match = self._match(ftext,
                        self.text_buffer.get_slice(start,end),
                        s_opts)
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
        """respond to left and right clicks on the number column
        left-click toggles breakpoint on and off at current line (red)
        right-click cycles through:
            off->embeded_trace(green)->embeded-shell(blue)->off . . .
        right-click on the inserted line is same as right click on line following it
        left click during embeded shell or trace is ignored
        """

        if event.window == self.text_view.get_window(gtk.TEXT_WINDOW_LEFT):
            #click  was in left gutter:          
            x_buf, y_buf = self.text_view.window_to_buffer_coords(gtk.TEXT_WINDOW_LEFT,
                                                                  int(event.x,),int(event.y))
            #get contents of the line 
            line_start = self.text_view.get_line_at_y(y_buf)[0]
            self.clicked_line_num = line_start.get_line()
            self.current_line = self.get_current_line()
            if not self.current_line:
                return
            line_end = line_start.copy()
            line_end.forward_line()
            
            if self.current_line.find('PyDebugTemp') == -1:
                if event.button == 1:                    
                    self.left_button_click_on_code_line(line_start, line_end)
                    return    
                else:
                    current_state = self.right_button_click_on_code_line(line_start, line_end)
            else:
                #click_on_inserted_line
                if event.button == 1:
                    #do nothing for left click on inserted line
                    return
                current_state = self.delete_current_insertion(line_start, line_end)

            #previously inserted lines, marks are deleted, now do next_state
            self.make_insertion(current_state, line_start, line_end)
        return False        

    def get_current_line(self):
        line_start = self.text_buffer.get_iter_at_line(self.clicked_line_num)
        line_end = line_start.copy()
        if not line_end.forward_line():
            #couldn't advance to next line, so just return
            return None
        current_line = self.text_buffer.get_text(line_start, line_end)
        _logger.debug('current line:%s'%(current_line))
        return current_line
    
    def left_button_click_on_code_line(self, start_iter, line_end):
        current_line_marks_list = self.text_buffer.get_source_marks_at_line(self.clicked_line_num, None)
        self._activity.breakpoints_changed = True
        for m in current_line_marks_list:
            if m.get_category() == BREAKPOINT_CAT:
                self.text_buffer.delete_mark(m)
                self.text_buffer.remove_tag_by_name(BREAKPOINT_CAT, start_iter, line_end)
                _logger.debug('clear breakpoint')
                return
        self.text_buffer.apply_tag_by_name(BREAKPOINT_CAT, start_iter, line_end)
        mark = self.text_buffer.create_source_mark(None, BREAKPOINT_CAT, start_iter)
        self.breakpoints[self.clicked_line_num] = ''
        _logger.debug('set breakpoint')

    def right_button_click_on_code_line(self, line_start, line_end):
        #if we specify None for marks_category, we get all of them
        current_line_marks_list = self.text_buffer.get_source_marks_at_line(self.clicked_line_num, None)
        current_state = None
        if len(current_line_marks_list) > 0:
            for m in current_line_marks_list:
                if m.get_category() == TRACE_CAT:
                    current_state = TRACE_CAT
                    self.text_buffer.remove_tag_by_name(TRACE_CAT, line_start,line_end)
                    self.text_buffer.delete_mark(m)
                if m.get_category() == SHELL_CAT:
                    current_state = SHELL_CAT
                    self.text_buffer.remove_tag_by_name(SHELL_CAT, line_start,line_end)
                    self.text_buffer.delete_mark(m)
                _logger.debug('mark category:%s'%(m.get_category(),))
            #now delete the embed code in the line preceedng the marker line
            debug_start = line_start.copy()
            debug_start.backward_line()
            delete_candidate = self.text_buffer.get_text(debug_start, line_start)
            _logger.debug('delete candidate line:%s'%(delete_candidate,))
            if delete_candidate.find('PyDebugTemp') > -1:
                self.text_buffer.delete(debug_start, line_start)
        else:
            #no marks on this non-inserted line
            _logger.debug('no marks on this line')
            current_state = None
        return current_state
        
    def delete_current_insertion(self, line_start, line_end):
        """receives iters for start, end of inserted line, returns current_state"""
        current_line = self.text_buffer.get_text(line_start, line_end)
        line_no = line_start.get_line()
        if line_no in self.embeds:
            del self.embeds[line_no]
        _logger.debug('about to delete: %s'%(current_line,))
        self.text_buffer.delete(line_start, line_end)
        if self.current_line.find(TRACE_INSERT) > -1:
            current_state = TRACE_CAT
        elif self.current_line.find(SHELL_INSERT) > -1:
            current_state = SHELL_CAT
        else:
            current_state = None            
        line_start = self.text_buffer.get_iter_at_line(self.clicked_line_num)
        if line_start:
            line_end = line_start.copy()
            line_end.forward_line()
            self.text_buffer.remove_tag_by_name(current_state, line_start, line_end)
            self.text_buffer.remove_source_marks(line_start, line_end, None)
        else:
            _logger.debug('failed to find mark %s during click on inserted line'%(current_cat,))
        return current_state

    def make_insertion(self, current_state, line_start, line_end):
        if current_state == None:
            insertion = TRACE_INSERT
            tag_name = TRACE_CAT
        elif current_state == TRACE_CAT:
            file_nickname = os.path.basename(self.fullPath)
            line_no = line_start.get_line()
            shell_at = '%s:%s'%(file_nickname,line_no,)
            insertion = SHELL_INSERT%(shell_at,)
            tag_name = SHELL_CAT
        elif current_state == SHELL_CAT:
            #previous insertion is deleted, no insertion to do
            return
        mark = self.text_buffer.create_source_mark(None, tag_name, line_start)
        line_no = line_start.get_line()
        self.embeds[line_no] = ''
        padding = self.get_indent(self.current_line)
        indent = self.pad(padding)
        self.text_buffer.insert(line_start,indent+insertion)
        line_start = self.text_buffer.get_iter_at_mark(mark)
        line_end = line_start.copy()
        forwarded = line_end.forward_line() #self.text_buffer.forward_iter_to_source_mark(line_end,tag_name)
        if forwarded:
            self.text_buffer.move_mark(mark, line_end)
            line_end.forward_line()
            self.text_buffer.apply_tag_by_name(tag_name, line_start, line_end)
        else:
            _logger.debug('failed to forward to mark with tag:%s'%(tag_name,))
        _logger.debug('inserted line %s'%(tag_name,))

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