#!/usr/bin/env python
from __future__ import with_statement
#
# Copyright (C) 2007, Red Hat, Inc.
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
import sys
from subprocess import PIPE, Popen
from gettext import gettext as _

#debug tool to analyze the activity environment
# Initialize logging.
import logging
from  pydebug_logging import _logger, log_environment
_logger.setLevel(logging.DEBUG)

from sugar.activity import activityfactory
from sugar.bundle.activitybundle import ActivityBundle
from sugar import profile
from sugar.graphics.xocolor import XoColor

#figure out which version of sugar we are dealing with
def command_line(cmd):
    _logger.debug('command_line cmd:%s'%cmd)
    p1 = Popen(cmd,stdout=PIPE, shell=True)
    output = p1.communicate()
    if p1.returncode != 0:
        return None
    return output[0]
    
def sugar_version():
    cmd = '/bin/rpm -q sugar'
    reply = command_line(cmd)
    if reply and reply.find('sugar') > -1:
        version = reply.split('-')[1]
        version_chunks = version.split('.')
        major_minor = version_chunks[0] + '.' + version_chunks[1]
        return float(major_minor) 
    return None

version = 0.0
version = sugar_version() 

#define the interface with the GUI
from Rpyc import *
try:
    c = SocketConnection('localhost')
    db = c.modules.pydebug.pydebug_instance
except AttributeError:
    print('cannot connect to localhost')
except Exception,e:
    print(str(e))
    assert False

#define interface with the command line ipython instance
#from IPython.core import ipapi
from IPython import ipapi
ip = ipapi.get()
global __IPYTHON__
try:
    __IPYTHON__
    print('IPTHON is defined')
except:
    __IPYTHON__ = ip

def edit_glue(self,filename,linenumber=0):
    _logger.debug('position to editor file:%s. Line:%d'%(filename,linenumber))
    if filename.endswith('.pyc') or filename.endswith('.pyo'):
        filename = filename[:-1]
    if linenumber > 0:
        linenumber -= 1
    db.editor.position_to(filename,linenumber)

ip.set_hook('editor',edit_glue)

def sync_called(self,filename,linenumber,col):
    if filename.endswith('.pyc'):
        filename = filename[:-1]
    if linenumber > 0:
        linenumber -= 1
    print('synchronize called. file:%s. line:%s. Col:%s'%(filename,linenumber,col))
    db.editor.position_to(filename,linenumber)
    
ip.set_hook('synchronize_with_editor',sync_called)

#get the information about the Activity we are about to debug
child_path = db.child_path
_logger.debug('child path: %s'%child_path)
if not child_path:
    print _('\n\nThere is no program loaded into the Work Area. \nPlease use the "Project" tab so set up the debug session\n\n')
    sys.exit(1)
    
#set the traceback level of detail
#ip.options.xmode = db.debug_dict['traceback']
__IPYTHON__.magic_xmode(db.debug_dict['traceback'])
_logger.debug('xmode set to %s'%db.debug_dict['traceback'])

#put module in top level namespace so it can be dreload()-ed
exec 'import ' + db.pdbmodule
exec 'reload(%s)'%db.pdbmodule

""" if this were to work properly we should set go equal to object Macro
go_cmd = 'run -d -b %s %s'%(os.path.join(db.pydebug_path,'bin','start_debug.py'),child_path)
_logger.debug('defining go: %s'%go_cmd)
ip.user_ns['go'] = go_cmd
"""
_logger.debug('pydebug home: %s'%db.debugger_home)
path = child_path
pydebug_home = db.debugger_home
os.environ['PYDEBUG_HOME'] = pydebug_home
os.chdir(path)
os.environ['SUGAR_BUNDLE_PATH'] = path
_logger.debug('sugar_bundle_path set to %s'%path)

#set up python module search path
sys.path.insert(0,path)
bundle_info = ActivityBundle(path)
bundle_id = bundle_info.get_bundle_id()

#following two statements eliminate differences between sugar 0.82 and 0.84
bundle_info.path = path
bundle_info.bundle_id = bundle_id

bundle_name = bundle_info.get_name()
os.environ['SUGAR_BUNDLE_NAME'] = bundle_name
os.environ['SUGAR_BUNDLE_ID'] = bundle_id

if version and version >= 0.839:
    #do 0.84 stuff
    cmd_args = activityfactory.get_command(bundle_info)
else:
    from sugar.activity.registry import get_registry
    registry = get_registry()
    registry.add_bundle(path)
    activity_list = registry.find_activity(bundle_id)
    if len(activity_list) == 0:
        _logger.error('Activity %s not found'%bundle_id)
        print 'Activity %s not found'%bundle_id
        exit(1)
    cmd_args = activityfactory.get_command(activity_list[0])
    myprofile = profile.get_profile()
    myprofile.color = XoColor()
_logger.debug('command args:%r'%cmd_args)
    

#need to get activity root, but activity bases off of HOME which some applications need to change
#following will not work if storage system changes with new OS
#required because debugger needs to be able to change home so that foreign apps will work
activity_root = os.path.join('/home/olpc/.sugar/default/',bundle_id)
os.environ['SUGAR_ACTIVITY_ROOT'] = activity_root
_logger.debug('sugar_activity_root set to %s'%activity_root)

#following is useful for its side-effects    
info = activityfactory.get_environment(bundle_info)

_logger.debug("Command args:%s."%cmd_args)
if not cmd_args[0].startswith('sugar-activity'):
    #it is a batch file which will try to set up the environment
    #debugger will try to preserve python path, path settings
    target = os.path.join(pydebug_home,'pydebug','.hide',os.path.basename(cmd_args[0]))
    source = './' + os.path.join('bin',cmd_args[0])
    with open(target,'w+') as write_script_fd:
        #rewrite the batch file in the debugger home directory without exec line
        with open(source,'r') as read_script_fd:
            for line in read_script_fd.readlines():
                if line.startswith('exec') or line.startswith('sugar-activity'):
                    pass
                    cmd_args[1] = line.split()[2]                    
                else:
                    write_script_fd.write(line)
        #write the environment variables to another file
        line = 'export -p > %s_env\n'%target
        write_script_fd.write(line)
        #write_script_fd.close()
    _logger.debug('Completed writing env script:%s'%target)
    os.chmod(target,0755)  #make it executable
    os.system(target)
    
    #read the environment back into the current process
    with open('%s_env'%target,'r') as env_file:
        env_dict = os.environ.copy()
        for line in env_file.readlines():
            skip_line = False
            start_scan = 0
            if not line.startswith('export'):
                continue
            #we will only deal with attempts to set the environment
            payload = line.split()[1]
            pair = payload.split('=')
            if len(pair)> 1:
                key = pair[0]
                value = pair[1]
                value = value[1:-1] #clip off quote marks
                _logger.debug('key:%s.value:%s'%(key,value,))
                if key == 'PYTHONPATH':
                    os.environ['PYTHONPATH']= value + ':' +os.environ['PYTHONPATH']
                elif key == 'LD_LIBRARY_PATH':
                    os.environ['LD_LIBRARY_PATH']= value + ':' +os.environ.get('LD_LIBRARY_PATH','')
                elif key == 'HOME':
                    continue
                else:
                    index = value.find(pydebug_home[:-6], start_scan)
                    while index > -1:
                        #the batch file commonly in use uses $0 to capture curdir
                        # this will be incorrect since we executed the script in pydebug_home
                        testvalue = value[index:index + len(path)]
                        if index > -1 and testvalue != path:
                            #substitute path for pydebug_home
                            testval = value[index + len(pydebug_home) - 5:]
                            value = value[:index] + path + testval
                            #permit repeated debug runs without creating monster environment strings
                            if os.environ.has_key(key):
                                if os.environ[key] == value: skip_line = True
                        if not skip_line: env_dict[key] = value
                        start_scan = index + len(path)
                        index = value.find(pydebug_home[:-6], start_scan)
    #os.environ = env_dict        
#bundle_id = cmd_args[5]
#sys.argv = [None, cmd_args[1],'-s'] + cmd_args[1:]
#sys.argv = [None, cmd_args[1],] + cmd_args[1:]
#sys.argv = [None,] + cmd_args[1:] 
sys.argv = cmd_args

log_environment()
_logger.debug('about to call main.main() with args %r'%sys.argv)

from sugar.activity import main
main.main()

            


