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

import os
import shutil
import sys
import hashlib
import time
import datetime
import pickle

from subprocess import Popen
from subprocess import PIPE

from gettext import gettext as _
import project_glade

#major packages
from gi.repository import Gtk
from gi.repository import Gdk
from gi.repository import Vte
from gi.repository import Pango
from gi.repository import Gio

#sugar stuff
from sugar3.graphics.toolbutton import ToolButton
from sugar3.graphics.xocolor import XoColor
from sugar3.graphics.icon import Icon
from sugar3.graphics.objectchooser import ObjectChooser
from sugar3.datastore import datastore
from sugar3.graphics.alert import *
from sugar3.activity import bundlebuilder
from sugar3.bundle.activitybundle import ActivityBundle
from sugar3.activity import activityfactory
from sugar3.graphics.alert import ConfirmationAlert

#application stuff
from terminal_pd import Terminal
#public api for ipython

#from IPython.core import ipapi 0.11 requires this
import IPython.ipapi

#from sourceview import SourceViewPd
import sourceview_editor
from sugar3.activity.activity import Activity
from help_pd import Help

#following taken from Rpyc module
#import Rpyc 
from Rpyc.Utils.Serving import start_threaded_server, DEFAULT_PORT
from Rpyc.Connection import *
from Rpyc.Stream import *
import select
from filetree import FileTree
from datastoretree import DataStoreTree
import pytoolbar
#from pytoolbar import ActivityToolBox

import logging
from  pydebug_logging import _logger, log_environment

MASKED_ENVIRONMENT = [
    'DBUS_SESSION_BUS_ADDRESS',
    'PPID'
]

#PANES = ['TERMINAL','EDITOR','CHILD','PROJECT','HELP']
PANES = ['TERMINAL','EDITOR','PROJECT','HELP']

#global module variable communicates to debugged programs
pydebug_instance = None


#following options taken from Develop_App
class Options:

    def __init__(self, template = None, **kw):
        if template:
            self.__dict__ = template.__dict__.copy()

        else:
            self.__dict__ = {}

        self.__dict__.update(kw)


class SearchOptions(Options):
    pass


S_WHERE = sourceview_editor.S_WHERE
    

class PyDebugActivity(Activity,Terminal):

    MIME_TYPE = 'application/vnd.olpc-sugar'
    DEPRECATED_MIME_TYPE = 'application/vnd.olpc-x-sugar'
    _zipped_extension = '.xo'
    _unzipped_extension = '.activity'
    dirty = False
    
    def __init__(self, handle):
        self.handle = handle
        _logger.debug('Activity id:%s.Object id: %s. uri:%s' % (handle.activity_id, handle.object_id, handle.uri))
        ds = datastore.get(handle.object_id)
        debugstr = ''
        for key in ds.metadata.keys():
            if key == 'preview': continue
            debugstr += key + ':'+str(ds.metadata[key]) + ', '

        _logger.debug('initial datastore metadata dictionary==>: %r'%debugstr)
        #Save a global poiinter so remote procedure calls can communicate with pydebug
        global pydebug_instance
        pydebug_instance = self

        #init variables
        self.make_paths()
        self.save_icon_clicked = False
        self.source_directory = None
        self.data_file = None
        self.help = None
        self.help_x11 = None
        self.project_dirty = False
        self.sock = None
        self.last_filename = None
        self.debug_dict = {}
        self.activity_dict = {}
        self.file_pane_is_activities = False
        self.manifest_treeview = None  #set up to recognize an re-display of playpen
        #self.set_title(_('PyDebug Activity'))
        self.ds = None #datastore pointer
        self._logger = _logger
        self.traceback = 'Context'
        self.abandon_changes = False
        
        # init the Classes we are subclassing
        Activity.__init__(self, handle,  create_jobject = False)
        #Terminal has no needs for init
        #Help.__init__(self,self)
        
        # setup the search options
        self.s_opts = SearchOptions(where = S_WHERE.multifile,
                                    use_regex = False,
                                    ignore_caps = True,
                                    replace_all = False,
                                    
                                    #defaults to avoid creating
                                    #a new SearchOptions object for normal searches
                                    #should never be changed, just make a copy like:
                                    #SearchOptions(self.s_opts, forward=False)
                                    forward = True, 
                                    stay = False
                                    )
        self.safe_to_replace = False
        
        
        #set up the PANES for the different functions of the debugger
        self.canvas_list = []
        self.panes = {}
        pane_index = 0
        pane_index =  self.new_pane(self._get_terminal_canvas,pane_index)         
        pane_index =  self.new_pane(self._get_edit_canvas,pane_index) 
        #pane_index =  self.new_pane(self._get_child_canvas,pane_index) 
        pane_index =  self.new_pane(self._get_project_canvas,pane_index) 
        pane_index =  self.new_pane(self._get_help_canvas,pane_index)

        nb = Gtk.Notebook()
        nb.show()
        nb.set_show_tabs(False)

        for c in self.canvas_list:
            nb.append_page(c)

        self.pydebug_notebook = nb
        #the following call to the activity code puts our notebook under the stock toolbar
        self.set_canvas(nb)

        #set up tool box/menu buttons
        self.toolbox = pytoolbar.ActivityToolbox(self)
        self.toolbox.connect('current_toolbar_changed',self._toolbar_changed_cb)

        activity_toolbar = self.toolbox.get_activity_toolbar()
        activity_toolbar.share.props.visible = True

        separator = Gtk.SeparatorToolItem()
        separator.set_draw(True)
        separator.show()
        activity_toolbar.insert(separator, 0)

        activity_go = ToolButton(stock_id=Gtk.STOCK_MEDIA_FORWARD)
        activity_go.set_icon_widget(None)
        activity_go.set_tooltip(_('Start Debugging'))
        activity_go.connect('clicked', self.project_run_cb)
        #activity_go.props.accelerator = '<Ctrl>O'
        activity_go.show()
        activity_toolbar.insert(activity_go, 0)

        activity_copy_tb = ToolButton('edit-copy')
        activity_copy_tb.set_tooltip(_('Copy'))
        activity_copy_tb.connect('clicked', self._copy_cb)
        #activity_copy_tb.props.accelerator = '<Ctrl>C'
        activity_toolbar.insert(activity_copy_tb, 3)
        activity_copy_tb.show()

        activity_paste_tb = ToolButton('edit-paste')
        activity_paste_tb.set_tooltip(_('Paste'))
        activity_paste_tb.connect('clicked', self._paste_cb)
        #activity_paste_tb.props.accelerator = '<Ctrl>V'
        activity_toolbar.insert(activity_paste_tb, 4)
        activity_paste_tb.show()

        activity_tab_tb = sugar.graphics.toolbutton.ToolButton('list-add')
        activity_tab_tb.set_tooltip(_("Open New Tab"))
        activity_tab_tb.props.accelerator = '<Ctrl>T'
        activity_tab_tb.show()
        activity_tab_tb.connect('clicked', self._open_tab_cb)
        activity_toolbar.insert(activity_tab_tb, 5)

        activity_tab_delete_tv = sugar.graphics.toolbutton.ToolButton('list-remove')
        activity_tab_delete_tv.set_tooltip(_("Close Tab"))
        activity_tab_delete_tv.props.accelerator = '<Ctrl><Shift>X'
        activity_tab_delete_tv.show()
        activity_tab_delete_tv.connect('clicked', self._close_tab_cb)
        activity_toolbar.insert(activity_tab_delete_tv, 6)


        activity_fullscreen_tb = sugar.graphics.toolbutton.ToolButton('view-fullscreen')
        activity_fullscreen_tb.set_tooltip(_("Fullscreen"))
        activity_fullscreen_tb.props.accelerator = '<Alt>Enter'
        activity_fullscreen_tb.connect('clicked', self._fullscreen_cb)
        activity_toolbar.insert(activity_fullscreen_tb, 7)
        activity_fullscreen_tb.hide()

        #Add editor functionality to the debugger
        editbar = Gtk.Toolbar()

        editopen = ToolButton(stock_id=Gtk.STOCK_NEW)
        editopen.set_icon_widget(None)
        editopen.set_tooltip(_('New File'))
        editopen.connect('clicked', self._read_file_cb)
        #editopen.props.accelerator = '<Ctrl>O'
        editopen.show()
        editbar.insert(editopen, -1)

        editfile = ToolButton(stock_id=Gtk.STOCK_OPEN)
        editfile.set_icon_widget(None)
        editfile.set_tooltip(_('Open File'))
        editfile.connect('clicked', self._read_file_cb)
        editfile.props.accelerator = '<Ctrl>O'
        editfile.show()
        editbar.insert(editfile, -1)

        editsave = ToolButton(stock_id=Gtk.STOCK_SAVE)
        editsave.set_icon_widget(None)
        editsave.set_tooltip(_('Save File'))
        editsave.props.accelerator = '<Ctrl>S'
        editsave.connect('clicked', self.save_cb)
        editsave.show()
        editbar.insert(editsave, -1)

        editsaveas = ToolButton(stock_id=Gtk.STOCK_SAVE_AS)
        editsaveas.set_icon_widget(None)
        editsaveas.set_tooltip(_('Save As'))
        #editsaveas.props.accelerator = '<Ctrl>S'
        editsaveas.connect('clicked', self.save_file_cb)
        editsaveas.show()
        editbar.insert(editsaveas, -1)

        separator = Gtk.SeparatorToolItem()
        separator.set_draw(True)
        separator.show()
        editbar.insert(separator, -1)

        editundo = ToolButton('undo')
        editundo.set_tooltip(_('Undo'))
        editundo.connect('clicked', self.editor.undo)
        editundo.props.accelerator = '<Ctrl>Z'
        editundo.show()
        editbar.insert(editundo, -1)

        editredo = ToolButton('redo')
        editredo.set_tooltip(_('Redo'))
        editredo.connect('clicked', self.editor.redo)
        editredo.props.accelerator = '<Ctrl>Y'
        editredo.show()
        editbar.insert(editredo, -1)

        separator = Gtk.SeparatorToolItem()
        separator.set_draw(True)
        separator.show()
        editbar.insert(separator, -1)

        editcut = ToolButton(stock_id=Gtk.STOCK_CUT)
        editcut.set_icon_widget(None)
        editcut.set_tooltip(_('Cut'))
        self.edit_cut_handler_id = editcut.connect('clicked', self.editor.cut)
        editcut.props.accelerator = '<Ctrl>X'
        editbar.insert(editcut, -1)
        editcut.show()

        editcopy = ToolButton('edit-copy')
        editcopy.set_tooltip(_('Copy'))
        self.edit_copy_handler_id = editcopy.connect('clicked', self.editor.copy)
        editcopy.props.accelerator = '<Ctrl>C'
        editbar.insert(editcopy, -1)
        editcopy.show()

        editpaste = ToolButton('edit-paste')
        editpaste.set_tooltip(_('Paste'))
        self.edit_paste_handler_id = editpaste.connect('clicked', self.editor.paste)
        editpaste.props.accelerator = '<Ctrl>V'
        editpaste.show()
        editbar.insert(editpaste, -1)

        separator = Gtk.SeparatorToolItem()
        separator.set_draw(True)
        separator.show()
        editbar.insert(separator, -1)

        editfind = ToolButton('viewmag1')
        editfind.set_tooltip(_('Find and Replace'))
        editfind.connect('clicked', self.show_find)
        editfind.props.accelerator = '<Ctrl>F'
        editfind.show()
        editbar.insert(editfind, -1)

        separator = Gtk.SeparatorToolItem()
        separator.set_draw(True)
        separator.show()
        editbar.insert(separator, -1)

        self.zoomout = ToolButton('zoom-out')
        self.zoomout.set_tooltip(_('Zoom out'))
        self.zoomout.connect('clicked', self.__zoomout_clicked_cb)
        editbar.insert(self.zoomout, -1)
        self.zoomout.show()

        self.zoomin = ToolButton('zoom-in')
        self.zoomin.set_tooltip(_('Zoom in'))
        self.zoomin.connect('clicked', self.__zoomin_clicked_cb)
        editbar.insert(self.zoomin, -1)
        self.zoomin.show()

        editbar.show_all()
        self.toolbox.add_toolbar(_('Edit'), editbar)

        project_run = ToolButton(stock_id=Gtk.STOCK_MEDIA_FORWARD)
        project_run.set_icon_widget(None)
        project_run.set_tooltip(_('Start Debugging'))
        project_run.connect('clicked', self.project_run_cb)
        #project_run.props.accelerator = '<Ctrl>C'
        project_run.show()

        separator = Gtk.SeparatorToolItem()
        separator.set_draw(False)
        separator.set_expand(True)
        separator.show()

        self.keep = ToolButton(tooltip=_('Save Snapshot of the program in the Playpen to the GIT repository'))
        #client = gconf.client_get_default()
        #color = XoColor(client.get_string('/desktop/sugar/user/color'))
        #keep_icon = Icon(icon_name='document-save', xo_color=color)
        keep_icon = Icon(icon_name='document-save')
        self.keep.set_icon_widget(keep_icon)
        keep_icon.show()
        #self.keep.props.accelerator = '<Ctrl>S'
        self.keep.connect('clicked', self.__keep_clicked_cb)
        #self.insert(self.keep, -1)
        self.keep.show()

        projectbar = Gtk.Toolbar()
        projectbar.show_all()
        projectbar.insert(project_run, -1)
        projectbar.insert(separator, -1)
        projectbar.insert(self.keep,-1)
        self.toolbox.add_toolbar(_('Project'), projectbar)

        self.help = Help(self)
        helpbar = self.help.get_help_toolbar()
        self.toolbox.add_toolbar(_('Help'), helpbar)

        self.set_toolbox(self.toolbox)
        self.toolbox.show()

        #set the default contents for edit
        self.font_size = self.debug_dict.get('font_size',8) 

        #set which PANE is visible initially
        self.set_visible_canvas(self.panes['PROJECT'])
        self.set_toolbar(self.panes['PROJECT'])
        self.non_blocking_server()
        #glib.idle_add(self.non_blocking_server)
        self.setup_project_page()
        _logger.debug('child path for program to be debugged is %r\nUser Id:%s'%(self.child_path,os.geteuid()))

        #create the terminal tabs, start up the socket between 1st and 2nd terminal instances
        self.setup_terminal()

    def __stop_clicked_cb(self,button):
        _logger('caught stop clicked call back')
        self.close(skip_save = True)

    def __zoomin_clicked_cb(self,button):
            self.font_size += 1
            self.editor.change_font_size(self.font_size)
            self.debug_dict['font_size'] = self.font_size

    def __zoomout_clicked_cb(self,botton):
            self.font_size -= 1
            self.editor.change_font_size(self.font_size)
            self.debug_dict['font_size'] = self.font_size

    def command_line(self,cmd, alert_error=True):
        _logger.debug('command_line cmd:%s'%cmd)
        p1 = Popen(cmd,stdout=PIPE, shell=True)
        output = p1.communicate()
        if p1.returncode != 0 :
            _logger.debug('error returned from shell command: %s was %s'%(cmd,output[0]))
            if alert_error: self.alert(' Command returned non zero\n'+output[0])
        return output[0]

    def sugar_version(self):
        cmd = '/bin/rpm -q sugar'
        reply = self.command_line(cmd)
        if reply and reply.find('sugar') > -1:
            version = reply.split('-')[1]
            version_chunks = version.split('.')
            major_minor = version_chunks[0] + '.' + version_chunks[1]
            return float(major_minor) 
        return None

    def non_blocking_server(self):
        start_threaded_server()
    
    def new_pane(self,funct,i):
        self.panes[PANES[i]] = i
        self.canvas_list.append(funct())
        i += 1
        return i
    
    def make_paths(self):
        self.pydebug_path = os.environ['SUGAR_BUNDLE_PATH']
        p_path = os.environ['SUGAR_BUNDLE_PATH']
        if not os.environ.get("PYTHONPATH",'') == '':
            p_path = p_path + ':'
        os.environ['PYTHONPATH'] = p_path + os.environ.get("PYTHONPATH",'')
        _logger.debug('sugar_bundle_path:%s\nsugar_activity_root:%s' % (os.environ['SUGAR_BUNDLE_PATH'], os.environ['SUGAR_ACTIVITY_ROOT']))
        self.debugger_home = os.path.join(os.environ['SUGAR_ACTIVITY_ROOT'],'data')
        self.child_path = None
        os.environ["HOME"]=self.debugger_home
        os.environ['PATH'] = os.path.join(self.pydebug_path,'bin:') + os.environ['PATH']
        self.storage = os.path.join(os.environ['SUGAR_ACTIVITY_ROOT'],'data/pydebug')
        self.sugar_bundle_path = os.environ['SUGAR_BUNDLE_PATH']
        self.activity_playpen = os.path.join(self.storage,'playpen')
        if not os.path.isdir(self.activity_playpen):
            os.makedirs(self.activity_playpen)

    def _get_edit_canvas(self):
        self.editor =  sourceview_editor.GtkSourceview2Editor(self)
        return self.editor

    def setup_terminal(self):
        os.environ['IPYTHONDIR'] = self.pydebug_path
        _logger.debug('Set IPYTHONDIR to %s'%self.pydebug_path)
        self._create_tab({'cwd':self.sugar_bundle_path})
        self._create_tab({'cwd':self.sugar_bundle_path})
        #start the debugger user interface
        alias_cmd = 'alias go="%s"\n'%('./bin/ipython.py',)
        self.feed_virtual_terminal(0,alias_cmd)

        self.feed_virtual_terminal(0,'./bin/ipython.py  \n')
        #cmd = 'run ' + os.path.join(self.sugar_bundle_path,'bin','start_debug.py') + '\n'
        #self.feed_virtual_terminal(0,cmd)

    def start_debugging(self): #check for a start up script in bundle root or bundle_root/bin
        command = self.activity_dict.get('command','')
        if command == '':
            self.alert('No Activity Loaded')
            return

        _logger.debug("Command to execute:%s."%command)
        self.editor.save_all()
        
        #try to restore a clean debugging environment
        #self.feed_virtual_terminal(0,'quit()\r\n\r\n')

        self.set_visible_canvas(self.panes['TERMINAL'])
        #change the menus
        self.toolbox.set_current_toolbar(self.panes['TERMINAL'])
        message = _('\n\n Use the HELP in the Ipython interpreter to learn to DEBUG your program.\n')
        self.message_terminal(0,message)

        #get the ipython shell object
        """ this works but is not needed now
        ip = ipapi.get()
        arg_str = 'run -d -b %s %s'%(self.pydebug_path,self.child_path)
        ip.user_ns['go'] = arg_str
        _logger.debug('about to use "%s" to start ipython debugger\n'%(arg_str))
        """
        self.feed_virtual_terminal(0,'go\n')

    def set_ipython_traceback(self):
        pass
        """
        tb = self.debug_dict['traceback']
        ip = IPython.ipapi.get()
        ipmagic = ip.user_ns['ipmagic']
        ipmagic('xmode ' + tb)
        """

    def find_import(self,fn):
        _logger.debug('find_import in file %s'%fn)
        try_fn = os.path.join(self.child_path,fn)
        if not os.path.isfile(try_fn):
            try_fn += '.py'
            if not os.path.isfile(try_fn):
                _logger.debug('in find_import, failed to find file %s'%try_fn)
                return

            line_no = 0
            for line in open(try_fn,'r'):
                if line.startswith('import'):
                    return line_no, try_fn

                line_no += 1

            return -1, None

    def _get_child_canvas(self):
        fr = Gtk.Frame()
        label = Gtk.Label("This page will be replaced with the \noutput from your program")
        label.show()
        fr.add(label)
        fr.show()

        return fr

    def _get_help_canvas(self):
        fr = Gtk.Frame()
        label = Gtk.Label(_("Loading Help Page"))
        label.show()
        fr.add(label)
        fr.show()

        return fr

    def get_icon_pixbuf(self, stock):
        return self.treeview.render_icon(stock_id=getattr(Gtk, stock), size=Gtk.IconSize.MENU, detail=None)

    def _child_cb(self,event):
        pass

    def _project_cb(self,event):
        pass

    #lots of state to change whenever one of the major tabs is clicked
    def set_visible_canvas(self,index): #track the toolbox tab clicks
        self.pydebug_notebook.set_current_page(index)
        if index == self.panes['TERMINAL']:
            self.set_terminal_focus()
            self.editor.save_all()
        elif index == self.panes['HELP']:
            self.help_selected()
        self.current_pd_page = index

    def _toolbar_changed_cb(self,widget,tab_no):
        _logger.debug('tool tab changed notification %d'%tab_no)
        self.set_visible_canvas(tab_no)

    def set_toolbar(self,page_no):
        self.toolbox.set_current_toolbar(page_no)

    def key_press_cb(self,widget,event):
        state = event.get_state()
        if state and Gdk.ModifierType.SHIFT_MASK and Gdk.ModifierType.CONTROL_MASK and Gk.ModifierType.MOD1_MASK == 0:
            self.file_changed = True
            #put a star in front of the filename

        return False
    
    ###   following routines are copied from develop_app for use with sourceview_editor 
    def _replace_cb(self, button=None):
        ftext = self._search_entry.props.text
        rtext = self._replace_entry.props.text
        _logger.debug('replace %s with %s usiing options %r'%(ftext,rtext,self.s_opts))
        replaced, found = self.editor.replace(ftext, rtext, self.s_opts)
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
                if self.editor.find_next(text, SearchOptions(self.s_opts, stay=True,
                    where=(self.s_opts.where if self.s_opts.where != S_WHERE.multifile else S_WHERE.file))):
                    #no multifile, or focus gets grabbed
                    self._replace_button.set_sensitive(True)

    def _replace_entry_changed_cb(self, entry):
        if self._replace_entry.props.text:
            self.safe_to_replace = True

    def _findprev_cb(self, button=None):
        ftext = self._search_entry.props.text
        if ftext:
            if self.editor.find_next(ftext, SearchOptions(self.s_opts, forward=False)):
                self._replace_button.set_sensitive(True)

    def _findnext_cb(self, button=None):
        ftext = self._search_entry.props.text
        _logger.debug('find next %s'%ftext)
        if ftext:
            if self.editor.find_next(ftext, self.s_opts):
                self._replace_button.set_sensitive(True)

            self.editor.set_focus()

    def show_find(self,button):
        self.find_window = self.wTree.get_widget("find")
        self.find_window.show()
        self.find_window.connect('destroy',self.close_find_window)
        self.find_connect()
        self.find_window.set_title(_('FIND OR REPLACE'))
        self.find_window.set_size_request(400, 200)
        self.find_window.set_decorated(True)
        self.find_window.set_resizable(True)
        self.find_window.set_modal(False)
        self.find_window.set_border_width(10)

    def find_connect(self):
        mdict = {
            'find_close_clicked_cb':self.close_find_window,
            'find_entry_changed_cb':self.find_entry_changed_cb,
            'replace_entry_changed_cb':self.replace_entry_changed_cb,
            'find_previous_clicked_cb':self._findprev_cb,
            'find_next_clicked_cb':self._findnext_cb,
            'find_entry_changed_cb':self._search_entry_changed_cb,
            'replace_entry_changed_cb':self._replace_entry_changed_cb,
            'replace_clicked_cb':self._replace_cb,
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

    def delete_event(self,widget,event):
        if widget == self.find_window:
            self.find_window.hide()

        return True
    
    def find_entry_changed_cb(self,button):
        #self.editor.search_for = 
        pass

    def replace_entry_changed_cb(self,button):
        #self.editor.search_for = 
        pass

    def project_run_cb(self,button):
        _logger.debug('entered project_run_cb')
        self.start_debugging()

    def __keep_clicked_cb(self, button):
        self.save_icon_clicked = True
        self.copy()

    ######  SUGAR defined read and write routines -- do not let them overwrite what's on disk
    def read_file(self, file_path):
        """
        If the ds_object passed to PyDebug is the last one saved, then just assume that the playpen is valid.
        If the ds_object is not the most recent one,  try to load the playpen with the contents referenced
        """
        #keep our own copy of the selected metadata
        self.activity_dict = self.metadata.copy()
        debugstr = ''
        for key in self.activity_dict.keys():
            debugstr += key + ':'+str(self.activity_dict[key]) + ', '

        _logger.debug ('In read_file: activity dictionary==> %s'%debugstr)
        self.get_config()
        if self.debug_dict.get('jobject_id','XxXxXx') == self.activity_dict.get('uid') and self.debug_dict.has_key('git_head') and not self.debug_dict['git_head']:
            #this is the most recent but if not git_head it has been overwritten by earlier version -- restore
            os.chdir(self.activity_dict['git_home'])
            cmd = 'git checkout master'
            git_output = self.command_line(cmd)
            if git_output:
                self.debug_dict['git_head'] = True
                fullpath = self.activity_dict.get('git_home','')
                if not fullpath == '':
                    os.chdir(fullpath)
                    self.load_activity_to_playpen(fullpath)

            os.chdir(self.child_path)

        else:
            _logger.debug('RELOADING ACTIVITY from earlier saved copy ...Object_id:%s. File_path:%s.'%(self.metadata['object_id'],file_path))
            if not self.activity_dict.get('git_id') == '':
                self.debug_dict['git_head'] = False
                os.chdir(self.activity_dict.get('git_home'))
                cmd = 'git checkout %s'%self.activity_dict.get('git_id')
                git_output = self.command_line(cmd)
                if git_output:
                    self.load_activity_to_playpen(self.activity_dict.get('git_home'))
                os.chdir(self.child_path)

            else:
                self.try_to_load_from_journal(self.activity_dict.get('uid'))

    def write_file(self, file_path):
        """
        The paradigm designed into the XO, ie an automatic load from the Journal at activity startup
        does not make sense during a debugging session.  An errant stack overflow can easily crash
        the system and require a reboot.  For the session manager to overwrite the changes that are stored
        on disk, but not yet saved in the journal is highly undesireable. So we'll let the user save to
        the journal, and perhaps optionally to the sd card (because it is removable, should the system die)
        """
        if self.save_icon_clicked == True: #this was a specific request to save a commit to git
            self.save_icon_clicked = False
            _logger.debug('saving current playpen contents')
            alert = self.alert(_('Saving current Activity to Home Directory'))
            self.to_home_clicked_cb(None) #copies playpen and sets self._to_home_dest
            if alert: self.remove_alert(alert)
            alert = self.alert(_('Copying changes to GIT repository'))
            git_id = self.do_git_commit(self._to_home_dest)
            if alert: self.remove_alert(alert)

            if git_id:
                self.alert(_('GIT commit successful. ID:%s')%git_id)
                self._jobject.metadata['commit_id'] = git_id
                self._jobject.metadata['git_home'] = self._to_home_dest
                today = datetime.date.today()
                self._jobject.metadata['title'] = self.activity_dict['name'] +' GIT-'+ git_id #self.activity_dict.get('commit_text',today)
                datastore.write(self._jobject)
                self._jobject.destroy()
                #get a new dsobject
                self.debug_dict['jobject_id'] = self.get_new_dsobject()
                self._jobject = self.debug_dict['jobject_id']

        jid = self.debug_dict.get('jobject_id','')
        _logger.debug('write file object_id: %s'%jid)
        chunk = self.debug_dict.get('name')
        self._jobject.metadata['title'] = 'PyDebug' + chunk
        self._jobject.metadata['activity'] = 'org.laptop.PyDebug'
        self._jobject.metadata['activity_id'] = self.handle.activity_id
        datastore.write(self._jobject)
        self.write_activity_info()
        self.put_config()
        return
        
    def do_git_commit(self, tree):
        """ First check the status of the source tree, if it is modified, do a commit, and store the
        commit id in the metadata.
        Input: path of the source tree
        Returns: Commit id or None if there is an error
        """
        os.chdir(tree)
        if not os.path.isdir(os.path.join(tree,'.git')):
            cmd = 'git init'
            cmd_output = self.command_line(cmd, alert_error=False)
            cmd = 'git add *'
            cmd_output = self.command_line(cmd, alert_error=False)

        cmd = 'git status'
        cmd_output = self.command_line(cmd, alert_error=False)
        do_commit = False

        if cmd_output:
            for line in cmd_output.split('\n'):
                if line.find('modified') > -1: do_commit = True
                if line.find('new file:') > -1: do_commit = True

        if not do_commit:
            _logger.debug('git did not commit because no unmodified files were detected')
            return  None #there have been no changes to write to library

        today = datetime.date.today()
        commit_message = self.activity_dict.get('commit_text',today)
        cmd = 'git commit -a -m "%s"'%commit_message
        cmd_output = self.command_line(cmd)
        git_id = None
        if not cmd_output:
            _logger.debug('git commit returned no response')
            return None
        _logger.debug('git commit response:%s'%cmd_output)
        for line in cmd_output.split('\n'):
            chunks = line.split()
            if len(chunks) < 2: continue
            if chunks[0] == '[master':
                if chunks[1][:-1] == ']':
                    git_id = chunks[1][:-1]
                if len(chunks) < 3: continue
                if chunks[2][:-1] == ']':
                    git_id = chunks[2][:-1]
        if not git_id: return None
        self.activity_dict['git_id'] = git_id
        return git_id
    
    def write_binary_to_datastore(self):
        """
        Check to see if there is a child loaded.
        Then copy the home directory data for this application into the bundle
        then bundle it up and write it to the journal
        lastly serialize the project information and write it to the journal
        """
        _logger.debug('Entered write_binary_to_datastore with child_path:%s'%self.child_path)
        if not (os.path.isdir(self.child_path) and self.child_path.split('.')[-1:][0] == 'activity'):
            self.alert(_('No Program loaded'))
            return

        dsobject = datastore.create()
        dsobject.metadata['mime_type'] = 'binary'
        
        #copy the home directory config stuff into the bundle
        home_dir = os.path.join(self.child_path,'HOME')
        try:
            os.rmtree(home_dir)
        except:
            pass

        try:
            os.mkdir(home_dir)
        except:
            pass

        source = self.debugger_home
        dest = os.path.join(self.child_path,'HOME')
        _logger.debug('writing HOME info from %s to %s.'%(source,dest))
        for f in os.listdir(self.debugger_home):
            if f == '.':
                continue

            if f == '..':
                continue

            if f == 'pydebug':
                continue

            if f == '.sugar':
                continue

            try:
                if os.path.isdir(f):
                    shutil.copytree(f,dest)
                else:
                    shutil.copy(f,dest)
            except:
                pass

        #create the manifest for the bundle
        try:
            os.remove(os.path.join(self.child_path,'MANIFEST'))
        except:
            pass

        dest = self.child_path
        _logger.debug('Writing manifest to %s.'%(dest))
        config = bundlebuilder.Config(dest)
        b = bundlebuilder.Builder(config)

        try:
            b.fix_manifest()
        except:
            _logger.debug('fix manifest error: ',sys.exc_type,sys.exc_info[0],sys.exc_info[1])

        #actually write the xo file
        packager = bundlebuilder.XOPackager(bundlebuilder.Builder(config))
        packager.package()
        source = os.path.join(self.child_path,'dist',str(config.xo_name))
        dest = os.path.join(self.get_activity_root(),'instance',str(config.xo_name))
        _logger.debug('writing to the journal from %s to %s.'%(source,dest))

        try:
            shutil.copy(source,dest)
        except IOError:
            _logger.debug('shutil.copy error %d: %s. ',IOError[0],IOError[1])

        dsobject.metadata['package'] = config.xo_name
        dsobject.metadata['title'] = config.xo_name  #_('PyDebug Zipped app')
        dsobject.metadata['mime_type'] = 'binary'
        dsobject.metadata['activity'] = 'org.laptop.PyDebug'
        dsobject.metadata['icon'] = self.debug_dict.get('icon','')
        #calculate and store the new md5sum
        self.debug_dict['tree_md5'] = self.md5sum_tree(self.child_path)
        dsobject.metadata['tree_md5'] = self.debug_dict['tree_md5']
        dsobject.set_file_path(dest)
        
        #actually make the call which writes to the journal
        datastore.write(dsobject,transfer_ownership=True)
        _logger.debug('succesfully wrote to the journal from %s.'%(dest))
        #update the project display
        self.journal_class = DataStoreTree(self,self.journal_treeview,self.wTree)

    def load_activity_to_playpen(self,file_path):
        """loads from a disk tree"""
        self._new_child_path =  os.path.join(self.activity_playpen,os.path.basename(file_path))
        _logger.debug('copying file for %s to %s'%(file_path,self._new_child_path))
        self._load_playpen(file_path)

    def try_to_load_from_journal(self,object_id):
        """
        loads a zipped XO application file,  asks whether it is ok to
        delete/overwrite path if the md5 has changed.
        """
        self.ds = datastore.get(object_id[0])
        if not self.ds:
            _logger.debug('failed to get datastore object with id:%s'%object_id[0])
            return

        dsdict=self.ds.get_metadata()
        file_name_from_ds = self.ds.get_file_path()
        project = dsdict.get('package','')
        if not project.endswith('.xo'):
            self.alert(_('This journal item does not appear to be a zipped activity. Package:%s.'%project))
            self.ds.destroy()
            self.ds = None

            return

        filestat = os.stat(file_name_from_ds)
        size = filestat.st_size

        _logger.debug('In try_to_load_from_journal. Object_id %s. File_path %s. Size:%s'%(object_id[0], file_name_from_ds, size))

        try:
            self._bundler = ActivityBundle(file_name_from_ds)
        except:
            self.alert('Error:  Malformed Activity Bundle')
            self.ds.destroy()
            self.ds = None

            return

        self._new_child_path = os.path.join(self.activity_playpen,self._bundler.get_name()+'.activity')
        self._load_playpen(file_name_from_ds, iszip=True)
        
    def _load_playpen(self,source_fn, iszip = False):
        """entry point for both xo and file tree sources"""
        self.iszip = iszip
        self._load_to_playpen_source = source_fn

        if self.child_path and os.path.isdir(self.child_path):
            #check to see if it has been modified
            stored_hash = self.debug_dict.get('tree_md5','')
            if stored_hash != '' and stored_hash != self.md5sum_tree(self.child_path):
                self.confirmation_alert(_('The currently loaded %s project in the playpen has been changed.'%os.path.basename(self.child_path)),_('Ok to abandon changes?'),self._clear_playpen_cb)
                return

        self._clear_playpen_cb(None,None)

    def _clear_playpen_cb(self,alert, response):
        #if necessary clean up contents of playpen
        if alert != None:
            self.remove_alert(alert)

        if self.child_path and os.path.isdir(self.child_path):
            self.abandon_changes = True
            self.debug_dict['tree_md5'] = ''
            self.debug_dict['child_path'] = ''
            self.editor.remove_all()

            if self.child_path:
                shutil.rmtree(self.child_path)

            self.abandon_changes = False

        if self._load_to_playpen_source == None:
            #having done the clearing, just stop
            return

        if self.iszip:
            self._bundler.install(self.activity_playpen)
            if self.ds: self.ds.destroy()
            self.ds = None

        else:
            
            if self.activity_playpen[-1] == '/':
                dest = self.activity_playpen[:-1]

            else:
                dest = self.activity_playpen

            os.chdir(self._load_to_playpen_source)
            cmd = 'rsync -av %s %s'%(self._load_to_playpen_source,self.activity_playpen)
            output = self.command_line(cmd)
            if not output:
                return
        self.debug_dict['source_tree'] = self._load_to_playpen_source
        self.child_path = self._new_child_path
        self.setup_new_activity()

    def  setup_new_activity(self):
        _logger.debug('in setup_new_activity. child path before chdir:%s'%self.child_path)
        if self.child_path == None:
            return
        os.chdir(self.child_path)
        self.read_activity_info(self.child_path)
        self.display_current_project()

        #add the bin directory to path
        os.environ['PATH'] = os.path.join(self.child_path,'bin') + ':' + os.environ['PATH']

        #calculate and store the md5sum
        self.debug_dict['tree_md5'] = self.md5sum_tree(self.child_path)

        #find largest python files for editor
        list = [f for f in os.listdir(self.child_path) if f[0] <> '.']
        #list = self.manifest_class.get_filenames_list(self.child_path)
        if not list: return
        sizes = []

        for f in list:
            full_path = os.path.join(self.child_path,f)
            if not f.endswith('.py'):continue
            size = self.manifest_class.file_size(full_path)
            sizes.append((size,full_path,))
            #_logger.debug('python file "%s size %d'%(f,size))

        for s,f in sorted(sizes,reverse=True)[:5]:
            self.editor.load_object(f,os.path.basename(f)) 

        self.editor.set_current_page(0)
        
    #####################            ALERT ROUTINES   ##################################
    def alert(self,msg,title=None):
        alert = NotifyAlert(10)

        if title != None:
            alert.props.title=_('There is no Activity file')

        alert.props.msg = msg
        alert.connect('response',self.no_file_cb)
        self.add_alert(alert)
        return alert
        
    def no_file_cb(self,alert,response_id):
        self.remove_alert(alert)

    def confirmation_alert(self,msg,title=None,confirmation_cb = None):
        alert = ConfirmationAlert()
        alert.props.title=title
        alert.props.msg = msg
        alert.pydebug_cb = confirmation_cb
        alert.connect('response', self._alert_response_cb)
        self.add_alert(alert)

    #### Method: _alert_response_cb, called when an alert object throws a
                 #response event.
    def _alert_response_cb(self, alert, response_id):
        #remove the alert from the screen, since either a response button
        #was clicked or there was a timeout
        this_alert = alert  #keep a reference to it
        self.remove_alert(alert)
        #Do any work that is specific to the type of button clicked.
        if response_id is Gtk.ResponseType.OK and this_alert.pydebug_cb != None:
            this_alert.pydebug_cb (this_alert, response_id)

    def _read_file_cb(self,widget):
        _logger.debug('Reading a file into editor')
        dialog = Gtk.FileChooserDialog("Open..", None,
                                       Gtk.FileChooserAction.OPEN,
                                       (Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL,
                                        Gtk.STOCK_OPEN, Gtk.ResponseType.OK))

        dialog.set_default_response(Gtk.ResponseType.OK)
        if self.last_filename == None:
            self.last_filename = self.child_path

        dialog.set_current_folder(os.path.dirname(self.last_filename))

        filter = Gtk.FileFilter()
        filter.set_name("All files")
        filter.add_pattern("*")
        dialog.add_filter(filter)

        filter = Gtk.FileFilter()
        filter.set_name("Python")
        filter.add_pattern("*.py")
        dialog.add_filter(filter)

        filter = Gtk.FileFilter()
        filter.set_name("Activity")
        filter.add_pattern("*.xo")
        dialog.add_filter(filter)
        
        response = dialog.run()
        if response == Gtk.ResponseType.OK:
            _logger.debug(dialog.get_filename(), 'selected')
            fname = dialog.get_filename()
            self.last_filename = fname
            self.editor.load_object(fname,os.path.basename(fname))

        elif response == Gtk.ResponseType.CANCEL:
            _logger.debug( 'File chooseer closed, no files selected')

        dialog.destroy()

    def save_file_cb(self, button):
        chooser = Gtk.FileChooserDialog(title=None, action=Gtk.FileChooserAction.OPEN,
                                        buttons=(Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL,
                                                 Gtk.STOCK_SAVE, Gtk.ResponseType.OK))

        file_path = self.editor.get_full_path()
        _logger.debug('Saving file %s'%(file_path))
        chooser.set_filename(file_path)
        response = chooser.run()
        new_fn = chooser.get_filename()
        chooser.destroy()

        if response == Gtk.ResponseType.CANCEL:
            return

        if response == Gtk.ResponseType.OK:
            self.save_cb(None, new_fn)

    def save_cb(self,button,new_fn=None):
        if new_fn and not new_fn.startswith(self.child_root):
            msg = _('You can only write %{new_fn}s to subdirectories of %{child_root}s')
            args = {"new_fn":os.path.basename(new_fn) ,"child_root":self.child_root}
            self.alert(msg % args)
            return

        page = self.editor._get_page()

        if new_fn:
            page.fullPath = new_fn
            page.save(skip_md5 = True)

        else:
            page.save()

        self.editor.clear_changed_star()
        page.save_hash()
        
    def set_dirty(self, dirty):
        self.dirty = dirty

    def md5sum_buffer(self, buffer, hash = None):
        if hash == None:
            hash = hashlib.md5()

        hash.update(buffer)
        return hash.hexdigest()

    def md5sum(self, filename, hash = None):
        h = self._md5sum(filename,hash)
        return h.hexdigest()
       
    def _md5sum(self, filename, hash = None):
        if hash == None:
            hash = hashlib.md5()

        try:
            fd = None
            fd =  open(filename, 'rb')
            while True:
                block = fd.read(128)
                if not block: break
                hash.update(block)
        finally:
            if fd != None:
                fd.close()

        return hash
    
    def md5sum_tree(self,root):
        if not os.path.isdir(root):
            return None
        h = hashlib.md5()
        for dirpath, dirnames, filenames in os.walk(root):
            for filename in filenames:
                abs_path = os.path.join(dirpath, filename)
                h = self._md5sum(abs_path,h)
                #print abs_path
        return h.hexdigest()

    ##############    Following code services the Project page   #####################
    def _get_project_canvas(self):
        self.project_win_toplevel = project_glade.toplevel()
        self.contents = self.project_win_toplevel.contents
        self.contents.unparent()

        return self.contents

    def setup_project_page(self):
        ## FIXME

        self.activity_treeview = self.project_win_toplevel.file_system
        ##self.activity_window = FileTree(self, self.activity_treeview,self.wTree)

        ##self.activity_window.set_file_sys_root('/home/olpc/Activities')

        self.examples_treeview = self.project_win_toplevel.examples
        ##self.examples_window = FileTree(self, self.examples_treeview,self.wTree)

        ##self.examples_window.set_file_sys_root(os.path.join(self.sugar_bundle_path,'examples'))

        self.journal_treeview = self.project_win_toplevel.journal
        ##self.journal_class = DataStoreTree(self,self.journal_treeview,self.wTree)
        ##self.connect_object()  #make connections to signals from buttons
        ##self.activity_toggled_cb(None)
        if self.child_path and self.child_path.endswith('.activity') and os.path.isdir(self.child_path):
            self.setup_new_activity()

        #get set to sense addition of a usb flash drive
        self.volume_monitor = Gio.VolumeMonitor.get()
        self.volume_monitor.connect('mount-added',self.__mount_added_cb)
        self.volume_monitor.connect('mount-removed',self.__mount_removed_cb)
        mount_list = self.volume_monitor.get_mounts()
        for m in mount_list:
            s = m.get_root().get_path()
            if s.startswith('/media'):_logger.debug('volume:%s', s)

    def __mount_added_cb(self, vm, mount):
        pass

    def __mount_removed_cb(self, vm, mount):
        pass

    def display_current_project(self):
        self.manifest_treeview = self.wTree.get_widget('manifest')
        self.manifest_class = FileTree(self, self.manifest_treeview,self.wTree)

        if self.child_path:
            self.manifest_class.set_file_sys_root(self.child_path)

        else:
            self.manifest_class.set_file_sys_root(self.activity_playpen)
        
        self.wTree.get_widget('name').set_text(self.activity_dict.get('name',''))        
        self.wTree.get_widget('version').set_text(self.activity_dict.get('version',''))
        self.wTree.get_widget('bundle_id').set_text(self.activity_dict.get('bundle_id',''))
        self.wTree.get_widget('class').set_text(self.activity_dict.get('class',''))
        self.wTree.get_widget('module').set_text(self.activity_dict.get('module',''))

    def manifest_point_to(self,fullpath):
        if self.child_path:
            self.manifest_class.set_file_sys_root(self.child_path)

        else:
            self.manifest_class.set_file_sys_root(self.activity_playpen)

        self.manifest_class.position_to(fullpath)

    #first connect the glade xml file to the servicing call backs
    def connect_object(self,  wTree=None):
        """if wTree:
            self.wTree=wTree
        if self.wTree:"""
        mdict = {
            'name_changed_cb':self.name_changed_cb,
            'bundle_id_changed_cb':self.bundle_id_changed_cb,
            'class_changed_cb':self.class_changed_cb,
            'icon_changed_cb':self.icon_changed_cb,
            'version_changed_cb':self.version_changed_cb,
            'file_toggle_clicked_cb':self.activity_toggled_cb,
            'to_activities_clicked_cb':self.to_home_clicked_cb,
            'from_activities_clicked_cb':self.from_home_clicked_cb,
            'from_examples_clicked_cb':self.from_examples_clicked_cb,
            'run_clicked_cb':self.project_run_cb,
            'delete_file_clicked_cb':self.delete_file_cb,
        }

        self.wTree.signal_autoconnect(mdict)
        button = self.wTree.get_widget('file_toggle')
        button.set_tooltip_text(_('Switch views between the "Installed" Activities directory and your "home" storage directory'))
        button = self.wTree.get_widget('to_activities')
        button.set_tooltip_text(_('Copy the files in the debug workplace to your "home" storage directory'))
        button = self.wTree.get_widget('from_examples')
        button.set_tooltip_text(_('Load and modify these example programs. See the help Tutorials'))

    def name_changed_cb(self, widget):
        self.activity_dict['name'] = widget.get_text()
        
    def bundle_id_changed_cb(self,widget):
        self.activity_dict['bundle_id'] = widget.get_text()
        
    def class_changed_cb(self, widget): 
        self.activity_dict['class'] = widget.get_text()
     
    def icon_changed_cb(self, widget):
        self.activity_dict['icon'] = widget.get_text()
        
    def version_changed_cb(self, widget):
        self.activity_dict['version'] = widget.get_text()
        
    def name_changed_cb(self, widget):
        self.activity_dict['name'] = widget.get_text()
        
    def commit_changed_cb(self, widget):
        self.activity_dict['commit_text'] = widget.get_text()
        
    def volume_drop_changed_cb(self, widget):
        self.activity_dict['name'] = widget.get_text()
        
    def volume_save_cb(self, widget):
        self.activity_dict['save'] = widget.get_text()
                
    def activity_toggled_cb(self, widget):
        _logger.debug('Entered activity_toggled_cb. Button: %r'%self.file_pane_is_activities)
        but = self.wTree.get_widget('to_activities')
        to_what = self.wTree.get_widget('file_toggle')
        window_label = self.wTree.get_widget('file_system_label')
        if self.file_pane_is_activities == True:
            to_what.set_label('Installed')
            but.show()
            display_label = self.storage[:18]+' . . . '+self.storage[-24:]
            self.activity_window.set_file_sys_root(self.storage)
            button = self.wTree.get_widget('from_activities')
            button.set_tooltip_text(_('Copy the selected directory  from your "home" storage to the debug workplace'))
            window_label.set_text(display_label)

        else:
            to_what.set_label('home')
            but.hide()
            self.activity_window.set_file_sys_root('/home/olpc/Activities')  ## FIXME
            button = self.wTree.get_widget('from_activities')
            button.set_tooltip_text(_('Copy the selected Activity to the debug workplace and start debugging'))
            window_label.set_text('/home/olpc/Activities')

        self.file_pane_is_activities =  not self.file_pane_is_activities
    
    def to_home_clicked_cb(self,widget):
        _logger.debug('Entered to_home_clicked_cb')
        self._to_home_dest = os.path.join(self.storage,self.activity_dict['name']+'.activity')
        if os.path.isdir(self._to_home_dest):
            target_md5sum = self.md5sum_tree(self._to_home_dest)
            if target_md5sum != self.debug_dict.get('tree_md5',''):
                self.confirmation_alert(_('OK to delete/overwrite %s?'%self._to_home_dest), _('This destination has been changed by another application'), self._to_home_cb)

            return

        self._to_home_cb(None, Gtk.ResponseType.OK)

    def _to_home_cb(self, alert, response_id):
        if alert != None:
            self.remove_alert(alert)

        if response_id is Gtk.ResponseType.OK:
            cmd = ['rsync','-av', self.child_path + '/', self._to_home_dest]
            _logger.debug('do to_home_cb with cmd:%s'%cmd)
            p1 = Popen(cmd,stdout=PIPE)
            output = p1.communicate()

            if p1.returncode != 0:
                self.alert('rsync command returned non zero\n'+output[0]+ 'COPY FAILURE')
                return

            #redraw the treeview
            self.activity_window.set_file_sys_root(self.storage)

    def from_home_clicked_cb(self,widget):
        _logger.debug('Entered from_home_clicked_cb')
        selection=self.activity_treeview.get_selection()
        (model, iter) = selection.get_selected()

        if iter == None:
            self.alert(_('Must select File or Directory item to Load'))
            return

        fullpath = model.get(iter,4)[0]
        if os.path.isdir(fullpath):
            if not fullpath.endswith('.activity'):
                self.alert(_('Use this button for Activities or Files'), _('ERROR: This folder name does not end with ".activity"'))
                return

            self.load_activity_to_playpen(fullpath)

        else:
            #selected is a file, just copy it into the current project
            basename = os.path.basename(fullpath)
            if os.path.isfile(os.path.join(self.child_path, basename)):
                #change name if necessary to prevent collision 
                basename = self.non_conflicting(self.child_path,basename)

            shutil.copy(fullpath,os.path.join(self.child_path,basename))
            self.manifest_point_to(os.path.join(self.child_path,basename))
            
    def non_conflicting(self,root,basename):
        """
        create a non-conflicting filename by adding '-<number>' to a filename before extension
        """
        ext = ''
        basename = basename.split('.')
        word = basename[0]
        if len(basename) > 1:
            ext = basename[1]

        adder = ''
        index = 0
        while os.path.isfile(os.path.join(root, word + adder + '.' + ext)):
            index +=1
            adder = '-%s'%index

        return os.path.join(root, word + adder + '.' + ext)
    
    def from_examples_clicked_cb(self,widget):
        _logger.debug('Entered from_examples_clicked_cb')
        selection=self.examples_treeview.get_selection()
        (model,iter)=selection.get_selected()
        if iter == None:
            self.alert(_('Must select File or Directory item to Load'))
            return

        fullpath = model.get(iter,4)[0]
        if fullpath.endswith('.activity'):
            self.load_activity_to_playpen(fullpath)
            return

        self._load_to_playpen_source = fullpath

        try:
            self._bundler = ActivityBundle(fullpath)
        except:
            self.alert('Error:  Malformed Activity Bundle')
            return

        self._new_child_path = os.path.join(self.activity_playpen,self._bundler._zip_root_dir)
        #check to see if current activity in playpen needs to be saved, and load new activity if save is ok
        self._load_playpen(fullpath, iszip=True)
   
    def filetree_activated(self):
        _logger.debug('entered pydebug filetree_activated')
    
    def read_activity_info(self, path):
        try:
            bundle = ActivityBundle(path)
        except:
            msg = _('%s not recognized by ActivityBundle parser. Does activity/activity.info exist?' % os.path.basename(path))
            self.alert(msg)
            return  #maybe should issue an alert here

        self.activity_dict['version'] = str(bundle.get_activity_version())
        self.activity_dict['name'] = bundle.get_name()
        self.activity_dict['bundle_id'] = bundle.get_bundle_id()
        self.activity_dict['command'] = bundle.get_command()
        cmd_args = activityfactory.get_command(bundle)
        mod_class = cmd_args[1]

        if '.' in mod_class:
            self.activity_dict['class'] = mod_class.split('.')[1]
            self.activity_dict['module'] = mod_class.split('.')[0]

        self.activity_dict['icon'] = bundle.get_icon()

    def write_activity_info(self):
        #write the activity.info file
        _logger.debug('entered write_actiity_info')
        if self.child_path == None:
            return

        filen = os.path.join(self.child_path,'activity','activity.info')
        with open(filen,'r') as fd:
            #and also write to a new file
            filewr = os.path.join(self.child_path,'activity','activity.new')
            with open(filewr,'w') as fdw:
                #write the required lines
                _logger.debug('writing activity info to %s'%filewr)
                fdw.write('[Activity]\n')
                fdw.write('name = %s\n'%self.activity_dict.get('name'))
                fdw.write('bundle_id = %s\n'%self.activity_dict.get('bundle_id'))
                fdw.write('activity_version = %s\n'%self.activity_dict.get('version'))
                icon = self.activity_dict.get('icon')[len(self.child_path)+10:-4]
                fdw.write('icon = %s\n'%icon)

                if self.activity_dict.get('class','') == '':
                    fdw.write('exec = %s\n'%self.activity_dict.get('module'))
                else:
                    fdw.write('class = %s.%s\n'%(self.activity_dict.get('module'),
                                                    self.activity_dict.get('class')))                       
                #pass the rest of the input to the output
                passup = ('[activity]','exec','activity_version','name','bundle_id',
                            'service_name','icon','class')
                for line in  fd.readlines():
                    tokens = line.split('=')
                    keyword = tokens[0].lower().rstrip()
                    if keyword in passup: continue
                    fdw.write(line)

    def delete_file_cb(self,widget):
        selection = self.manifest_treeview.get_selection()
        (model, iter) = selection.get_selected()

        if iter == None:
            self.alert(_('Must select File delete'))
            return

        fullpath = model.get(iter,4)[0]
        _logger.debug(' delete_file_clicked_cb. File: %s'%os.path.basename(fullpath))
        self.delete_file_storage = fullpath

        if os.path.isdir(fullpath):
            self.alert(_('Use the terminal "rm -rf <directory> --CAREFULLY','Cannot delete Folders!'))
            return

        self.confirmation_alert(_('Would you like to continue deleting %s?' % os.path.basename(fullpath)), _('ABOUT TO DELETE A FILE!!'),self.do_delete)

    def do_delete(self, alert, response):
        _logger.debug('doing delete of: %s'%self.delete_file_storage)
        self.manifest_point_to(self.delete_file_storage)
        os.unlink(self.delete_file_storage)
        self.manifest_class.set_file_sys_root(self.child_path)
        self.manifest_class.position_recent()

    ################  Help routines
    def help_selected(self):
        """
        if help is not created in a gtk.mainwindow then create it
        else just switch to that viewport
        """
        if not self.help_x11:
            self.window_instance = self.window.window
            self.help_x11 = self.help.realize_help()
            #self.x11_window = self.get_x11()os.geteuid()

        else:
            self.help.activate_help()
            #self.help.reshow()
            #self.help.toolbox.set_current_page(self.panes['HELP']

    ################  save config state from one invocation to another -- not activity state
    def get_config(self):
        try:
            fd = open(os.path.join(self.debugger_home,'pickl'),'rb')
            local = pickle.load(fd)
            self.debug_dict = local.copy()
            _logger.debug('unpickled successfully')
            """
            object_id = self.debug_dict.get('jobject_id','')
            if object_id != '':
                self._jobject = datastore.get(object_id)
            else:
                self._jobject = None
            """

        except:
            try:
                fd = open(os.path.join(self.debugger_home,'pickl'),'wb')
                self.debug_dict['host'] = 'localhost'
                self.debug_dict['port'] = 18812
                self.debug_dict['autosave'] = True
                self.debug_dict['child_path'] = ''
                local = self.debug_dict.copy()
                pickle.dump(local,fd,pickle.HIGHEST_PROTOCOL)

            except IOError:
                _logger.debug('get_config -- Error writing pickle file %s' % os.path.join(self.debugger_home,'pickl'))
        finally:
            fd.close()

        object_id = self.debug_dict.get('jobject_id','')
        if object_id == '':
            jobject = self.get_new_dsobject()
            self._jobject = jobject
            self.debug_dict['jobject_id'] = str(self._jobject.object_id)
            _logger.debug('in get_config created jobject id:%s'%self.debug_dict['jobject_id'])

        else:
            pass

            #self._jobject = datastore.get(object_id)
        self.child_path = self.debug_dict.get('child_path','')
        if self.child_path == '' or not os.path.isdir(self.child_path):
            self.child_path = None
    
        debugstr = ''
        for key in self.debug_dict.keys():
            debugstr += key + ':'+str(self.debug_dict[key]) + ', '
        _logger.debug ('In get_config: debug dictionary==> %s'%debugstr)
        
    def get_new_dsobject(self):
        jobject = datastore.create()
        jobject.metadata['title'] = 'PyDebug'
        jobject.metadata['activity'] = 'org.laptop.PyDebug'
        jobject.metadata['keep'] = '1'
        jobject.metadata['preview'] = ''
        datastore.write(jobject)
        return jobject

    def check_child_md5(self):    
        if self.child_path and self.debug_dict.get('tree_md5',''):
            if self.debug_dict.get('tree_md5','') == self.md5sum_tree(self.child_path):
                self.setup_new_activity()
                #the tree is valid so take up where we left off

            else:
                self.confirmation_alert(_('Continue even though stored checksum does not match current checksum'), _('CAUTION: The program in the playpen may have been changed.'), self.startup_continue)

    def startup_continue(self,alert,response):
        self.setup_new_activity()

    def put_config(self):
        if self.child_path:
            self.debug_dict['tree_md5'] = self.md5sum_tree(self.child_path)
            self.debug_dict['child_path'] = self.child_path 

        try:
            fd = open(os.path.join(self.debugger_home,'pickl'),'wb')
            local = self.debug_dict.copy()
            pickle.dump(local,fd,pickle.HIGHEST_PROTOCOL)

        except IOError:
            _logger.debug('put_config routine Error writing pickle file %s' % os.path.join(self.debugger_home,'pickl'))
            return

        finally:
            fd.close()

        debugstr = ''
        return  ## WTF?

        for key in self.debug_dict.keys():
            debugstr += key + ':'+str(self.debug_dict[key]) + ', '

        _logger.debug ('In put_config: debug dictionary==> %s'%debugstr)

