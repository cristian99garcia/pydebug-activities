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
import time
import logging
from gettext import gettext as _

from gi.repository import Gtk
from gi.repository import GObject
from gi.repository import WebKit

from sugar3.datastore import datastore
from sugar3 import profile
from sugar3 import env
from sugar3.activity import activity
from sugar3.graphics import style

_ZOOM_AMOUNT = 0.1


class Browser(Gtk.ScrolledWindow):

    def __init__(self):

        Gtk.ScrolledWindow.__init__(self)

        self.browser = WebKit.WebView()
        self.add(self.browser)

    def do_setup(self):
        pass

    def zoom_in(self):
        self.browser.set_zoom_level(self.browser.get_zoom_level() + _ZOOM_AMOUNT)

    def zoom_out(self):
        self.browser.set_zoom_level(self.browser.get_zoom_level() - _ZOOM_AMOUNT)

    def load_uri(self, uri):
        self.browser.load_uri(uri)

    def can_go_back(self):
        return self.browser.can_go_back()

    def can_go_forward(self):
        return self.browser.can_go_forward()

    def go_back(self):
        if self.can_go_back():
            self.go_back()

    def go_forward(self):
        if self.can_go_forward():
            self.go_forward()

