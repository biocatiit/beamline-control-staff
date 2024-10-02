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
import six

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
import wx.lib.inspection
import wx.lib.scrolledpanel as scrolled
import numpy as np

import utils
utils.set_mppath() #This must be done before importing any Mp Modules.
import Mp as mp

import motorcon as mc
import ampcon as ac
import diocon as dioc
import aiocon as aioc
import atten
import ic_calc
import dbpm_calc
import switch_monos
import overview
import epics_launcher
import motor_config


class MainFrame(wx.Frame):
    """
    .. todo::
        Support for scalers, measuring and taking dark counts

    This frame is the top level frame for the sector controls. it consists of a
    tab panel and several buttons for adding new controls. Each tab is a
    control group, the button opens a control set. It calls the :mod:`scancon`
    and :mod:`motorcon` and :mod:`ampcon` libraries to actually do anything.
    It communicates with the devices by calling ``Mp``, the python wrapper for ``MX``.
    """
    def __init__(self, *args, **kwargs):
        """
        Initializes the main frame. It takes the standard arguments for a
        :mod:`wx.Frame`, except parent should not be specified.
        """
        wx.Frame.__init__(self, None, *args, **kwargs)

        self.controls = collections.OrderedDict()
        self.ctrl_types = {'Amplifier'      : ac.AmpPanel,
                        'Motor'             : mc.MotorPanel,
                        'Digital IO'        : dioc.DIOPanel,
                        'Digital O, Btn.'   : dioc.DOButtonPanel,
                        'Analog IO'         : aioc.AIOPanel,
                        'Custom'            : self.make_custom_ctrl,
                        }

        self.custom_ctrl_type = {
            'Attenuators'  : atten.AttenuatorPanel,
            'Ion Chamber Calculator'    : ic_calc.ICCalcPanel,
            'Diamond BPM Calculator'    : dbpm_calc.DBPMCalcPanel,
            'Switch Monos'  : switch_monos.SWMonosPanel,
            'Beamline Overview' : overview.MainStatusPanel,
            'D BPM Amplifier'   : ac.DBPMAmpPanel,
            'EPICS Launcher'    : epics_launcher.EPICSLauncherPanel,
            'Motor Config'  : motor_config.MotorConfigPanel,
            }

        self.ctrl_panels = {}

        self._start_mxdatabase()
        self._load_controls()
        self._create_layout()

        self.mx_timer = wx.Timer()
        self.mx_timer.Bind(wx.EVT_TIMER, self._on_mxtimer)

        self.Bind(wx.EVT_CLOSE, self._on_closewindow)

        self.mx_timer.Start(10)

        if int(wx.__version__.split('.')[0]) > 3:
            self.SetSizeHints(self._FromDIP((600,350)))
        else:
            self.SetSizeHints(self._FromDIP(600),self._FromDIP(350))
        self.Layout()
        self.Fit()

    def _FromDIP(self, size):
        # This is a hack to provide easy back compatibility with wxpython < 4.1
        try:
            return self.FromDIP(size)
        except Exception:
            return size

    def _start_mxdatabase(self):
        """
        Starts the MX database. It first looks for the database specified
        by the ``MXDATABASE`` environment variable. If that is not found, then
        it looks for a database in the standard ``mx/etc/mxmotor.dat`` location.

        This also creates lists of all amplifiers and motors available to the
        controls.
        """
        try:
            # First try to get the name from an environment variable.
            database_filename = os.environ["MXDATABASE"]
        except Exception:
            # If the environment variable does not exist, construct
            # the filename for the default MX database.
            mxdir = utils.get_mxdir()
            database_filename = os.path.join(mxdir, "etc", "mxmotor.dat")
            database_filename = os.path.normpath(database_filename)

        self.mx_db = mp.setup_database(database_filename)
        self.mx_db.set_plot_enable(2)
        self.mx_db.set_program_name("sectorcon")

        self.amp_list = []
        self.motor_list = []
        self.dio_list = []
        self.do_list = []
        self.aio_list = []


        self.custom_list = ['Attenuators', 'Ion Chamber Calculator',
            'Diamond BPM Calculator', 'Switch Monos', 'Beamline Overview',
            'D BPM Amplifier', 'EPICS Launcher', 'Motor Config']

        for record in self.mx_db.get_all_records():
            try:
                class_name = record.get_field('mx_class')
            except mp.Illegal_Argument_Error:
                class_name = 'None'

            if class_name == 'amplifier':
                self.amp_list.append(record.get_field('name'))
            elif class_name == 'motor':
                self.motor_list.append(record.get_field('name'))
            elif class_name == 'digital_input' or class_name == 'digital_output':
                self.dio_list.append(record.get_field('name'))
                if class_name == 'digital_output':
                    self.do_list.append(record.get_field('name'))
            elif class_name == 'analog_input' or class_name == 'analog_output':
                self.aio_list.append(record.get_field('name'))


        self.amp_list = sorted(self.amp_list, key=str.lower)
        self.motor_list = sorted(self.motor_list, key=str.lower)
        self.dio_list = sorted(self.dio_list, key=str.lower)
        self.do_list = sorted(self.do_list, key=str.lower)
        self.aio_list = sorted(self.aio_list, key=str.lower)

    def _load_controls(self):
        """
        This loads in a previously saved configuration of controls for the
        panel. It looks in the user local data directory (using :mod:`wx.StandardPaths`)
        and if there is a file called ``<node_name>_sector_ctrl_settings.txt``.
        Settings are loaded assuming a json format.
        """
        standard_paths = wx.StandardPaths.Get()
        savedir = standard_paths.GetUserLocalDataDir()
        sname = '{}_sector_ctrl_settings.txt'.format(platform.node().replace('.','_'))
        settings = os.path.join(savedir, sname)

        if not os.path.exists(savedir):
            os.mkdir(savedir)

        if os.path.exists(settings):
            with open(settings, 'r') as f:
                try:
                    self.controls = json.load(f, object_pairs_hook=collections.OrderedDict)

                    if len(self.controls) > 0:
                        load_backup = False
                    else:
                        load_backup = True
                except Exception:
                    load_backup = True

        else:
            load_backup = False

        if load_backup:
            sname = '{}_sector_ctrl_settings_bak.txt'.format(platform.node().replace('.','_'))
            settings = os.path.join(savedir, sname)

            if os.path.exists(settings):
                with open(settings, 'r') as f:
                    try:
                        self.controls = json.load(f, object_pairs_hook=collections.OrderedDict)
                    except Exception:
                        pass

    def _create_layout(self):
        """
        .. todo::
            Save the AuiNotebook layout (might have to switch to the AGW version),
            and load in the correct layout every time.

        .. todo::
            Is it possible to save the layout of the open windows (using the aui manager)
            and then reopen all open windows when the program is reopened?

        Creates the layout for the panel.
        """
        self._mgr = aui.AuiManager()
        self._mgr.SetManagedWindow(self)

        self.ctrl_nb = aui.AuiNotebook(self, style=aui.AUI_NB_TAB_SPLIT|
            aui.AUI_NB_TAB_MOVE|aui.AUI_NB_TOP)
        ctrlnb_info = aui.AuiPaneInfo().Floatable(False).Center().CloseButton(False)
        ctrlnb_info.Gripper(False).PaneBorder(False).CaptionVisible(False)

        for group in self.controls.keys():
            ctrl_panel = CtrlsPanel(self.controls[group], self,
                parent=self.ctrl_nb, name=group)
            self.ctrl_panels[group] = ctrl_panel
            self.ctrl_nb.AddPage(ctrl_panel, group)

        btn_panel = wx.Panel(self)
        add_ctrl_btn = wx.Button(btn_panel, label='Add Persistent Control(s)')
        add_ctrl_btn.Bind(wx.EVT_BUTTON, self._on_addctrl)

        show_ctrl_btn = wx.Button(btn_panel, label='Show Temporary Control(s)')
        show_ctrl_btn.Bind(wx.EVT_BUTTON, self._on_showctrl)

        btn_sizer = wx.BoxSizer(wx.HORIZONTAL)
        btn_sizer.AddStretchSpacer(1)
        btn_sizer.Add(add_ctrl_btn,0, border=self._FromDIP(5), flag=wx.ALL)
        btn_sizer.Add(show_ctrl_btn,0, border=self._FromDIP(5), flag=wx.ALL)
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
        """
        Called when the window is closed to clean up running processes and save
        the current layout before the program quits.
        """
        self.mx_timer.Stop()

        self.save_layout()

        sys.excepthook = sys.__excepthook__

        for w in wx.GetTopLevelWindows():
            if w != self:
                w.Destroy()

        self._mgr.UnInit()

        self.Destroy()

    def save_layout(self):
        """
        This saves the current layout. It saves both the AUI layout and the
        control sets and groups. However, at the moment the AUI layout is not used
        on loading.
        """
        standard_paths = wx.StandardPaths.Get()
        savedir = standard_paths.GetUserLocalDataDir()

        pname = '{}_sector_ctrl_layout.bak'.format(platform.node().replace('.','_'))
        pfile = os.path.join(savedir, pname)
        perspective = self._mgr.SavePerspective()
        with open(pfile, 'w') as f:
            f.write(perspective)

        sname = '{}_sector_ctrl_settings.txt'.format(platform.node().replace('.','_'))
        sfile = os.path.join(savedir, sname)
        with open(sfile, 'w', encoding='utf-8') as f:
            if six.PY2:
                out = unicode(json.dumps(self.controls, indent=4, sort_keys=False,
                    cls=MyEncoder))
            else:
                out = json.dumps(self.controls, indent=4, sort_keys=False,
                    cls=MyEncoder)
            f.write(out)

        try:
            with open(sfile, 'r') as f:
                controls = json.load(f, object_pairs_hook=collections.OrderedDict)

            if len(controls) > 0:
                sname = '{}_sector_ctrl_settings_bak.txt'.format(platform.node().replace('.','_'))
                sfile = os.path.join(savedir, sname)
                with open(sfile, 'w', encoding='utf-8') as f:
                    if six.PY2:
                        out = unicode(json.dumps(self.controls, indent=4,
                            sort_keys=False, cls=MyEncoder))
                    else:
                        out = json.dumps(self.controls, indent=4,
                            sort_keys=False, cls=MyEncoder)
                    f.write(out)

        except Exception:
            pass

    def _load_layout(self):
        """
        This funciton is currently unused. it loads in the aui manager perspective.
        """
        perspective = 'sector_ctrl_layout.bak'
        if os.path.exists(perspective):
            with open(perspective) as f:
                layout = f.read()
            self._mgr.LoadPerspective(layout)

    def show_ctrls(self,ctrl_data):
        """
        This creates a :class:`CtrlsFrame` with the controls given by the
        ctrl_data.

        :param collections.OrderedDict ctrl_data: This is a dictionary that
            contains all of the controls that will be shown in the new controls
            frame.
        """
        self.mx_timer.Stop()
        ctrl_frame = CtrlsFrame(ctrl_data, self.mx_db, parent=self)
        ctrl_frame.Show()
        self.mx_timer.Start()

    def make_custom_ctrl(self, ctrl_name, mx_db, parent):
        if ctrl_name == 'D BPM Amplifier':
            full_ctrl_name = '18ID_D_BPM_'
        else:
            full_ctrl_name = ctrl_name

        ctrl = self.custom_ctrl_type[ctrl_name](full_ctrl_name, mx_db, parent)

        return ctrl

    def _on_addctrl(self, evt):
        """
        Called when the Add Control Button is pressed. Calls the :func:`add_ctrl`
        function.
        """
        self.add_ctrl()

    def _on_showctrl(self, evt):
        add_dlg = AddCtrlDialog(set_group=False, parent=self, title='Define control set',
            style=wx.RESIZE_BORDER|wx.CLOSE_BOX|wx.CAPTION)
        if add_dlg.ShowModal() == wx.ID_OK:
            ctrl_data = add_dlg.ctrl_data
            if len(ctrl_data)>1:
                self.show_ctrls(ctrl_data)

        add_dlg.Destroy()

    def add_ctrl(self):
        """
        Adds a new control set to the control frame. Calls the :class:`AddCtrlDialog`
        to do the actual add.
        """
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
                    ctrl_panel = CtrlsPanel(self.controls[group], self,
                        parent=self.ctrl_nb, name=group)
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
        """Starts the mx timer."""
        self.mx_timer.Start()

    def redo_layout(self):
        """Redo the tab layout after changes have been made."""
        for i in range(self.ctrl_nb.GetPageCount()):
            if self.ctrl_nb.GetPageText(i) not in self.controls.keys():
                self.ctrl_nb.DeletePage(i)

    def _showDupWarning(self, group, ctrl):
        """
        When adding or moving control sets (buttons) between groups (tabs),
        this function checks whether there is already a set with the desired name
        on that tab. If there is, it asks to confirm the overwritten.

        :param str group: The group (tab) name on which the duplicate set appears.
        :param str ctrl: The set (button) name which is being duplicated.

        :returns: True if the user wants to overwrite the control. False
            if the user doesn't want to overwrite the control.
        :rtype: bool
        """
        msg = ('Warning: Control group {} already has a control set named '
            '{}. This will be overwritten if you continue. Proceed and '
            'overwrite?'.format(group, ctrl))

        dlg = wx.MessageDialog(self, msg, 'Proceed and overwrite?',
            style=wx.YES_NO|wx.YES_DEFAULT|wx.ICON_EXCLAMATION|wx.STAY_ON_TOP|wx.CENTER)

        result = dlg.ShowModal()
        dlg.Destroy()

        if result == wx.ID_YES:
            return True
        else:
            return False

class CtrlsPanel(scrolled.ScrolledPanel):
    """
    This is the base panel for laying out a group (tab) of control sets (buttons).
    It basically consists of a grid of buttons that can be clicked to open the
    control sets.
    """
    def __init__(self, panel_data, main_frame, *args, **kwargs):
        """
        Initializes the control panel. It takes all of the arguments of a wx.Panel
        object, plus those listed below.

        :param collections.OrderedDict panel_data: The dictionary of panel data
            that defines a control set. Used to create the control layout on the
            panel.

        :param wx.Frame main_frame: The :class:`MainFrame`.
        """
        scrolled.ScrolledPanel.__init__(self, *args, **kwargs)
        self.main_frame = main_frame
        self._create_layout(panel_data)

        self.SetupScrolling()

        self.Bind(wx.EVT_RIGHT_UP, self._onRightMouseClick)

    def _FromDIP(self, size):
        # This is a hack to provide easy back compatibility with wxpython < 4.1
        try:
            return self.FromDIP(size)
        except Exception:
            return size

    def _create_layout(self, panel_data):
        """
        Creates the layout for the panel

        :param collections.OrderedDict panel_data: The dictionary of panel data
            that defines a control set. Used to create the control layout on the
            panel.
        """
        nitems = len(panel_data.keys())

        self.grid_sizer = wx.FlexGridSizer(cols=4, vgap=self._FromDIP(5),
            hgap=self._FromDIP(5))

        for label in panel_data.keys():
            button = wx.Button(self, label=label, name=label)
            button.Bind(wx.EVT_BUTTON, self._on_button)
            button.Bind(wx.EVT_RIGHT_UP, self._onBtnRightMouseClick)
            self.grid_sizer.Add(button)

        top_sizer = wx.BoxSizer()

        top_sizer.Add(self.grid_sizer, border=self._FromDIP(5), flag=wx.ALL)

        self.SetSizer(top_sizer)

    def _on_button(self, evt):
        """
        Called when a control set button is clicked. Opens a new window showing
        the controls.
        """
        button = evt.GetEventObject()

        ctrl = button.GetName()
        group = self.GetName()

        self.main_frame.show_ctrls(self.main_frame.controls[group][ctrl])

    def add_ctrl(self, label):
        """
        This adds a new control to the group (tab).

        :param str label: The label for the control set (button).
        """
        rows = self.grid_sizer.GetRows()
        cols = self.grid_sizer.GetCols()
        nitems = self.grid_sizer.GetItemCount()

        if nitems+1 > rows*cols:
            self.grid_sizer.SetRows(rows+1)

        button = wx.Button(self, label=label, name=label)
        button.Bind(wx.EVT_BUTTON, self._on_button)
        button.Bind(wx.EVT_RIGHT_UP, self._onBtnRightMouseClick)
        self.grid_sizer.Add(button)

        self.main_frame.save_layout()

    def _onRightMouseClick(self, event):
        """Opens a context menu on right click on the panel (but not a button)."""
        if int(wx.__version__.split('.')[0]) >= 3 and platform.system() == 'Darwin':
            wx.CallAfter(self._showPopupMenu)
        else:
            self._showPopupMenu()

    def _showPopupMenu(self):
        """
        Shows the palen context menu. Allows users to make modifications to the
        order of the control sets (tabs) and control groups (buttons), or remove
        some entirely.
        """
        menu = wx.Menu()

        menu.Append(1, 'Remove/reorder control sets')
        menu.Append(2, 'Remove/reorder control groups')
        self.Bind(wx.EVT_MENU, self._onPopupMenuChoice)
        self.PopupMenu(menu)

        menu.Destroy()

    def _onPopupMenuChoice(self, evt):
        """
        This handles making modification to the control sets (tabs) and control
        groups (buttons) after the users makes a choice in the context menu.
        It calls the :class:`RemoveCtrlDialog` for the user to make a choice,
        an then handles making modifications to itself and/or the :class:MainFrame
        as a result of the choice.
        """
        choice = evt.GetId()

        if choice == 1:
            group = self.GetName()
            dlg = RemoveCtrlDialog(self.main_frame.controls[group], parent=self,
                title='Modify Control Sets',
                style=wx.RESIZE_BORDER|wx.CLOSE_BOX|wx.CAPTION)
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
                title='Modify Control Groups',
                style=wx.RESIZE_BORDER|wx.CLOSE_BOX|wx.CAPTION)
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

        self.main_frame.save_layout()

    def _onBtnRightMouseClick(self, evt):
        """
        Called after a user right clicks on a button (but not the panel). Calls
        :func:`_showBtnPopupMenu`
        """
        if int(wx.__version__.split('.')[0]) >= 3 and platform.system() == 'Darwin':
            wx.CallAfter(self._showBtnPopupMenu, evt.GetEventObject())
        else:
            self._showBtnPopupMenu(evt.GetEventObject())

    def _showBtnPopupMenu(self, btn):
        """
        Shows a button context menu. Allows user to modify the controls in the set.

        :param wx.Button btn: The button that was clicked on.
        """
        menu = wx.Menu()

        menu.Append(1, 'Modify controls')
        menu.Bind(wx.EVT_MENU, self._onBtnPopupMenuChoice)
        btn.PopupMenu(menu)

        menu.Destroy()

    def _onBtnPopupMenuChoice(self, evt):
        """
        Handles users makign modifications to a control set (button). It calls
        the :class:`AddCtrlDialog` to allow users to make modifications, and then
        handles the results of that, including moving the button to a diferent
        (possibly new) tab if necessary.

        :returns: Nothing. Return used just to exit at various points in the function.
        """
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
                ctrl_panel = CtrlsPanel(self.main_frame.controls[new_group],
                    self.main_frame, parent=self.main_frame.ctrl_nb, name=new_group)
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
                    else:
                        self.main_frame.controls[new_group][new_ctrl] = ctrl_data

        self.main_frame.save_layout()

        add_dlg.Destroy()

        return

    def _showDupWarning(self, group, ctrl):
        """
        When adding or moving control sets (buttons) between groups (tabs),
        this function checks whether there is already a set with the desired name
        on that tab. If there is, it asks to confirm the overwritten.

        :param str group: The group (tab) name on which the duplicate set appears.
        :param str ctrl: The set (button) name which is being duplicated.

        :returns: True if the user wants to overwrite the control. False
            if the user doesn't want to overwrite the control.
        :rtype: bool
        """
        msg = ('Warning: Control group {} already has a control set named '
            '{}. This will be overwritten if you continue. Proceed and '
            'overwrite?'.format(group, ctrl))

        dlg = wx.MessageDialog(self, msg, 'Proceed and overwrite?',
            style=wx.YES_NO|wx.YES_DEFAULT|wx.ICON_EXCLAMATION|wx.STAY_ON_TOP|wx.CENTER)

        result = dlg.ShowModal()
        dlg.Destroy()

        if result == wx.ID_YES:
            return True
        else:
            return False

class CtrlsFrame(wx.Frame):
    """
    This is the base for a independent control window that actually shows the
    controls to the user. It users the :mod:`ampcon` and :mod:`motorcon` modules
    to generate the controls for amplifiers and motors respectively. All controls
    are laid out in a grid with dimensions defined by the user.
    """
    def __init__(self, ctrls, mx_db, *args, **kwargs):
        """
        Initializes the frame. Takes all the standard arguments of a wx.Frame
        except title, which is generated from the control set name, plus those
        listed below.

        :param collections.OrderedDict ctrls: A dictionary of the controls. The
            first value should contain entries for the settings: title, rows, cols.
            The subsequent entries contain the controls: a key/value pair of control
            name and control type (as defined in the :class:`MainFrame` ctrl_types
            dictionary).

        :param MP.RecordList mx_db: The MX database containing the records of
            interest.
        """
        wx.Frame.__init__(self, title=ctrls[0]['title'], *args, **kwargs)

        self._ctrls = []

        self._create_layout(ctrls, mx_db)

        self.Layout()
        self.Fit()
        # self.Raise()
        self.PostSizeEvent()

        self.Bind(wx.EVT_CLOSE, self._on_closewindow)

    def _create_layout(self, ctrls, mx_db):
        """
        Creates the frame layout.

        :param collections.OrderedDict ctrls: A dictionary of the controls. The
            first value should contain entries for the settings: title, rows, cols.
            The subsequent entries contain the controls: a key/value pair of control
            name and control type (as defined in the :class:`MainFrame` ctrl_types
            dictionary).

        :param MP.RecordList mx_db: The MX database containing the records of
            interest.
        """
        settings = ctrls[0]
        ctrls = ctrls[1:]
        main_window = self.GetParent()

        grid_sizer = wx.FlexGridSizer(rows=settings['rows'], cols=settings['cols'],
            hgap=5, vgap=5)

        for i in range(settings['cols']):
            grid_sizer.AddGrowableCol(i)

        for i in range(settings['rows']):
            grid_sizer.AddGrowableRow(i)

        for ctrl_name, ctrl_type in ctrls:
            ctrl_panel = main_window.ctrl_types[ctrl_type](ctrl_name, mx_db, self)
            box = wx.StaticBox(self, label='{} Control'.format(ctrl_name))
            box.SetOwnForegroundColour(wx.RED)
            box_sizer = wx.StaticBoxSizer(box)
            box_sizer.Add(ctrl_panel, 1, flag=wx.EXPAND)
            grid_sizer.Add(box_sizer, 1, flag=wx.EXPAND)

            self._ctrls.append(ctrl_panel)

        self.SetSizer(grid_sizer)

    def _on_closewindow(self, evt):
        """
        Closes the window. In an attempt to minimize trouble with MX it
        stops and then restarts the MX timer while it destroys the controls.
        """
        main_frame = self.GetParent()
        main_frame.mx_timer.Stop()

        for ctrl in self._ctrls:
            ctrl.on_close()

        wx.CallLater(1000, main_frame.start_timer)
        self.Destroy()


class AddCtrlDialog(wx.Dialog):
    """
    This dialog allows users to add a new control set(button) or modify the
    controls in a control set (button). If they are adding a new set of controls
    they have to provide a group (tab) and a name for the set (button label).
    They then provide one or more controls to go in the group, providing the
    mx record name and the type of control. If they first set the control
    type using the drop down menu, then they can select from a list generated
    by the text control autocomplete function as to the control type they want.

    The actual list of controls is handled by the :class:`ControlList`.
    """
    def __init__(self, set_group=True, *args, **kwargs):
        """
        Initializes the dialog.

        :param bool set_group: If True, the group field is displayed in the
            control. If False, it is not.
        """
        wx.Dialog.__init__(self, *args, **kwargs)
        self._set_group = set_group
        self._create_layout()

        self.Layout()
        self.Fit()

    def _FromDIP(self, size):
        # This is a hack to provide easy back compatibility with wxpython < 4.1
        try:
            return self.FromDIP(size)
        except Exception:
            return size

    def _create_layout(self):
        """ Creates the dialog layout."""
        info_grid = wx.FlexGridSizer(rows=4, cols=2, vgap=self._FromDIP(5),
            hgap=self._FromDIP(5))
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

        self.list_ctrl = ControlList(self,
            agwStyle=ULC.ULC_REPORT|ULC.ULC_HAS_VARIABLE_ROW_HEIGHT)
        self.list_ctrl.InsertColumn(0, 'MX Record Name')
        self.list_ctrl.InsertColumn(1, 'Control Type')
        self.list_ctrl.InsertColumn(2, '')
        # self.list_ctrl.SetUserLineHeight(30)
        self.list_ctrl.SetMinSize(self._FromDIP((370,250)))

        add_btn = wx.Button(self, label='Add control')
        add_btn.Bind(wx.EVT_BUTTON, self._on_add)

        remove_btn = wx.Button(self, label='Remove control')
        remove_btn.Bind(wx.EVT_BUTTON, self._on_remove)

        list_ctrl_btn_sizer = wx.BoxSizer(wx.HORIZONTAL)
        list_ctrl_btn_sizer.Add(add_btn)
        list_ctrl_btn_sizer.Add(remove_btn, border=self._FromDIP(5), flag=wx.LEFT)

        button_sizer = self.CreateButtonSizer(wx.OK | wx.CANCEL)
        self.Bind(wx.EVT_BUTTON, self._on_ok, id=wx.ID_OK)

        top_sizer = wx.BoxSizer(wx.VERTICAL)
        top_sizer.Add(info_grid, border=self._FromDIP(5),
            flag=wx.LEFT|wx.RIGHT|wx.TOP)
        top_sizer.Add(self.list_ctrl, 1, border=self._FromDIP(5),
            flag=wx.EXPAND|wx.LEFT|wx.RIGHT|wx.TOP)
        top_sizer.Add(list_ctrl_btn_sizer, border=self._FromDIP(5),
            flag=wx.ALL|wx.CENTER)
        top_sizer.Add(wx.StaticLine(self), flag=wx.EXPAND)
        top_sizer.Add(button_sizer, border=self._FromDIP(5), flag=wx.ALL)

        self.list_ctrl.SetColumnWidth(0, wx.LIST_AUTOSIZE_USEHEADER)
        self.list_ctrl.SetColumnWidth(1, wx.LIST_AUTOSIZE_USEHEADER)

        self.SetSizer(top_sizer)

    def _on_add(self, evt):
        """Called when the Add control buttion is used. Calls :func:`_add`"""
        self._add()

    def _add(self):
        """
        Adds a new control to the ControlList. The user then needs to set the
        control name and type. The type is automatically set equal to the previous
        control in the list (if any). The name can be set by text auto completion,
        typing the full record name, or using the '...' button to list all available
        records of the selected type.

        :returns: The index of the newly added control in the list.
        :rtype: int
        """
        index = self.list_ctrl.GetItemCount()
        self.list_ctrl.InsertStringItem(index, '')
        main_frame = self.GetParent()

        record_panel = wx.Panel(self.list_ctrl)
        textctrl = wx.TextCtrl(record_panel, name='record')
        textctrl.AutoComplete(main_frame.motor_list)
        button = wx.Button(record_panel, id=index, label='...',
            size=self._FromDIP((30, -1)))
        button.Bind(wx.EVT_BUTTON, self._show_motors)
        record_sizer = wx.BoxSizer(wx.HORIZONTAL)
        record_sizer.Add(textctrl, 1, flag=wx.EXPAND)
        record_sizer.Add(button, border=self._FromDIP(2), flag=wx.LEFT)
        record_panel.SetSizer(record_sizer)

        self.list_ctrl.SetItemWindow(index, 0, record_panel, expand=True)

        item = self.list_ctrl.GetItem(index, 1)
        choice_ctrl = wx.Choice(self.list_ctrl, id=index, choices=list(main_frame.ctrl_types.keys()),
            style=wx.CB_SORT)
        choice_ctrl.SetStringSelection('Motor')
        choice_ctrl.Bind(wx.EVT_CHOICE, self._on_typechange)

        if index>0:
            prev_item = self.list_ctrl.GetItem(index-1, 1)
            prev_choice = prev_item.GetWindow().GetStringSelection()
            choice_ctrl.SetStringSelection(prev_choice)

            if prev_choice == 'Amplifier':
                textctrl.AutoComplete(main_frame.amp_list)

            elif prev_choice == 'Digital IO':
                textctrl.AutoComplete(main_frame.dio_list)

            elif prev_choice == 'Digital O, Btn.':
                textctrl.AutoComplete(main_frame.do_list)

            elif prev_choice == 'Analog IO':
                textctrl.AutoComplete(main_frame.aio_list)

            elif prev_choice == 'Custom':
                textctrl.AutoComplete(main_frame.custom_list)

        self.list_ctrl.SetItemWindow(index, 1, choice_ctrl, expand=True)

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
        """Called by the Remove control button, removes a control."""
        selected = self.list_ctrl.GetFirstSelected()

        while selected != -1:
            self.list_ctrl.DeleteItem(selected)
            selected = self.list_ctrl.GetFirstSelected()

        self.list_ctrl.DoLayout()

    def _on_ok(self, evt):
        """
        Called by the Ok button. When the user attempst to exit the control it
        checks that everything is set appropriately, and, if it is, sets the
        control_data list that is later grabbed to see what contorls the user
        selected.

        :returns: Nothing. Return is just used to exit at various points.
        """
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

            if ctrl_type != 'Custom':
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
        """
        If the dialog is being used to modify a control set, this function
        populates the control values of the existing set.

        :param collections.OrderedDict ctrl_data: A dictionary of the controls. The
            first value should contain entries for the settings: title, rows, cols.
            The subsequent entries contain the controls: a key/value pair of control
            name and control type (as defined in the :class:`MainFrame` ctrl_types
            dictionary).

        :param str group: The name of the control group.
        """
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
            # test = type_ctrl.SetStringSelection(ctrl[1])
            # SetStringSelection not working for 'Custom', here's a stupid workaround
            for i in range(type_ctrl.GetCount()):
                if type_ctrl.GetString(i) == ctrl[1]:
                    type_ctrl.SetSelection(i)


    def _show_motors(self, evt):
        """
        Called when the user presses the '...' button for a control. It
        shows a popup menu with a list of all the motors or amplifiers in the
        mx database, depending on if the control type is 'Motor' or 'Amplifier'.
        """
        index =evt.GetId()
        button = evt.GetEventObject()
        main_frame = self.GetParent()

        ctrl_type = self.list_ctrl.GetItem(index, 1).GetWindow().GetStringSelection()

        if ctrl_type == 'Motor':
            records = main_frame.motor_list
        elif ctrl_type == 'Amplifier':
            records = main_frame.amp_list
        elif ctrl_type == 'Digital IO':
            records = main_frame.dio_list
        elif ctrl_type == 'Digital O, Btn.':
            records = main_frame.do_list
        elif ctrl_type == 'Analog IO':
            records = main_frame.aio_list
        elif ctrl_type == 'Custom':
            records = main_frame.custom_list

        menu = wx.Menu()
        menu.Bind(wx.EVT_MENU, self._on_motor_menu_choice)

        for i, name in enumerate(records):
            menu.Append(i+1, name)

        button.PopupMenu(menu)

        menu.Destroy()

    def _on_motor_menu_choice(self, evt):
        """
        When a record is selected in the popup menu, this sets it as the record
        for the item in the control list.
        """
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
        elif ctrl_type == 'Digital IO':
            txtctrl.SetValue(main_frame.dio_list[choice])
        elif ctrl_type == 'Digital O, Btn.':
            txtctrl.SetValue(main_frame.do_list[choice])
        elif ctrl_type == 'Analog IO':
            txtctrl.SetValue(main_frame.aio_list[choice])
        elif ctrl_type == 'Custom':
            txtctrl.SetValue(main_frame.custom_list[choice])

    def _on_typechange(self, evt):
        """
        Called when the control type is changed for an item in the control list.
        This changes the textctrl autocompletion dictionary.
        """
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
        elif evt.GetString() == 'Digital IO':
            txtctrl.AutoComplete(main_frame.dio_list)
        elif evt.GetString() == 'Digital O, Btn.':
            txtctrl.AutoComplete(main_frame.do_list)
        elif evt.GetString() == 'Analog IO':
            txtctrl.AutoComplete(main_frame.aio_list)
        elif evt.GetString() == 'Custom':
            txtctrl.AutoComplete(main_frame.custom_list)


class RemoveCtrlDialog(wx.Dialog):
    """
    This dialog is used to modify order of and/or remove items from a control
    group (in which case the items are control sets), or from the list of control
    groups (in which case the items are control groups).
    """
    def __init__(self, params, *args, **kwargs):
        """
        Initializes the  dialog. It takes all of the arguments for a wx.Dialog
        and also the following arguments.

        :param collections.OrderedDict params: A dictionary where the keys
            are the names of the control items of interest.
        """
        wx.Dialog.__init__(self, *args, **kwargs)
        self._params = params
        self._create_layout()

    def _FromDIP(self, size):
        # This is a hack to provide easy back compatibility with wxpython < 4.1
        try:
            return self.FromDIP(size)
        except Exception:
            return size

    def _create_layout(self):
        """Creates the layout for the dialog."""

        self.list_ctrl = wx.ListCtrl(self, style=wx.LC_REPORT)
        self.list_ctrl.InsertColumn(0, 'Control')

        for param in self._params.keys():
            self.list_ctrl.InsertItem(sys.maxsize, param)

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
        """Called when the Remove button is clicked. Removes the item."""
        selected = self.list_ctrl.GetFirstSelected()

        while selected != -1:
            self.list_ctrl.DeleteItem(selected)
            selected = self.list_ctrl.GetFirstSelected()

    def _on_up(self, evt):
        """Called when the Up button is clicked. Moves the selected item(s) up."""
        selected_items = []
        selected = self.list_ctrl.GetFirstSelected()

        while selected != -1:
            selected_items.append(selected)
            if selected > 0:
                data = self.list_ctrl.GetItemText(selected)
                self.list_ctrl.DeleteItem(selected)
                self.list_ctrl.InsertItem(selected-1, data)
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
        """
        Called when the Down button is clicked. Moves the selected item(s) down.
        """
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
            self.list_ctrl.InsertItem(idx+1, data)

        if selected_items[-1] == nitems-1:
            item = self.list_ctrl.FindItem(-1, last_data)
            self.list_ctrl.DeleteItem(item)
            self.list_ctrl.InsertItem(nitems, last_data)


        for idx in selected_items:
            if idx<nitems-1:
                self.list_ctrl.Select(idx+1, True)
            else:
                self.list_ctrl.Select(nitems-1, True)

    def _on_ok(self, evt):
        """
        Called when Ok is selected to close the control. Gathers values so
        that the controls can be modified.
        """
        nitems = self.list_ctrl.GetItemCount()
        self.keys = [self.list_ctrl.GetItemText(i) for i in range(nitems)]
        if self.GetTitle() == 'Modify Control Groups':
            msg = ('Note: you will have to restart the program for any changes '
                'in group ordering to take effect (you can also drag the tabs '
                'to reorder them).')
            wx.MessageBox(msg, 'Tab order changes on restart')
        self.EndModal(wx.ID_OK)

class ControlList(ULC.UltimateListCtrl, listmix.ListCtrlAutoWidthMixin):
    """
    A ControlList, which is an AGW ultimate list control with a the list control
    auto width mixin added.
    """
    def __init__(self, *args, **kwargs):
        """
        Initializes the list. Takes all arguments that the wx.agw.UltimateListCtrl
        takes.
        """
        ULC.UltimateListCtrl.__init__(self, *args, **kwargs)
        listmix.ListCtrlAutoWidthMixin.__init__(self)

#This class was lifted from:
#https://stackoverflow.com/questions/27050108/convert-numpy-type-to-python/27050186#27050186
class MyEncoder(json.JSONEncoder):
    """
    A json.JSONEncoder that converts np types into normal types so that
    they can be properly saved in json format.
    """
    def default(self, obj):
        """A json encoder."""
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
    """The top level wx.App that we subclass to add an exceptionhook."""

    def OnInit(self):
        """Initializes the app. Calls the :class:`MainFrame`"""

        # sys.excepthook = self.ExceptionHook
        if len(sys.argv) > 1:
            title = ' '.join(sys.argv[1:])
        else:
            title = 'BioCAT Staff Controls'

        frame = MainFrame(title=title, name='MainFrame')
        frame.Show()

        return True

    def BringWindowToFront(self):
        """
        Overwrites this default method to deal with the possibility that it
        is called when the frame is closed.
        """
        try: # it's possible for this event to come when the frame is closed
            self.GetTopWindow().Raise()
        except:
            pass

    def ExceptionHook(self, errType, value, trace):
        """
        Creates an exception hook that catches all uncaught exceptions and informs
        users of them, instead of letting the program crash. From
        http://apprize.info/python/wxpython/10.html
        """
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

        :return: True to allow program to continue running without showing error.
            False to show the error.
        """
        return False


if __name__ == '__main__':
    setup_thread_excepthook()

    app = MyApp(0)   #MyApp(redirect = True)
    # wx.lib.inspection.InspectionTool().Show()
    app.MainLoop()
