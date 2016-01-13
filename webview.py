# Copyright (C) 2007, Red Hat, Inc.
#
# This library is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation; either
# version 2 of the License, or (at your option) any later version.
#
# This library is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public
# License along with this library; if not, write to the
# Free Software Foundation, Inc., 59 Temple Place - Suite 330,
# Boston, MA 02111-1307, USA.
import logging

from gi.repository import Gtk
from gi.repository import GObject
from gi.repository import WebKit


class _Chrome:

    def __init__(self, web_view):
        self.web_view = web_view
        self.title = ''
        self._modal = False
        self._visible = False

    def provideWindow(self, parent, flags, position_specified, size_specified, uri, name, features):
        if name == "_blank":
            return parent, False
        else:
            return None, False

    # nsIWebBrowserChrome
    def destroyBrowserWindow(self):
        logging.debug("nsIWebBrowserChrome.destroyBrowserWindow")
        if self._modal:
            self.exitModalEventLoop(0)
        self.web_view.get_toplevel().destroy()

    def exitModalEventLoop(self, status):
        logging.debug("nsIWebBrowserChrome.exitModalEventLoop: %r" % status)
        """
        if self._continue_modal_loop:
            self.enable_parent(True)
        """
        if self._modal:
            self._continue_modal_loop = False
            self._modal = False
            self._modal_status = status
            #self.web_view.get_toplevel().grab_remove()

    def isWindowModal(self):
        logging.debug("nsIWebBrowserChrome.isWindowModal")
        return self._modal

    def setStatus(self, statusType, status):
        #logging.debug("nsIWebBrowserChrome.setStatus")
        self.web_view._set_status(status.encode('utf-8'))

    def showAsModal(self):
        logging.debug("nsIWebBrowserChrome.showAsModal")
        self._modal = True
        self._continue_modal_loop = True
        self._modal_status = None
        #EnableParent(PR_FALSE);
        #self.web_view.get_toplevel().grab_add()

        cls = components.classes["@mozilla.org/thread-manager;1"]
        thread_manager = cls.getService(interfaces.nsIThreadManager)
        current_thread = thread_manager.currentThread

        self.web_view.push_js_context()
        while self._continue_modal_loop:
            processed = current_thread.processNextEvent(True)
            if not processed:
                break
        self.web_view.pop_js_context()

        self._modal = False
        self._continue_modal_loop = False

        return self._modal_status

    def sizeBrowserTo(self, cx, cy):
        logging.debug("nsIWebBrowserChrome.sizeBrowserTo: %r %r" % (cx, cy))
        self.web_view.get_toplevel().resize(cx, cy)
        self.web_view.type = WebView.TYPE_POPUP

    # nsIWebBrowserChrome2
    def setStatusWithContext(self, statusType, statusText, statusContext):
        self.web_view._set_status(statusText.encode('utf-8'))

    # nsIEmbeddingSiteWindow
    def getDimensions(self, flags):
        return (100, 100)

    def setDimensions(self, flags, x, y, cx, cy):
        logging.debug("nsIEmbeddingSiteWindow.setDimensions: %r" % flags)

    def setFocus(self):
        logging.debug("nsIEmbeddingSiteWindow.setFocus")
        self.web_view.grab_focus()

    def get_title(self):
        logging.debug("nsIEmbeddingSiteWindow.get_title: %r" % self.title)
        return self.title

    def set_title(self, title):
        logging.debug("nsIEmbeddingSiteWindow.set_title: %r" % title)
        self.title = title
        ##self.web_view._notify_title_changed()

    def get_webBrowser(self):
        return self.web_view.browser

    def get_chromeFlags(self):
        return self._chrome_flags

    def set_chromeFlags(self, flags):
        self._chrome_flags = flags

    def get_visibility(self):
        logging.debug("nsIEmbeddingSiteWindow.get_visibility: %r" % self._visible)
        visibility = self.web_view.props.visibility
        mapped = self.web_view.get_mapped()
        return visibility or (not self.web_view.is_chrome and mapped)

    def set_visibility(self, visibility):
        logging.debug("nsIEmbeddingSiteWindow.set_visibility: %r" % visibility)
        if visibility == self.web_view.props.visibility:
            return

        self.web_view.props.visibility = visibility

    # nsIWebProgressListener
    def onStateChange(self, web_progress, request, state_flags, status):
        if (state_flags & interfaces.nsIWebProgressListener.STATE_STOP) and (state_flags & interfaces.nsIWebProgressListener.STATE_IS_NETWORK):
            if self.web_view.is_chrome:
                self.web_view.dom_window.sizeToContent()

    def onStatusChange(self, web_progress, request, status, message):
        pass

    def onSecurityChange(self, web_progress, request, state):
        pass

    def onProgressChange(self, web_progress, request, cur_self_progress, max_self_progress, cur_total_progress, max_total_progress):
        pass

    def onLocationChange(self, web_progress, request, location):
        pass

    # nsIInterfaceRequestor
    def queryInterface(self, uuid):
        if not uuid in self._com_interfaces_:
            # Components.returnCode = Cr.NS_ERROR_NO_INTERFACE;
            logging.warning('Interface %s not implemented by this instance: %r' % (uuid, self))
            return None

    def getInterface(self, uuid):
        result = self.queryInterface(uuid)
        
        if not result:
            # delegate to the nsIWebBrowser
            requestor = self.web_view.browser.queryInterface(interfaces.nsIInterfaceRequestor)
            try:
                result = requestor.getInterface(uuid)
            except xpcom.Exception:
                logging.warning('Interface %s not implemented by this instance: %r' % (uuid, self.web_view.browser))
                result = None

        return result


class WebView(WebKit.WebView):

    TYPE_WINDOW = 0
    TYPE_POPUP = 1

    __gproperties__ = {
        'title': (str, None, None, None, GObject.PARAM_READABLE),
        'status': (str, None, None, None, GObject.PARAM_READABLE),
        'visibility': (bool, None, None, False, GObject.PARAM_READWRITE)
    }

    def __init__(self):
        WebKit.WebView.__init__(self)

        self.is_chrome = False
        chrome = _Chrome(self)

        self._chrome = xpcom.server.WrapObject(chrome, interfaces.nsIEmbeddingSiteWindow)

        self._status = ''
        self._first_uri = None
        self._visibility = False

    def do_setup(self):
        if self._first_uri:
            self.load_uri(self._first_uri)

    def _notify_title_changed(self):
        self.notify('title')

    def _set_status(self, status):
        self._status = status
        self.notify('status')

    def do_get_property(self, pspec):
        if pspec.name == 'title':
            return self._chrome.title
        elif pspec.name == 'status':
            return self._status
        elif pspec.name == 'visibility':
            return self._visibility

    def do_set_property(self, pspec, value):
        if pspec.name == 'visibility':
            self._visibility = value

    def get_window_root(self):
        return None

    def get_browser(self):
        return None

    def get_doc_shell(self):
        return None

    def get_web_progress(self):
        return self.get_progress()

    def get_web_navigation(self):
        return None

    def get_dom_window(self):
        return None

    def load_uri(self, uri):
        self.open(uri)

