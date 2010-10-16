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
import os, os.path, ConfigParser, shutil, sys
from subprocess import Popen, PIPE

from gettext import gettext as _

#major packages
import gtk
import gtk.glade
import vte
import pango
#import gconf
#import glib
import pickle
import hashlib
import time
#import gio
import datetime
import gobject

#sugar stuff
from sugar.graphics.toolbutton import ToolButton
import sugar.graphics.toolbutton

import sugar.env
from sugar.graphics.xocolor import XoColor
from sugar.graphics.icon import Icon
from sugar.graphics.objectchooser import ObjectChooser
from sugar.datastore import datastore
from sugar.graphics.alert import *
import sugar.activity.bundlebuilder as bundlebuilder
from sugar.bundle.activitybundle import ActivityBundle
from sugar.activity import activityfactory
#following only works in sugar 0.82
#from sugar.activity.registry import get_registry
from sugar.activity.activity import Activity
from sugar import profile

#application stuff
from terminal_pd import Terminal

#public api for ipython
from IPython.core import ipapi #0.11 requires this
#changes to debugger.py line 508, magic.py:1567
#import IPython.ipapi

import sourceview_editor
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
from IPython.frontend.terminal.embed import InteractiveShellEmbed

import logging
from  pydebug_logging import _logger, log_environment

MASKED_ENVIRONMENT = [
    'DBUS_SESSION_BUS_ADDRESS',
    'PPID'
]
#PANES = ['TERMINAL','EDITOR','CHILD','PROJECT','HELP']
PANES = ['TERMINAL','EDITOR','PROJECT','HELP']

#colors for the playpen side of the project page
PROJECT_FG = '#990000'
PROJECT_BASE = "#fdd99b"
PROJECT_BG = '#FFFFCC'

#global module variable communicates to debugged programs
pydebug_instance = None
start_clock = 0

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
    #ipshell = IPShellEmbed()
    MIME_TYPE = 'application/vnd.olpc-sugar'
    DEPRECATED_MIME_TYPE = 'application/vnd.olpc-x-sugar'
    _zipped_extension = '.xo'
    _unzipped_extension = '.activity'
    dirty = False
    #global start_clock
    
    def __init__(self, handle):
        #handle object contains command line inputs to this activity
        self.handle = handle
        _logger.debug('Activity id:%s.Object id: %s. uri:%s'%(handle.activity_id, 
                    handle.object_id, handle.uri))
        self.passed_in_ds_object = None
        if handle.object_id and handle.object_id != '':
            self.passed_in_ds_object = datastore.get(handle.object_id)
            debugstr = ''
            if self.passed_in_ds_object:
                d = self.passed_in_ds_object.metadata
                #self.log_dict(d,'initial datastore metadata ==>:')
            self.request_new_jobject = False
        else:
            self.request_new_jobject = True
            _logger.debug('no initial datastore object id passed in via handle')

        #Save a global poiinter so remote procedure calls can communicate with pydebug
        global pydebug_instance
        pydebug_instance = self
        start_clock = time.clock()

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
        self.manifest_class = None
        #self.set_title(_('PyDebug Activity'))
        self.ds = None #datastore pointer
        self._logger = _logger
        self.traceback = 'Context'
        self.abandon_changes = False
        self.journal_class = None
        self.delete_after_load = None
        self.find_window = None
        self.icon_outline = 'icon_square'
        self.icon_window = None
        self.last_icon_file = None
        self.activity_data_changed = False
        self.ignore_changes = True #disable the change callbacks on the activity.info panel
        self.icon_basename = None
        
        #sugar 0.82 has a different way of getting colors and dies during init unless the following
        self.profile = profile.get_profile()
        self.profile.color = XoColor()
        
        #get the persistent data across all debug sessions
        self.get_config ()
        if self.request_new_jobject and self.debug_dict.get('jobject_id','') != '':
            self.request_new_jobject = False
            
        #keep on using the same journal entry
        if self.debug_dict.get('jobject_id','') != '':
            handle.object_id = self.debug_dict.get('jobject_id','')

        # init the Classes we are subclassing
        _logger.debug('about to init  superclass activity. Elapsed time: %f'%(time.clock()-start_clock))
        Activity.__init__(self, handle,  create_jobject = self.request_new_jobject)
        if self.request_new_jobject:
            #check to see if the object was created
            if self._jobject:
                self.debug_dict['jobject_id'] = str(self._jobject.object_id)
            else:
                _logger.debug('failed to create jobject in Activity.__init__')
        self.connect('realize',self.realize_cb)
        self.accelerator = gtk.AccelGroup()
        self.add_accel_group(self.accelerator)
        #Terminal has no needs for init
        #Help.__init__(self,self)
        
        # setup the search options
        self.s_opts = SearchOptions(where = S_WHERE.file,
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
        _logger.debug('about to set up Menu panes. Elapsed time: %f'%(time.clock()-start_clock))
        self.canvas_list = []
        self.panes = {}
        pane_index = 0
        pane_index =  self.new_pane(self._get_terminal_canvas,pane_index)         
        pane_index =  self.new_pane(self._get_edit_canvas,pane_index) 
        #pane_index =  self.new_pane(self._get_child_canvas,pane_index) 
        pane_index =  self.new_pane(self._get_project_canvas,pane_index) 
        pane_index =  self.new_pane(self._get_help_canvas,pane_index)
        
        nb = gtk.Notebook()
        nb.show()
        nb.set_show_tabs(False)
        
        for c in self.canvas_list:
            nb.append_page(c)
            
        self.pydebug_notebook = nb
        #the following call to the activity code puts our notebook under the stock toolbar
        self.set_canvas(nb)
                
        #set up tool box/menu buttons
        self.toolbox = pytoolbar.ActivityToolbox(self)
        self.toolbox.connect_after('current_toolbar_changed',self._toolbar_changed_cb)
        
        activity_toolbar = self.toolbox.get_activity_toolbar()
        #activity_toolbar.share.props.visible = True
        #activity_toolbar.keep.props.visible = True

        separator = gtk.SeparatorToolItem()
        separator.set_draw(True)
        separator.show()
        activity_toolbar.insert(separator, 0)
        
        activity_go = ToolButton()
        activity_go.set_stock_id('gtk-media-forward')
        activity_go.set_icon_widget(None)
        activity_go.set_tooltip(_('Start Debugging'))
        activity_go.connect('clicked', self.project_run_cb)
        activity_go.add_accelerator('clicked',self.accelerator,ord('O'),gtk.gdk.CONTROL_MASK,gtk.ACCEL_VISIBLE)
        #activity_go.props.accelerator = '<Ctrl>O'
        activity_go.show()
        activity_toolbar.insert(activity_go, 0)
        

        activity_copy_tb = ToolButton('edit-copy')
        activity_copy_tb.set_tooltip(_('Copy'))
        activity_copy_tb.connect('clicked', self._copy_cb)
        activity_toolbar.insert(activity_copy_tb, 3)
        activity_copy_tb.show()

        activity_paste_tb = ToolButton('edit-paste')
        activity_paste_tb.set_tooltip(_('Paste'))
        activity_paste_tb.connect('clicked', self._paste_cb)
        activity_paste_tb.add_accelerator('clicked',self.accelerator,ord('V'),gtk.gdk.CONTROL_MASK,gtk.ACCEL_VISIBLE)
        #activity_paste_tb.props.accelerator = '<Ctrl>V'
        activity_toolbar.insert(activity_paste_tb, 4)
        activity_paste_tb.show()

        activity_tab_tb = sugar.graphics.toolbutton.ToolButton('list-add')
        activity_tab_tb.set_tooltip(_("Open New Tab"))
        activity_tab_tb.add_accelerator('clicked',self.accelerator,ord('T'),gtk.gdk.CONTROL_MASK,gtk.ACCEL_VISIBLE)
        #activity_tab_tb.props.accelerator = '<Ctrl>T'
        activity_tab_tb.show()
        activity_tab_tb.connect('clicked', self._open_tab_cb)
        activity_toolbar.insert(activity_tab_tb, 5)

        activity_tab_delete_tv = sugar.graphics.toolbutton.ToolButton('list-remove')
        activity_tab_delete_tv.set_tooltip(_("Close Tab"))
        #activity_tab_delete_tv.props.accelerator = '<Ctrl><Shift>X'
        activity_tab_delete_tv.show()
        activity_tab_delete_tv.connect('clicked', self._close_tab_cb)
        activity_toolbar.insert(activity_tab_delete_tv, 6)


        activity_fullscreen_tb = sugar.graphics.toolbutton.ToolButton('view-fullscreen')
        activity_fullscreen_tb.set_tooltip(_("Fullscreen"))
        #activity_fullscreen_tb.props.accelerator = '<Alt>Enter'
        activity_fullscreen_tb.connect('clicked', self._fullscreen_cb)
        activity_toolbar.insert(activity_fullscreen_tb, 7)
        activity_fullscreen_tb.hide()

        #Add editor functionality to the debugger
        editbar = gtk.Toolbar()
        
        editopen = ToolButton()
        editopen.set_stock_id('gtk-new')
        editopen.set_icon_widget(None)
        editopen.set_tooltip(_('New File'))
        editopen.connect('clicked', self._new_file_cb)
        editopen.add_accelerator('clicked',self.accelerator,ord('N'),gtk.gdk.CONTROL_MASK,gtk.ACCEL_VISIBLE)
        #editopen.props.accelerator = '<Ctrl>O'
        editopen.show()
        editbar.insert(editopen, -1)
        
        editfile = ToolButton()
        editfile.set_stock_id('gtk-open')
        editfile.set_icon_widget(None)
        editfile.set_tooltip(_('Open File'))
        editfile.connect('clicked', self._read_file_cb)
        editfile.add_accelerator('clicked',self.accelerator,ord('O'),gtk.gdk.CONTROL_MASK,gtk.ACCEL_VISIBLE)
        #editfile.props.accelerator = '<Ctrl>O'
        editfile.show()
        editbar.insert(editfile, -1)
        
        editsave = ToolButton()
        editsave.set_stock_id('gtk-save')
        editsave.set_icon_widget(None)
        editsave.set_tooltip(_('Save File'))
        editsave.add_accelerator('clicked',self.accelerator,ord('S'),gtk.gdk.CONTROL_MASK,gtk.ACCEL_VISIBLE)
        #editsave.props.accelerator = '<Ctrl>S'
        editsave.connect('clicked', self.save_cb)
        editsave.show()
        editbar.insert(editsave, -1)
        
        editsaveas = ToolButton()
        editsaveas.set_stock_id('gtk-save-as')
        editsaveas.set_icon_widget(None)
        editsaveas.set_tooltip(_('Save As'))
        #editsaveas.props.accelerator = '<Ctrl>S'
        editsaveas.connect('clicked', self.save_file_cb)
        editsaveas.show()
        editbar.insert(editsaveas, -1)
        
        
        """
        editjournal = ToolButton(tooltip=_('Open Journal'))
        client = gconf.client_get_default()
        color = XoColor(client.get_string('/desktop/sugar/user/color'))
        journal_icon = Icon(icon_name='document-save', xo_color=color)
        editjournal.set_icon_widget(journal_icon)
        editjournal.connect('clicked', self._show_journal_object_picker_cb)
        #editjournal.props.accelerator = '<Ctrl>J'
        editjournal.show()
        editbar.insert(editjournal, -1)
        """
        
        separator = gtk.SeparatorToolItem()
        separator.set_draw(True)
        separator.show()
        editbar.insert(separator, -1)
        
        editundo = ToolButton('undo')
        editundo.set_tooltip(_('Undo'))
        editundo.connect('clicked', self.editor.undo)
        editundo.add_accelerator('clicked',self.accelerator,ord('Z'),gtk.gdk.CONTROL_MASK,gtk.ACCEL_VISIBLE)
        #editundo.props.accelerator = '<Ctrl>Z'
        editundo.show()
        editbar.insert(editundo, -1)

        editredo = ToolButton('redo')
        editredo.set_tooltip(_('Redo'))
        editredo.connect('clicked', self.editor.redo)
        editredo.add_accelerator('clicked',self.accelerator,ord('Y'),gtk.gdk.CONTROL_MASK,gtk.ACCEL_VISIBLE)
        #editredo.props.accelerator = '<Ctrl>Y'
        editredo.show()
        editbar.insert(editredo, -1)

        separator = gtk.SeparatorToolItem()
        separator.set_draw(True)
        separator.show()
        editbar.insert(separator, -1)
        
        editcut = ToolButton()
        editcut.set_stock_id('gtk-cut')
        editcut.set_icon_widget(None)
        editcut.set_tooltip(_('Cut'))
        self.edit_cut_handler_id = editcut.connect('clicked', self.editor.cut)
        editcut.add_accelerator('clicked',self.accelerator,ord('X'),gtk.gdk.CONTROL_MASK,gtk.ACCEL_VISIBLE)
        #editcut.props.accelerator = '<Ctrl>X'
        editbar.insert(editcut, -1)
        editcut.show()

        editcopy = ToolButton('edit-copy')
        editcopy.set_tooltip(_('Copy'))
        self.edit_copy_handler_id = editcopy.connect('clicked', self.editor.copy)
        editcopy.add_accelerator('clicked',self.accelerator,ord('C'),gtk.gdk.CONTROL_MASK,gtk.ACCEL_VISIBLE)
        #editcopy.props.accelerator = '<Ctrl>C'
        editbar.insert(editcopy, -1)
        editcopy.show()

        editpaste = ToolButton('edit-paste')
        editpaste.set_tooltip(_('Paste'))
        self.edit_paste_handler_id = editpaste.connect('clicked', self.editor.paste)
        editpaste.add_accelerator('clicked',self.accelerator,ord('V'),gtk.gdk.CONTROL_MASK,gtk.ACCEL_VISIBLE)
        #editpaste.props.accelerator = '<Ctrl>V'
        editpaste.show()
        editbar.insert(editpaste, -1)

        separator = gtk.SeparatorToolItem()
        separator.set_draw(True)
        separator.show()
        editbar.insert(separator, -1)
        
        editfind = ToolButton('viewmag1')
        editfind.set_tooltip(_('Find and Replace'))
        editfind.connect('clicked', self.show_find)
        editfind.add_accelerator('clicked',self.accelerator,ord('F'),gtk.gdk.CONTROL_MASK,gtk.ACCEL_VISIBLE)
        #editfind.props.accelerator = '<Ctrl>F'
        editfind.show()
        editbar.insert(editfind, -1)

        separator = gtk.SeparatorToolItem()
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
        
        #childbar = gtk.Toolbar()
        #childbar.show_all()
        #self.toolbox.add_toolbar(_('Your Program'), childbar)
        
        project_run = ToolButton()
        project_run.set_stock_id('gtk-media-forward')
        project_run.set_icon_widget(None)
        project_run.set_tooltip(_('Start Debugging'))
        project_run.connect('clicked', self.project_run_cb)
        project_run.add_accelerator('clicked',self.accelerator,ord('G'),gtk.gdk.CONTROL_MASK,gtk.ACCEL_VISIBLE)
        #project_run.props.accelerator = '<Ctrl>C'
        project_run.show()
        
        separator = gtk.SeparatorToolItem()
        separator.set_draw(False)
        separator.set_expand(True)
        separator.show()
        """ Keep seems similar to left arrow to journal or home,--confuses the issue
        self.keep = ToolButton(tooltip=_('Write the activity.info with this project data'))
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
        """
        projectbar = gtk.Toolbar()
        projectbar.show_all()
        projectbar.insert(project_run, -1)
        projectbar.insert(separator, -1)
        #projectbar.insert(self.keep,-1)
        self.toolbox.add_toolbar(_('Project'), projectbar)
        
        _logger.debug('about to init Help. Elapsed time: %f'%(time.clock()-start_clock))

        self.help = Help(self)
        helpbar = self.help.get_help_toolbar()
        self.toolbox.add_toolbar(_('Help'), helpbar)

        
        self.set_toolbox(self.toolbox)
        self.toolbox.show()
        
        #set the default contents for edit
        self.font_size = self.debug_dict.get('font_size',8) 
                
        #get the journal datastore information and resume previous activity
        #self.metadata = self.ds
        if self.passed_in_ds_object and self.passed_in_ds_object.get_file_path():
            ds_file = self.passed_in_ds_object.get_file_path()
        else:
            ds_file = ''
        _logger.debug('about to  call read  routine Elapsed time: %f'%(time.clock()-start_clock))
        self.read_file(ds_file)
        
        #set which PANE is visible initially
        self.set_visible_canvas(self.panes['PROJECT'])
        self.set_toolbar(self.panes['PROJECT'])
        self.non_blocking_server()
        #glib.idle_add(self.non_blocking_server)
        _logger.debug('about to setup_project_page. Elapsed time: %f'%(time.clock()-start_clock))
        self.setup_project_page()
        _logger.debug('child path for program to be debugged is %r\nUser Id:%s'%(self.child_path,os.geteuid()))

        #create the terminal tabs, start up the socket between 1st and 2nd terminal instances
        _logger.debug('about to setup terminal. Elapsed time: %f'%(time.clock()-start_clock))
        self.setup_terminal()
        
    def realize_cb(self):
        _logger.debug('about total time to realize event: %f'%(time.clock()-start_clock))
        
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
            if alert_error: self.alert(_('%s Command returned non zero\n'%cmd+output[0]))
        return output[0],p1.returncode
        
    def sugar_version(self):
        cmd = '/bin/rpm -q sugar'
        reply = self.command_line(cmd)
        if reply and reply[0].find('sugar') > -1:
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
        if os.environ.get("PYTHONPATH",'') == '':
            os.environ['PYTHONPATH'] = self.pydebug_path
        else:
            p_path_list = os.environ['PYTHONPATH'].split(':')
            if not self.pydebug_path in p_path_list:
                os.environ['PYTHONPATH'] = self.pydebug_path + ':' + os.environ.get("PYTHONPATH",'')
        _logger.debug('sugar_bundle_path:%s\nsugar_activity_root:%s'%(os.environ['SUGAR_BUNDLE_PATH'],
                                                                      os.environ['SUGAR_ACTIVITY_ROOT']))
        self.debugger_home = os.path.join(os.environ['SUGAR_ACTIVITY_ROOT'],'data')
        self.child_path = None
        os.environ["HOME"]=self.debugger_home
        if not os.path.isfile(os.path.join(self.debugger_home,'.bashrc')):
            self.setup_home_directory()
        path_list = os.environ['PATH'].split(':')
        new_path = os.path.join(self.pydebug_path,'bin:')
        if not new_path in path_list:
            os.environ['PATH'] = new_path + os.environ['PATH']
        self.storage = os.path.join(os.environ['SUGAR_ACTIVITY_ROOT'],'data/pydebug')
        self.sugar_bundle_path = os.environ['SUGAR_BUNDLE_PATH']
        self.activity_playpen = os.path.join(self.storage,'playpen')
        if not os.path.isdir(self.activity_playpen):
            os.makedirs(self.activity_playpen)
        self.hide = os.path.join(self.storage,'.hide')
        if not os.path.isdir(self.hide):
            os.makedirs(self.hide)
    
    def setup_home_directory(self):
        src = os.path.join(self.pydebug_path,'bin','.bashrc')
        try:
            shutil.copy(src,self.debugger_home)
        except Exception,e:
            _logger.debug('copy .bashrc exception %r'%e)
        try:
            shutil.rmtree(os.path.join(self.debugger_home,'.ipython'))
        except Exception,e:
            pass
            #_logger.debug('rmtree exception %r trying to setup .ipython '%e)
        try:
            shutil.copytree(os.path.join(self.pydebug_path,'bin','.ipython'),self.debugger_home)
        except Exception,e:
            _logger.debug('copytree exception %r trying to copy .ipython directory'%e)
        #for build 802 (sugar 0.82) we need a config file underneath home -- which pydebug moves
        # we will place the config file at ~/.sugar/default/
        try:
            shutil.rmtree(os.path.join(self.debugger_home,'.sugar'))
        except Exception,e:
            pass
            #_logger.debug('rmtree exception %r trying to setup .ipython '%e)
        try:
            shutil.copytree(os.path.join(self.pydebug_path,'bin','.sugar'),self.debugger_home)
        except Exception,e:
            _logger.debug('copytree exception %r trying to copy .sugar directory'%e)
        #make sure we will have write permission when rainbow changes our identity
        self.set_permissions(self.debugger_home)
        
    def _get_edit_canvas(self):
        self.editor =  sourceview_editor.GtkSourceview2Editor(self)
        return self.editor
           
    def setup_terminal(self):
        os.environ['IPYTHONDIR'] = self.debugger_home
        _logger.debug('Set IPYTHONDIR to %s'%self.debugger_home)
        self._create_tab({'cwd':self.sugar_bundle_path})
        self._create_tab({'cwd':self.activity_playpen})
        #start the debugger user interface
        #alias_cmd = 'alias go="%s/bin/ipython.py -gthread"\n'%(self.sugar_bundle_path,)
        alias_cmd = 'alias go="%s/bin/ipython.py "\n'%(self.sugar_bundle_path,)
        self.feed_virtual_terminal(0,alias_cmd)

        #self.feed_virtual_terminal(0,'%s/bin/ipython.py  -gthread\n'%self.sugar_bundle_path)
        self.feed_virtual_terminal(0,'%s/bin/ipython.py  \n'%self.sugar_bundle_path)
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
        fr = gtk.Frame()
        label = gtk.Label("This page will be replaced with the \noutput from your program")
        label.show()       
        fr.add(label)
        fr.show()
        return fr

             
    def _get_help_canvas(self):
        fr = gtk.Frame()
        label = gtk.Label(_("Loading Help Page"))
        label.show()       
        fr.add(label)
        fr.show()
        return fr

    def get_icon_pixbuf(self, stock):
        return self.treeview.render_icon(stock_id=getattr(gtk, stock),
                                size=gtk.ICON_SIZE_MENU,
                                detail=None)

 
    """    
    def _get_help_canvas(self):
        fr = gtk.Frame() #FIXME explore whether frame is still needed--was to fix webview problem
        fr.show()
        nb = gtk.Notebook()
        nb.show()        
        fr.add(nb)
        nb.append_page(self.get_first_webview())
        self.help_notebook = nb
        return fr
    """
        
    def _child_cb(self,event):
        pass
        
    def _project_cb(self,event):
        pass

    #lots of state to change whenever one of the major tabs is clicked    
    def set_visible_canvas(self,index): #track the toolbox tab clicks
        self.pydebug_notebook.set_current_page(index)
        if index == self.panes['TERMINAL']:
            gobject.idle_add(self.set_terminal_focus)
            self.editor.save_all()
            self.icon_window.hide()
        elif index == self.panes['HELP']:
            self.help_selected()
        elif index == self.panes['PROJECT'] and self.manifest_class:
            self.manifest_class.set_file_sys_root(self.child_path)
        if self.icon_window:
            self.icon_window.destroy()
        self.current_pd_page = index
        gobject.idle_add(self.grab_notebook_focus)
        
    def grab_notebook_focus(self):
        self.pydebug_notebook.grab_focus()
        return False
                
    def _toolbar_changed_cb(self,widget,tab_no):
        _logger.debug('tool tab changed notification %d'%tab_no)
        self.set_visible_canvas(tab_no)
        
    def set_toolbar(self,page_no):
        self.toolbox.set_current_toolbar(page_no)
        
    def key_press_cb(self,widget,event):
        state = event.get_state()
        if state and gtk.gdk.SHIFT_MASK and gtk.gdk.CONTROL_MASK and gtk.gdk.MOD1_MASK == 0:
            self.file_changed = True
            #put a star in front of the filename
        return False
    
    ###   following routines are copied from develop_app for use with sourceview_editor 
    def _replace_cb(self, button=None):
        ftext = self._search_entry.props.text
        rtext = self._replace_entry.props.text
        _logger.debug('replace %s with %s usiing options %r'%(ftext,rtext,self.s_opts))
        replaced, found = self.editor.replace(ftext, rtext, 
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
                if self.editor.find_next(text, 
                                SearchOptions(self.s_opts, 
                                              stay=True, 
                                where=(self.s_opts.where if 
                                       self.s_opts.where != S_WHERE.multifile
                                       else S_WHERE.file))):
                    #no multifile, or focus gets grabbed
                    self._replace_button.set_sensitive(True)
                    
    def _replace_entry_changed_cb(self, entry):
        if self._replace_entry.props.text:
            self.safe_to_replace = True
            
    def _findprev_cb(self, button=None):
        ftext = self._search_entry.props.text
        if ftext:
            if self.editor.find_next(ftext, 
                                               SearchOptions(self.s_opts,
                                                             forward=False)):
                self._replace_button.set_sensitive(True)
                        
    def _findnext_cb(self, button=None):
        ftext = self._search_entry.props.text
        _logger.debug('find next %s'%ftext)
        if ftext:
            if self.editor.find_next(ftext, self.s_opts):
                self._replace_button.set_sensitive(True)
            self.editor.set_focus()
    
    
    def show_find(self,button):
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
        #if there is any selected text, put it in the find entry field, and grab focus
        selected = self.editor.get_selected()
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
            'find_entry_changed_cb':self.find_entry_changed_cb,
            'replace_entry_changed_cb':self.replace_entry_changed_cb,
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
    
    def find_entry_changed_cb(self,button):
        #self.editor.search_for = 
        pass    
    def replace_entry_changed_cb(self,button):
        #self.editor.search_for = 
        pass
        
    def project_run_cb(self,button):
        _logger.debug('entered project_run_cb')
        """
        start_script = ['python','import sys','from Rpyc import *','from Rpyc.Utils import remote_interpreter',
                        'c = SocketConnection("localhost")','remote_interpreter(c)']
        for l in start_script:
            self.feed_virtual_terminal(0,l+'\r\n')
        """
        self.start_debugging()
        
    def __keep_clicked_cb(self, button):
        self._keep_activity_info()


    ######  SUGAR defined read and write routines -- do not let them overwrite what's being debugged
    
    def read_file(self, file_path):
        """
        If the ds_object passed to PyDebug is the last one saved, then just assume that the playpen is valid.
        If the ds_object is not the most recent one,  try to load the playpen with the contents referenced by the git_id
        (reading the wiki, I discover we cannot count on metadata -- so cancel the git_id scheme)
        """
        #keep our own copy of the metadata
        if self.metadata:
            for key in self.metadata.keys():  #merge in journal information
                self.activity_dict[key] = self.metadata[key]
        self.log_dict(self.activity_dict,"read_file merged")
        if not self.debug_dict: self.get_config()
        if self.activity_dict.get('uid','XxXxXx') == self.debug_dict.get('jobject_id','YyYyY'):
            _logger.debug('pick up where we left off')
            #OLPC bug reports suggest not all keys are preserved, so restore what we really need
            self.activity_dict['child_path'] = self.debug_dict.get('child_path','')
            if os.path.isdir(self.activity_dict.get('child_path')):
                self.child_path = self.activity_dict['child_path']
                self.setup_new_activity()
        #update the journal display - required when the journal is used to delete an item
        if self.journal_class: 
            self.journal_class.new_directory()            
                       
    def write_file(self, file_path):
        """
        The paradigm designed into the XO, ie an automatic load from the Journal at activity startup
        does not make sense during a debugging session.  An errant stack overflow can easily crash
        the system and require a reboot.  For the session manager to overwrite the changes that are stored
        on disk, but not yet saved in the journal is highly undesireable. So we'll let the user save to
        the journal, and perhaps optionally to the sd card (because it is removable, should the system die)
        """
        try:
            fd = open(file_path,'w+')
            if fd:
                fd.close()
            else:
                _logger.debug('failed to open output file')
            self.update_metadata()    
            #self.write_activity_info()
            self.save_editor_status()
            self.put_config()
        except Exception,e:
            _logger.debug('Write file exception %s'%e)
        return
        
    def update_metadata(self):
        obj = self._jobject
        #ipshell()
        if obj:
            md = obj.get_metadata()
            obj._file_path = None
            if md:
                self.log_dict(md,'journal metadata')                
                _logger.debug('write file  Jobject passed to write:%s'%(obj.object_id,))
                chunk = self.activity_dict.get('name','')            
                for key in self.activity_dict.keys():
                    if key == 'title' or key == 'activity': continue
                    md[key] = self.activity_dict[key]
                md['title'] = 'PyDebug_' + chunk
                md['bundle_id'] = 'org.laptop.PyDebug'
                try:
                    pass
                    #datastore.write(obj)
                except Exception, e:
                    _logger.debug('datastore write exception %s'%e)
            else:
                _logger.error('no metadata in write_file')
        else:
            _logger.error('no jobject in write_file')
            
    def log_dict(self, d, label = ''):
        debugstr = ''
        for a_key in d.keys():
            if a_key == 'preview': continue
            try:
                dict_value = '%s:%s, '%(a_key, d[a_key], )
                debugstr += dict_value
            except:
                pass
        _logger.debug('%s Dictionary ==>:%s'%(label,debugstr))

    def write_binary_to_datastore(self):
        """
        Check to see if there is a child loaded.
        then bundle it up and write it to the journal
        lastly serialize the project information and write it to the journal
        """
        if self.child_path == None: return
        dist_dir = os.path.join(self.child_path,'dist')
        try:
            os.rmtree(dist_dir)
        except:
            _logger.debug('failed to rmtree %s'%dist_dir)
        try:
            os.mkdir(dist_dir)
        except:
            _logger.debug('failed to os.mkdir %s'%dist_dir)
        
        #remove any embeded shell breakpoints
        self.editor.clear_embeds()
        
        #the activity info file is read by the bundle maker - must be updated from screen
        #self.write_activity_info()
        
        #create the manifest for the bundle
        config = self.write_manifest()
        do_tgz = True
        mime = 'application/binary'
        activity = 'org.laptop.PyDebug'
        #if manifest was successful, write the xo bundle to the instance directory
        if config:
            do_tgz = False
            try:                
                #actually write the xo file
                packager = bundlebuilder.XOPackager(bundlebuilder.Builder(config))
                packager.package()
                source = os.path.join(self.child_path,'dist',str(config.xo_name))
                dest = os.path.join(self.get_activity_root(),'instance',str(config.xo_name))
                _logger.debug('writing to the journal from %s to %s.'%(source,dest))
                if os.path.isfile(dest):
                    os.unlink(dest)
                try:
                    package = str(config.xo_name)
                    shutil.copy(source,dest)
                    mime = self.MIME_TYPE
                    activity = self.activity_dict.get('activity','')
                    self.to_removable_bin(source)
                except IOError:
                    _logger.debug('shutil.copy error %d: %s. ',IOError[0],IOError[1])
                    do_tgz = True
                    mime = 'application/zip'
            except Exception, e:
                _logger.debug('outer exception %r'%e)
                do_tgz = True
        else:
            _logger.debug('unable to create manifest')
        if do_tgz:
            dest = self.just_do_tar_gz()
            if dest:
                package = os.path.basename(dest)                
        dsobject = datastore.create()
        dsobject.metadata['package'] = package
        dsobject.metadata['title'] = package  
        dsobject.metadata['mime_type'] = mime
        dsobject.metadata['icon'] = self.activity_dict.get('icon','')
        dsobject.metadata['bundle_id'] = self.activity_dict.get('bundle_id','')
        dsobject.metadata['activity'] = activity
        dsobject.metadata['version'] = self.activity_dict.get('version',1) 
        #calculate and store the new md5sum
        self.debug_dict['tree_md5'] = self.md5sum_tree(self.child_path)
        dsobject.metadata['tree_md5'] = self.debug_dict['tree_md5']
        if dest: dsobject.set_file_path(dest)
        
        #actually make the call which writes to the journal
        try:
            datastore.write(dsobject,transfer_ownership=True)
            _logger.debug('succesfully wrote to the journal from %s.'%(dest))
        except Exception, e:
            _logger.error('datastore.write exception %r'%e)
            return
        #update the project display
        if self.journal_class: 
            self.journal_class.new_directory()
        #write snapshot of source tree to removable media if /pydebug directory exists
        self.removable_backup()
        
    def removable_backup(self):
        rs = self.removable_storage()
        _logger.debug('removable storage %r'%rs)
        for dest in rs:
            root = os.path.join(dest,'pydebug')
            if os.path.isdir(root):  #there is a pydebug directory in the root of this device
                today = datetime.date.today()               
                name = self.child_path.split('/')[-1].split(".")[0] + '-' + str(today)
                #change name if necessary to prevent collision 
                basename = self.non_conflicting(root,name)
                try:
                    shutil.copytree(self.child_path, os.path.join(root,basename))
                    self.set_permissions(os.path.join(root,basename))
                except Exception, e:
                    _logger.error('copytree exception %r'%e)
    
    def to_removable_bin(self, source):
        for dest in self.removable_storage():
            root = os.path.join(dest,'bin')
            if not os.path.isdir(root):  #there is no bin directory in the root of this device
                try:
                    os.mkdir(root)
                except Exception, e:
                    _logger.debug('mkdir exception %r'%e)
            if os.path.isdir(root):
                basename = os.path.basename(source)
                target = os.path.join(root,basename)
                if os.path.isfile(target):
                    os.unlink(target)
                _logger.debug('copying %s to %s'%(source,target))
                shutil.copyfile(source,target)
    
    def removable_storage(self):
        cmd = 'mount'
        ret = []
        resp, status = self.command_line(cmd)
        if status == 0:
            for line in resp.split('\n'):
                chunks = line.split()
                if len(chunks) > 2:
                    if chunks[2].startswith('/media'):
                        if chunks[2] == '/media/Boot': continue
                        _logger.debug('mount point: %s'%chunks[2])
                        ret.append(chunks[2])
            return ret
        return None
    
    def write_manifest(self):
        try:
            os.remove(os.path.join(self.child_path,'MANIFEST'))
        except:
            pass
        dest = self.child_path
        _logger.debug('Writing manifest to %s.'%(dest))
        try:
            config = bundlebuilder.Config(dest)
            b = bundlebuilder.Builder(config)
            b.fix_manifest()
        except:
            _logger.debug('fix manifest error: ',sys.exc_type,sys.exc_info()[0],sys.exc_info()[1])
            return None
        return config

    def just_do_tar_gz(self):
        """
        tar and compress the child_path tree to the journal
        """
        name = self.child_path.split('/')[-1].split(".")[0]+'.tar.gz'
        os.chdir(self.activity_playpen)
        dest = os.path.join(self.get_activity_root(),'instance',name)
        cmd = 'tar czf %s %s'%(dest,'./'+os.path.basename(self.child_path))
        ans = self.command_line(cmd)
        _logger.debug('cmd:%s'%cmd)
        if ans[1]!=0:
            return None
        return dest
        
    def load_activity_to_playpen(self,file_path):
        """loads from a disk tree"""
        self._new_child_path =  os.path.join(self.activity_playpen,os.path.basename(file_path))
        _logger.debug('copying file for %s to %s'%(file_path,self._new_child_path))
        self._load_playpen(file_path)
        
    def try_to_load_from_journal(self,object_id):
        """
        loads a zipped XO or tar.gz application file (tar.gz if bundler cannot parse the activity.info file)
        """
        self.ds = datastore.get(object_id[0])
        if not self.ds:
            _logger.debug('failed to get datastore object with id:%s'%object_id[0])
            return
        dsdict=self.ds.get_metadata()
        file_name_from_ds = self.ds.get_file_path()
        project = dsdict.get('package','')
        if not (project.endswith('.xo') or project.endswith('.tar.gz')):
            self.alert(_('This journal item does not appear to be a zipped activity. Package:%s.'%project))
            self.ds.destroy()
            self.ds = None
            return
        filestat = os.stat(file_name_from_ds)         
        size = filestat.st_size
        _logger.debug('In try_to_load_from_journal. Object_id %s. File_path %s. Size:%s'%(object_id[0], file_name_from_ds, size))
        if project.endswith('.xo'):
            try:
                self._bundler = ActivityBundle(file_name_from_ds)
                name = self._bundler.get_name()
                iszip=True
                istar = False
            except:
                self.alert('Error:  Malformed Activity Bundle')
                self.ds.destroy()
                self.ds = None
                return
        else:
            name = project.split('.')[0]
            #self.delete_after_load = os.path.abspath(file_name_from_ds,name)
            iszip = False
            istar = True
        self._new_child_path = os.path.join(self.activity_playpen,name+'.activity')
        self._load_playpen(file_name_from_ds, iszip, istar)
        
    def _load_playpen(self,source_fn, iszip = False, istar=False):
        """entry point for both xo and file tree sources"""
        self._load_to_playpen_source = source_fn
        #if necessary clean up contents of playpen
        if self.child_path and os.path.isdir(self.child_path) and source_fn.endswith('.activity'):        
            self.abandon_changes = True  #there is a on change call back to disable
            self.debug_dict['tree_md5'] = ''
            self.debug_dict['child_path'] = ''
            self.editor.remove_all()
            if self.child_path:
                shutil.rmtree(self.child_path)
            self.abandon_changes = False
        if self._load_to_playpen_source == None:
            #having done the clearing, just stop
            return
        if iszip:
            self._bundler.install(self.activity_playpen)
            if self.ds: self.ds.destroy()
            self.ds = None
        elif istar:
            dsdict = self.ds.get_metadata()
            project = dsdict.get('package','dummy.tar.gz')
            name = project.split('.')[0]
            dest = os.path.join(self.activity_playpen,project)
            shutil.copy(source_fn,dest)
            os.chdir(self.activity_playpen)
            cmd = 'tar zxf %s'%dest
            _logger.debug('loading tar.gz with cmd %s'%cmd)
            rtn = self.command_line(cmd)
            if rtn[1] != 0: return
            #os.unlink(dest)
            if self.ds: self.ds.destroy()
            self.ds = None
        elif os.path.isdir(self._load_to_playpen_source):
            #shutil.copy dies if the target exists, so rmtree if target exists
            basename = self._load_to_playpen_source.split('/')[-1]
            if basename.endswith('.activity'):
                dest = self._new_child_path
            else:
                dest = os.path.join(self.child_path,basename)
            if  os.path.isdir(dest):
                shutil.rmtree(dest,ignore_errors=True)
            #os.mkdir(dest)
            _logger.debug('dest:%s'%dest)
            _logger.debug('copying tree from %s to %s'%(self._load_to_playpen_source,dest))
            shutil.copytree(self._load_to_playpen_source,dest)
            _logger.debug('returned from copytree')
        elif os.path.isfile(self._load_to_playpen_source):
            source_basename = os.path.basename(self._load_to_playpen_source)
            dest = os.path.join(self.child_path,source_basename)
            shutil.copy(self._load_to_playpen_source,dest)
        self.debug_dict['source_tree'] = self._load_to_playpen_source
        self.child_path = self._new_child_path
        self.setup_new_activity()
            
    def copy_tree(self,source,dest):
            if os.path.isdir(dest):
                try:
                    shutil.rmtree(dest)
                except Exception, error:
                    _logger.debug('rmtree exception %r'%error)
            try:
                shutil.copytree(source,dest)
                self.set_permissions(dest)
            except Exception, error:
                _logger.debug('copytree exception %r'%error)

    def  setup_new_activity(self):
        _logger.debug('in setup_new_activity. child path before chdir:%s'%self.child_path)
        if self.child_path == None or not os.path.isdir(self.child_path):
            return
        os.chdir(self.child_path)
        #cd_cmd = 'cd %s'%self.child_path
        #self.feed_virtual_terminal(0,cd_cmd)
        self.read_activity_info(self.child_path)
        self.debug_dict['child_path'] = self.child_path
        self.display_current_project()
        
        #set the current working directory for debugging in the child context
        cwd_cmd = 'cd %s\n'%(self.child_path,)
        self.feed_virtual_terminal(0,cwd_cmd)

        #add the bin directory to path
        if self.child_path not in os.environ['PATH'].split(':'):
            os.environ['PATH'] = os.path.join(self.child_path,'bin') + ':' + os.environ['PATH']
        
        #calculate and store the md5sum
        self.debug_dict['tree_md5'] = self.md5sum_tree(self.child_path)
        
        #if this is a resumption, open previous python files and position to previous location
        if self.debug_dict.get(os.path.basename(self.child_path)):
            for filenm, line in self.debug_dict.get(os.path.basename(self.child_path)):
                if os.path.isfile(filenm):
                    self.editor.load_object(filenm,os.path.basename(filenm)) 
                    self.editor.position_to(filenm,line)
                current_page = self.debug_dict.get(os.path.basename(self.child_path)+'-page',0) 
                self.editor.set_current_page(current_page)
            self.editor.load_breakpoints = False
        else:             
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
            _logger.debug('about completed setup new activity. Elapsed time: %f'%(time.clock()-start_clock))        
    #####################            ALERT ROUTINES   ##################################
    
    def alert(self,msg,title=None):
        alert = NotifyAlert(0)
        if title != None:
            alert.props.title=_('There is no Activity file')
        alert.props.msg = msg
        alert.connect('response',self.no_file_cb)
        self.add_alert(alert)
        return alert
        
    def no_file_cb(self,alert,response_id):
        self.remove_alert(alert)

    from sugar.graphics.alert import ConfirmationAlert
  
    def confirmation_alert(self,msg,title=None,confirmation_cb = None):
        alert = ConfirmationAlert()
        alert.props.title=title
        alert.props.msg = msg
        alert.pydebug_cb = confirmation_cb
        alert.connect('response', self._alert_response_cb)
        self.add_alert(alert)
        return alert

    #### Method: _alert_response_cb, called when an alert object throws a
                 #response event.
    def _alert_response_cb(self, alert, response_id):
        #remove the alert from the screen, since either a response button
        #was clicked or there was a timeout
        this_alert = alert  #keep a reference to it
        self.remove_alert(alert)
        #Do any work that is specific to the type of button clicked.
        if response_id is gtk.RESPONSE_OK and this_alert.pydebug_cb != None:
            this_alert.pydebug_cb (this_alert, response_id)
            
    def _new_file_cb(self, widget):
        full_path = self.non_conflicting(self.child_path,'Unsaved_Document.py')
        self.editor.load_object(full_path,os.path.basename(full_path))
        
    def _read_file_cb(self,widget):
        _logger.debug('Reading a file into editor')
        dialog = gtk.FileChooserDialog("Open..",
                                       None,
                                       gtk.FILE_CHOOSER_ACTION_OPEN,
                                       (gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL,
                                        gtk.STOCK_OPEN, gtk.RESPONSE_OK))
        dialog.set_default_response(gtk.RESPONSE_OK)
        if self.last_filename == None:
            self.last_filename = self.child_path
        if not self.last_filename:  
            self.last_filename = self.activity_playpen                 
        if self.last_filename:       
            dialog.set_current_folder(os.path.dirname(self.last_filename))       
        
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
            self.last_filename = fname
            self.editor.load_object(fname,os.path.basename(fname))
            line = self.get_remembered_line_number(fname)
            if line:
                self.editor.position_to(fname,line)
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
        file_path = self.editor.get_full_path()
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
            full_path = self.editor.get_full_path()
        if os.path.basename(full_path).startswith('Unsaved_Document'): #force a choice to keep or change the name
            #fd = open(full_path,'w')
            #fd.close()
            self.save_file_cb(None)            
            return
        page = self.editor._get_page()
        if  new_fn:
            page.fullPath = new_fn
            page.save(skip_md5 = True,new_file=new_fn)
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
    
    def set_permissions(self,root, perms='664'):
        if not os.path.isdir(root):
            return None
        for dirpath, dirnames, filenames in os.walk(root):
            for filename in filenames:
                abs_path = os.path.join(dirpath, filename)
                old_perms = os.stat(abs_path).st_mode
                if os.path.isdir(abs_path):
                    new_perms = int(perms,8) | int('771',8)
                else:
                    new_perms = old_perms | int(perms,8)
                os.chmod(abs_path,new_perms)
    
    
        
        
    ##############    Following code services the Project page   #####################
    
    def _get_project_canvas(self):
        #initialize the link between program and the glade XML file
        self.wTree=gtk.glade.XML(os.path.join(self.sugar_bundle_path,"project.glade"))
        self.contents = self.wTree.get_widget("contents")
        self.contents.unparent()
        return self.contents
    
    def setup_project_page(self):
        self.activity_treeview = self.wTree.get_widget('file_system')
        self.activity_window = FileTree(self, self.activity_treeview,self.wTree)
        self.activity_window.set_file_sys_root('/home/olpc/Activities')
        self.examples_treeview = self.wTree.get_widget('examples')
        self.examples_window = FileTree(self, self.examples_treeview,self.wTree)
        self.examples_window.set_file_sys_root(os.path.join(self.sugar_bundle_path,'examples'))
        self.journal_treeview = self.wTree.get_widget('journal')
        self.journal_class = DataStoreTree(self,self.journal_treeview,self.wTree)
        self.connect_object()  #make connections to signals from buttons
        self.activity_toggled_cb(None)
        
        self.icon_type = self.wTree.get_widget('icon_outline')
        model = gtk.ListStore(str,str)
        model.append(["icon_circle", _('Circle')])
        model.append(['icon_square', _('Square')])
        model.append(['icon_diamond', _('Diamond')])
        model.append(['icon_star', _('Star')])
        cell = gtk.CellRendererText()
        self.icon_type.set_model(model)
        self.icon_type.pack_start(cell)
        self.icon_type.add_attribute(cell,'text',1)
        self.icon_type.set_active(self.debug_dict.get('icon_active',1))
        
        if self.child_path and self.child_path.endswith('.activity') and \
                                os.path.isdir(self.child_path):
            self.setup_new_activity()
        """
        ds_mounts = datastore.mounts()
        for x in ds_mounts:
            _logger.debug('Title:%s Uri:%s'%(x.get('title'),x.get('uri')))
        """
        self.activity_data_changed = False
        
        """
        #get set to sense addition of a usb flash drive
        self.volume_monitor = gio.volume_monitor_get()
        self.volume_monitor.connect('mount-added',self.__mount_added_cb)
        self.volume_monitor.connect('mount-removed',self.__mount_removed_cb)
        mount_list = self.volume_monitor.get_mounts()
        for m in mount_list:
            s = m.get_root().get_path()
            if s.startswith('/media'):_logger.debug('volume:%s',s)
        """
    def __mount_added_cb(self, vm, mount):
        pass
    
    def __mount_removed_cb(self, vm, mount):
        pass
        
    def display_current_project(self):
        global start_clock            
        #try to colorize the playpen
        pp = self.wTree.get_widget('playpen_event_box')
        map = pp.get_colormap()
        color = map.alloc_color(PROJECT_BG)
        style = pp.get_style().copy()
        style.bg[gtk.STATE_NORMAL] = color
        pp.set_style(style)
        
        self.manifest_treeview = self.wTree.get_widget('manifest')
        map =self.manifest_treeview.get_colormap()
        color = map.alloc_color(PROJECT_BASE)
        style = self.manifest_treeview.get_style().copy()
        style.bg[gtk.STATE_NORMAL] = color
        color = map.alloc_color(PROJECT_BASE)
        style.base[gtk.STATE_NORMAL] = color
        self.manifest_treeview.set_style(style)
        if self.manifest_class == None:
            self.manifest_class = FileTree(self, self.manifest_treeview,self.wTree)
        self.manifest_class.set_file_sys_root(self.child_path)
        
        #disable the on change callbacks
        self.ignore_changes = True
        
        name = self.wTree.get_widget('name')
        #map = name.get_colormap()
        color = map.alloc_color(PROJECT_BASE)
        style = name.get_style().copy()
        style.base[gtk.STATE_NORMAL] = color
        name.set_style(style)        
        name.set_text(self.activity_dict.get('name',''))
        
        version = self.wTree.get_widget('version')
        version.set_style(style)
        version.set_text(self.activity_dict.get('version',''))
        
        bundle = self.wTree.get_widget('bundle_id')
        bundle.set_style(style)
        bundle.set_text(self.activity_dict.get('bundle_id',''))
        
        pyclass = self.wTree.get_widget('class')
        pyclass.set_style(style)
        pyclass.set_text(self.activity_dict.get('class',''))
        self.pdbclass = pyclass
        
        pymodule = self.wTree.get_widget('module')
        pymodule.set_style(style)
        pymodule.set_text(self.activity_dict.get('module',''))
        self.pdbmodule = pymodule.get_text()

        pyicon = self.wTree.get_widget('icon_chr')
        pyicon.set_style(style)
        pyicon.set_text(self.activity_dict.get('icon_chr',''))

        #re-enable the on change callbacks
        self.ignore_changes = False
        _logger.debug('about completed display current project. Elapsed time: %f'%(time.clock()-start_clock))
        
        """
        self.wTree.get_widget('home_save').set_text(self.activity_dict.get('home_save',''))
        self.wTree.get_widget('host').set_text(self.debug_dict.get('host',''))
        self.wTree.get_widget('port').set_text(str(self.debug_dict.get('port','')))
        activity_size = os.system('du  --max-depth=0')
        self.wTree.get_widget('activity_size').set_text(str(activity_size))
        self.wTree.get_widget('icon').set_text(self.activity_dict.get('icon','').split('/')[-1:][0])
        """
    
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
                 'name_leave_notify_event_cb':self.name_changed_cb,
                 'bundle_id_leave_notify_event_cb':self.bundle_id_changed_cb,
                 'module_leave_notify_event_cb':self.module_changed_cb,
                 'class_leave_notify_event_cb':self.class_changed_cb,
                 'icon_outline_changed_cb':self.icon_changed_cb,
                 'version_leave_notify_event_cb':self.version_changed_cb,
                 'file_toggle_clicked_cb':self.activity_toggled_cb,
                 'to_activities_clicked_cb':self.to_home_clicked_cb,
                 'from_activities_clicked_cb':self.from_home_clicked_cb,
                 'from_examples_clicked_cb':self.from_examples_clicked_cb,
                 'help_clicked_cb':self._keep_activity_info,
                 'create_icon_clicked_cb':self.create_icon_cb,
                 'delete_file_clicked_cb':self.delete_file_cb,
                 'clear_clicked_cb':self.clear_clicked_cb,
             }
        self.wTree.signal_autoconnect(mdict)
        
        button = self.wTree.get_widget('file_toggle')
        tt = gtk.Tooltips()
        tt.set_tip(button,_('Switch views between the "Installed" Activities directory and your "home" storage directory'))
        #button.set_tooltip_text(_('Switch views between the "Installed" Activities directory and your "home" storage directory'))
        
        button = self.wTree.get_widget('to_activities')
        tt = gtk.Tooltips()
        tt.set_tip(button,_('Copy the files in the debug workplace to your "home" storage directory'))
        #button.set_tooltip_text(_('Copy the files in the debug workplace to your "home" storage directory')
        
        button = self.wTree.get_widget('from_examples')
        tt = gtk.Tooltips()
        tt.set_tip(button,_('Load and modify these example programs. See the help Tutorials'))
        #button.set_tooltip_text(_('Load and modify these example programs. See the help Tutorials'))

        button = self.wTree.get_widget('delete_file')
        map = button.get_colormap()
        color = map.alloc_color(PROJECT_FG)
        style = button.get_style().copy()
        style.bg[gtk.STATE_NORMAL] = color
        button.set_style(style)
         
        button = self.wTree.get_widget('clear')
        button.set_style(style)
         
        button = self.wTree.get_widget('help')
        button.set_style(style)

        button = self.wTree.get_widget('create_icon')
        button.set_style(style)
         
        button = self.wTree.get_widget('icon_outline')
        button.set_style(style)
         
         
    def project_help_cb(self):
        self.help_selected()
        
    def name_changed_cb(self, widget, event):
        if self.ignore_changes: return
        self.activity_data_changed = True
        name = widget.get_text()
        
        #make a suggestion for module if it is blank
        widget_field = self.wTree.get_widget('module')
        module = widget_field.get_text()
        if module == '':
            widget_field.set_text(name.lower())
            
        #make a suggestion for class if it is blank
        widget_field = self.wTree.get_widget('class')
        myclass = widget_field.get_text()
        if myclass == '':
            widget_field.set_text(name)
            
        #make a suggestion for bundle_id if it is blank
        widget_field = self.wTree.get_widget('bundle_id')
        bundle_id = widget_field.get_text()
        if bundle_id == '':
            suggestion = 'org.laptop.' + name
        else: #working from a template, suggest changing last element
            bundle_chunks = bundle_id.split('.')
            prefix = '.'.join(bundle_chunks[:-1])
            suggestion = prefix + '.' + name
        widget_field.set_text(suggestion)
        #self.display_current_project()
            
    def bundle_id_changed_cb(self,widget, event):
        if self.ignore_changes: return
        self.activity_data_changed = True
        
    def module_changed_cb(self, widget, event): 
        if self.ignore_changes: return
        self.activity_data_changed = True
     
    def class_changed_cb(self, widget, event): 
        if self.ignore_changes: return
        self.activity_data_changed = True
     
    def version_changed_cb(self, widget, event):
        if self.ignore_changes: return
        self.activity_data_changed = True
        version = widget.get_text()
        _logger.debug('version changed to %s'%version)
        
    def icon_changed_cb(self, combo):
        self.activity_data_changed = True
        model = combo.get_model()
        i = combo.get_active()
        self.icon_outline = model[i][0]
        _logger.debug('icon outline select is %s'%self.icon_outline)
        self.debug_dict['icon_active'] = i
                
    def create_icon_cb(self,widget):
        self.activity_data_changed = True
        #get the two characters and substitute them in the proper svg template
        chrs_entry = self.wTree.get_widget('icon_chr')
        chars = chrs_entry.get_text()
        _logger.debug('CREATE A NEW ICON !!!!text characters: %s'%chars)
        if chars == '':chars = '??'
        template = os.path.join(self.pydebug_path,'bin',self.icon_outline)+'.svg'
        try:
            icon_fd = file(template,'r')
            icon_str = icon_fd.read()
        except IOError, e:
            _logger.error('read exception %s'%e)
            return
        icon_str = icon_str.replace('??', chars)
        self.icon_basename = self.activity_dict.get('bundle_id','dummy').split('.')[-1] + \
                '_' + chars + '_' + self.icon_outline[5:6]
        self.activity_dict['icon_base'] = os.path.join(self.child_path,'activity',self.icon_basename)
                        
        target =  self.activity_dict['icon_base'] + '.svg'
        if self.last_icon_file:
            os.unlink(self.last_icon_file)
            self.last_icon_file = None
        try:
            _file = file(target, 'w+')
            _file.write(icon_str)
            _file.close()
        except IOError, e:
            msg = _("I/O error(%s): %s"%(e))
            _logger.error(msg)
        except Exception, e:
            msg = "Unexpected error:%s"%e
            _logger.error(msg)
        if _file:
            self.last_icon_file = target
            _file.close()
        self.activity_dict['icon'] = self.activity_dict.get('name')
        self.update_metadata()
        _logger.debug('about to POP UP THE ICON')
        if self.icon_window:
            self.icon_window.destroy()
        self.icon_window = Icon_Panel(None)
        self.icon_window._icon.set_file(target)
        self.icon_window._icon.show()
        self.icon_window.connect_button_press(self.button_press_event)
        self.icon_window.show()
        
    def button_press_event(self,event, data=None):
        self.icon_window.destroy()
        self.icon_window = None
            
    def activity_toggled_cb(self, widget):
        _logger.debug('Entered activity_toggled_cb. Button: %r'%self.file_pane_is_activities)
        but = self.wTree.get_widget('to_activities')
        to_what = self.wTree.get_widget('file_toggle')
        window_label = self.wTree.get_widget('file_system_label')
        if self.file_pane_is_activities == True:
            to_what.set_label('Installed_')
            but.show()
            #display_label = self.storage[:18]+' . . . '+self.storage[-24:]
            display_label = 'PyDebug SHELF storage:'
            self.activity_window.set_file_sys_root(self.storage)
            button = self.wTree.get_widget('from_activities')
            tt = gtk.Tooltips()
            tt.set_tip(button,_('Copy the selected directory or file from your "home" storage to the debug workplace'))
            #button.set_tooltip_text(_('Copy the selected directory or file from your "home" storage to the debug workplace'))
            window_label.set_text(display_label)
        else:
            to_what.set_label('shelf')
            but.hide()
            self.activity_window.set_file_sys_root('/home/olpc/Activities')
            button = self.wTree.get_widget('from_activities')
            tt = gtk.Tooltips()
            tt.set_tip(button,_('Copy the selected Activity or file to the debug workplace'))
            #button.set_tooltip_text(_('Copy the selected Activity or file to the debug workplace'))
            window_label.set_text('INSTALLED ACTIVITIES:')
        self.file_pane_is_activities =  not self.file_pane_is_activities
    
    
    def to_home_clicked_cb(self,widget):
        _logger.debug('Entered to_home_clicked_cb')
        self._to_home_dest = os.path.join(self.storage,self.activity_dict['name']+'.activity')
        if False: #os.path.isdir(self._to_home_dest):
            target_md5sum = self.md5sum_tree(self._to_home_dest)
            if target_md5sum != self.debug_dict.get('tree_md5',''):
                self.confirmation_alert(_('OK to delete/overwrite %s?'%self._to_home_dest),
                                        _('This destination has been changed by another application'),
                                        self._to_home_cb)
            return
        self._to_home_cb( None, gtk.RESPONSE_OK)
            
    def _to_home_cb(self, alert, response_id):
        if alert != None: self.remove_alert(alert)
        if response_id is gtk.RESPONSE_OK:
            """
            cmd = ['rsync','-av',self.child_path + '/',self._to_home_dest]
            _logger.debug('do to_home_cb with cmd:%s'%cmd)
            p1 = Popen(cmd,stdout=PIPE)
            output = p1.communicate()
            if p1.returncode != 0:
                self.alert('rsync command returned non zero\n'+output[0]+ 'COPY FAILURE')
                return
            """
            
            #remove any embeded shell breakpoints
            self.editor.clear_embeds()

            _logger.debug('removing tree, and then copying to %s'%self._to_home_dest)
            if os.path.isdir(self._to_home_dest):
                shutil.rmtree(self._to_home_dest, ignore_errors=True)
            shutil.copytree(self.child_path,self._to_home_dest)
            self.set_permissions(self._to_home_dest)
            #redraw the treeview
            self.activity_window.set_file_sys_root(self.storage)

    def from_home_clicked_cb(self,widget):
        _logger.debug('Entered from_home_clicked_cb')
        selection=self.activity_treeview.get_selection()
        (model,iter)=selection.get_selected()
        if iter == None:
            self.alert(_('Must select File or Directory item to Load'))
            return
        fullpath = model.get(iter,4)[0]
        if os.path.isdir(fullpath):
            if fullpath.endswith('.activity'):
                if fullpath.startswith(self.activity_playpen): #just re-initialize the project
                    self.debug_dict['source_tree'] = fullpath
                    self.child_path = fullpath
                    self.setup_new_activity()
                    return
                self.load_activity_to_playpen(fullpath)
            else: #this is a file folder, just copy it to project
                source_basename = os.path.basename(fullpath)
                dest = os.path.join(self.activity_playpen,source_basename)
                self.copy_tree(fullpath,dest)
        else:
            #selected is a file, just copy it into the current project
            basename = os.path.basename(fullpath)
            if os.path.isfile(os.path.join(self.child_path,basename)):
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
            ext = '.' + basename[1]
        adder = ''
        index = 0
        while (os.path.isfile(os.path.join(root,word+adder+ext)) or 
                                os.path.isdir(os.path.join(root,word+adder+ext))):
            index +=1
            adder = '-%s'%index
        _logger.debug('non conflicting:%s'%os.path.join(root,word+adder+ext))
        return os.path.join(root,word+adder+ext)
    
    def from_examples_clicked_cb(self,widget):
        _logger.debug('Entered from_examples_clicked_cb')
        selection=self.examples_treeview.get_selection()
        (model,iter)=selection.get_selected()
        if iter == None:
            self.alert(_('Must select File or Directory item to Load'))
            return
        fullpath = model.get(iter,4)[0]
        self._load_to_playpen_source = fullpath
        if fullpath.endswith('.activity'):
            self.load_activity_to_playpen(fullpath)
            return        
        if fullpath.endswith('.xo'):
            try:
                self._bundler = ActivityBundle(fullpath)
            except:
                self.alert('Error:  Malformed Activity Bundle')
                return    
            self._new_child_path = os.path.join(self.activity_playpen,self._bundler._zip_root_dir)
            #check to see if current activity in playpen needs to be saved, and load new activity if save is ok
            self._load_playpen(fullpath, iszip=True)
            return
        if fullpath.endswith('.tar.gz'):    
            self._new_child_path = os.path.join(self.activity_playpen,self._bundler._zip_root_dir)
            #check to see if current activity in playpen needs to be saved, and load new activity if save is ok
            self._load_playpen(fullpath, istar=True)
            return
        #if os.path.isdir(fullpath):
        self._new_child_path = self.child_path
        self._load_playpen(fullpath)
   
    #def filetree_activated(self):
    #_logger.debug('entered pydebug filetree_activated')
    
    def read_activity_info(self, path):
        """
        Parses the ./activity/activity.info file 
        """
        try:
            _logger.debug ('passed in file path: %s'%path)       
            bundle = ActivityBundle(path)
        except Exception,e:
            _logger.debug('exception %r'%e)
            #msg = _('%s not recognized by ActivityBundle parser. Does activity/activity.info exist?'%os.path.basename(path))
            #self.alert(msg)
            self.init_activity_dict()
            if self.child_path and os.path.isdir(self.child_path) and self.child_path.endswith('.activity'):
                name = os.path.basename(self.child_path).split('.')[0]
                self.activity_dict['name'] = name
                self.activity_dict['bundle_id'] = 'org.laptop.'  + name               
                return  #maybe should issue an alert here
        self.activity_dict['version'] = str(bundle.get_activity_version())
        self.activity_dict['name'] = bundle.get_name()
        self.activity_dict['bundle_id'] = bundle.get_bundle_id()
        self.activity_dict['command'] = bundle.get_command()
        cmd_args = bundle.get_command()
        self.activity_dict['command'] = cmd_args
        if cmd_args.startswith('sugar-activity'):
            mod_class = cmd_args.split()[1]
            if '.' in mod_class:
                self.activity_dict['class'] = mod_class.split('.')[1]  
                self.activity_dict['module'] = mod_class.split('.')[0]
        else:
            self.activity_dict['module'] = cmd_args
            self.activity_dict['class'] = ''
        self.activity_dict['icon'] = bundle.get_icon()
        self.activity_dict['title'] = 'PyDebug_' + self.activity_dict['name']
        self.log_dict(self.activity_dict,'Contents of activity_dict')
        self.update_metadata()
        
    def init_activity_dict(self):
        self.activity_dict['version'] = '1'
        self.activity_dict['name'] = 'untitled'
        self.activity_dict['bundle_id'] = ''
        self.activity_dict['command'] = ''
        self.activity_dict['class'] = ''
        self.activity_dict['module'] = ''           
        self.activity_dict['icon'] = ''
        self.activity_dict['activity_id'] = ''
        self.activity_dict['package'] = ''
        self.activity_dict['jobject _id'] = ''
        
    def _keep_activity_info(self,widget):
        """ Act on the changes made to the screen project data fields
        changing the name of the activity turns out to be a big deal --
        it will be done frequently in order to branch off an experimental branch
        and it requires changing the root path, and therefore all the open edit files which
        include the old root name in the path.  There's also the meta- that has to be updated.
        So let's deal with writing the activity.info file first
        """
        _logger.debug('in keep_activity_activity.info')
        name_widget = self.wTree.get_widget('name')
        name = name_widget.get_text()
        old_name =  self.activity_dict['name']
        self.old_icon = self.activity_dict.get('icon')
        self.activity_dict['name'] = name
                
        name_widget = self.wTree.get_widget('version')
        self.activity_dict['version'] = name_widget.get_text()
            
        name_widget = self.wTree.get_widget('version')
        self.activity_dict['version'] = name_widget.get_text()
            
        name_widget = self.wTree.get_widget('bundle_id')
        self.activity_dict['bundle_id'] = name_widget.get_text()
            
        name_widget = self.wTree.get_widget('module')
        self.activity_dict['module'] = name_widget.get_text()
            
        name_widget = self.wTree.get_widget('class')
        self.activity_dict['class'] = name_widget.get_text()
            
        self.update_metadata()
        self.write_activity_info()
        
        #now the to the more difficult part -- is renaming required?       
        new_name = name + '.activity'
        new_child_path = os.path.join(self.activity_playpen,new_name)
        if name.startswith('untitled'):
            self.alert(_("Activities must be given a new and unique name"))
            return
        if old_name != self.activity_dict.get('name'):
            #check to see if the folder already exists, if so change its name
            _logger.debug('need to make decision to move or create child base:%s. new_name:%s'%\
                          (os.path.basename(self.child_path), new_name))
            if os.path.isdir(self.child_path) and os.path.basename(self.child_path) !=  new_name:
                self.editor.remove_all()
                self.init_activity_dict()

                cmd = 'mv %s %s'%(self.child_path,new_child_path)
                result,status = self.command_line(cmd)
                if status != 0:
                    _logger.error('tried to rename %s directory unsuccessfully'%self.child_path)
                    return
                self.child_path = new_child_path
        else: #need to create the directories
            if not os.path.isdir(os.path.join(new_child_path,'activity')):
                os.makedirs(os.path.join(new_child_path,'activity'))
                
        
    def write_activity_info(self):
        #write the activity.info file
        #if not self.activity_data_changed: return
        filen = os.path.join(self.child_path,'activity','activity.info')
        _logger.debug('write_activity_info to %s'%filen)
        if os.path.isfile(filen): #set aside the info file encountered
            new_filename = self.non_conflicting(os.path.join(self.child_path,'activity'),'activity.info')
            _logger.debug('decided to move %s to %s'%(filen,new_filename))
            cmd = 'mv %s %s'%(filen,new_filename)
            results,status = self.command_line(cmd)    
        self.write_new_activity_info(filen)
        """
        else:            
            try:
                with open(filen,'r') as fd:
                    #and also write to a new file
                    filewr = os.path.join(self.child_path,'activity','activity.new')
                    _logger.debug('write from %s to %s'%(filen,filewr,))
                    self.write_new_activity_info(filewr)
                    fdw = open(filewr,'a')
                    #pass the rest of the input to the output
                    passup = ('[activity]','exec','activity_version','name','bundle_id',
                                'service_name','icon','class')                        
                    for line in  fd.readlines():
                        tokens = line.split('=')
                        keyword = tokens[0].lower().rstrip()
                        if keyword in passup: continue
                        fdw.write(line)
                    if fdw: fdw.close()
                    filesave = filen.rsplit('.',1)[:-1][0] + '.save'
                    _logger.debug('filesave:%s'%filesave)
                    if not os.path.isfile(filesave):
                        cmd = 'mv %s %s'%(filen,filesave)
                        results,status = self.command_line(cmd)
                    if os.path.isfile(filen):                
                        os.unlink(filen)
                    cmd = 'mv %s %s'%(filewr,filen)
                    results,status = self.command_line(cmd)                    
                return True
            except Exception, e:
                _logger.debug('exception %r'%e)
                return False
        """
    def write_new_activity_info(self,fn):
        dirname = os.path.dirname(fn)
        if not os.path.isdir(dirname):
            try:
                os.makedirs(dirname)
            except:
                pass
        try:
            with open(fn,'w+') as fdw:
                #write the required lines
                _logger.debug('writing activity info to %s'%fn)
                fdw.write('[Activity]\n')
                fdw.write('name = %s\n'%self.activity_dict.get('name'))
                fdw.write('bundle_id = %s\n'%self.activity_dict.get('bundle_id'))
                fdw.write('activity_version = %s\n'%self.activity_dict.get('version'))
                fdw.write('show_launcher = yes\n')
                icon = self.activity_dict.get('icon')
                if self.icon_basename:
                    icon_nibble = self.icon_basename
                else:
                    icon_nibble = os.path.basename(self.old_icon).split('.')[0]
                fdw.write('icon = %s\n'%icon_nibble)
                if self.activity_dict.get('class','') == '':
                    if self.activity_dict.get('module'):
                        fdw.write('exec = %s\n'%self.activity_dict.get('module'))
                    else:
                        fdw.write('exec = %s\n'%self.activity_dict.get('name'))
                else:
                    fdw.write('class = %s.%s\n'%(self.activity_dict.get('module'),
                                                self.activity_dict.get('class')))                       
                fdw.close()
        except Exception, e:
            _logger.debug('write new activity info file exception %s'%e)
            raise e
                
    def delete_file_cb(self,widget):
        selection=self.manifest_treeview.get_selection()
        (model,iter)=selection.get_selected()
        if iter == None:
            self.alert(_('Must select a File or Folder to delete'))
            return
        fullpath = model.get(iter,4)[0]
        _logger.debug(' delete_file_clicked_cb. File: %s'%(fullpath))
        self.delete_file_storage = fullpath
        if os.path.isdir(fullpath):
            self.confirmation_alert(_('Would you like to continue deleting %s?'%os.path.basename(fullpath)),
                                    _('CAUTION: You are about to DELETE a FOLDER!!'),self.do_delete_folder)
            return
        self.confirmation_alert(_('Would you like to continue deleting %s?'%os.path.basename(fullpath)),
                                _('ABOUT TO DELETE A FILE!!'),self.do_delete)
            
    def do_delete(self, alert, response):
        _logger.debug('doing delete of: %s'%self.delete_file_storage)
        self.manifest_point_to(self.delete_file_storage)
        os.unlink(self.delete_file_storage)
        self.manifest_class.set_file_sys_root(self.child_path)
        self.manifest_class.position_recent()
     
    def do_delete_folder(self, alert, response):
        _logger.debug('doing delete of: %s'%self.delete_file_storage)
        self.manifest_point_to(self.delete_file_storage)
        shutil.rmtree(self.delete_file_storage)
        self.manifest_class.set_file_sys_root(self.child_path)
        self.manifest_class.position_recent()
     
    def clear_clicked_cb(self, button):
        new_tree = os.path.join(self.activity_playpen,'untitled.activity')
        if self.child_path == new_tree:
            root = self.storage            
        else:
            self.editor.remove_all()
            self.init_activity_dict()
            if os.path.isdir(new_tree):
                shutil.rmtree(new_tree,ignore_errors=True)
            act_path = os.path.join(new_tree,'activity')
            if not os.path.isdir(act_path):
                os.makedirs(act_path)
            self.child_path = new_tree
            self.activity_dict['child_path'] = new_tree
            src = os.path.join(self.sugar_bundle_path,'setup.py')
            shutil.copy(src,new_tree)
            root = self.activity_playpen
        if self.manifest_class:
            self.manifest_class.set_file_sys_root(root)        
        self.display_current_project()
        
    ################  Help routines
    def help_selected(self):
        """
        if help is not created in a gtk.mainwindow then create it
        else just switch to that viewport
        """
        if not self.help_x11:
            screen = gtk.gdk.screen_get_default()
            self.pdb_window = screen.get_root_window()
            _logger.debug('xid for pydebug:%s'%self.pdb_window.xid)
            #self.window_instance = self.window.window
            self.help_x11 = self.help.realize_help()
            #self.x11_window = self.get_x11()os.geteuid()
        else:
            self.help.activate_help()
            #self.help.reshow()
            #self.help.toolbox.set_current_page(self.panes['HELP']
    """
    def get_x11(self):
        home_model = shell.get_model()
        activity = home_model.get_active_activity()
        if activity and activity.get_window():
            
            return activity.get_window().activate(1)
        else:
            return None
    """
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
                self.debug_dict['child_path'] = ''
                local = self.debug_dict.copy()
                pickle.dump(local,fd,pickle.HIGHEST_PROTOCOL)
            except IOError:
                _logger.debug('get_config -- Error writing pickle file %s'
                              %os.path.join(self.debugger_home,'pickl'))
        finally:
            fd.close()
        object_id = self.debug_dict.get('jobject_id','')
        if False: #object_id == '':
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
                self.confirmation_alert(_('Continue even though stored checksum does not match current checksum'),
                           _('CAUTION: The program in the playpen may have been changed.'),
                           self.startup_continue)
        
    def startup_continue(self,alert,response):
        self.setup_new_activity()
        
    def save_editor_status(self):
        if self.editor.get_n_pages() == 0: return
        current_page = self.editor.get_current_page()
        edit_files = []
        for i in range(self.editor.get_n_pages()):
            page = self.editor.get_nth_page(i)
            if isinstance(page,sourceview_editor.GtkSourceview2Page):
                _logger.debug('updating debug_dict with %s' % page.fullPath)
                edit_files.append([page.fullPath, page.get_iter().get_line()])
        self.debug_dict[os.path.basename(self.child_path)] = edit_files
        self.debug_dict[os.path.basename(self.child_path)+'-page'] = current_page
    
    def remember_line_no(self,fullPath,line):
        activity_name = self.glean_file_id_from_fullpath(fullPath)
        if activity_name:         
            self.debug_dict[activity_name] = line
        _logger.debug('remembering id:%s at line:%s'%(activity_name,line,))
        
    def glean_file_id_from_fullpath(self,fullPath):
        """use folder name of activity as namespace for filename"""
        folder_list = fullPath.split('/')
        activity_name = ''
        for folder in folder_list:
            if folder.find('.activity') >-1:
                activity_name = folder
        i = folder_list.index(activity_name)
        ret = '/'.join(folder_list[i:])
        _logger.debug('file_id:%s'%ret)
        return ret
    
    def get_remembered_line_number(self,fullPath):
        activity_name = self.glean_file_id_from_fullpath(fullPath)
        if activity_name:
            return self.debug_dict.get(activity_name)
            
    def put_config(self):
        if self.child_path:
            #self.debug_dict['tree_md5'] = self.md5sum_tree(self.child_path)
            self.debug_dict['child_path'] = self.child_path 
        try:
            fd = open(os.path.join(self.debugger_home,'pickl'),'wb')
            local = self.debug_dict.copy()
            pickle.dump(local,fd,pickle.HIGHEST_PROTOCOL)
        except IOError:
            _logger.debug('put_config routine Error writing pickle file %s'
                          %os.path.join(self.debugger_home,'pickl'))
            return
        finally:
            fd.close()
        #self.log_dict(self.debug.dict,'put config debug_dict contents:)
            
    def sugar_version(self):
        cmd = 'rpm -q sugar'
        reply,err = self.command_line(cmd)
        if reply and reply.find('sugar') > -1:
            version = reply.split('-')[1]
            version_chunks = version.split('.')
            release_holder = reply.split('-')[2]
            release = release_holder.split('.')[0]
            return (int(version_chunks[0]),int(version_chunks[1]),int(version_chunks[2]),int(release),)
        return ()

class Icon_Panel(gtk.Window):

    def __init__(self, icon):
        gtk.Window.__init__(self)

        self.set_decorated(False)
        self.set_resizable(False)
        self.set_type_hint(gtk.gdk.WINDOW_TYPE_HINT_DIALOG)

        self.set_border_width(0)

        self.props.accept_focus = False

        #Setup estimate of width, height
        w, h = gtk.icon_size_lookup(gtk.ICON_SIZE_LARGE_TOOLBAR)
        self._width = w
        self._height = h

        self.connect('size-request', self._size_request_cb)

        screen = self.get_screen()
        screen.connect('size-changed', self._screen_size_changed_cb)

        self._button = gtk.Button()
        self._button.set_relief(gtk.RELIEF_NONE)

        self._icon = Icon( icon_size=gtk.ICON_SIZE_LARGE_TOOLBAR)
        self._button.add(self._icon)

        self._button.show()
        self.add(self._button)
        _logger.debug('completed init of icon_panel')

    def connect_button_press(self, cb):
        self._button.connect('button-press-event', cb)

    def _reposition(self):
        x = gtk.gdk.screen_width() - self._width
        self.move(x, 347)

    def _size_request_cb(self, widget, req):
        self._width = req.width
        self._height = req.height
        self._reposition()

    def _screen_size_changed_cb(self, screen):
        self._reposition()
        
