from gettext import gettext as _

from gi.repository import Gtk
from gi.repository import Gdk


class toplevel(Gtk.Window):

    def __init__(self):
        self.set_size_request(1200, 900)

        self.contents = Gtk.HBox()
        self.add(self.contents)

        self.vbox2 = Gtk.VBox()
        self.vbox2.set_size_request(550, 1)
        self.contents.add(self.vbox2)

        self.frame1 = Gtk.Frame()
        self.frame1.set_size_request(1, 300)
        self.frame1.set_label_align(0, self.frame1.get_label_align()[1])
        self.frame1.set_shadow_type(Gtk.ShadowType.IN)
        self.vbox2.pack_start(self.frame1, True, True, 5)

        self.alignment1 = Gtk.Alignment()
        self.alignment1.props.left_padding = 12
        self.frame1.add(self.alignment1)

        self.scrolledwindow1 = Gtk.ScrolledWindow()
        self.scrolledwindow1.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)

        self.journal = Gtk.TreeView()
        self.journal.set_headers_clickable(True)
        self.scrolledwindow1.add(self.journal)

        self.label1 = Gtk.Label()
        self.label1.set_markup("<b>%s</b>" % _("Journal"))

        self.frame2 = Gtk.Frame()
        self.frame2.set_size_request(1, 250)
        self.frame2.set_label_align(0, self.frame2.get_label_align()[1])
        self.frame2.set_shadow_type(Gtk.ShadowType.NONE)
        self.frame1.add(self.frame2)

        self.alignment2 = Gtk.Alignment()
        self.alignment2.props.left_padding = 12
        self.frame2.add(self.alignment2)

        self.scrolledwindow2 = Gtk.ScrolledWindow()
        self.scrolledwindow2.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)

        self.file_system = Gtk.TreeView()
        self.file_system.set_tooltip_text(_("These are other examples of Activities you can examine."))
        ##self.file_system.connect("toggle-cursor-row", self.i_dont_know)
        ##self.file_system.connect("row-activated", self.i_dont_know)
        ##self.file_system.connect("cursor-changed", self.i_dont_know)
        self.scrolledwindow2.add(self.file_system)

        self.file_system_label = Gtk.Label()
        self.file_system_label.set_markup("<b>%s</b>" % _("Activities Directory"))
        self.frame2.add(self.file_system_label)

        self.frame3 = Gtk.Frame()
        self.frame3.set_size_request(1, 250)
        self.frame3.set_label_align(0, self.frame3.get_label_align()[1])
        self.frame3.set_shadow_type(Gtk.ShadowType.NONE)
        self.vbox2.pack_start(self.frame3, True, True, 5)

        self.alignment3 = Gtk.Alignment()
        self.alignment3.props.left_padding = 12
        self.alignment3.props.right_padding = 5
        self.frame3.add(self.alignment3)

        self.scrolledwindow3 = Gtk.ScrolledWindow()
        self.scrolledwindow3.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        self.alignment3.add(self.scrolledwindow3)

        self.examples = Gtk.TreeView()
        self.examples.set_headers_clickable(True)
        ##self.examples.connect("toggle-cursor-row", self.i_dont_know)
        ##self.examples.connect("row-activated", self.i_dont_know)
        ##self.examples.connect("cursor-changed", self.i_dont_know)
        self.scrolledwindow3.add(self.examples)

        self.label3 = Gtk.Label()
        self.label3.set_markup("<b>Examples</b>")
        self.frame3.add(self.label3)

        self.table1 = Gtk.Table(20, 1)
        self.table1.set_homogeneous(True)
        self.contents.pack_start(self.table1, True, True, 0)

        self.file_toggle = Gtk.Button.new_with_label(_("Home"))
        self.file_toggle.set_tooltip_text(_('Switch views between the "Installed" Activities directory and your "home" storage directory'))
        ##self.file_toggle.connect("clicked", "file_toggle_clicked_cb")
        self.table1.attach(self.file_toggle, 13, 14, 1, 1)

        self.to_activities = Gtk.Button()
        self.to_activities.set_tooltip_text(_('Copy the files in the debug workplace to your "home" storage directory'))
        self.to_activities.add(Gtk.Arrow.new(Gtk.ArrowType.LEFT, Gtk.ShadowType.NONE))
        ##self.connect("clicked", "to_activities_clicked_cb")
        self.table1.attach(self.to_activities, 11, 12, 1, 1)

        self.from_examples = Gtk.Button()
        self.from_examples.set_tooltip_text(_('Load and modify these example programs. See the help Tutorials'))
        self.from_examples.add(Gtk.Arrow())
        ##self.from_examples.connect("clicked", "from_examples_clicked_cb")
        self.table1.attach(self.from_examples, 17, 18, 1, 1)

        self.from_activities = Gtk.Button()
        self.from_activities.set_tooltip_text(_('Copy the selected directory or file from your "home" storage to the debug workplace'))
        self.from_activities.add(Gtk.Arrow())
        ##self.from_activities.connect("clicked", "from_activities_clicked_cb")
        self.table1.attach(self.from_activities, 9, 10, 1, 1)

        self.to_journal = Gtk.Button()
        self.to_journal.set_tooltip_text(_('Zip up all the files in your debug workplace and store them in the Journal'))
        self.to_journal.add(Gtk.Arrow.new(Gtk.ArrowType.LEFT, Gtk.ShadowType.NONE))
        ##self.to_journal.connect("clicked", "to_journal_clicked_cb")
        self.table1.attach(self.to_journal, 4, 5, 1, 1)

        self.from_journal = Gtk.Button()
        self.from_journal.set_tooltip_text(_('Load the selected Journal XO (or tar.gz) file to the debug workplace'))
        self.from_journal.add(Gtk.Arrow())
        ##self.from_journal.connect("clicked", "from_journal_clicked_cb")
        self.table1.attach(self.from_journal, 2, 3, 1, 1)

        self.PROJECT_DETAILS = Gtk.Frame()
        self.PROJECT_DETAILS.set_label_align(0, 0)
        self.PROJECT_DETAILS.set_shadow_type(Gtk.ShadowType.ETCHED_OUT)
        self.table1.attach(self.PROJECT_DETAILS, 5, 2, 1, 1)

        self.playpen_event_box = Gtk.EventBox()
        self.playpen_event_box.set_size_request(1, 650)
        self.PROJECT_DETAILS.add(self.playpen_event_box)

        self.playpen = Gtk.Frame()
        self.playpen.set_label_align(0, 1)
        self.playpen_event_box.add(self.playpen)

        self.vbox1 = Gtk.VBox()
        self.vbox1.set_size_request(550, 1)
        self.playpen.add(self.vbox1)

        self.table2 = Gtk.Table(14, 10)
        self.table2.set_size_request(1, 800)
        self.table2.set_homogeneous(True)

        self.icon_outline = Gtk.ComboBox()
        ##self.icon_outline.connect("changed", "icon_outline_changed_cb")
        self.table2.attach(self.icon_outline, 4, 7, 5, 6)

        self.create_icon = Gtk.Button()
        ##self.create_icon.connect("clicked", "create_icon_clicked_cb")
        self.table2.attach(self.create_icon, 7, 10, 5, 6)

        self.label16 = Gtk.Label()
        self.label16.set_markup("<b>%s</b>" % _("Create"))
        self.create_icon.add(self.label16)

        self.icon_chr = Gtk.Entry()
        self.icon_chr.set_max_length(2)
        ##self.icon_chr.connect("leave-notify-event", "icon_chr_leave_notify_event_cb")
        self.table2.attach(self.icon_chr, 3, 4, 5, 6)

        self.label15 = Gtk.Label()
        self.label15.set_markup("<b>%s<b>" % "Icon(2char)")
        self.table2.attach(self.label15, 3, 5, 6, 1)

        self.clear = Gtk.Button()
        ##self.connect("clicked", "clear_clicked_cb")
        self.table2.attach(self.clear, 1, 5, 13, 14)

        self.label4 = Gtk.Label()
        self.label4.set_markup("<b>%s</b>" % _("Clear Work Area"))
        self.clear.add(self.label4)

        self.frame5 = Gtk.Frame()
        self.frame5.set_label_align(0, 0)
        self.frame5.set_shadow_type(Gtk.ShadowType.NONE)
        self.table2.attach(self.frame5, 10, 6, 13, 1)

        self.alignment4 = Gtk.Alignment()
        self.alignment4.props.left_padding = 12
        self.frame5.add(self.alignment4)

        self.scrolledwindow4 = Gtk.ScrolledWindow()
        self.scrolledwindow4.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        self.alignment4.add(self.scrolledwindow4)

        self.mainfest = Gtk.TreeView()
        self.mainfest.set_headers_clickable(True)
        ##self.mainfest.connect("select-cursor-row", "file_system_select_cursor_row_cb")
        ##self.mainfest.connect("row-activated", "file_system_row_activated_cb")
        ##self.mainfest.connect("cursor-changed", "file_system_row_activated_cb")
        self.scrolledwindow4.add(self.mainfest)

        self.label9 = Gtk.Label()
        self.label9.set_markup("<b>%s</b>" % _("Project Files"))
        self.frame5.add(self.label9)

        self.delete_file = Gtk.Button()
        ##self.delete_file.connect("clicked", "delete_file_clicked_cb")
        self.table2.attach(self.delete_file, 6, 9, 13, 14)

        self.label12 = Gtk.Label()
        self.label12.set_markup("<b>%s</b>" % _("Delete"))
        self.delete_file.add(self.label12)

        self.help = Gtk.Button()
        ##self.help.connect("clicked", "help_clicked_cb")
        self.table2.attach(self.help, 7, 10, 1, 1)

        self.label14 = Gtk.Label()
        self.label14.set_markup("<b>%s</b>" % _("Write info"))
        self.label14.set_justify(Gtk.Justification.CENTER)
        self.help.add(self.label14)

        self.label13 = Gtk.Label(_("Version: "))
        self.label13.set_xalign(1)
        self.label13.set_justify(Gtk.Justification.RIGHT)
        self.table2.attach(self.label13, 6, 8, 1, 2)

        self.version = Gtk.Entry()
        ##self.version.connect("leave-notify-event", "version_leave_notify_event_cb")
        self.table2.attach(self.version, 8, 9, 1, 2)

        self._class = Gtk.Entry()
        ##self._class.connect("leave-notify-event", "class_leave_notify_event_cb")
        self.table2.attach(self._class, 6, 9, 3, 4)

        self.label11 = Gtk.Label(_("Class: "))
        self.label11.set_xalign(1)
        self.table2.attach(self.label11, 5, 6, 3, 4)

        self.label10 = Gtk.Label(_("Project Data\n(./activity/activity.info)"))
        self.label10.set_justify(Gtk.Justification.CENTER)
        self.table2.attach(self.label10, 2, 7, 1, 1)

        self.label8 = Gtk.Label(_("Name: "))
        self.label8.set_justify(Gtk.Justification.RIGHT)
        self.table2.attach(self.label8, 2, 1, 2, 1)

        self.label6 = Gtk.Label(_("Unique id: "))
        self.label6.set_justify(Gtk.Justification.RIGHT)
        self.table2.attach(self.label6, 2, 2, 3, 1)

        self.label7 = Gtk.Label(_("Module: "))
        self.label7.set_justify(Gtk.Justification.RIGHT)
        self.table2.attach(self.label7, 2, 3, 4, 1)

        self.name = Gtk.Entry()
        ##self.name.connect("leave-notify-event", "name_leave_notify_event_cb")
        self.table2.attach(self.name, 2, 6, 1, 2)

        self.bundle_id = Gtk.Entry()
        ##self.bundle_id.connect("leave-notify-event", "bundle_id_leave_notify_event_cb")
        self.table2.attach(self.bundle_id, 2, 9, 2, 3)

        self.module = Gtk.Entry()
        ##self.module.connect("leave-notify-event", "module_leave_notify_event_cb")
        self.table2.attach(self.module, 2, 5, 3, 4)

        self.label5 = Gtk.Label()
        self.label5.set_markup("<b>%s</b>" % _("PROJECT  INFORMATION"))
        self.playpen.add(self.label5)


class find(Gtk.Window):

    def __init__(self):
        Gtk.Window.__init__(self)

        self.set_size_request(200, 100)
        self.set_title(_("Find / Replace"))
        self.set_resizable(False)
        self.set_modal(True)
        self.set_type_hint(Gdk.WindowTypeHint.DIALOG)

        self.table3 = Gtk.Table(6, 9, 1, 1)
        self.table3.set_homogeneous(True)
        self.add(self.table3)

        self.find_close = Gtk.Button.new_with_label(_("Close"))
        ##self.find_close.connect("clicked", "find_close_clicked_cb")
        self.table3.attach(self.find_close, 6, 9, 4, 5)

        self.table3.attach(Gtk.Label(_("Find What:")), 1, 4, 1, 1)

        self.find_entry = Gtk.Entry()
        ##self.entry.connect("changed", "find_entry_changed_cb")
        self.find_entry.attach(self.find_entry, 5, 1, 2, 1)

        self.table3.attach(Gtk.Label(_("Replace with:")), 1, 4, 2, 3)

        self.replace_entry = Gtk.Entry()
        ##self.replace_entry.connect("changed", "replace_entry_changed_cb")
        self.table3.attach(self.replace_entry, 5, 3, 4, 1)

        self.checkbutton1 = Gtk.CheckButton.new_with_label(_("Match Case"))
        self.checkbutton1.props.xalign = 0.40000000596046448
        self.table3.attach(self.checkbutton1, 5, 4, 5, 1)

        self.find_previous = Gtk.Button.new_with_label(_("Previous"))
        ##self.find_previous.connect("clicked", "find_previous_clicked_cb")
        self.table3.attach(self.find_previous, 6, 9, 1, 1)

        self.find_next = Gtk.Button.new_with_label(_("Next"))
        ##self.find_next.connect("clicked", "find_next_clicked_cb")
        self.table3.attach(self.find_next, 6, 9, 1, 2)

        self.replace = Gtk.Button.new_with_label(_("Next"))
        ##self.replace.connect("clicked", "replace_clicked_cb")
        self.table3.attach(self.replace, 6, 9, 2, 3)

        self.entry1 = Gtk.Entry()
        self.entry1.attach(self.entry1, 9, 5, 6, 1)


class browser(Gtk.Window):

    def __init__(self):
        Gtk.Window.__init__(self)

        self.set_resizable(False)

        self.help_notebook = Gtk.Notebook()
        self.add(self.help_notebook)

        self.scrolledwindow5 = Gtk.ScrolledWindow()
        self.scrolledwindow5.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        self.help_notebook.append_page(self.scrolledwindow5, Gtk.Label(_("page 1")))

        self.help_notebook.append_page(Gtk.VBox(), Gtk.Label(_("page 2")))
        self.help_notebook.append_page(Gtk.VBox(), Gtk.Label(_("page 3")))

