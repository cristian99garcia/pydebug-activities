#!/usr/bin/env python
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

#debug tool to analyze the activity environment
# Initialize logging.
import logging
from  pydebug_logging import _logger, log_environment
_logger.setLevel(logging.DEBUG)

from sugar3.activity import main
from sugar3.activity import activityfactory
from sugar3.bundle.activitybundle import ActivityBundle

#define the interface with the GUI
from Rpyc import *
try:
    c = SocketConnection('localhost')
    db = c.modules.pydebug.pydebug_instance

except AttributeError:
    print('cannot connect to localhost')

except e:
    print(e[1])
    assert False

#define interface with the command line ipython instance
from IPython.core import ipapi
ip = ipapi.get()
global __IPYTHON__
try:
    __IPYTHON__
    print('IPTHON is defined')

except:
    __IPYTHON__ = ip

o = ip.options
o.xmode = db.traceback


def edit_glue(self, filename, linenumber):
    _logger.debug('position to editor file:%s. Line:%d' % (filename, linenumber))

ip.set_hook('editor', edit_glue)


def sync_called(self, filename, line, col):
    print('synchronize called. file:%s. line:%s. Col:%s' % (filename, line, col))

ip.set_hook('synchronize_with_editor', sync_called)


#get the information about the Activity we are about to debug
child_path = db.child_path
_logger.debug('child path: %s' % child_path)

print('child path starting activity: %s' % child_path)

go_cmd = 'run -d -b %s %s' % (os.path.join(db.pydebug_path, 'bin', 'start_debug.py'), child_path)
_logger.debug('defining go: %s' % go_cmd)
ip.user_ns['go'] = go_cmd
_logger.debug('pydebug home: %s' % db.debugger_home)
path = child_path
pydebug_home = db.debugger_home
os.environ['PYDEBUG_HOME'] = pydebug_home
os.chdir(path)
os.environ['SUGAR_BUNDLE_PATH'] = path
_logger.debug('sugar_bundle_path set to %s' % path)

#set up module search path
sys.path.insert(0, path)
activity = ActivityBundle(path)
cmd_args = activityfactory.get_command(activity)
_logger.debug('command args:%r' % cmd_args)
bundle_name = activity.get_name()
bundle_id = activity.get_bundle_id()

#need to get activity root, but activity bases off of HOME which some applications need to change
#following will not work if storage system changes with new OS
#required because debugger needs to be able to change home so that foreign apps will work
activity_root = os.path.join('/home/olpc/.sugar/default/', bundle_id)
os.environ['SUGAR_ACTIVITY_ROOT'] = activity_root
_logger.debug('sugar_activity_root set to %s'%activity_root)

#following is useful for its side-effects
info = activityfactory.get_environment(activity)

_logger.debug("Command to execute:%s." % cmd_args[0])
if not cmd_args[0].startswith('sugar-activity'):
    target = os.path.join(pydebug_home, os.path.basename(cmd_args[0]))
    with open(target,'w') as write_script_fd:
        with open(cmd_args[0], 'r') as read_script_fd:
            for line in read_script_fd.readlines():
                if line.startswith('exec') or line.startswith('sugar-activity'):
                    pass
                else:
                    write_script_fd.write(line)

        line = 'export -p > %s_env\n'%target
        write_script_fd.write(line) #write the environment variables to another file
        write_script_fd.close()
    
    os.chmod(target, 0755)
    os.system(target)
    _logger.debug('writing env script:%s' % target)
    #read the environment back into the current process
    with open('%s_env'%target,'r') as env_file:
        env_dict = {}
        for line in env_file.readlines():
            if not line.startswith('export'):
                pass

            payload = line.split()[1]
            pair = payload.split('=')
            if len(pair) > 1:
                key = pair[0]
                value = pair[1]
                env_dict[key] = value
                _logger.debug('reading environment. %s => %s'%(key, value))

    os.environ = env_dict


more_args = ['-a', bundle_name, '-b', bundle_id]
sys.argv = cmd_args[:2] + more_args
_logger.debug('about to call main.main() with args %r' % sys.argv)
log_environment()

main.main()

