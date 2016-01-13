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

import os
import shutil
import time
from gettext import gettext as _

import project_glade

#major packages
from gi.repository import Gtk
from gi.repository import Gdk
from gi.repository import GdkPixbuf

#sugar stuff
from sugar3.graphics.toolbutton import ToolButton
from sugar3.graphics.icon import Icon
from sugar3.datastore import datastore

#pydebug stuff
from filetree import FileTree
from project import ProjectFunctions

from pydebug_logging import _logger

#colors for the playpen side of the project page
PROJECT_FG = '#990000'
PROJECT_BASE = "#fdd99b"
PROJECT_BG = '#FFFFCC'


class ProjectGui(ProjectFunctions):

    def __init__(self, activity):
        self._activity = activity
        self.file_pane_is_activities = False
        self.manifest_class = None
        self.journal_class = None

        #establish the glade pydebug connection
        self.connect_journal()

        #disable the change callbacks on the activity.info panel
        self.ignore_changes = True

        #set up the toolbar
        project_run = ToolButton(stock_id=Gtk.STOCK_MEDIA_FORWARD)
        project_run.set_icon_widget(None)
        project_run.set_tooltip(_('Start Debugging'))
        project_run.connect('clicked', self._activity.project_run_cb)
        project_run.add_accelerator('clicked',self._activity.accelerator, ord('G'), Gdk.ModifierType.CONTROL_MASK, Gtk.AccelFlags.VISIBLE)
        #project_run.props.accelerator = '<Ctrl>C'
        project_run.show()

        separator = Gtk.SeparatorToolItem()
        separator.set_draw(False)
        separator.set_expand(True)
        separator.show()

        stop_button = ToolButton('activity-stop')
        stop_button.set_tooltip(_('Stop'))
        stop_button.props.accelerator = '<Ctrl>Q'
        stop_button.connect('clicked', self.__stop_clicked_cb)
        stop_button.show()

        projectbar = Gtk.Toolbar()
        projectbar.show_all()
        projectbar.insert(project_run, -1)
        projectbar.insert(separator, -1)
        projectbar.insert(stop_button, -1)
        
        self.projectbar = projectbar
        
    def __stop_clicked_cb(self, button):
        self._activity.py_stop()
        
    def get_editor(self):
        raise NotImplimentedError
        
    def get_activity(self):
        raise NotImplimentedError
        
    def get_activity_toolbar(self):
        raise NotImplimentedError

    def get_projectbar(self):
        return self.projectbar

    def _get_project_canvas(self):
        #initialize the link between program and the glade XML file
        self.project_win_toplevel = project_glade.toplevel()
        self.contents = self.project_win_toplevel.contents
        self.contents.unparent()
        return self.contents
    
    def setup_project_page(self):
        ## FIXME

        self.activity_treeview = self.project_win_toplevel.file_system
        ##self.activity_window = FileTree(self, self.activity_treeview,self.wTree)
        #activity_dir = os.path.dirname(self._activity.sugar_bundle_path)
        #self.activity_window.set_file_sys_root(activity_dir)
        #self.activity_window.set_file_sys_root('/usr/share/activities', append = True)

        self.examples_treeview = self.project_win_toplevel.examples
        ##self.examples_window = FileTree(self._activity, self.examples_treeview,self.wTree)
        ##self.examples_window.set_file_sys_root(os.path.join (self._activity.sugar_bundle_path, 'examples'))
        self.journal_treeview = self.project_win_toplevel.journal
        ##self.journal_class = DataStoreTree(self._activity, self.journal_treeview, self.wTree)

        ##if self.journal_class:
        ##    _logger.debug('journal class object created')

        self.connect_project_info()  #make connections to signals from buttons
        self.activity_toggled_cb(None)

        self.icon_type = self.project_win_toplevel.icon_outline
        model = Gtk.ListStore(str, str)
        model.append(["icon_circle", _('Circle')])
        model.append(['icon_square', _('Square')])
        model.append(['icon_diamond', _('Diamond')])
        model.append(['icon_star', _('Star')])

        cell = Gtk.CellRendererText()
        self.icon_type.set_model(model)
        self.icon_type.pack_start(cell, False)
        self.icon_type.add_attribute(cell, 'text', 1)
        self.icon_type.set_active(self._activity.debug_dict.get('icon_active', 1))

        if self._activity.child_path and self._activity.child_path.endswith('.activity') and os.path.isdir(self._activity.child_path):
            self.setup_new_activity()

        self.activity_data_changed = False

    #first connect the glade xml file to the servicing call backs
    def connect_project_info(self,  wTree=None):
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

        ## Fixme
        ##self.wTree.signal_autoconnect(mdict)

        ## FIXME
        ##button = self.wTree.get_object('delete_file')
        ##map = button.get_colormap()
        ##color = map.alloc_color(PROJECT_FG)
        ##style = button.get_style().copy()
        ##style.bg[Gtk.StateType.NORMAL] = color
        ##button.set_style(style)

        ##button = self.wTree.get_object('clear')
        ##button.set_style(style)

        ##button = self.wTree.get_object('help')
        ##button.set_style(style)

        ##button = self.wTree.get_object('create_icon')
        ##button.set_style(style)

        ##button = self.wTree.get_object('icon_outline')
        ##button.set_style(style)

    def connect_journal(self, wTree=None):
        mdict = {
            'from_journal_clicked_cb': self.load_from_journal_cb,
            'to_journal_clicked_cb': self.save_to_journal_cb,
        }

        ##self.wTree.signal_autoconnect(mdict)

    def load_from_journal_cb(self,button):
        selection = self.journal_treeview.get_selection()
        (model, iter) = selection.get_selected()

        if iter == None:
            self.parent.util.alert(_('Must select Journal item to Load'))
            return

        object_id = model.get(iter, 9)
        _logger.debug('object id %s from journal' % object_id)
        self.try_to_load_from_journal(object_id)

    def save_to_journal_cb(self,button):
        if self.activity_data_changed:
            self._keep_activity_info(None)

        self.write_binary_to_datastore()

    def name_changed_cb(self, widget, event):
        if self.ignore_changes:
            return

        self.activity_data_changed = True
        name = widget.get_text()

        #make a suggestion for module if it is blank
        widget_field = self.project_win_toplevel.module
        module = widget_field.get_text()
        if module == '' or module == 'untitled':
            widget_field.set_text(name.lower())

        #make a suggestion for class if it is blank
        widget_field = self.project_win_toplevel._class
        myclass = widget_field.get_text()
        if myclass == '':
            widget_field.set_text('sugar_subclass')

        #make a suggestion for bundle_id if it is blank
        widget_field = self.project_win_toplevel.bundle_id
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
        self._activity.debug_dict['icon_active'] = i
                
    def create_icon_cb(self,widget):
        self.activity_data_changed = True
        #get the two characters and substitute them in the proper svg template
        chrs_entry = self.project_win_toplevel.icon_chr
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
        self.icon_basename = self._activity.activity_dict.get('bundle_id','dummy').split('.')[-1] + \
                '_' + chars + '_' + self.icon_outline[5:6]
        self._activity.activity_dict['icon_base'] = os.path.join(self._activity.child_path,'activity',self.icon_basename)
                        
        target =  self._activity.activity_dict['icon_base'] + '.svg'
        if self.last_icon_file:
            os.unlink(self.last_icon_file)
            self.last_icon_file = None
        try:
            _file = file(target, 'w+')
            _file.write(icon_str)
            _file.close()
        except IOError, e:
            msg = _("I/O error:") + str(e)
            _logger.error(msg)
        except Exception, e:
            msg = "Unexpected error:%s"%e
            _logger.error(msg)
        if _file:
            self.last_icon_file = target
            _file.close()
        self._activity.activity_dict['icon'] = self._activity.activity_dict.get('name')
        self._activity.update_metadata()
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
        but = self.project_win_toplevel.to_activities
        to_what = self.project_win_toplevel.file_toggle
        window_label = self.project_win_toplevel.file_system_label
        if self.file_pane_is_activities == True:
            to_what.set_label('Installed_')
            but.show()
            #display_label = self.storage[:18]+' . . . '+self.storage[-24:]
            display_label = 'PyDebug SHELF storage:'
            ##self.activity_window.set_file_sys_root(self._activity.storage)
            window_label.set_text(display_label)

        else:
            to_what.set_label('shelf')
            but.hide()
            activity_dir = os.path.dirname(self._activity.sugar_bundle_path)
            ##self.activity_window.set_file_sys_root(activity_dir)
            ##self.activity_window.set_file_sys_root('/usr/share/activities', append = True)
            ##self.activity_window.set_file_sys_root('/usr/share/sugar/activities', append = True)
            button = self.project_win_toplevel.from_activities
            button.set_tooltip_text(_('Copy the selected Activity or file to the debug workplace'))
            window_label.set_text('INSTALLED ACTIVITIES:')

        self.file_pane_is_activities =  not self.file_pane_is_activities
    
    def to_home_clicked_cb(self,widget):
        _logger.debug('Entered to_home_clicked_cb')
        if self.activity_data_changed:
            self._keep_activity_info(None)
        self._to_home_dest = os.path.join(self.storage,self._activity.activity_dict['name']+'.activity')
        if False: #os.path.isdir(self._to_home_dest):
            target_md5sum = self._activity.util.md5sum_tree(self._to_home_dest)
            if target_md5sum != self._activity.debug_dict.get('tree_md5',''):
                self._activity.util.confirmation_alert(_('OK to delete/overwrite %s?'%self._to_home_dest),
                                        _('This destination has been changed by another application'),
                                        self._to_home_cb)
            return
        self._to_home_cb(None, Gtk.ResponseType.OK)
            
    def _to_home_cb(self, alert, response_id):
        """write playpen tree to writeable storage, and USB/SD if pydebug folder exists
        in root directory"""
        if alert != None:
            self.remove_alert(alert)

        if response_id is Gtk.ResponseType.OK:
            #remove any embeded shell breakpoints
            self.get_editor().clear_embeds()
            _logger.debug('removing tree, and then copying to %s'%self._to_home_dest)

            if os.path.isdir(self._to_home_dest):
                shutil.rmtree(self._to_home_dest, ignore_errors=True)

            shutil.copytree(self._activity.child_path,self._to_home_dest)
            self._activity.util.set_permissions(self._to_home_dest)
            #mark the md5 as saved
            self.save_tree_md5(self._activity.child_path)
            #redraw the treeview
            self.activity_window.set_file_sys_root(self.storage)
            self.activity_window.position_to(self._to_home_dest)

            #write snapshot of source tree to removable media if /pydebug directory exists
            self.removable_backup()

    def from_home_clicked_cb(self,widget):
        _logger.debug('Entered from_home_clicked_cb')
        selection=self.activity_treeview.get_selection()
        (model,iter)=selection.get_selected()
        if iter == None:
            self._activity.util.alert(_('Must select File or Directory item to Load'))
            return
        fullpath = model.get(iter,4)[0]
        if os.path.isdir(fullpath):
            if fullpath.endswith('.activity'):
                if fullpath.startswith(self._activity.activity_playpen): #just re-initialize the project
                    self._activity.debug_dict['source_tree'] = fullpath
                    self._activity.child_path = fullpath
                    self.setup_new_activity()
                    return
                self.load_activity_to_playpen(fullpath)
            else: #this is a file folder, just copy it to project
                source_basename = os.path.basename(fullpath)
                dest = os.path.join(self._activity.child_path,source_basename)
                self.copy_tree(fullpath,dest)
        else:
            #selected is a file, just copy it into the current project
            basename = os.path.basename(fullpath)
            dest = os.path.join(self._activity.child_path,basename)
            if os.path.isfile(dest):
                #change name if necessary to prevent collision 
                basename = self._activity.util.non_conflicting(self._activity.child_path,basename)
            shutil.copy(fullpath,dest)
            self.manifest_point_to(dest)
            
    def from_examples_clicked_cb(self,widget):
        selection=self.examples_treeview.get_selection()
        (model,iter)=selection.get_selected()
        if iter == None:
            self._activity.util.alert(_('Must select File or Directory item to Load'))
            return
        fullpath = model.get(iter,4)[0]
        _logger.debug('Entered from_examples_clicked_cb. source fullpath: %s'%fullpath)
        self._load_to_playpen_source = fullpath
        if fullpath.endswith('.activity'):
            self.load_activity_to_playpen(fullpath)
            return
        """
        if fullpath.endswith('.xo'):
            try:
                self._bundler = ActivityBundle(fullpath)
            except:
                self._activity.util.alert('Error:  Malformed Activity Bundle')
                return    
            self._new_child_path = os.path.join(self._activity.activity_playpen,self._bundler._zip_root_dir)
            #check to see if current activity in playpen needs to be saved, and load new activity if save is ok
            self._load_playpen(fullpath, iszip=True)
            return
        if fullpath.endswith('.tar.gz'):    
            self._new_child_path = os.path.join(self._activity.activity_playpen,self._bundler._zip_root_dir)
            #check to see if current activity in playpen needs to be saved, and load new activity if save is ok
            self._load_playpen(fullpath, istar=True)
            return
        #if os.path.isdir(fullpath):
        self._new_child_path = self._activity.child_path
        self._load_playpen(fullpath)
        """
        #is this is a file folder, just copy it to project
        if os.path.isdir(fullpath):
            basename = os.path.basename(fullpath)
            dest = os.path.join(self._activity.child_path, basename)
            self.copy_tree(fullpath,dest)
            _logger.debug('copying tree from %s to %s'%(fullpath, dest, ))
        else:
            #selected is a file, just copy it into the current project
            basename = os.path.basename(fullpath)
            dest = os.path.join(self._activity.child_path,basename)
            if os.path.isfile(dest):
                #change name if necessary to prevent collision 
                basename = self._activity.util.non_conflicting(self._activity.child_path,basename)
            shutil.copy(fullpath, os.path.join(self._activity.child_path,basename))
        self.manifest_point_to(os.path.join(self._activity.child_path,basename))

   
    #def filetree_activated(self):
    #_logger.debug('entered pydebug filetree_activated')
    
    def _keep_activity_info(self,widget):
        """ Act on the changes made to the screen project data fields
        changing the name of the activity turns out to be a big deal --
        it will be done frequently in order to branch off an experimental branch
        and it requires changing the root path, and therefore all the open edit files which
        include the old root name in the path.  There's also the meta- that has to be updated.
        So let's deal with writing the activity.info file first
        """
        _logger.debug('in keep_activity_activity.info')
        name_widget = self.project_win_toplevel.name
        name = name_widget.get_text()
        old_name =  self._activity.activity_dict['name']
        self.old_icon = self._activity.activity_dict.get('icon')
        self._activity.activity_dict['name'] = name
                
        name_widget = self.project_win_toplevel.version
        self._activity.activity_dict['version'] = name_widget.get_text()
            
        name_widget = self.project_win_toplevel.version
        self._activity.activity_dict['version'] = name_widget.get_text()
            
        name_widget = self.project_win_toplevel.bundle_id
        self._activity.activity_dict['bundle_id'] = name_widget.get_text()
            
        name_widget = self.project_win_toplevel.module
        self._activity.activity_dict['module'] = name_widget.get_text()
            
        name_widget = self.project_win_toplevel._class
        self._activity.activity_dict['class'] = name_widget.get_text()
            
        self._activity.update_metadata()
        self.write_activity_info()
        
        #now the to the more difficult part -- is renaming required?       
        new_name = name + '.activity'
        new_child_path = os.path.join(self._activity.activity_playpen,new_name)
        if name.startswith('untitled'):
            self._activity.util.alert(_("Activities must be given a new and unique name"))
            return
        if old_name != self._activity.activity_dict.get('name'):
            #check to see if the folder already exists, if so change its name
            _logger.debug('need to make decision to move or create child base:%s. new_name:%s'%\
                          (os.path.basename(self._activity.child_path), new_name))
            if os.path.isdir(self._activity.child_path) and \
                    os.path.basename(self._activity.child_path) !=  new_name:
                self.get_editor().remove_all()
                #self._activity.init_activity_dict()

                cmd = 'mv %s %s'%(self._activity.child_path,new_child_path)
                result,status = self._activity.util.command_line(cmd)
                if status != 0:
                    _logger.error('tried to rename %s directory unsuccessfully'%self._activity.child_path)
                    return
                self._activity.child_path = new_child_path
                self.setup_new_activity()
        """
        else: #need to create the directories
            if not os.path.isdir(os.path.join(new_child_path,'activity')):
                os.makedirs(os.path.join(new_child_path,'activity'))
        """        
        
    def write_activity_info(self):
        #write the activity.info file
        #if not self.activity_data_changed: return
        filen = os.path.join(self._activity.child_path,'activity','activity.info')
        _logger.debug('write_activity_info to %s'%filen)
        if os.path.isfile(filen): #set aside the info file encountered
            new_filename = self._activity.util.non_conflicting(os.path.join(self._activity.child_path,'activity'),'activity.info')
            _logger.debug('decided to move %s to %s'%(filen,new_filename))
            cmd = 'mv %s %s'%(filen,new_filename)
            results,status = self._activity.util.command_line(cmd)    
        self.write_new_activity_info(filen)

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
                fdw.write('name = %s\n'%self._activity.activity_dict.get('name'))
                fdw.write('bundle_id = %s\n'%self._activity.activity_dict.get('bundle_id'))
                fdw.write('activity_version = %s\n'%self._activity.activity_dict.get('version'))
                fdw.write('show_launcher = yes\n')
                icon = self._activity.activity_dict.get('icon')
                if self.icon_basename:
                    icon_nibble = self.icon_basename
                else:
                    icon_nibble = os.path.basename(self.old_icon).split('.')[0]
                fdw.write('icon = %s\n'%icon_nibble)
                if self._activity.activity_dict.get('class','') == '':
                    if self._activity.activity_dict.get('module'):
                        fdw.write('exec = %s\n'%self._activity.activity_dict.get('module'))
                    else:
                        fdw.write('exec = %s\n'%self._activity.activity_dict.get('name'))
                else:
                    fdw.write('class = %s.%s\n'%(self._activity.activity_dict.get('module'),
                                                self._activity.activity_dict.get('class')))                       
                fdw.close()
        except Exception, e:
            _logger.debug('write new activity info file exception %s'%e)
            raise e
                
    def delete_file_cb(self,widget):
        selection=self.manifest_treeview.get_selection()
        (model,iter)=selection.get_selected()
        if iter == None:
            self._activity.util.alert(_('Must select a File or Folder to delete'))
            return
        fullpath = model.get(iter,4)[0]
        _logger.debug(' delete_file_clicked_cb. File: %s'%(fullpath))
        self.delete_file_storage = fullpath
        if os.path.isdir(fullpath):
            self._activity.util.confirmation_alert(_('Would you like to continue deleting %s?'%os.path.basename(fullpath)),
                                    _('CAUTION: You are about to DELETE a FOLDER!!'),self.do_delete_folder)
            return
        self._activity.util.confirmation_alert(_('Would you like to continue deleting %s?'%os.path.basename(fullpath)),
                                _('ABOUT TO DELETE A FILE!!'),self.do_delete)
            
    def do_delete(self, alert, response):
        _logger.debug('doing delete of: %s'%self.delete_file_storage)
        self.manifest_point_to(self.delete_file_storage)
        os.unlink(self.delete_file_storage)
        self.manifest_class.set_file_sys_root(self._activity.child_path)
        self.manifest_class.position_recent()
     
    def do_delete_folder(self, alert, response):
        _logger.debug('doing delete of: %s'%self.delete_file_storage)
        self.manifest_point_to(self.delete_file_storage)
        shutil.rmtree(self.delete_file_storage)
        self.manifest_class.set_file_sys_root(self._activity.child_path)
        self.manifest_class.position_recent()
     
    def clear_clicked_cb(self, button):
        #if necessary clean up contents of playpen
        #has the tree md5 changed?
        if not self._activity.debug_dict['tree_md5'] == '':            
            tree_md5 = self._activity.util.md5sum_tree(self._activity.child_path)
            if tree_md5 != self._activity.debug_dict['tree_md5']:
                action_prompt = _('Select OK to abandon changes to ') + \
                            os.path.basename(self._activity.child_path)
                self._activity.util.confirmation_alert(action_prompt, \
                        _('Changes have been made to the PyDebug work area.'), \
                        self.continue_clear_clicked_cb)
                return        
        self.continue_clear_clicked_cb(None, None)

    def continue_clear_clicked_cb(self, alert, confirmation):
        self._unload_playpen()
        new_tree = os.path.join(self._activity.activity_playpen,'untitled.activity')
        if self._activity.child_path == new_tree:
            root = self.storage            
        else:
            self.get_editor().remove_all()
            self._activity.init_activity_dict()
            if os.path.isdir(new_tree):
                shutil.rmtree(new_tree,ignore_errors=True)
            act_path = os.path.join(new_tree,'activity')
            if not os.path.isdir(act_path):
                os.makedirs(act_path)
            self._activity.child_path = new_tree
            self._activity.activity_dict['child_path'] = new_tree
            src = os.path.join(self._activity.sugar_bundle_path,'setup.py')
            shutil.copy(src,new_tree)
            root = self._activity.activity_playpen
        if self.manifest_class:
            self.manifest_class.set_file_sys_root(root)        
        self.display_current_project()
        
    def  setup_new_activity(self):
        _logger.debug('in setup_new_activity. child path before chdir:%s'%self._activity.child_path)
        if self._activity.child_path == None or not os.path.isdir(self._activity.child_path):
            return
        os.chdir(self._activity.child_path)
        #cd_cmd = 'cd %s'%self._activity.child_path
        #self._activity.feed_virtual_terminal(0,cd_cmd)
        self.read_activity_info(self._activity.child_path)
        self._activity.debug_dict['child_path'] = self._activity.child_path
        self.display_current_project()
        
        #set the current working directory for debugging in the child context
        cwd_cmd = 'cd %s\n'%(self._activity.child_path,)
        self._activity.feed_virtual_terminal(0,cwd_cmd)
        self._activity.feed_virtual_terminal(1,cwd_cmd)
        alias_cmd = 'alias pp="cd %s"\n'%(self._activity.child_path,)
        self._activity.feed_virtual_terminal(1,alias_cmd)
        self._activity.feed_virtual_terminal(0,alias_cmd)
        
        #add the bin directory to path
        if self._activity.child_path not in os.environ['PATH'].split(':'):
            os.environ['PATH'] = os.path.join(self._activity.child_path,'bin') + ':' + os.environ['PATH']
            
        #make a link to the playpen if it doesn't conflict with existing diredtory
        link_dir = os.path.join('/home/olpc/Activities',
                            os.path.basename(self._activity.child_path))
        if not os.path.isdir(link_dir):
            os.symlink(self._activity.child_path,link_dir)
        
        #calculate and store the md5sum
        self._activity.debug_dict['tree_md5'] = self._activity.util.md5sum_tree(self._activity.child_path)
        
        #if this is a resumption, open previous python files and position to previous location
        if self._activity.debug_dict.get(os.path.basename(self._activity.child_path)):
            for file_id, line in self._activity.debug_dict.get(os.path.basename(self._activity.child_path)):
                filenm = os.path.join(self._activity.activity_playpen,file_id)
                if os.path.isfile(filenm):
                    self.get_editor().load_object(filenm,os.path.basename(filenm)) 
                    self.get_editor().position_to(filenm,line)
                current_page = self._activity.debug_dict.get(os.path.basename(self._activity.child_path)+'-page',0) 
                self.get_editor().edit_notebook.set_current_page(current_page)
            self.get_editor().load_breakpoints = False
        else:             
            #find largest python files for editor
            list = [f for f in os.listdir(self._activity.child_path) if f[0] <> '.']
            #list = self.manifest_class.get_filenames_list(self._activity.child_path)
            if not list: return
            sizes = []
            for f in list:
                full_path = os.path.join(self._activity.child_path,f)
                if not f.endswith('.py'):continue
                size = self.manifest_class.file_size(full_path)
                sizes.append((size,full_path,))
                #_logger.debug('python file "%s size %d'%(f,size))
            for s,f in sorted(sizes,reverse=True)[:5]:
                self.get_editor().load_object(f,os.path.basename(f)) 
            self.get_editor().set_current_page(0)           
     
    def get_manifest_class(self):
        return self.manifest_class
        
    def display_current_project(self):
        global start_clock            
        #try to colorize the playpen

        ## FIXME:
        ##pp = self.wTree.get_object('playpen_event_box')
        ##map = pp.get_colormap()
        ##color = map.alloc_color(PROJECT_BG)
        ##style = pp.get_style().copy()
        ##style.bg[Gtk.StateType.NORMAL] = color
        ##pp.set_style(style)

        ##self.manifest_treeview = self.wTree.get_object('manifest')
        ##map = self.manifest_treeview.get_colormap()
        ##color = map.alloc_color(PROJECT_BASE)
        ##style = self.manifest_treeview.get_style().copy()
        ##style.bg[Gtk.StateType.NORMAL] = color
        ##color = map.alloc_color(PROJECT_BASE)
        ##style.base[Gtk.StateType.NORMAL] = color
        ##self.manifest_treeview.set_style(style)
        
        if self.manifest_class == None:
            self.manifest_class = FileTree(self, self.manifest_treeview, self.project_win_toplevel)

        self.manifest_class.set_file_sys_root(self._activity.child_path)

        #disable the on change callbacks
        self.ignore_changes = True

        ##name = self.wTree.get_object('name')
        #map = name.get_colormap()
        ##color = map.alloc_color(PROJECT_BASE)
        ##style = name.get_style().copy()
        ##style.base[Gtk.StateType.NORMAL] = color
        ##name.set_style(style)
        ##name.set_text(self._activity.activity_dict.get('name',''))

        ##version = self.wTree.get_object('version')
        ##version.set_style(style)
        ##version.set_text(self._activity.activity_dict.get('version',''))

        ##bundle = self.wTree.get_object('bundle_id')
        ##bundle.set_style(style)
        ##bundle.set_text(self._activity.activity_dict.get('bundle_id',''))

        pyclass = self.project_win_toplevel._class
        ##pyclass.set_style(style)
        ##pyclass.set_text(self._activity.activity_dict.get('class',''))
        self.pdbclass = pyclass

        pymodule = self.project_win_toplevel.module
        ##pymodule.set_style(style)
        ##pymodule.set_text(self._activity.activity_dict.get('module',''))
        self.pdbmodule = pymodule.get_text()

        pyicon = self.project_win_toplevel.icon_chr
        ##pyicon.set_style(style)
        pyicon.set_text(self._activity.activity_dict.get('icon_chr',''))

        #re-enable the on change callbacks
        self.ignore_changes = False

    def manifest_point_to(self,fullpath):
        if self.child_path:
            self.manifest_class.set_file_sys_root(self.child_path)

        else:
            self.manifest_class.set_file_sys_root(self._activity.activity_playpen)

        self.manifest_class.position_to(fullpath)


class DataStoreTree():

    column_names = [_('Name'), _('Size'), _('Last Changed')]

    def __init__(self, parent, widget=None, win=None):
        self.parent = parent
        self._activity = parent
        self.treeview = widget
        self.project_win_toplevel = win
        self.init_model()
        self.init_columns()
        self.limit=10
        self.journal_page_size =10
        self.journal_page_num = 0
        self.journal_max = 0
        self.new_directory()

    def init_model(self):
        #plan for the store: pixbuf,title,size,last-updated,tooltip,jobject-id
        self.journal_model = Gtk.TreeStore(GdkPixbuf.Pixbuf, str, str, str, str, str, str, str, str, str, str)
        if not self.treeview:
            self.treeview = Gtk.TreeView()

        self.treeview.set_model(self.journal_model)
        self.treeview.show()
        #the following 3 lines were probably disabled because earlier sugar complained
        #search for TOOLTIP to find problem areas
        #self.treeview.connect('query-tooltip',self.display_tooltip)
        self.treeview.set_tooltip_column(10)
        self.treeview.has_tooltip = True
        self.show_hidden = False

    def show_tooltip(self, widget, event, tooltips, cell, emptytext='no information'):
        """
        If emptyText is None, the cursor has to enter widget from a side
        that contains an item, otherwise no tooltip will be displayed. """

        try:
            (path, col, x, y) = widget.get_path_at_pos(int(event.x), int(event.y))
            it = widget.get_model().get_iter(path)
            value = widget.get_model().get_value(it, cell)
            widget.set_tooltip_text(str(value))
            tooltips.enable()

        except:
            widget.set_tooltip_text(emptytext)

    def init_columns(self):
        col = Gtk.TreeViewColumn()
        col.set_title(self.column_names[0])

        render_pixbuf = Gtk.CellRendererPixbuf()
        col.pack_start(render_pixbuf, expand=False)
        col.add_attribute(render_pixbuf, 'pixbuf', 0)

        render_text = Gtk.CellRendererText()
        col.pack_start(render_text, expand=True)
        col.add_attribute(render_text, 'text', 1)
        col.set_fixed_width(20)
        self.treeview.append_column(col)

        cell = Gtk.CellRendererText()
        col = Gtk.TreeViewColumn(self.column_names[1], cell)
        col.add_attribute(cell, 'text', 2)
        self.treeview.append_column(col)

        cell = Gtk.CellRendererText()
        col = Gtk.TreeViewColumn(self.column_names[2], cell)
        col.add_attribute(cell, 'text', 3)
        self.treeview.append_column(col)
           
    def get_datastore_list(self, next=False):
        dslist = []
        self.journal_model.clear()
        ds_list = []
        num_found = 0
        mime_list = [self._activity.MIME_TYPE, self._activity.MIME_ZIP]

        #build 650 doesn't seem to understand correctly the dictionary with a list right hand side
        info = self._activity.util.sugar_version()
        if len(info) > 0:
            (major,minor,micro,release) = info
            _logger.debug('sugar version major:%s minor:%s micro:%s release:%s' % info)

        else:
            _logger.debug('sugar version failure')
            minor = 70

        try:
            if minor > 80:
                (ds_list,num_found) = datastore.find({'mime_type': mime_list})

            else:
                (results,count) = datastore.find({'mime_type': self._activity.MIME_TYPE})
                ds_list.extend(results)
                num_found += count            
                (results,count) = datastore.find({'mime_type': self._activity.MIME_ZIP})
                ds_list.extend(results)
                num_found += count            

        except Exception,e:
            _logger.exception('datastore error %s'%e)
            return dslist
        
        #sort the list around mtime
        ds_list = sorted(ds_list, key=lambda entry: entry.get_metadata().get('mtime'), reverse=True)
        if num_found < self.limit:
            self.journal_max = self.journal_page_num * self.journal_page_size + num_found

        _logger.debug( 'datastoretree-get_datastore_list: count= %s' % num_found)

        keys = ('title', 'size', 'timestamp', 'activity', 'package', 'mime_type', 'file_path')
        for jobject in ds_list:
            itemlist = [None]
            datastoredict=jobject.get_metadata().get_dictionary() #get the property dictionary
            src = jobject.get_file_path() #returns the full path of the file
            datastoredict['object_id'] = jobject.object_id
            
            if False: #if  src null, there is no file related to this meta data
                jobject.destroy()
                continue	#go get the next iterations

            #add in the info that we intend to use
            if src:
                info = os.stat(src) #get the directory information about this file
                datastoredict['size'] = info.st_size

            else:
                 datastoredict['size'] = 0               

            datastoredict['file_path'] = src
            for key in keys:
                if datastoredict.has_key(key):
                    if key == 'timestamp':
                        pkg = time.strftime('%Y-%m-%d %H:%M:%S',time.gmtime(float(datastoredict[key])))

                    elif key == 'title':
                        pkg = datastoredict[key][:18]

                    else:
                        pkg = '%s'%(datastoredict[key])

                else:
                    pkg = ''

                itemlist.append(pkg)

            itemlist.append(datastoredict['title'])
            itemlist.append(jobject.object_id)
            text = 'Mime_type: %s, Journal ID: %s, Bundle: %s' % (datastoredict.get('mime_type',''),
                                                                  datastoredict.get('object_id',''),
                                                                  datastoredict.get('package',''))
            itemlist.append(text)
            #_logger.debug('journal tooltip:%s'%text)
            dslist.append(itemlist)
            jobject.destroy()

        return dslist

    def new_directory(self,piter = None, next=True):
        journal_list = self.get_datastore_list(next)
        for journal_selected_data in journal_list:
            appended_iter = self.journal_model.append(piter, journal_selected_data )
            model=self.journal_model
            appended_path = model.get_path(appended_iter)
       
    def file_pixbuf(self, filename):
        folderpb = self.get_icon_pixbuf('STOCK_DIRECTORY')
        filepb = self.get_icon_pixbuf('STOCK_FILE')

        if os.path.isdir(filename):
            pb = folderpb

        else:
            pb = filepb

        return pb

    def get_icon_pixbuf(self, stock):
        return self.treeview.render_icon(stock_id=getattr(Gtk, stock), size=Gtk.ICON_SIZE_MENU, detail=None)

    def get_treeview(self):
        return self.treeview

    def newer_in_journal_cb(self,button):
        _logger.debug('younger call back')
        self.get_datastore_list(next=False)
        
    def older_in_journal_cb(self,button):
        _logger.debug('older call back')
        self.get_datastore_list(next=True)
        
    def datastore_row_activated_cb(self):
        self.load_from_journal_cb()
    
    def display_tooltip(self, widget,x,y,mode,tooltip):
        _logger.debug('in display_tooltip')
        tooltip.show()
        return True


class Icon_Panel(Gtk.Window):

    def __init__(self, icon):
        Gtk.Window.__init__(self)

        self.set_decorated(False)
        self.set_resizable(False)
        self.set_type_hint(Gdk.WindowTypeHint.DIALOG)

        self.set_border_width(0)

        self.props.accept_focus = False

        #Setup estimate of width, height
        b, w, h = Gtk.icon_size_lookup(Gtk.IconSize.LARGE_TOOLBAR)
        self._width = w
        self._height = h

        self.connect('size-request', self._size_request_cb)

        screen = self.get_screen()
        screen.connect('size-changed', self._screen_size_changed_cb)

        self._button = Gtk.Button()
        self._button.set_relief(Gtk.ReliefStyle.NONE)

        self._icon = Icon(icon_size=Gtk.IconSize.LARGE_TOOLBAR)
        self._button.add(self._icon)

        self._button.show()
        self.add(self._button)

        _logger.debug('completed init of icon_panel')

    def connect_button_press(self, cb):
        self._button.connect('button-press-event', cb)

    def _reposition(self):
        x = Gdk.Screen.width() - self._width
        self.move(x, 347)

    def _size_request_cb(self, widget, req):
        self._width = req.width
        self._height = req.height
        self._reposition()

    def _screen_size_changed_cb(self, screen):
        self._reposition()

