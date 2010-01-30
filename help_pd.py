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
#
#NOTE: The webview module shipped with FC11 does a get_Main_window.hide()
#       which makes it unusable in the PyDebug application. A more recent git version
#       toggles the visibility of the gecko engine and is more compatible.
#       The browser.py and webview.py modules included are essential for PyDebug
#
import os
from gettext import gettext as _

import gtk
import gobject

from sugar.activity import activity
from sugar.graphics.toolbutton import ToolButton

import hulahop
hulahop.startup(os.path.join(activity.get_activity_root(), 'data/gecko'))
from zipfile import ZipFile, ZipInfo

#from hulahop.webview import WebView
from browser import Browser
#import xpcom
#from xpcom.components import interfaces

gobject.threads_init()

#HOME = os.path.join(activity.get_bundle_path(), 'help/index.html')
#HOME = "http://website.com/something.html"

# Initialize logging.
import logging
from sugar import logger
#Get the standard logging directory. 
_logger = logging.getLogger('PyDebug')

ZIP_SUFFIXES = ['.xol','.zip',]
sugar_activity_root = os.environ['SUGAR_ACTIVITY_ROOT']
help_notebook_pages = []

class HelpToolbar(gtk.Toolbar):
    def __init__(self, parent):
        gtk.Toolbar.__init__(self)
        self.help_toolbar_parent = parent
        self.child_root = os.path.join(os.environ['SUGAR_ACTIVITY_ROOT'],'tmp')

        self._back = ToolButton('go-previous-paired')
        self._back.set_tooltip(_('Back'))
        self._back.props.sensitive = False
        self._back.connect('clicked', self.help_toolbar_parent._go_back_cb)
        self.insert(self._back, -1)
        self._back.show()

        self._forward = ToolButton('go-next-paired')
        self._forward.set_tooltip(_('Forward'))
        self._forward.props.sensitive = False
        self._forward.connect('clicked', self.help_toolbar_parent._go_forward_cb)
        self.insert(self._forward, -1)
        self._forward.show()

        home = ToolButton('zoom-home')
        home.set_tooltip(_('Home'))
        home.connect('clicked', self.help_toolbar_parent._go_home_cb)
        self.insert(home, -1)
        home.show()

class Help():
    current_url_prefix = ''
    file_changed = False
    current_web_view = None
    web_view_list = []
    def __init__(self, parent):
        self.pydebug = parent
        self.url_root = 'file://'+ self.sugar_bundle_path +"/"+_('help/PyDebug.htm')
        self.help_toolbar = HelpToolbar(self.pydebug)
        self.help_toolbar.show()
        self.first_webview = self.new_tab(self.url_root)
        self.web_view_list.append(self.first_webview)
        self.current_web_view = self.first_webview
        translation = self.translate_zip_url(self.url_root)
        _logger.debug("this is url root: %s"%translation)
        self.first_webview.load_uri(translation)
        
    def get_help_toolbar(self):
        return self.help_toolbar
        
    def _get_help_canvas(self):
        nb = gtk.Notebook()
        nb.show()        
        nb.append_page(self.first_webview)
        self.help_notebook = nb
        return nb
       
    def new_tab(self,url = None):
        if url == None:
            url = self.url_root
        self._web_view = Browser()
        _logger.debug('loading new tab with url: %s' % url  )
        self._web_view.load_uri(url)
        self._web_view.connect('destroy',self._web_view.hide)
        self.current_url = url
        self._web_view.show()
        progress_listener = self._web_view.progress
        progress_listener.connect('location-changed',
                                  self._location_changed_cb)
        progress_listener.connect('loading-stop', self._loading_stop_cb)

        return self._web_view
    
    def repaint(self):
        self._web_view.load_uri(self.current_url)
        
    def get_first_webview(self):
        return self.first_webview

    def _location_changed_cb(self, progress_listener, uri):
        myuri=''
        myuri = str(uri)
        _logger.debug('location changed callback %s'%(myuri))
        self.update_navigation_buttons()
        target = self.translate_zip_url(uri)
        _logger.debug(' which translated to %s'%(target))
        #self.current_webview.load_uri(target)
        uri = target
    
    def translate_zip_url(self,uri): #string in, string returned
        #if this file is already unzipped then allow normal processing
        if os.path.isfile(uri[7:]):  #don't want the leading 'file://'
            return uri
        #look for the zip suffixes in the uri
        self.current_url_prefix = ''
        for pattern in ZIP_SUFFIXES:
            if uri.find(pattern) > -1:
                self.current_url_prefix = uri[:uri.find(pattern)] + pattern
                found_pattern = pattern
        if self.current_url_prefix == '':
            return uri
        _logger.debug('pattern found:%s. Prefix: %s'%(found_pattern,self.current_url_prefix))

        #find the file in the zip, write it somewhere writeable, load this url instead
        zipfile_name = self.current_url_prefix[7:] #clip off the leading "file:"
        name_in_zip = uri[len(self.current_url_prefix)+1:]
        try:
            zf = ZipFile(zipfile_name,'r')
        except:
            _logger.debug('Opening Zip file failed: %s'%zipfile_name)             
            return uri
        try: #first check to see if this location is already filled
            dest = os.path.join(sugar_activity_root,'tmp')
            write_zip_to_here = os.path.join(dest, name_in_zip)
            if os.path.isfile(write_zip_to_here):
                return write_zip_to_here
            else:
                zf.extract(name_in_zip,dest)
                _logger.debug('Writing Zip file to %s '%(write_zip_to_here))             
        except:
            _logger.debug('Extracting Zip file %s to %s failed'%(name_in_zip,dest))             
        #self.current_web_view.load_uri(dest)
        self.last_file_unzipped = write_zip_to_here
        url = 'file://' + self.last_file_unzipped
        uri.replace(url)
        return(url)

    def _loading_stop_cb(self, progress_listener):
        self.update_navigation_buttons()

    def update_navigation_buttons(self):
        can_go_back = self.current_web_view.web_navigation.canGoBack
        self.help_toolbar._back.props.sensitive = can_go_back

        can_go_forward = self.current_web_view.web_navigation.canGoForward
        self.help_toolbar._forward.props.sensitive = can_go_forward

    def _go_back_cb(self, button):
        self.current_web_view.web_navigation.goBack()
    
    def _go_forward_cb(self, button):
        self.current_web_view.web_navigation.goForward()

    def _go_home_cb(self, button):
        self.current_web_view.load_uri(self.url_root)

        
