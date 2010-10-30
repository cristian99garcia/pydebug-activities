#!/usr/bin/env python
#
# Copyright (C) 2009, George Hunt <georgejhunt@gmail.com>
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

# Initialize logging.
import logging
_logger = logging.getLogger('PyDebug')
_logger.setLevel(logging.DEBUG)

#establish a remote procedure call pipe connection with the PyDebug process
from Rpyc import SocketConnection
try:
    c = SocketConnection('localhost')
    db = c.modules.pydebug.pydebug_instance
except AttributeError:
    _logger.error('cannot connect to localhost')
except e:
    print(e[1])
    assert False
pydebug_path = db.pydebug_path
print('./bin/start_debug.py established connectioon. pydebug path: %s'%pydebug_path)

#these alternative definitions are required for ipython v0.11 and greater
#define interface with the command line ipython instance
from IPython.core import ipapi
from IPython.core.macro import Macro

#from IPython import ipapi
# IPython.macro import Macro #0,10
ip = ipapi.get()

#define  macros, one which sets pdb on, the other off
if not ip.user_ns.has_key('gb'):
    cmd = 'run -b 242 -d %s\n'% os.path.join(pydebug_path,'bin','continue_debug.py')
    ip.user_ns['gb'] = Macro(cmd)
if not ip.user_ns.has_key('go'):
    cmd = 'run  %s\n'% os.path.join(pydebug_path,'bin','continue_debug.py')
    ip.user_ns['go'] = Macro(cmd)
if not ip.user_ns.has_key('pi'):
    cmd = 'for k in _margv[0].__dict__.keys(): print "_margv[0]",k,"=",_margv[0].__dict__[k]\n'
    ip.user_ns['pi'] = Macro(cmd)
if not ip.user_ns.has_key('ps'):
    cmd = 'pi self\n'
    ip.user_ns['ps'] = Macro(cmd)

#change the directory to the child_path
os.chdir(db.child_path)