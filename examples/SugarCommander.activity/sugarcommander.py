# SugarCommander.py

# Copyright (C) 2010 James D. Simmons
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
import logging
import os
import gtk
import pango
import zipfile
from sugar import mime
from sugar.activity import activity
from sugar.datastore import datastore
from sugar.graphics.alert import NotifyAlert
from sugar.graphics import style
from gettext import gettext as _
import gobject
import dbus

COLUMN_TITLE = 0
COLUMN_MIME = 1
COLUMN_JOBJECT = 2

DS_DBUS_SERVICE = 'org.laptop.sugar.DataStore'
DS_DBUS_INTERFACE = 'org.laptop.sugar.DataStore'
DS_DBUS_PATH = '/org/laptop/sugar/DataStore'

_logger = logging.getLogger('sugar-commander')

class SugarCommander(activity.Activity):
    def __init__(self, handle, create_jobject=True):
        "The entry point to the Activity"
        activity.Activity.__init__(self, handle,  False)
        self.selected_journal_entry = None
        self.selected_path = None
        
        canvas = gtk.Notebook()
        canvas.props.show_border = True
        canvas.props.show_tabs = True
        canvas.show()
        
        self.ls_journal = gtk.ListStore(gobject.TYPE_STRING, 
                gobject.TYPE_STRING,
                gobject.TYPE_PYOBJECT)
        tv_journal = gtk.TreeView(self.ls_journal)
        tv_journal.set_rules_hint(True)
        tv_journal.set_search_column(COLUMN_TITLE)
        self.selection_journal = tv_journal.get_selection()
        self.selection_journal.set_mode(gtk.SELECTION_BROWSE)
        self.selection_journal.connect("changed", self.selection_journal_cb)
        renderer = gtk.CellRendererText()
        renderer.set_property('wrap-mode', gtk.WRAP_WORD)
        renderer.set_property('wrap-width', 500)
        renderer.set_property('width', 500)
        self.col_journal = gtk.TreeViewColumn(_('Title'), renderer, 
                                              text=COLUMN_TITLE)
        self.col_journal.set_sort_column_id(COLUMN_TITLE)
        tv_journal.append_column(self.col_journal)
        
        self.col_mime = gtk.TreeViewColumn(_('MIME'), renderer, 
                                           text=COLUMN_MIME)
        self.col_mime.set_sort_column_id(COLUMN_MIME)
        tv_journal.append_column(self.col_mime)
        
        self.list_scroller_journal = gtk.ScrolledWindow(
                        hadjustment=None, vadjustment=None)
        self.list_scroller_journal.set_policy(
                    gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
        self.list_scroller_journal.add(tv_journal)
        
        label_attributes = pango.AttrList()
        label_attributes.insert(pango.AttrSize(14000, 0, -1))
        label_attributes.insert(pango.AttrForeground(65535, 65535, 65535, 0, -1))

        tab1_label = gtk.Label(_("Journal"))
        tab1_label.set_attributes(label_attributes)
        tab1_label.show()
        tv_journal.show()
        self.list_scroller_journal.show()
        
        column_table = gtk.Table(rows=1,  columns=2,  homogeneous = False)
        
        image_table = gtk.Table(rows=2,  columns=2,  homogeneous=False)
        self.image = gtk.Image()
        image_table.attach(self.image, 0, 2, 0, 1, xoptions=gtk.FILL|gtk.SHRINK, 
                           yoptions=gtk.FILL|gtk.SHRINK, xpadding=10, ypadding=10)

        self.btn_save = gtk.Button(_("Save"))
        self.btn_save.connect('button_press_event',  
                              self.save_button_press_event_cb)
        image_table.attach(self.btn_save,  0, 1, 1, 2,  xoptions=gtk.SHRINK,
                             yoptions=gtk.SHRINK,  xpadding=10,  ypadding=10)
        self.btn_save.props.sensitive = False
        self.btn_save.show()

        self.btn_delete = gtk.Button(_("Delete"))
        self.btn_delete.connect('button_press_event',  
                                self.delete_button_press_event_cb)
        image_table.attach(self.btn_delete,  1, 2, 1, 2,  xoptions=gtk.SHRINK,
                            yoptions=gtk.SHRINK,  xpadding=10,  ypadding=10)
        self.btn_delete.props.sensitive = False
        self.btn_delete.show()

        column_table.attach(image_table,  0, 1, 0, 1,  
                            xoptions=gtk.FILL|gtk.SHRINK,
                              yoptions=gtk.SHRINK,  xpadding=10,  ypadding=10)

        entry_table = gtk.Table(rows=3, columns=2, 
                                homogeneous=False)

        title_label = gtk.Label(_("Title"))
        entry_table.attach(title_label, 0, 1, 0, 1, 
                           xoptions=gtk.SHRINK, 
                           yoptions=gtk.SHRINK, 
                           xpadding=10, ypadding=10)
        title_label.show()
      
        self.title_entry = gtk.Entry(max=0)
        entry_table.attach(self.title_entry, 1, 2, 0, 1, 
                           xoptions=gtk.FILL|gtk.SHRINK, 
                           yoptions=gtk.SHRINK, xpadding=10, ypadding=10)
        self.title_entry.connect('key_press_event',  
                                 self.key_press_event_cb)
        self.title_entry.show()
    
        description_label = gtk.Label(_("Description"))
        entry_table.attach(description_label, 0, 1, 1, 2, 
                           xoptions=gtk.SHRINK, 
                           yoptions=gtk.SHRINK, 
                           xpadding=10, ypadding=10)
        description_label.show()
        
        self.description_textview = gtk.TextView()
        self.description_textview.set_wrap_mode(gtk.WRAP_WORD)
        entry_table.attach(self.description_textview, 1, 2, 1, 2, 
                           xoptions=gtk.EXPAND|gtk.FILL|gtk.SHRINK, 
                           yoptions=gtk.EXPAND|gtk.FILL|gtk.SHRINK, 
                           xpadding=10, ypadding=10)
        self.description_textview.props.accepts_tab = False
        self.description_textview.connect('key_press_event', 
                                          self.key_press_event_cb)
        self.description_textview.show()

        tags_label = gtk.Label(_("Tags"))
        entry_table.attach(tags_label, 0, 1, 2, 3, 
                           xoptions=gtk.SHRINK, 
                           yoptions=gtk.SHRINK, 
                           xpadding=10, ypadding=10)
        tags_label.show()
        
        self.tags_textview = gtk.TextView()
        self.tags_textview.set_wrap_mode(gtk.WRAP_WORD)
        entry_table.attach(self.tags_textview, 1, 2, 2, 3, 
                           xoptions=gtk.FILL, 
                           yoptions=gtk.EXPAND|gtk.FILL, 
                           xpadding=10, ypadding=10)
        self.tags_textview.props.accepts_tab = False
        self.tags_textview.connect('key_press_event', 
                                    self.key_press_event_cb)
        self.tags_textview.show()
        
        entry_table.show()

        self.scroller_entry = gtk.ScrolledWindow(
                                                 hadjustment=None, vadjustment=None)
        self.scroller_entry.set_policy(gtk.POLICY_NEVER, gtk.POLICY_AUTOMATIC)
        self.scroller_entry.add_with_viewport(entry_table)
        self.scroller_entry.show()
        
        column_table.attach(self.scroller_entry,  1, 2, 0, 1,  
                            xoptions=gtk.FILL|gtk.EXPAND|gtk.SHRINK,  
                            yoptions=gtk.FILL|gtk.EXPAND|gtk.SHRINK, 
                            xpadding=10,  ypadding=10)
        image_table.show()
        column_table.show()

        vbox = gtk.VBox(homogeneous=True,  spacing=5)
        vbox.pack_start(column_table)
        vbox.pack_end(self.list_scroller_journal)

        canvas.append_page(vbox,  tab1_label)
 
        self._filechooser = gtk.FileChooserWidget(
            action=gtk.FILE_CHOOSER_ACTION_OPEN, backend=None)
        self._filechooser.set_current_folder("/media")
        self.copy_button = gtk.Button(_("Copy File To The Journal"))
        self.copy_button.connect('clicked',  self.create_journal_entry)
        self.copy_button.show()
        self._filechooser.set_extra_widget(self.copy_button)
        preview = gtk.Image()
        self._filechooser.set_preview_widget(preview)
        self._filechooser.connect("update-preview", 
                                  self.update_preview_cb, preview)
        tab2_label = gtk.Label(_("Files"))
        tab2_label.set_attributes(label_attributes)
        tab2_label.show()
        canvas.append_page(self._filechooser,  tab2_label)

        self.set_canvas(canvas)
        self.show_all()
        
        toolbox = activity.ActivityToolbox(self)
        activity_toolbar = toolbox.get_activity_toolbar()
        activity_toolbar.keep.props.visible = False
        activity_toolbar.share.props.visible = False
        self.set_toolbox(toolbox)
        toolbox.show()

        self.load_journal_table()

        bus = dbus.SessionBus()
        remote_object = bus.get_object(DS_DBUS_SERVICE, DS_DBUS_PATH)
        _datastore = dbus.Interface(remote_object, DS_DBUS_INTERFACE)
        _datastore.connect_to_signal('Created', self.datastore_created_cb)
        _datastore.connect_to_signal('Updated', self.datastore_updated_cb)
        _datastore.connect_to_signal('Deleted', self.datastore_deleted_cb)

        self.selected_journal_entry = None

    def update_preview_cb(self,  file_chooser, preview):
        filename = file_chooser.get_preview_filename()
        file_mimetype = mime.get_for_file(filename)
        if file_mimetype.startswith('image/'):
            pixbuf = gtk.gdk.pixbuf_new_from_file_at_size(filename, 
                                                          style.zoom(320), style.zoom(240))
            preview.set_from_pixbuf(pixbuf)
            have_preview = True
        elif file_mimetype  == 'application/x-cbz':
            fname = self.extract_image(filename)
            pixbuf = gtk.gdk.pixbuf_new_from_file_at_size(fname, 
                                                          style.zoom(320), style.zoom(240))
            preview.set_from_pixbuf(pixbuf)
            have_preview = True
            os.remove(fname)
        else:
            have_preview = False
        file_chooser.set_preview_widget_active(have_preview)
        return

    def key_press_event_cb(self, entry, event):
        self.btn_save.props.sensitive = True

    def save_button_press_event_cb(self, entry, event):
        self.update_entry()

    def delete_button_press_event_cb(self, entry, event):
        datastore.delete(self.selected_journal_entry.object_id)

    def datastore_created_cb(self, uid):
        self.load_journal_table()
        
    def datastore_updated_cb(self,  uid):
        self.load_journal_table()
        object_id = self.selected_journal_entry.object_id
        jobject = datastore.get(object_id)
        self.set_form_fields(jobject)
        
    def datastore_deleted_cb(self,  uid):
        self.load_journal_table()
        object_id = self.selected_journal_entry.object_id
        try:
            jobject = datastore.get(object_id)
        except:
            if not self.selected_path is None:
                self.selection_journal.select_path(self.selected_path)
            else:
                self.title_entry.set_text('')
                description_textbuffer = self.description_textview.get_buffer()
                description_textbuffer.set_text('')
                tags_textbuffer = self.tags_textview.get_buffer()
                tags_textbuffer.set_text('')
                self.btn_save.props.sensitive = False
                self.btn_delete.props.sensitive = False
                self.image.clear()
                self.image.show()
        
    def update_entry(self):
        needs_update = False
        needs_reload = False
        
        if self.selected_journal_entry is None:
            return

        object_id = self.selected_journal_entry.object_id
        jobject = datastore.get(object_id)
        
        old_title = jobject.metadata.get('title', None)
        if old_title != self.title_entry.props.text:
            jobject.metadata['title'] = self.title_entry.props.text
            jobject.metadata['title_set_by_user'] = '1'
            needs_update = True
            needs_reload = True

        old_tags = jobject.metadata.get('tags', None)
        new_tags = self.tags_textview.props.buffer.props.text
        if old_tags != new_tags:
            jobject.metadata['tags'] = new_tags
            needs_update = True

        old_description = jobject.metadata.get('description', None)
        new_description = self.description_textview.props.buffer.props.text
        if old_description != new_description:
            jobject.metadata['description'] = new_description
            needs_update = True

        if needs_update:
            datastore.write(jobject, update_mtime=False,
                            reply_handler=self.datastore_write_cb,
                            error_handler=self.datastore_write_error_cb)
        if needs_reload:
            self.load_journal_table()

        self.btn_save.props.sensitive = False
    
    def datastore_write_cb(self):
        pass

    def datastore_write_error_cb(self, error):
        logging.error('sugarcommander.datastore_write_error_cb: %r' % error)

    def close(self,  skip_save=False):
        "Override the close method so we don't try to create a Journal entry."
        activity.Activity.close(self,  True)

    def selection_journal_cb(self, selection):
        self.btn_delete.props.sensitive = True
        tv = selection.get_tree_view()
        model = tv.get_model()
        sel = selection.get_selected()
        if sel:
            model, iter = sel
            jobject = model.get_value(iter,COLUMN_JOBJECT)
            jobject = datastore.get(jobject.object_id)
            self.selected_journal_entry = jobject
            self.set_form_fields(jobject)
            self.selected_path = model.get_path(iter)

    def set_form_fields(self, jobject):
        self.title_entry.set_text(jobject.metadata['title'])
        description_textbuffer = self.description_textview.get_buffer()
        if jobject.metadata.has_key('description'):
            description_textbuffer.set_text(jobject.metadata['description'])
        else:
            description_textbuffer.set_text('')
        tags_textbuffer = self.tags_textview.get_buffer()
        if jobject.metadata.has_key('tags'):
            tags_textbuffer.set_text(jobject.metadata['tags'])
        else:
            tags_textbuffer.set_text('')
        self.create_preview(jobject.object_id)

    def create_preview(self,  object_id):
        jobject = datastore.get(object_id)
        
        if jobject.metadata.has_key('preview'):
            preview = jobject.metadata['preview']
            if preview is None or preview == '' or preview == 'None':
                if jobject.metadata['mime_type'] .startswith('image/'):
                    filename = jobject.get_file_path()
                    self.show_image(filename)
                    return
                if jobject.metadata['mime_type']  == 'application/x-cbz':
                    filename = jobject.get_file_path()
                    fname = self.extract_image(filename)
                    self.show_image(fname)
                    os.remove(fname)
                    return

        if jobject.metadata.has_key('preview') and \
                len(jobject.metadata['preview']) > 4:
            
            if jobject.metadata['preview'][1:4] == 'PNG':
                preview_data = jobject.metadata['preview']
            else:
                import base64
                preview_data = base64.b64decode(jobject.metadata['preview'])

            loader = gtk.gdk.PixbufLoader()
            loader.write(preview_data)
            scaled_buf = loader.get_pixbuf()
            loader.close()
            self.image.set_from_pixbuf(scaled_buf)
            self.image.show()
        else:
            self.image.clear()
            self.image.show()

    def load_journal_table(self):
        self.btn_save.props.sensitive = False
        self.btn_delete.props.sensitive = False
        ds_mounts = datastore.mounts()
        mountpoint_id = None
        if len(ds_mounts) == 1 and ds_mounts[0]['id'] == 1:
               pass
        else:
            for mountpoint in ds_mounts:
                id = mountpoint['id'] 
                uri = mountpoint['uri']
                if uri.startswith('/home'):
                    mountpoint_id = id

        query = {}
        if mountpoint_id is not None:
            query['mountpoints'] = [ mountpoint_id ]
        ds_objects, num_objects = datastore.find(query, properties=['uid', 
            'title',  'mime_type'])

        self.ls_journal.clear()
        for i in xrange (0, num_objects, 1):
            iter = self.ls_journal.append()
            title = ds_objects[i].metadata['title']
            self.ls_journal.set(iter, COLUMN_TITLE, title)
            mime = ds_objects[i].metadata['mime_type']
            self.ls_journal.set(iter, COLUMN_MIME, mime)
            self.ls_journal.set(iter, COLUMN_JOBJECT, ds_objects[i])
            if not self.selected_journal_entry is None and \
                self.selected_journal_entry.object_id == ds_objects[i].object_id:
                self.selection_journal.select_iter(iter)

        self.ls_journal.set_sort_column_id(COLUMN_TITLE,  gtk.SORT_ASCENDING)
        v_adjustment = self.list_scroller_journal.get_vadjustment()
        v_adjustment.value = 0
        return ds_objects[0]

    def create_journal_entry(self,  widget,  data=None):
        filename = self._filechooser.get_filename()
        journal_entry = datastore.create()
        journal_entry.metadata['title'] = self.make_new_filename(filename)
        journal_entry.metadata['title_set_by_user'] = '1'
        journal_entry.metadata['keep'] = '0'
        file_mimetype = mime.get_for_file(filename)
        if not file_mimetype is None:
            journal_entry.metadata['mime_type'] = file_mimetype
        journal_entry.metadata['buddies'] = ''
        if file_mimetype.startswith('image/'):
            preview = self.create_preview_metadata(filename)
        elif file_mimetype  == 'application/x-cbz':
            fname = self.extract_image(filename)
            preview = self.create_preview_metadata(fname)
            os.remove(fname)
        else:
            preview = ''
        if not preview  == '':
            journal_entry.metadata['preview'] =  dbus.ByteArray(preview)
        else:
            journal_entry.metadata['preview'] =  ''
            
        journal_entry.file_path = filename
        datastore.write(journal_entry)
        self.alert(_('Success'),  _('%s added to Journal.') 
                    % self.make_new_filename(filename))
   
    def alert(self, title, text=None):
        alert = NotifyAlert(timeout=20)
        alert.props.title = title
        alert.props.msg = text
        self.add_alert(alert)
        alert.connect('response', self.alert_cancel_cb)
        alert.show()

    def alert_cancel_cb(self, alert, response_id):
        self.remove_alert(alert)

    def show_image(self, filename):
        "display a resized image in a preview"
        scaled_buf = gtk.gdk.pixbuf_new_from_file_at_size(filename, 
                                                          style.zoom(320), style.zoom(240))
        self.image.set_from_pixbuf(scaled_buf)
        self.image.show()

    def extract_image(self,  filename):
        zf = zipfile.ZipFile(filename, 'r')
        image_files = zf.namelist()
        image_files.sort()
        if len(image_files) > 0:
            if self.save_extracted_file(zf, image_files[0]):
                fname = os.path.join(self.get_activity_root(), 'instance',  
                                     self.make_new_filename(image_files[0]))
                return fname

    def save_extracted_file(self, zipfile, filename):
        "Extract the file to a temp directory for viewing"
        try:
            filebytes = zipfile.read(filename)
        except zipfile.BadZipfile, err:
            print 'Error opening the zip file: %s' % (err)
            return False
        except KeyError,  err:
            self.alert('Key Error', 'Zipfile key not found: '  
                        + str(filename))
            return
        outfn = self.make_new_filename(filename)
        if (outfn == ''):
            return False
        fname = os.path.join(self.get_activity_root(), 'instance',  outfn)
        f = open(fname, 'w')
        try:
            f.write(filebytes)
        finally:
            f.close()
        return True

    def make_new_filename(self, filename):
        partition_tuple = filename.rpartition('/')
        return partition_tuple[2]

    def create_preview_metadata(self,  filename):

        file_mimetype = mime.get_for_file(filename)
        if not file_mimetype.startswith('image/'):
            return ''
            
        scaled_pixbuf = gtk.gdk.pixbuf_new_from_file_at_size(filename,
                                                              style.zoom(320), style.zoom(240))
        preview_data = []

        def save_func(buf, data):
            data.append(buf)

        scaled_pixbuf.save_to_callback(save_func, 'png', 
                                       user_data=preview_data)
        preview_data = ''.join(preview_data)

        return preview_data
