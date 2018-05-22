#! /usr/bin/env python
# coding: utf-8
#
#    Project: BioCAT staff beamline control software (CATCON)
#             https://github.com/biocatiit/beamline-control-staff
#
#
#    Principal author:       Jesse Hopkins
#
#    This is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    This software is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with this software.  If not, see <http://www.gnu.org/licenses/>.
from __future__ import absolute_import, division, print_function, unicode_literals
from builtins import object, range, map
from io import open

import sys
import threading
import traceback
import os
import json
import collections

import wx
import wx.aui as aui
from wx.lib.agw import ultimatelistctrl as ULC
import numpy as np

import utils
utils.set_mppath() #This must be done before importing any Mp Modules.
import Mp as mp
import MpWx as mpwx

import motorcon as mc
import ampcon as ac


class MainFrame(wx.Frame):

    def __init__(self, *args, **kwargs):
        wx.Frame.__init__(self, None, *args, **kwargs)

        self.controls = collections.OrderedDict()
        self.ctrl_types = {'Amplifier'  : ac.AmpPanel,
                        'Motor'         : mc.MotorPanel,
                        }

        self._start_mxdatabase()
        self._load_controls()
        self._create_layout()

        self.mx_timer = wx.Timer()
        self.mx_timer.Bind(wx.EVT_TIMER, self._on_mxtimer)

        self.Bind(wx.EVT_CLOSE, self._on_closewindow)








        self.mx_timer.Start(100)

    def _start_mxdatabase(self):
        try:
            # First try to get the name from an environment variable.
            database_filename = os.environ["MXDATABASE"]
        except:
            # If the environment variable does not exist, construct
            # the filename for the default MX database.
            mxdir = utils.get_mxdir()
            database_filename = os.path.join(mxdir, "etc", "mxmotor.dat")
            database_filename = os.path.normpath(database_filename)

        self.mx_db = mp.setup_database(database_filename)
        self.mx_db.set_plot_enable(2)

    def _load_controls(self):
        settings = 'sector_ctrl_settings.txt'
        if os.path.exists(settings):
            with open(settings, 'r') as f:
                self.controls = json.load(f)

    def _create_layout(self):
        self._mgr = aui.AuiManager()
        self._mgr.SetManagedWindow(self)

        self._ctrl_nb = aui.AuiNotebook(self, style=aui.AUI_NB_TAB_SPLIT|
            aui.AUI_NB_TAB_MOVE|aui.AUI_NB_TOP)
        ctrlnb_info = aui.AuiPaneInfo().Floatable(False).Center().CloseButton(False)
        ctrlnb_info.Gripper(False).PaneBorder(False).CaptionVisible(False)

        for key in self.controls.keys():
            ctrl_panel = CtrlsPanel(self.controls[key], self, parent=self._ctrl_nb, name=key)
            self._ctrl_nb.AddPage(ctrl_panel, key)


        add_ctrl_btn = wx.Button(self, label='Add New Control(s)')
        add_ctrl_btn.Bind(wx.EVT_BUTTON, self._on_addctrl)
        add_ctrl_info = aui.AuiPaneInfo().Floatable(False).Bottom().CloseButton(False)
        add_ctrl_info.Gripper(False).PaneBorder(False).CaptionVisible(False).Fixed()

        self._mgr.AddPane(self._ctrl_nb, ctrlnb_info)
        self._mgr.AddPane(add_ctrl_btn, add_ctrl_info)

        self._mgr.Update()

        # self._load_layout()

    def _on_mxtimer(self, evt):
        """
        Called on the mx_timer, refreshes mx values in the GUI by calling
        wait_for_messages on the database.
        """
        self.mx_db.wait_for_messages(0.01)

    def _on_closewindow(self, evt):
        perspective = self._mgr.SavePerspective()
        with open('sector_ctrl_layout.bak', 'w') as f:
            f.write(perspective)

        with open('sector_ctrl_settings.txt', 'w') as f:
            f.write(unicode(json.dumps(self.controls, indent=4, sort_keys=False, cls=MyEncoder)))

        self.Destroy()

    def _load_layout(self):
        perspective = 'sector_ctrl_layout.bak'
        if os.path.exists(perspective):
            with open(perspective) as f:
                layout = f.read()
            self._mgr.LoadPerspective(layout)

    def show_ctrls(self, group, ctrl):
        ctrl_frame = CtrlsFrame(self.controls[group][ctrl], self.mx_db, parent=self)
        ctrl_frame.Show()

    def _on_addctrl(self, evt):
        self.add_ctrl()

    def add_ctrl(self):
        add_dlg = AddCtrlDialog(parent=self, title='Create new control set',
            style=wx.RESIZE_BORDER|wx.CLOSE_BOX|wx.CAPTION)
        if add_dlg.ShowModal() == wx.ID_OK:
            ctrl_data = add_dlg.ctrl_data

            group = add_dlg.group
            ctrl = ctrl_data[0]['title']

            if group not in self.controls:
                self.controls[group]={}
            self.controls[group][ctrl] = ctrl_data

            self.show_ctrls(group, ctrl)

        add_dlg.Destroy()

class CtrlsPanel(wx.Panel):

    def __init__(self, panel_data, main_frame, *args, **kwargs):
        wx.Panel.__init__(self, *args, **kwargs)
        self.main_frame = main_frame
        self._create_layout(panel_data)

    def _create_layout(self, panel_data):
        nitems = len(panel_data.keys())

        grid_sizer = wx.FlexGridSizer(rows=(nitems+1)//2, cols=2, vgap=4, hgap=4)

        for label in panel_data.keys():
            button = wx.Button(self, label=label, name=label)
            button.Bind(wx.EVT_BUTTON, self._on_button)
            grid_sizer.Add(button)

        top_sizer = wx.BoxSizer()

        top_sizer.Add(grid_sizer)

        self.SetSizer(top_sizer)

    def _on_button(self, evt):
        button = evt.GetEventObject()

        btn_name = button.GetName()
        panel_name = self.GetName()

        self.main_frame.show_ctrls(panel_name, btn_name)

class CtrlsFrame(wx.Frame):
    def __init__(self, ctrls, mx_db, *args, **kwargs):
        wx.Frame.__init__(self, title=ctrls[0]['title'], *args, **kwargs)

        self._create_layout(ctrls, mx_db)

        self.Fit()
        self.Raise()

    def _create_layout(self, ctrls, mx_db):
        settings = ctrls[0]
        ctrls = ctrls[1:]
        main_window = self.GetParent()

        grid_sizer = wx.FlexGridSizer(rows=settings['rows'], cols=settings['cols'],
            hgap=2, vgap=2)

        for i in range(settings['cols']):
            grid_sizer.AddGrowableCol(i)

        for ctrl_name, ctrl_type in ctrls:
            ctrl_panel = main_window.ctrl_types[ctrl_type](ctrl_name, mx_db, self)
            box_sizer = wx.StaticBoxSizer(wx.StaticBox(self, label='{} Control'.format(ctrl_name)))
            box_sizer.Add(ctrl_panel)
            grid_sizer.Add(box_sizer, flag=wx.EXPAND)

        self.SetSizer(grid_sizer)

class AddCtrlDialog(wx.Dialog):
    def __init__(self, *args, **kwargs):
        wx.Dialog.__init__(self, *args, **kwargs)

        self._create_layout()

    def _create_layout(self):
        info_grid = wx.FlexGridSizer(rows=4, cols=2, vgap=2, hgap=2)
        self.group_ctrl = wx.TextCtrl(self)
        self.title = wx.TextCtrl(self)
        self.rows = wx.TextCtrl(self, value='1')
        self.cols = wx.TextCtrl(self, value='1')

        info_grid.Add(wx.StaticText(self, label='Control(s) Group:'))
        info_grid.Add(self.group_ctrl)
        info_grid.Add(wx.StaticText(self, label='Control(s) Name:'))
        info_grid.Add(self.title)
        info_grid.Add(wx.StaticText(self, label='Number of rows:'))
        info_grid.Add(self.rows)
        info_grid.Add(wx.StaticText(self, label='Number of columns:'))
        info_grid.Add(self.cols)

        self.list_ctrl = ULC.UltimateListCtrl(self, agwStyle=ULC.ULC_REPORT|ULC.ULC_USER_ROW_HEIGHT)
        self.list_ctrl.InsertColumn(0, 'MX Record Name')
        self.list_ctrl.InsertColumn(1, 'Control Type')
        self.list_ctrl.SetUserLineHeight(25)

        add_btn = wx.Button(self, label='Add Control')
        add_btn.Bind(wx.EVT_BUTTON, self._on_add)

        list_ctrl_btn_sizer = wx.BoxSizer(wx.HORIZONTAL)
        list_ctrl_btn_sizer.Add(add_btn)

        button_sizer = self.CreateButtonSizer(wx.OK | wx.CANCEL)
        self.Bind(wx.EVT_BUTTON, self._on_ok, id=wx.ID_OK)

        top_sizer = wx.BoxSizer(wx.VERTICAL)
        top_sizer.Add(info_grid)
        top_sizer.Add(self.list_ctrl, 1, flag=wx.EXPAND)
        top_sizer.Add(list_ctrl_btn_sizer, flag=wx.CENTER)
        top_sizer.Add(button_sizer)

        self.list_ctrl.SetColumnWidth(0, wx.LIST_AUTOSIZE_USEHEADER)
        self.list_ctrl.SetColumnWidth(1, wx.LIST_AUTOSIZE_USEHEADER)

        self.SetSizer(top_sizer)

    def _on_add(self, evt):
        index = self.list_ctrl.InsertStringItem(sys.maxint, '')
        main_frame = self.GetParent()

        item = self.list_ctrl.GetItem(index, 0)
        textctrl = wx.TextCtrl(self.list_ctrl)
        item.SetWindow(textctrl, expand=True)
        item.SetAlign(ULC.ULC_FORMAT_LEFT)
        self.list_ctrl.SetItem(item)

        item = self.list_ctrl.GetItem(index, 1)
        choice_ctrl = wx.Choice(self.list_ctrl, choices=main_frame.ctrl_types.keys(),
            style=wx.CB_SORT)
        item.SetWindow(choice_ctrl, expand=True)
        item.SetAlign(ULC.ULC_FORMAT_LEFT)
        self.list_ctrl.SetItem(item)

        self.list_ctrl.SetColumnWidth(1, wx.LIST_AUTOSIZE)

    def _on_ok(self, evt):
        rows = int(self.rows.GetValue())
        cols = int(self.cols.GetValue())

        if self.group_ctrl.GetValue() == '' or self.title.GetValue() == '':
            msg = ('The control(s) must have a group and name.')
            wx.MessageBox(msg, 'Control group and name required')
            return
        if rows*cols < self.list_ctrl.GetItemCount():
            msg = ('The value of rows*cols must be equal to or greater than the '
                'number of controls added to the panel. Please increase the number of '
                'rows and/or columns or remove controls.')
            wx.MessageBox(msg, 'Error adding controls')
            return

        self.ctrl_data = []
        self.ctrl_data.append({'title' :self.title.GetValue(),
            'rows'  : rows,
            'cols'  : cols,
            })
        for i in range(self.list_ctrl.GetItemCount()):
            ctrl_name = self.list_ctrl.GetItem(i, 0).GetWindow().GetValue()
            ctrl_type = self.list_ctrl.GetItem(i, 1).GetWindow().GetValue()

            self.ctrl_data.append((ctrl_name, ctrl_type))

        self.group = self.group_ctrl.GetValue()

        self.EndModal(wx.ID_OK)
        return

#This class goes with write header, and was lifted from:
#https://stackoverflow.com/questions/27050108/convert-numpy-type-to-python/27050186#27050186
class MyEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, np.integer):
            return int(obj)
        elif isinstance(obj, np.floating):
            return float(obj)
        elif isinstance(obj, np.ndarray):
            return obj.tolist()
        else:
            return super(MyEncoder, self).default(obj)

#########################################
#This gets around not being able to catch errors in threads
#Code from: https://bugs.python.org/issue1230540
def setup_thread_excepthook():
    """
    Workaround for `sys.excepthook` thread bug from:
    http://bugs.python.org/issue1230540

    Call once from the main thread before creating any threads.
    """

    init_original = threading.Thread.__init__

    def init(self, *args, **kwargs):

        init_original(self, *args, **kwargs)
        run_original = self.run

        def run_with_except_hook(*args2, **kwargs2):
            try:
                run_original(*args2, **kwargs2)
            except Exception:
                sys.excepthook(*sys.exc_info())

        self.run = run_with_except_hook

    threading.Thread.__init__ = init


class MyApp(wx.App):

    def OnInit(self):

        frame = MainFrame(title='BioCAT Staff Controls', name='MainFrame')
        frame.Show()

        return True

    def BringWindowToFront(self):
        try: # it's possible for this event to come when the frame is closed
            self.GetTopWindow().Raise()
        except:
            pass

    #########################
    # Here's some stuff to inform users of unhandled errors, and quit
    # gracefully. From http://apprize.info/python/wxpython/10.html

    def ExceptionHook(self, errType, value, trace):
        err = traceback.format_exception(errType, value, trace)
        errTxt = "\n".join(err)
        msg = ("An unexpected error has occurred, please report it to the "
                "developers. You may need to restart RAW to continue working"
                "\n\nError:\n%s" %(errTxt))

        if self and self.IsMainLoopRunning():
            if not self.HandleError(value):
                wx.CallAfter(wx.lib.dialogs.scrolledMessageDialog, None, msg, "Unexpected Error")
        else:
            sys.stderr.write(msg)

    def HandleError(self, error):
        """ Override in subclass to handle errors
        @return: True to allow program to continue running withou showing error"""

        return False


if __name__ == '__main__':
    setup_thread_excepthook()

    app = MyApp(0)   #MyApp(redirect = True)
    app.MainLoop()
