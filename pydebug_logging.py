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

# Initialize logging.
import logging
from sugar import logger
#Get the standard logging directory. 
std_log_dir = logger.get_logs_dir()
_logger = logging.getLogger('PyDebug')
"""
#First log handler: outputs to a file called 'VideoEdit.activity.log'
file_handler = logging.FileHandler(os.path.join(std_log_dir,'PyDebug.activity.log')
file_formatter = logging.Formatter('%(name)s -- %(asctime)s %(funcName)s: %(lineno)d\n %(message)s\n')
file_handler.setFormatter(file_formatter)
_logger.addHandler(file_handler)
"""
_logger.setLevel(logging.DEBUG)

#Second log handler: outputs to a the console, using a slightly different output structure
console_handler = logging.StreamHandler()
console_formatter = logging.Formatter('%(name)s %(levelname)s %(funcName)s: %(lineno)d||| %(message)s')
console_handler.setFormatter(console_formatter)
_logger.addHandler(console_handler)

def log_environment():
    keys = []
    for k in os.environ:
        if k.find('SUGAR') > -1 or k.find('PATH')>-1:
            print('%s => %s'%(k,os.environ[k]))
            