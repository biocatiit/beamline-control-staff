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
import platform
import copy

import wx
import wx.aui as aui
from wx.lib.agw import ultimatelistctrl as ULC
import wx.lib.mixins.listctrl  as  listmix
import wx.richtext as rt
import numpy as np

import utils
utils.set_mppath() #This must be done before importing any Mp Modules.
import Mp as mp

import motorcon as mc
import ampcon as ac


class MainFrame(wx.Frame):

    def __init__(self, *args, **kwargs):
        wx.Frame.__init__(self, None, *args, **kwargs)

        self.controls = collections.OrderedDict()
        self.ctrl_types = {'Amplifier'  : ac.AmpPanel,
                        'Motor'         : mc.MotorPanel,
                        }
        self.ctrl_panels = {}

        self._start_mxdatabase()
        self._load_controls()
        self._create_layout()

        self.mx_timer = wx.Timer()
        self.mx_timer.Bind(wx.EVT_TIMER, self._on_mxtimer)

        self.Bind(wx.EVT_CLOSE, self._on_closewindow)

        self.mx_timer.Start(100)

        if int(wx.__version__.split('.')[0]) > 3:
            self.SetSizeHints((440,300))
        else:
            self.SetSizeHints(440,300)
        self.Layout()
        self.Fit()

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

        self.amp_list = []
        self.motor_list = []

        for record in self.mx_db.get_all_records():
            try:
                class_name = record.get_field('mx_class')
            except mp.Illegal_Argument_Error:
                class_name = 'None'

            if class_name == 'amplifier':
                self.amp_list.append(record.get_field('name'))
            elif class_name == 'motor':
                self.motor_list.append(record.get_field('name'))

        self.amp_list = sorted(self.amp_list)
        self.motor_list = sorted(self.motor_list)

    def _load_controls(self):
        standard_paths = wx.StandardPaths.Get()
        savedir = standard_paths.GetUserLocalDataDir()
        sname = '{}_sector_ctrl_settings.txt'.format(platform.node().replace('.','_'))
        settings = os.path.join(savedir, sname)

        if not os.path.exists(savedir):
            os.mkdir(savedir)

        if os.path.exists(settings):
            with open(settings, 'r') as f:
                self.controls = json.load(f, object_pairs_hook=collections.OrderedDict)

    def _create_layout(self):
        self._mgr = aui.AuiManager()
        self._mgr.SetManagedWindow(self)

        self.ctrl_nb = aui.AuiNotebook(self, style=aui.AUI_NB_TAB_SPLIT|
            aui.AUI_NB_TAB_MOVE|aui.AUI_NB_TOP)
        ctrlnb_info = aui.AuiPaneInfo().Floatable(False).Center().CloseButton(False)
        ctrlnb_info.Gripper(False).PaneBorder(False).CaptionVisible(False)

        for group in self.controls.keys():
            ctrl_panel = CtrlsPanel(self.controls[group], self, parent=self.ctrl_nb, name=group)
            self.ctrl_panels[group] = ctrl_panel
            self.ctrl_nb.AddPage(ctrl_panel, group)

        btn_panel = wx.Panel(self)
        add_ctrl_btn = wx.Button(btn_panel, label='Add Persistent Control(s)')
        add_ctrl_btn.Bind(wx.EVT_BUTTON, self._on_addctrl)

        show_ctrl_btn = wx.Button(btn_panel, label='Show Temporary Control(s)')
        show_ctrl_btn.Bind(wx.EVT_BUTTON, self._on_showctrl)

        btn_sizer = wx.BoxSizer(wx.HORIZONTAL)
        btn_sizer.AddStretchSpacer(1)
        btn_sizer.Add(add_ctrl_btn,0, border=5, flag=wx.ALL)
        btn_sizer.Add(show_ctrl_btn,0, border=5, flag=wx.ALL)
        btn_sizer.AddStretchSpacer(1)
        btn_panel.SetSizer(btn_sizer)
        btn_panel.Layout()
        btn_panel.Fit()

        btn_sizer_info = aui.AuiPaneInfo().Floatable(False).Bottom().CloseButton(False)
        btn_sizer_info.Gripper(False).PaneBorder(False).CaptionVisible(False).Fixed()

        self._mgr.AddPane(self.ctrl_nb, ctrlnb_info)
        self._mgr.AddPane(btn_panel, btn_sizer_info)

        btn_panel.Layout()
        btn_panel.Fit()

        self._mgr.Update()

        # self._load_layout()

    def _on_mxtimer(self, evt):
        """
        Called on the mx_timer, refreshes mx values in the GUI by calling
        wait_for_messages on the database.
        """
        self.mx_db.wait_for_messages(0.01)

    def _on_closewindow(self, evt):
        self.mx_timer.Stop()

        standard_paths = wx.StandardPaths.Get()
        savedir = standard_paths.GetUserLocalDataDir()

        pname = '{}_sector_ctrl_layout.bak'.format(platform.node().replace('.','_'))
        pfile = os.path.join(savedir, pname)
        perspective = self._mgr.SavePerspective()
        with open(pfile, 'w') as f:
            f.write(perspective)

        sname = '{}_sector_ctrl_settings.txt'.format(platform.node().replace('.','_'))
        sfile = os.path.join(savedir, sname)
        with open(sfile, 'w') as f:
            f.write(unicode(json.dumps(self.controls, indent=4, sort_keys=False, cls=MyEncoder)))

        self.Destroy()

    def _load_layout(self):
        perspective = 'sector_ctrl_layout.bak'
        if os.path.exists(perspective):
            with open(perspective) as f:
                layout = f.read()
            self._mgr.LoadPerspective(layout)

    def show_ctrls(self,ctrl_data):
        self.mx_timer.Stop()
        ctrl_frame = CtrlsFrame(ctrl_data, self.mx_db, parent=self)
        ctrl_frame.Show()
        self.mx_timer.Start()

    def _on_addctrl(self, evt):
        self.add_ctrl()

    def _on_showctrl(self, evt):
        add_dlg = AddCtrlDialog(set_group=False, parent=self, title='Define control set',
            style=wx.RESIZE_BORDER|wx.CLOSE_BOX|wx.CAPTION)
        if add_dlg.ShowModal() == wx.ID_OK:
            ctrl_data = add_dlg.ctrl_data
            if len(ctrl_data)>1:
                self.show_ctrls(ctrl_data)

    def add_ctrl(self):
        add_dlg = AddCtrlDialog(parent=self, title='Define control set',
            style=wx.RESIZE_BORDER|wx.CLOSE_BOX|wx.CAPTION)
        if add_dlg.ShowModal() == wx.ID_OK:
            ctrl_data = add_dlg.ctrl_data

            if len(ctrl_data)>1:
                group = add_dlg.group
                ctrl = ctrl_data[0]['title']

                if group not in self.controls:
                    self.controls[group]=collections.OrderedDict()
                    self.controls[group][ctrl] = ctrl_data
                    ctrl_panel = CtrlsPanel(self.controls[group], self, parent=self.ctrl_nb, name=group)
                    self.ctrl_panels[group] = ctrl_panel
                    self.ctrl_nb.AddPage(ctrl_panel, group)
                    self.Layout()
                else:
                    if ctrl in self.controls[group]:
                        result = self._showDupWarning(group, ctrl)
                        if not result:
                            return
                        self.controls[group][ctrl] = ctrl_data
                    else:
                        self.controls[group][ctrl] = ctrl_data
                        ctrl_panel = self.ctrl_panels[group]
                        ctrl_panel.add_ctrl(ctrl)
                        ctrl_panel.Layout()

        add_dlg.Destroy()

    def start_timer(self):
        self.mx_timer.Start()

    def redo_layout(self):
        for i in range(self.ctrl_nb.GetPageCount()):
            if self.ctrl_nb.GetPageText(i) not in self.controls.keys():
                self.ctrl_nb.DeletePage(i)

    def _showDupWarning(self, group, ctrl):
        msg = ('Warning: Control group {} already has a control set named '
            '{}. This will be overwritten if you continue. Proceed and '
            'overwrite?'.format(group, ctrl))

        dlg = wx.MessageDialog(self, msg, 'Proceed and overwrite?',
            style=wx.YES_NO|wx.YES_DEFAULT|wx.ICON_EXCLAMATION|wx.STAY_ON_TOP|wx.CENTER)

        result = dlg.ShowModal()

        if result == wx.ID_YES:
            return True
        else:
            return False

class CtrlsPanel(wx.Panel):

    def __init__(self, panel_data, main_frame, *args, **kwargs):
        wx.Panel.__init__(self, *args, **kwargs)
        self.main_frame = main_frame
        self._create_layout(panel_data)

        self.Bind(wx.EVT_RIGHT_UP, self._onRightMouseClick)

    def _create_layout(self, panel_data):
        nitems = len(panel_data.keys())

        self.grid_sizer = wx.FlexGridSizer(rows=(nitems+1)//2, cols=2, vgap=5, hgap=5)

        for label in panel_data.keys():
            button = wx.Button(self, label=label, name=label)
            button.Bind(wx.EVT_BUTTON, self._on_button)
            button.Bind(wx.EVT_RIGHT_UP, self._onBtnRightMouseClick)
            self.grid_sizer.Add(button)

        top_sizer = wx.BoxSizer()

        top_sizer.Add(self.grid_sizer, border=5, flag=wx.ALL)

        self.SetSizer(top_sizer)

    def _on_button(self, evt):
        button = evt.GetEventObject()

        ctrl = button.GetName()
        group = self.GetName()

        self.main_frame.show_ctrls(self.main_frame.controls[group][ctrl])

    def add_ctrl(self, label):
        rows = self.grid_sizer.GetRows()
        cols = self.grid_sizer.GetCols()
        nitems = self.grid_sizer.GetItemCount()

        if nitems+1 > rows*cols:
            self.grid_sizer.SetRows(rows+1)

        button = wx.Button(self, label=label, name=label)
        button.Bind(wx.EVT_BUTTON, self._on_button)
        button.Bind(wx.EVT_RIGHT_UP, self._onBtnRightMouseClick)
        self.grid_sizer.Add(button)

    def _onRightMouseClick(self, event):
        if int(wx.__version__.split('.')[0]) >= 3 and platform.system() == 'Darwin':
            wx.CallAfter(self._showPopupMenu)
        else:
            self._showPopupMenu()

    def _showPopupMenu(self):
        menu = wx.Menu()

        menu.Append(1, 'Remove/reorder control sets')
        menu.Append(2, 'Remove/reorder control groups')
        self.Bind(wx.EVT_MENU, self._onPopupMenuChoice)
        self.PopupMenu(menu)

        menu.Destroy()

    def _onPopupMenuChoice(self, evt):
        choice = evt.GetId()

        if choice == 1:
            group = self.GetName()
            dlg = RemoveCtrlDialog(self.main_frame.controls[group], parent=self,
                title='Modify Control Sets', style=wx.RESIZE_BORDER|wx.CLOSE_BOX|wx.CAPTION)
            if dlg.ShowModal() == wx.ID_OK:
                new_ctrls = dlg.keys

                old_data = copy.deepcopy(self.main_frame.controls[group])

                self.main_frame.controls[group] = collections.OrderedDict()

                for ctrls in new_ctrls:
                    self.main_frame.controls[group][ctrls] = old_data[ctrls]

                for btn in self.grid_sizer.GetChildren():
                    btn.GetWindow().Destroy()

                self._create_layout(self.main_frame.controls[group])
                self.Layout()
            dlg.Destroy()

        elif choice == 2:
            group = self.GetName()
            dlg = RemoveCtrlDialog(self.main_frame.controls, parent=self,
                title='Modify Control Groups', style=wx.RESIZE_BORDER|wx.CLOSE_BOX|wx.CAPTION)
            if dlg.ShowModal() == wx.ID_OK:
                new_groups = dlg.keys

                old_data = copy.deepcopy(self.main_frame.controls)

                self.main_frame.controls = collections.OrderedDict()

                for group in new_groups:
                    self.main_frame.controls[group] = old_data[group]
                    wx.CallAfter(self.main_frame.redo_layout)

                for group in old_data:
                    if group not in new_groups:
                        del self.main_frame.ctrl_panels[group]
            dlg.Destroy()

    def _onBtnRightMouseClick(self, evt):
        if int(wx.__version__.split('.')[0]) >= 3 and platform.system() == 'Darwin':
            wx.CallAfter(self._showBtnPopupMenu, evt.GetEventObject())
        else:
            self._showBtnPopupMenu(evt.GetEventObject())

    def _showBtnPopupMenu(self, btn):
        menu = wx.Menu()

        menu.Append(1, 'Modify controls')
        menu.Bind(wx.EVT_MENU, self._onBtnPopupMenuChoice)
        btn.PopupMenu(menu)

        menu.Destroy()

    def _onBtnPopupMenuChoice(self, evt):
        button = evt.GetEventObject().GetInvokingWindow()

        ctrl = button.GetName()
        group = self.GetName()

        add_dlg = AddCtrlDialog(parent=self.main_frame, title='Modify control set',
            style=wx.RESIZE_BORDER|wx.CLOSE_BOX|wx.CAPTION)
        add_dlg.populate_ctrls(self.main_frame.controls[group][ctrl], group)

        if add_dlg.ShowModal() == wx.ID_OK:
            ctrl_data = add_dlg.ctrl_data
            new_group = add_dlg.group
            new_ctrl = ctrl_data[0]['title']

            if new_group not in self.main_frame.controls:
                self.main_frame.controls[new_group]=collections.OrderedDict()
                self.main_frame.controls[new_group][new_ctrl] = ctrl_data
                ctrl_panel = CtrlsPanel(self.main_frame.controls[new_group], self.main_frame,
                    parent=self.main_frame.ctrl_nb, name=new_group)
                self.main_frame.ctrl_panels[group] = ctrl_panel
                self.main_frame.ctrl_nb.AddPage(ctrl_panel, new_group)
                button.Destroy()
                self.Layout()
                self.main_frame.Layout()
                del self.main_frame.controls[group][ctrl]

            else:
                if new_group != group:
                    if new_ctrl in self.main_frame.controls[new_group]:
                        result = self._showDupWarning(new_group, new_ctrl)
                        if not result:
                            return
                        self.main_frame.controls[new_group][new_ctrl] = ctrl_data
                    else:
                        self.main_frame.controls[new_group][new_ctrl] = ctrl_data
                        ctrl_panel = self.main_frame.ctrl_panels[new_group]
                        ctrl_panel.add_ctrl(new_ctrl)
                        ctrl_panel.Layout()

                    button.Destroy()
                    self.Layout()
                    del self.main_frame.controls[group][ctrl]

                else:
                    if new_ctrl != ctrl:
                        if new_ctrl in self.main_frame.controls[new_group]:
                            result = self._showDupWarning(new_group, new_ctrl)
                            if not result:
                                return

                            self.main_frame.controls[new_group][new_ctrl] = ctrl_data
                            button.Destroy()
                            self.Layout()
                            del self.main_frame.controls[group][ctrl]

                        else:
                            button.SetLabel(new_ctrl)
                            button.SetName(new_ctrl)
                            self.Layout()
                            old_ctrls = self.main_frame.controls[new_group]
                            new_ctrls = collections.OrderedDict()

                            for key in old_ctrls:
                                if key == ctrl:
                                    new_ctrls[new_ctrl] = ctrl_data
                                else:
                                    new_ctrls[key] = old_ctrls[key]

                            self.main_frame.controls[new_group] = new_ctrls

        return

    def _showDupWarning(self, group, ctrl):
        msg = ('Warning: Control group {} already has a control set named '
            '{}. This will be overwritten if you continue. Proceed and '
            'overwrite?'.format(group, ctrl))

        dlg = wx.MessageDialog(self, msg, 'Proceed and overwrite?',
            style=wx.YES_NO|wx.YES_DEFAULT|wx.ICON_EXCLAMATION|wx.STAY_ON_TOP|wx.CENTER)

        result = dlg.ShowModal()

        if result == wx.ID_YES:
            return True
        else:
            return False

class CtrlsFrame(wx.Frame):
    def __init__(self, ctrls, mx_db, *args, **kwargs):
        wx.Frame.__init__(self, title=ctrls[0]['title'], *args, **kwargs)

        self._create_layout(ctrls, mx_db)

        self.Fit()
        self.Raise()

        self.Bind(wx.EVT_CLOSE, self._on_closewindow)

    def _create_layout(self, ctrls, mx_db):
        settings = ctrls[0]
        ctrls = ctrls[1:]
        main_window = self.GetParent()

        grid_sizer = wx.FlexGridSizer(rows=settings['rows'], cols=settings['cols'],
            hgap=5, vgap=5)

        for i in range(settings['cols']):
            grid_sizer.AddGrowableCol(i)

        for ctrl_name, ctrl_type in ctrls:
            ctrl_panel = main_window.ctrl_types[ctrl_type](ctrl_name, mx_db, self)
            box_sizer = wx.StaticBoxSizer(wx.StaticBox(self, label='{} Control'.format(ctrl_name)))
            box_sizer.Add(ctrl_panel, 1, border=2, flag=wx.ALL|wx.EXPAND)
            grid_sizer.Add(box_sizer, border=2, flag=wx.EXPAND|wx.ALL)

        self.SetSizer(grid_sizer)

    def _on_closewindow(self, evt):
        main_frame = self.GetParent()
        main_frame.mx_timer.Stop()
        wx.CallLater(1000, main_frame.start_timer)
        self.Destroy()


class AddCtrlDialog(wx.Dialog):
    def __init__(self, set_group=True, *args, **kwargs):
        wx.Dialog.__init__(self, *args, **kwargs)
        self._set_group = set_group
        self._create_layout()

        self.Layout()
        self.Fit()

    def _create_layout(self):
        info_grid = wx.FlexGridSizer(rows=4, cols=2, vgap=5, hgap=5)
        if self._set_group:
            self.group_ctrl = wx.TextCtrl(self)
        self.title = wx.TextCtrl(self)
        self.rows = wx.TextCtrl(self, value='1')
        self.cols = wx.TextCtrl(self, value='1')

        if self._set_group:
            info_grid.Add(wx.StaticText(self, label='Control(s) Group:'))
            info_grid.Add(self.group_ctrl)
        info_grid.Add(wx.StaticText(self, label='Control(s) Name:'))
        info_grid.Add(self.title)
        info_grid.Add(wx.StaticText(self, label='Number of rows:'))
        info_grid.Add(self.rows)
        info_grid.Add(wx.StaticText(self, label='Number of columns:'))
        info_grid.Add(self.cols)

        self.list_ctrl = ControlList(self, agwStyle=ULC.ULC_REPORT|ULC.ULC_USER_ROW_HEIGHT)
        self.list_ctrl.InsertColumn(0, 'MX Record Name')
        self.list_ctrl.InsertColumn(1, 'Control Type')
        self.list_ctrl.InsertColumn(2, '')
        self.list_ctrl.SetUserLineHeight(30)
        self.list_ctrl.SetMinSize((370,250))

        add_btn = wx.Button(self, label='Add control')
        add_btn.Bind(wx.EVT_BUTTON, self._on_add)

        remove_btn = wx.Button(self, label='Remove control')
        remove_btn.Bind(wx.EVT_BUTTON, self._on_remove)

        list_ctrl_btn_sizer = wx.BoxSizer(wx.HORIZONTAL)
        list_ctrl_btn_sizer.Add(add_btn)
        list_ctrl_btn_sizer.Add(remove_btn, border=5, flag=wx.LEFT)

        button_sizer = self.CreateButtonSizer(wx.OK | wx.CANCEL)
        self.Bind(wx.EVT_BUTTON, self._on_ok, id=wx.ID_OK)

        top_sizer = wx.BoxSizer(wx.VERTICAL)
        top_sizer.Add(info_grid, border=5, flag=wx.LEFT|wx.RIGHT|wx.TOP)
        top_sizer.Add(self.list_ctrl, 1, border=5, flag=wx.EXPAND|wx.LEFT|wx.RIGHT|wx.TOP)
        top_sizer.Add(list_ctrl_btn_sizer, border=5, flag=wx.ALL|wx.CENTER)
        top_sizer.Add(wx.StaticLine(self), flag=wx.EXPAND)
        top_sizer.Add(button_sizer, border=5, flag=wx.ALL)

        self.list_ctrl.SetColumnWidth(0, wx.LIST_AUTOSIZE_USEHEADER)
        self.list_ctrl.SetColumnWidth(1, wx.LIST_AUTOSIZE_USEHEADER)

        self.SetSizer(top_sizer)

    def _on_add(self, evt):
        self._add()

    def _add(self):
        index = self.list_ctrl.InsertStringItem(sys.maxint, '')
        main_frame = self.GetParent()

        record_panel = wx.Panel(self.list_ctrl)
        textctrl = wx.TextCtrl(record_panel, name='record')
        textctrl.AutoComplete(main_frame.motor_list)
        button = wx.Button(record_panel, id=index, label='...', size=(30, -1))
        button.Bind(wx.EVT_BUTTON, self._show_motors)
        record_sizer = wx.BoxSizer(wx.HORIZONTAL)
        record_sizer.Add(textctrl, 1, flag=wx.EXPAND|wx.ALIGN_CENTER_HORIZONTAL)
        record_sizer.Add(button, border=2, flag=wx.ALIGN_CENTER_HORIZONTAL|wx.LEFT)
        record_panel.SetSizer(record_sizer)

        item = self.list_ctrl.GetItem(index, 0)
        item.SetWindow(record_panel, expand=True)
        item.SetAlign(ULC.ULC_FORMAT_LEFT)
        self.list_ctrl.SetItem(item)

        item = self.list_ctrl.GetItem(index, 1)
        choice_ctrl = wx.Choice(self.list_ctrl, id=index, choices=main_frame.ctrl_types.keys(),
            style=wx.CB_SORT)
        choice_ctrl.SetStringSelection('Motor')
        choice_ctrl.Bind(wx.EVT_CHOICE, self._on_typechange)

        if index>0:
            prev_item = self.list_ctrl.GetItem(index-1, 1)
            prev_choice = prev_item.GetWindow().GetStringSelection()
            choice_ctrl.SetStringSelection(prev_choice)

            if prev_choice == 'Amplifier':
                textctrl.AutoComplete(main_frame.amp_list)

        item.SetWindow(choice_ctrl)
        item.SetAlign(ULC.ULC_FORMAT_LEFT)
        self.list_ctrl.SetItem(item)

        c0_width = self.list_ctrl.GetColumnWidth(0)
        c1_width = self.list_ctrl.GetColumnWidth(1)

        self.list_ctrl.SetColumnWidth(1, wx.LIST_AUTOSIZE)
        self.list_ctrl.SetColumnWidth(0, wx.LIST_AUTOSIZE)

        if c0_width > self.list_ctrl.GetColumnWidth(0):
            self.list_ctrl.SetColumnWidth(0, c0_width)

        if c1_width > self.list_ctrl.GetColumnWidth(1):
            self.list_ctrl.SetColumnWidth(1, c1_width)

        self.Layout()

        return index

    def _on_remove(self, evt):
        selected = self.list_ctrl.GetFirstSelected()

        while selected != -1:
            self.list_ctrl.DeleteItem(selected)
            selected = self.list_ctrl.GetFirstSelected()

        self.list_ctrl.DoLayout()

    def _on_ok(self, evt):
        rows = int(self.rows.GetValue())
        cols = int(self.cols.GetValue())

        if self._set_group:
            self.group = self.group_ctrl.GetValue()
        else:
            self.group = None

        if self.group == '' or self.title.GetValue() == '':
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

        main_frame = self.GetParent()
        mx_db = main_frame.mx_db

        for i in range(self.list_ctrl.GetItemCount()):
            record_panel = self.list_ctrl.GetItem(i, 0).GetWindow()
            if int(wx.__version__.split('.')[0]) > 3:
                name_ctrl = record_panel.FindWindowByName('record', parent=record_panel)
            else:
                name_ctrl = record_panel.FindWindowByName('record')
            ctrl_name =name_ctrl.GetValue()
            ctrl_type = self.list_ctrl.GetItem(i, 1).GetWindow().GetStringSelection()

            try:
                mx_db.get_record(ctrl_name)
            except mp.Not_Found_Error:
                msg = ('The control name "{}" is not an mx record. Please '
                    'fix this.'.format(ctrl_name))
                wx.MessageBox(msg, 'Error adding controls')
                return

            if ctrl_name != '':
                self.ctrl_data.append((ctrl_name, ctrl_type))

        self.EndModal(wx.ID_OK)
        return

    def populate_ctrls(self, ctrl_data, group):
        info = ctrl_data[0]
        ctrls = ctrl_data[1:]

        self.group_ctrl.SetValue(group)
        self.title.SetValue(info['title'])
        self.rows.SetValue(str(info['rows']))
        self.cols.SetValue(str(info['cols']))

        for ctrl in ctrls:
            index = self._add()
            record_panel = self.list_ctrl.GetItem(index, 0).GetWindow()
            if int(wx.__version__.split('.')[0]) > 3:
                name_ctrl = record_panel.FindWindowByName('record', parent=record_panel)
            else:
                name_ctrl = record_panel.FindWindowByName('record')
            type_ctrl = self.list_ctrl.GetItem(index, 1).GetWindow()

            name_ctrl.SetValue(ctrl[0])
            type_ctrl.SetStringSelection(ctrl[1])

    def _show_motors(self, evt):
        index =evt.GetId()
        button = evt.GetEventObject()
        main_frame = self.GetParent()

        ctrl_type = self.list_ctrl.GetItem(index, 1).GetWindow().GetStringSelection()

        if ctrl_type == 'Motor':
            records = main_frame.motor_list
        elif ctrl_type == 'Amplifier':
            records = main_frame.amp_list

        menu = wx.Menu()
        menu.Bind(wx.EVT_MENU, self._on_motor_menu_choice)

        for i, name in enumerate(records):
            menu.Append(i+1, name)

        button.PopupMenu(menu)

        menu.Destroy()

    def _on_motor_menu_choice(self, evt):
        button = evt.GetEventObject().GetInvokingWindow()
        index = button.GetId()
        main_frame = self.GetParent()
        choice = evt.GetId()-1

        record_panel = self.list_ctrl.GetItem(index, 0).GetWindow()
        if int(wx.__version__.split('.')[0]) > 3:
            txtctrl = record_panel.FindWindowByName('record', parent=record_panel)
        else:
            txtctrl = record_panel.FindWindowByName('record')

        ctrl_type = self.list_ctrl.GetItem(index, 1).GetWindow().GetStringSelection()

        if ctrl_type == 'Motor':
            txtctrl.SetValue(main_frame.motor_list[choice])
        elif ctrl_type == 'Amplifier':
            txtctrl.SetValue(main_frame.amp_list[choice])

    def _on_typechange(self, evt):
        index =evt.GetId()
        main_frame = self.GetParent()

        record_panel = self.list_ctrl.GetItem(index, 0).GetWindow()
        if int(wx.__version__.split('.')[0]) > 3:
            txtctrl = record_panel.FindWindowByName('record', parent=record_panel)
        else:
            txtctrl = record_panel.FindWindowByName('record')

        if evt.GetString() == 'Motor':
            txtctrl.AutoComplete(main_frame.motor_list)
        elif evt.GetString() == 'Amplifier':
            txtctrl.AutoComplete(main_frame.amp_list)


class RemoveCtrlDialog(wx.Dialog):
    def __init__(self, params, *args, **kwargs):
        wx.Dialog.__init__(self, *args, **kwargs)
        self._params = params
        self._create_layout()

    def _create_layout(self):

        self.list_ctrl = wx.ListCtrl(self, style=wx.LC_REPORT)
        self.list_ctrl.InsertColumn(0, 'Control')

        for param in self._params.keys():
            self.list_ctrl.InsertStringItem(sys.maxint, param)

        up_btn = wx.Button(self, label='Up')
        up_btn.Bind(wx.EVT_BUTTON, self._on_up)

        down_btn = wx.Button(self, label='Down')
        down_btn.Bind(wx.EVT_BUTTON, self._on_down)

        remove_btn = wx.Button(self, label='Remove')
        remove_btn.Bind(wx.EVT_BUTTON, self._on_remove)

        list_ctrl_btn_sizer = wx.BoxSizer(wx.HORIZONTAL)
        list_ctrl_btn_sizer.Add(up_btn)
        list_ctrl_btn_sizer.Add(down_btn)
        list_ctrl_btn_sizer.Add(remove_btn)

        button_sizer = self.CreateButtonSizer(wx.OK | wx.CANCEL)
        self.Bind(wx.EVT_BUTTON, self._on_ok, id=wx.ID_OK)

        top_sizer = wx.BoxSizer(wx.VERTICAL)
        top_sizer.Add(self.list_ctrl, 1, flag=wx.EXPAND)
        top_sizer.Add(list_ctrl_btn_sizer, flag=wx.CENTER)
        top_sizer.Add(button_sizer, flag=wx.RIGHT)

        self.list_ctrl.SetColumnWidth(0, wx.LIST_AUTOSIZE_USEHEADER)

        self.SetSizer(top_sizer)

    def _on_remove(self, evt):
        selected = self.list_ctrl.GetFirstSelected()

        while selected != -1:
            self.list_ctrl.DeleteItem(selected)
            selected = self.list_ctrl.GetFirstSelected()

    def _on_up(self, evt):
        selected_items = []
        selected = self.list_ctrl.GetFirstSelected()

        while selected != -1:
            selected_items.append(selected)
            if selected > 0:
                data = self.list_ctrl.GetItemText(selected)
                self.list_ctrl.DeleteItem(selected)
                self.list_ctrl.InsertStringItem(selected-1, data)
                selected = self.list_ctrl.GetFirstSelected()
            else:
                self.list_ctrl.Select(0, False)
                selected = self.list_ctrl.GetFirstSelected()

        for idx in selected_items:
            if idx>0:
                self.list_ctrl.Select(idx-1, True)
            else:
                self.list_ctrl.Select(0, True)

    def _on_down(self, evt):
        selected_items = []
        selected = self.list_ctrl.GetFirstSelected()

        while selected != -1:
            selected_items.append(selected)
            self.list_ctrl.Select(selected, False)
            selected = self.list_ctrl.GetFirstSelected()

        nitems = self.list_ctrl.GetItemCount()

        if selected_items[-1] == nitems-1:
            last_data = self.list_ctrl.GetItemText(nitems-1)

        for idx in selected_items[::-1]:
            data = self.list_ctrl.GetItemText(idx)
            self.list_ctrl.DeleteItem(idx)
            self.list_ctrl.InsertStringItem(idx+1, data)

        if selected_items[-1] == nitems-1:
            item = self.list_ctrl.FindItem(-1, last_data)
            self.list_ctrl.DeleteItem(item)
            self.list_ctrl.InsertStringItem(nitems, last_data)


        for idx in selected_items:
            if idx<nitems-1:
                self.list_ctrl.Select(idx+1, True)
            else:
                self.list_ctrl.Select(nitems-1, True)

    def _on_ok(self, evt):
        nitems = self.list_ctrl.GetItemCount()
        self.keys = [self.list_ctrl.GetItemText(i) for i in range(nitems)]
        if self.GetTitle() == 'Modify Control Groups':
            msg = ('Note: you will have to restart the program for any changes '
                'in group ordering to take effect (you can also drag the tabs '
                'to reorder them).')
            wx.MessageBox(msg, 'Tab order changes on restart')
        self.EndModal(wx.ID_OK)

class ControlList(ULC.UltimateListCtrl, listmix.ListCtrlAutoWidthMixin):
    def __init__(self, *args, **kwargs):
        ULC.UltimateListCtrl.__init__(self, *args, **kwargs)
        listmix.ListCtrlAutoWidthMixin.__init__(self)

class MyTextCtrl(wx.TextCtrl):
    def __init__(self, *args, **kwargs):
        wx.TextCtrl.__init__(self, *args, **kwargs)

        self.Bind(wx.EVT_CONTEXT_MENU, self.OnContextMenu)
        self.Bind(wx.EVT_RIGHT_DOWN, self.OnContextMenu)
        self.Bind(wx.EVT_RIGHT_UP, self.OnContextMenu)

    def OnContextMenu(self, evt):
        print('here!')
        pass

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

        # sys.excepthook = self.ExceptionHook
        if len(sys.argv) > 1:
            title = ' '.join(sys.argv[1:])
        else:
            title = 'BioCAT Staff Controls'

        frame = MainFrame(title=title, name='MainFrame')
        frame.Show()

        return True

    def BringWindowToFront(self):
        try: # it's possible for this event to come when the frame is closed
            self.GetTopWindow().Raise()
        except:
            pass

    #########################
    # Here's some stuff to inform users of unhandled errors. From
    # http://apprize.info/python/wxpython/10.html

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
        """
        Override in subclass to handle errors
        @return: True to allow program to continue running withou showing error
        """
        return False


if __name__ == '__main__':
    setup_thread_excepthook()

    app = MyApp(0)   #MyApp(redirect = True)
    app.MainLoop()
