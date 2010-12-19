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
import os, os.path, ConfigParser, shutil, sys
from subprocess import Popen, PIPE

from gettext import gettext as _

#major packages
import gtk
import time
import datetime
import gobject
from fnmatch import fnmatch

#sugar stuff
import sugar.env
from sugar.datastore import datastore
from sugar.graphics.alert import *
import sugar.activity.bundlebuilder as bundlebuilder
#build 650 doesn't include fix_manifest
#import bundlebuilder
from sugar.bundle.activitybundle import ActivityBundle

#following only works in sugar 0.82
#from sugar.activity.registry import get_registry
from sugar.activity.activity import Activity
from sugar import profile

#import logging
from  pydebug_logging import _logger, log_environment, log_dict

class ProjectFunctions:
    
    def __init__(self,activity):
        self._activity = activity
        self._load_to_playpen_source = None

    def get_editor(self):
        raise NotImplimentedError
        
    def write_binary_to_datastore(self):
        """
        Check to see if there is a child loaded.
        then bundle it up and write it to the journal
        lastly serialize the project information and write it to the journal
        """
        if self._activity.child_path == None: return
        dist_dir = os.path.join(self._activity.child_path,'dist')
        try:
            os.rmtree(dist_dir)
        except:
            _logger.debug('failed to rmtree %s'%dist_dir)
        try:
            os.mkdir(dist_dir)
        except:
            _logger.debug('failed to os.mkdir %s'%dist_dir)
        
        #are there changes in edit buffers not flushed to disk?
        self.get_editor().save_all()

        #remove any embeded shell breakpoints
        self.get_editor().clear_embeds()
        
        #create the manifest for the bundle
        manifest_ok = self.write_manifest()
        do_tgz = True
        mime = self._activity.MIME_ZIP
        activity = 'org.laptop.PyDebug'
        #if manifest was successful, write the xo bundle to the instance directory
        if manifest_ok:
            do_tgz = False
            try:                
                #actually write the xo file
                if self._activity.sugar_minor >= 84:
                    config = bundlebuilder.Config(self._activity.child_path)
                    packager = bundlebuilder.XOPackager(bundlebuilder.Builder(config))
                    packager.package()
                    xo_name = config.xo_name
                    source = os.path.join('dist', xo_name)
                else:
                    #how to create the zipped xo file on build 650
                    name = self._activity.activity_dict.get('name','')
                    xo_name = bundlebuilder._get_package_name(name)
                    _logger.debug('zipped xo name:%s current dir: %s'%(xo_name, os.getcwd(),))
                    bundlebuilder.cmd_dist(name, 'MANIFEST')
                    source = xo_name
                    
                dest = os.path.join(self._activity.get_activity_root(),
                                    'instance', xo_name)
                _logger.debug('writing to the journal from %s to %s.'%(source,dest))
                if os.path.isfile(dest):
                    os.unlink(dest)
                try:
                    package = xo_name
                    shutil.copy(source,dest)
                    mime = self._activity.MIME_TYPE
                    activity = self._activity.activity_dict.get('activity','')
                    self.to_removable_bin(source)
                except IOError:
                    _logger.debug('shutil.copy error %d: %s. ',IOError[0],IOError[1])
                    do_tgz = True
                    mime = self._activity.MIME_ZIP
            except Exception, e:
                _logger.exception('outer exception %r'%e)
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
        dsobject.metadata['icon'] = self._activity.activity_dict.get('icon','')
        dsobject.metadata['bundle_id'] = self._activity.activity_dict.get('bundle_id','')
        dsobject.metadata['activity'] = activity
        dsobject.metadata['version'] = self._activity.activity_dict.get('version',1) 
        #calculate and store the new md5sum
        dsobject.metadata['tree_md5'] = self.save_tree_md5(self._activity.child_path)
        self._activity.debug_dict['tree_md5'] = dsobject.metadata['tree_md5']
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
        
    def save_tree_md5(self, path):
        #calculate and store the new md5sum
        self._activity.debug_dict['tree_md5'] = self._activity.util.md5sum_tree(self._activity.child_path)
        return self._activity.debug_dict['tree_md5']

    def removable_backup(self):
        """ if there is a pydebug folder in root directory of a USB or SD, this
        routine will copy the debugee source tree to a folder name which includes
        the datetime
        """
        rs = self.removable_storage()
        _logger.debug('removable storage %r'%rs)
        for dest in rs:
            root = os.path.join(dest,'pydebug')
            if os.path.isdir(root):  #there is a pydebug directory in the root of this device
                today = datetime.date.today()               
                name = self._activity.child_path.split('/')[-1].split(".")[0] + '-' + str(today)
                #change name if necessary to prevent collision 
                basename = self._activity.util.non_conflicting(root,name)
                try:
                    shutil.copytree(self._activity.child_path, os.path.join(root,basename))
                    self._activity.util.set_permissions(os.path.join(root,basename))
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
        """uses shell 'mount' cmd dto get mounted volumes
        needs to be tested on various builds
        """
        cmd = 'mount'
        ret = []
        resp, status = self._activity.util.command_line(cmd)
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
        """ use sugar routines to build a new MANIFEST file """
        IGNORE_DIRS = ['dist', '.git']
        IGNORE_FILES = ['.gitignore', 'MANIFEST', '*.pyc', '*~', '*.bak', 'pseudo.po']
        try:
            os.remove(os.path.join(self._activity.child_path,'MANIFEST'))
        except:
            pass
        dest = self._activity.child_path
        manifest = self.list_files(dest, IGNORE_DIRS, IGNORE_FILES)
        _logger.debug('Writing manifest to %s.'%(dest))
        try:
            """
            config = bundlebuilder.Config(dest)
            b = bundlebuilder.Builder(config)
            b.fix_manifest()
            """
            f = open(os.path.join(self._activity.child_path, "MANIFEST"), "wb")
            for line in manifest:
                f.write(line + "\n")
            f.close()
        except Exception, e:
            _logger.debug('fix manifest error: %s'%(e,))
            return False
        return True

    #following two functions lifted (slight mods) from bundlebuilder build 852
    def fix_manifest(self):

        
        f = open(os.path.join(self._activity.child_path, "MANIFEST"), "wb")
        for line in manifest:
            f.write(line + "\n")

    def list_files(self, base_dir, ignore_dirs=None, ignore_files=None):
        result = []
    
        base_dir = os.path.abspath(base_dir)
    
        for root, dirs, files in os.walk(base_dir):
            if ignore_files:
                for pattern in ignore_files:
                    files = [f for f in files if not fnmatch(f, pattern)]
                    
            rel_path = root[len(base_dir) + 1:]
            for f in files:
                result.append(os.path.join(rel_path, f))
    
            if ignore_dirs and root == base_dir:
                for ignore in ignore_dirs:
                    if ignore in dirs:
                        dirs.remove(ignore)
    
        return result

    def just_do_tar_gz(self):
        """
        tar and compress the child_path tree to the journal
        """
        name = self._activity.child_path.split('/')[-1].split(".")[0]+'.tar.gz'
        os.chdir(self._activity.activity_playpen)
        dest = os.path.join(self._activity.get_activity_root(),'instance',name)
        cmd = 'tar czf %s %s'%(dest,'./'+os.path.basename(self._activity.child_path))
        ans = self._activity.util.command_line(cmd)
        _logger.debug('cmd:%s'%cmd)
        if ans[1]!=0:
            return None
        return dest
        
    def load_activity_to_playpen(self,file_path):
        """loads from a disk tree"""
        self._new_child_path =  os.path.join(self._activity.activity_playpen,os.path.basename(file_path))
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
            self._activity.util.alert(_('This journal item does not appear to be a zipped activity. Package:%s.'%project))
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
                self._activity.util.alert('Error:  Malformed Activity Bundle')
                self.ds.destroy()
                self.ds = None
                return
        else:
            name = project.split('.')[0]
            #self.delete_after_load = os.path.abspath(file_name_from_ds,name)
            iszip = False
            istar = True
        self._new_child_path = os.path.join(self._activity.activity_playpen,name+'.activity')
        self._load_playpen(file_name_from_ds, iszip, istar)
        
    def _load_playpen(self,source_fn, iszip = False, istar=False):
        """entry point for both xo and file tree sources"""
        self._load_to_playpen_source = source_fn
        #need to pass parameters to continuation routine
        self.lp_iszip = iszip
        self.lp_istar = istar
        #if necessary clean up contents of playpen
        #has the tree md5 changed?
        if not self._activity.debug_dict['tree_md5'] == '':            
            tree_md5 = self._activity.util.md5sum_tree(self._activity.child_path)
            if tree_md5 and tree_md5 != self._activity.debug_dict['tree_md5']:
                action_prompt = _('Select OK to abandon changes to ') + \
                            os.path.basename(self._activity.child_path)
                self._activity.util.confirmation_alert(action_prompt, \
                        _('Changes have been made to the PyDebug work area.'), \
                        self.continue_loading_playpen_cb)
                return        
        self.continue_loading_playpen_cb(None, None)
            
    def continue_loading_playpen_cb(self, alert, confirmation):           
        self._unload_playpen()
        iszip = self.lp_iszip
        istar = self.lp_istar
        if self._load_to_playpen_source == None:
            #having done the clearing, just stop
            return
        if iszip:
            self._bundler.install(self._activity.activity_playpen)
            if self.ds: self.ds.destroy()
            self.ds = None
        elif istar:
            dsdict = self.ds.get_metadata()
            project = dsdict.get('package','dummy.tar.gz')
            name = project.split('.')[0]
            dest = os.path.join(self._activity.activity_playpen,project)
            shutil.copy(source_fn,dest)
            os.chdir(self._activity.activity_playpen)
            cmd = 'tar zxf %s'%dest
            _logger.debug('loading tar.gz with cmd %s'%cmd)
            rtn = self._activity.util.command_line(cmd)
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
                dest = os.path.join(self._activity.child_path,basename)
            if  os.path.isdir(dest):
                shutil.rmtree(dest,ignore_errors=True)
            #os.mkdir(dest)
            _logger.debug('dest:%s'%dest)
            _logger.debug('copying tree from %s to %s'%(self._load_to_playpen_source,dest))
            shutil.copytree(self._load_to_playpen_source,dest)
            _logger.debug('returned from copytree')
        elif os.path.isfile(self._load_to_playpen_source):
            source_basename = os.path.basename(self._load_to_playpen_source)
            dest = os.path.join(self._activity.child_path,source_basename)
            shutil.copy(self._load_to_playpen_source,dest)
        self._activity.debug_dict['source_tree'] = self._load_to_playpen_source
        self._activity.child_path = self._new_child_path
        self.setup_new_activity()
        
   
        """The following code needs to be copied inline to any routine which overwrites playpen
        #has the tree md5 changed?
        tree_md5 = self._activity.util.md5sum_tree(self._activity.child_path)
        if tree_md5 != self._activity.debug_dict['tree_md5']:
            action_prompt = _('Select OK to abandon changes to ') + \
                            os.path.basename(self._activity.child_path)
            self._activity.util.confirmation_alert(action_prompt,
                                                   _('Changes have been made to the PyDebug work area.'),
                                                   self.continue_inline_cb)
        """
        
    def _unload_playpen(self):                                           
        #IPython gets confused if path it knows about suddenly disappears
        cmd = 'cd %s\n'%self._activity.activity_playpen
        self._activity.feed_virtual_terminal(0,cmd)
        if self._activity.child_path and os.path.isdir(self._activity.child_path):
            self.abandon_changes = True
            #there is a on change call back to disable
            self._activity.debug_dict['tree_md5'] = ''
            self._activity.debug_dict['child_path'] = ''
            self.get_editor().remove_all()
            if self._activity.child_path:
                shutil.rmtree(self._activity.child_path)
            self.abandon_changes = False
            
    def copy_tree(self,source,dest):
            if os.path.isdir(dest):
                try:
                    shutil.rmtree(dest)
                except Exception, error:
                    _logger.debug('rmtree exception %r'%error)
            try:
                shutil.copytree(source,dest)
                self._activity.util.set_permissions(dest)
            except Exception, error:
                _logger.debug('copytree exception %r'%error)

    
    def read_activity_info(self, path):
        """
        Fetch the activity info from Datastore object and Sugar system calls 
        """
        try:
            _logger.debug ('passed in file path: %s'%path)       
            bundle = ActivityBundle(path)
        except Exception,e:
            _logger.debug('exception %r'%e)
            #msg = _('%s not recognized by ActivityBundle parser. Does activity/activity.info exist?'%os.path.basename(path))
            #self._activity.util.alert(msg)
            self._activity.init_activity_dict()
            if self._activity.child_path and os.path.isdir(self._activity.child_path) and self._activity.child_path.endswith('.activity'):
                name = os.path.basename(self._activity.child_path).split('.')[0]
                self._activity.activity_dict['name'] = name
                self._activity.activity_dict['bundle_id'] = 'org.laptop.'  + name               
                return  #maybe should issue an alert here
        self._activity.activity_dict['version'] = str(bundle.get_activity_version())
        self._activity.activity_dict['name'] = bundle.get_name()
        self._activity.activity_dict['bundle_id'] = bundle.get_bundle_id()
        self._activity.activity_dict['command'] = bundle.get_command()
        cmd_args = bundle.get_command()
        self._activity.activity_dict['command'] = cmd_args
        if cmd_args.startswith('sugar-activity'):
            mod_class = cmd_args.split()[1]
            if '.' in mod_class:
                self._activity.activity_dict['class'] = mod_class.split('.')[1]  
                self._activity.activity_dict['module'] = mod_class.split('.')[0]
        else:
            self._activity.activity_dict['module'] = cmd_args
            self._activity.activity_dict['class'] = ''
        self._activity.activity_dict['icon'] = bundle.get_icon()
        self._activity.activity_dict['title'] = 'PyDebug_' + self._activity.activity_dict['name']
        log_dict(self._activity.activity_dict,'Contents of activity_dict')
        self._activity.update_metadata()
        
