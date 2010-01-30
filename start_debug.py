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

# Initialize logging.
import logging
_logger = logging.getLogger('PyDebug')
_logger.setLevel(logging.DEBUG)

from Rpyc import *
try:
    c = SocketConnection('localhost')
    db = c.modules.pydebug.pydebug_instance
except AttributeError:
    _logger.error('cannot connect to localhost')
except e:
    print(e[1])
    assert False
pydebug_path = db.pydebug_path
print('pydebug path: %s'%pydebug_path)
#define interface with the command line ipython instance
from IPython.core import ipapi
from IPython.core.macro import Macro
ip = ipapi.get()
cmd = 'run -pdb -d %s\n'% os.path.join(pydebug_path,'bin','continue_debug.py')
ip.user_ns['go'] = Macro(cmd)
alias_cmd = '!alias go=%s'%os.path.join(pydebug_path,'bin','continue_debug.py')
os.system(alias_cmd)
