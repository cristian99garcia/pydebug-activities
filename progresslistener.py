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

from gi.repository import GObject


class ProgressListener(GObject.GObject):

    _com_interfaces_ = interfaces.nsIWebProgressListener

    __gsignals__ = {
        'location-changed': (GObject.SIGNAL_RUN_FIRST, GObject.TYPE_NONE,
                             ([object])),
        'loading-start':    (GObject.SIGNAL_RUN_FIRST, GObject.TYPE_NONE,
                             ([])),
        'loading-stop':     (GObject.SIGNAL_RUN_FIRST, GObject.TYPE_NONE,
                             ([])),
        'loading-progress': (GObject.SIGNAL_RUN_FIRST, GObject.TYPE_NONE,
                             ([float]))
    }

    def __init__(self):
        GObject.GObject.__init__(self)

        self.total_requests = 0
        self.completed_requests = 0

        self._reset_requests_count()

    def setup(self, browser):
        pass
    
    def _reset_requests_count(self):
        self.total_requests = 0
        self.completed_requests = 0

    def onLocationChange(self, webProgress, request, location):
        self.emit('location-changed', location)
        print('on location change call back executed')
        
    def onProgressChange(self, webProgress, request, curSelfProgress, ss, curTotalProgress, maxTotalProgress):
        pass
    
    def onSecurityChange(self, webProgress, request, state):
        pass
        
    def onStateChange(self, webProgress, request, stateFlags, status):
        pass

    def onStatusChange(self, webProgress, request, status, message):
        pass
