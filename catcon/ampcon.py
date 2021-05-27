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

if __name__ == "__main__" and __package__ is None:
    __package__ = "catcon"

import os

import wx
import epics, epics.wx

import utils
utils.set_mppath() #This must be done before importing any Mp Modules.
import Mp as mp
import MpWx as mpwx
import custom_widgets

class AmpPanel(wx.Panel):
    """
    .. todo::
        Eventually this should allow viewing (and setting?) of the amp
        settings, ideally through a generic GUI that works for various
        types of devices, not just amps.

    This amp panel supports standard amplifier controls, such as setting the
    gain and the offset. It is mean to be embedded in a larger application,
    and can be instanced several times, once for each amp. It communicates
    with the amps by calling ``Mp``, the python wrapper for ``MX``.
    """
    def __init__(self, amp_name, mx_database, parent, panel_id=wx.ID_ANY,
        panel_name=''):
        """
        Initializes the custom panel. Important parameters here are the
        ``amp_name``, and the ``mx_database``.

        :param str amp_name: The amplifier name in the Mx database.

        :param Mp.RecordList mx_database: The database instance from Mp.

        :param wx.Window parent: Parent class for the panel.

        :param int panel_id: wx ID for the panel.

        :param str panel_name: Name for the panel.
        """
        wx.Panel.__init__(self, parent, panel_id, name=panel_name)

        self.mx_database = mx_database
        self.amp_name = amp_name
        self.amp = self.mx_database.get_record(self.amp_name)
        server_record_name = self.amp.get_field("server_record")
        self.server_record = self.mx_database.get_record(server_record_name)
        self.remote_record_name = self.amp.get_field("remote_record_name")

        self._enabled = True

        top_sizer = self._create_layout()

        self.SetSizer(top_sizer)

    def _create_layout(self):
        """
        Creates the layout for the panel.

        :returns: wx Sizer for the panel.
        :rtype: wx.Sizer
        """

        #Don't know how to get possible amplifications from mx, if it even knows. So this instead.
        amp_choices = ['1e+02', '1e+03', '1e+04', '1e+05', '1e+06', '1e+07',
            '1e+08', '1e+09', '1e+10']

        gain_name = "{}.gain".format(self.remote_record_name)
        gain = mpwx.Choice(self, self.server_record, gain_name,
            choices=amp_choices, function=self._choice_update)

        offset_name = "{}.offset".format(self.remote_record_name)
        offset = mpwx.ValueEntry(self, self.server_record, offset_name)

        timec_name = "{}.time_constant".format(self.remote_record_name)
        timec = mpwx.ValueEntry(self, self.server_record, timec_name)

        control_grid = wx.FlexGridSizer(rows=4, cols=2, vgap=5, hgap=5)
        control_grid.Add(wx.StaticText(self, label='Amplifier name:'), flag=wx.ALIGN_CENTER_VERTICAL)
        control_grid.Add(wx.StaticText(self, label=self.amp.get_field('name')),
            flag=wx.EXPAND|wx.ALIGN_CENTER_VERTICAL)
        control_grid.Add(wx.StaticText(self, label='Gain:'), flag=wx.ALIGN_CENTER_VERTICAL)
        control_grid.Add(gain, flag=wx.EXPAND|wx.ALIGN_CENTER_VERTICAL)
        control_grid.Add(wx.StaticText(self, label='Offset:'), flag=wx.ALIGN_CENTER_VERTICAL)
        control_grid.Add(offset, flag=wx.EXPAND|wx.ALIGN_CENTER_VERTICAL)
        control_grid.Add(wx.StaticText(self, label='Time constant:'), flag=wx.ALIGN_CENTER_VERTICAL)
        control_grid.Add(timec, flag=wx.EXPAND|wx.ALIGN_CENTER_VERTICAL)
        control_grid.AddGrowableCol(1)

        control_sizer = wx.BoxSizer(wx.VERTICAL)
        control_sizer.Add(control_grid, 1, flag=wx.EXPAND)

        top_sizer = wx.BoxSizer(wx.VERTICAL)
        top_sizer.Add(control_sizer, 1, flag=wx.EXPAND)

        self.Bind(wx.EVT_RIGHT_DOWN, self._on_rightclick)
        for item in self.GetChildren():
            if (isinstance(item, wx.StaticText) or isinstance(item, mpwx.Value)
                or isinstance(item, custom_widgets.CustomEpicsValue) or isinstance(item, wx.StaticBox)):
                item.Bind(wx.EVT_RIGHT_DOWN, self._on_rightclick)

        return top_sizer

    @staticmethod
    def _choice_update(nf, widget, args, value):
        """
        Callback function for the mpwx choice widget for the amps. It's modeled
        on the base callback function, but properly interprets the string formatting.
        """
        if isinstance(value, list):
            if (len(value) == 1):
                value = value[0]

        value = '{:.0e}'.format(value)

        if widget.FindString(value) != wx.NOT_FOUND:
            widget.SetStringSelection(value)
        else:
            if float(value) < float(widget.GetString(0)):
                widget.Insert(value, 0)
            else:
                widget.Insert(value, widget.GetCount())

            widget.SetStringSelection(value)

    def _on_rightclick(self, evt):
        """
        Shows a context menu. Current options allow enabling/disabling
        the control panel.
        """
        menu = wx.Menu()
        menu.Bind(wx.EVT_MENU, self._on_enablechange)

        if self._enabled:
            menu.Append(1, 'Disable Control')
        else:
            menu.Append(1, 'Enable Control')

        menu.Append(2, 'Show control info')

        self.PopupMenu(menu)
        menu.Destroy()

    def _on_enablechange(self, evt):
        """
        Called from the panel context menu. Enables/disables the control
        panel.
        """
        if self._enabled:
            self._enabled = False
        else:
            self._enabled = True

        for item in self.GetChildren():
            if (not isinstance(item, wx.StaticText) and not isinstance(item, custom_widgets.CustomValue)
                and not isinstance(item, custom_widgets.CustomEpicsValue) and not
                isinstance(item, wx.StaticBox)):
                item.Enable(self._enabled)


class DBPMAmpPanel(wx.Panel):
    """
    Sydor Diamond DBPM amplifier panel. Has to set the gain and the scale
    factor. Can also read out the value of the current, so we display that.
    """
    def __init__(self, amp_name, mx_database, parent, panel_id=wx.ID_ANY,
        panel_name=''):
        """
        Initializes the custom panel. Important parameters here are the
        ``amp_name``, and the ``mx_database``.

        :param str amp_name: The amplifier name in the Mx database.

        :param Mp.RecordList mx_database: The database instance from Mp.

        :param wx.Window parent: Parent class for the panel.

        :param int panel_id: wx ID for the panel.

        :param str panel_name: Name for the panel.
        """
        wx.Panel.__init__(self, parent, panel_id, name=panel_name)

        self.mx_database = mx_database
        self.amp_name = amp_name

        self.amp_gain_pv = epics.PV('{}Gain:Level-SP'.format(self.amp_name))
        self.amp_current_pv = epics.PV('{}Ampl:CurrTotal-I'.format(self.amp_name))
        self.amp_scale_pv = epics.PV('{}CtrlDAC:CLevel-SP'.format(self.amp_name))

        self.amp_gain_pv.get()
        self.amp_current_pv.get()
        self.amp_scale_pv.get()

        self._enabled = True

        top_sizer = self._create_layout()

        self.gain_callback = self.amp_gain_pv.add_callback(self._on_epics_gain_change)
        self.scale_callback = self.amp_scale_pv.add_callback(self._on_epics_scale_change)

        self._epics_gain_change(self.amp_gain_pv.get())

        self.SetSizer(top_sizer)

    def _create_layout(self):
        """
        Creates the layout for the panel.

        :returns: wx Sizer for the panel.
        :rtype: wx.Sizer
        """

        #Don't know how to get possible amplifications from mx, if it even knows. So this instead.
        amp_choices = ['1e+02', '1e+04', '1e+05', '1e+06', '1e+07']

        self.gain = wx.Choice(self, choices=amp_choices)
        self.gain.Bind(wx.EVT_CHOICE, self._on_change_gain)

        input_c = epics.wx.PVText(self, self.amp_current_pv, auto_units=True)

        control_grid = wx.FlexGridSizer(cols=2, vgap=5, hgap=5)
        control_grid.Add(wx.StaticText(self, label='Amplifier name:'), flag=wx.ALIGN_CENTER_VERTICAL)
        control_grid.Add(wx.StaticText(self, label=self.amp_name),
            flag=wx.EXPAND|wx.ALIGN_CENTER_VERTICAL)
        control_grid.Add(wx.StaticText(self, label='Gain:'), flag=wx.ALIGN_CENTER_VERTICAL)
        control_grid.Add(self.gain, flag=wx.EXPAND|wx.ALIGN_CENTER_VERTICAL)
        control_grid.Add(wx.StaticText(self, label='Input:'), flag=wx.ALIGN_CENTER_VERTICAL)
        control_grid.Add(input_c, flag=wx.EXPAND|wx.ALIGN_CENTER_VERTICAL)


        control_sizer = wx.BoxSizer(wx.VERTICAL)
        control_sizer.Add(control_grid, 1, flag=wx.EXPAND)

        top_sizer = wx.BoxSizer(wx.VERTICAL)
        top_sizer.Add(control_sizer, 1, flag=wx.EXPAND)

        self.Bind(wx.EVT_RIGHT_DOWN, self._on_rightclick)
        for item in self.GetChildren():
            if (isinstance(item, wx.StaticText) or isinstance(item, mpwx.Value)
                or isinstance(item, custom_widgets.CustomEpicsValue) or isinstance(item, wx.StaticBox)):
                item.Bind(wx.EVT_RIGHT_DOWN, self._on_rightclick)

        return top_sizer

    def _on_change_gain(self, evt):
        wx.CallAfter(self._change_gain)

    def _change_gain(self):
        gain = self.gain.GetStringSelection()

        if gain == '1e+07':
            gain_setting = '1uA'
            scale = 100.0

        elif gain == '1e+06':
            gain_setting = '10uA'
            scale = 10.0

        elif gain == '1e+05':
            gain_setting = '100uA'
            scale = 1.0

        elif gain == '1e+04':
            gain_setting = '1mA'
            scale = 0.1

        elif gain == '1e+02':
            gain_setting = '35mA'
            scale = 0.001

        self.amp_gain_pv.remove_callback(self.gain_callback)
        self.amp_scale_pv.remove_callback(self.scale_callback)

        self.amp_scale_pv.put(0, wait=True)
        self.amp_gain_pv.put(gain_setting, wait=True)
        self.amp_scale_pv.put(scale, wait=True)

        self.gain_callback = self.amp_gain_pv.add_callback(self._on_epics_gain_change)
        self.scale_callback = self.amp_scale_pv.add_callback(self._on_epics_scale_change)

    def _on_epics_gain_change(self, value, **kwargs):
        wx.CallAfter(self._epics_gain_change, value, **kwargs)

    def _epics_gain_change(self, value, **kwargs):

        if value == 0:
            gain = '1e+07'
        elif value == 1:
            gain = '1e+06'
        elif value == 2:
            gain = '1e+05'
        elif value == 3:
            gain = '1e+04'
        elif value == 4:
            gain = '1e+02'

        if gain == '1e+07':
            scale = 100.0

        elif gain == '1e+06':
            scale = 10.0

        elif gain == '1e+05':
            scale = 1.0

        elif gain == '1e+04':
            scale = 0.1

        elif gain == '1e+02':
            scale = 0.001

        if scale != float(self.amp_scale_pv.get(as_string=True)):
            self.amp_scale_pv.remove_callback(self.scale_callback)
            self.amp_scale_pv.put(scale, wait=True)
            self.scale_callback = self.amp_scale_pv.add_callback(self._on_epics_scale_change)

        if gain != self.gain.GetStringSelection():
            self.gain.SetStringSelection(gain)

    def _on_epics_scale_change(self, char_value, **kwargs):
        wx.CallAfter(self._epics_scale_change, char_value, **kwargs)

    def _epics_scale_change(self, char_value, **kwargs):
        value = float(char_value)

        if value >= 100.0:
            gain = '1e+07'
        elif value >= 10.0:
            gain = '1e+06'
        elif value >= 1.0:
            gain = '1e+05'
        elif value >= 0.1:
            gain = '1e+04'
        elif value >= 0.001:
            gain = '1e+02'
        else:
            gain = '1e+02'

        if gain == '1e+07':
            gain_setting = '1uA'
            gain_val = 0
            scale = 100.0

        elif gain == '1e+06':
            gain_setting = '10uA'
            gain_val = 1
            scale = 10.0

        elif gain == '1e+05':
            gain_setting = '100uA'
            gain_val = 2
            scale = 1.0

        elif gain == '1e+04':
            gain_setting = '1mA'
            gain_val = 3
            scale = 0.1

        elif gain == '1e+02':
            gain_setting = '35mA'
            gain_val = 4
            scale = 0.001

        if scale != float(self.amp_scale_pv.get(as_string=True)):
            self.amp_scale_pv.remove_callback(self.scale_callback)
            self.amp_scale_pv.put(scale, wait=True)
            self.scale_callback = self.amp_scale_pv.add_callback(self._on_epics_scale_change)

        if gain_val != self.amp_gain_pv.get():
            self.amp_gain_pv.remove_callback(self.gain_callback)
            self.amp_gain_pv.put(gain_setting, wait=True)
            self.gain_callback = self.amp_gain_pv.add_callback(self._on_epics_gain_change)

        if gain != self.gain.GetStringSelection():
            self.gain.SetStringSelection(gain)

    def _on_rightclick(self, evt):
        """
        Shows a context menu. Current options allow enabling/disabling
        the control panel.
        """
        menu = wx.Menu()
        menu.Bind(wx.EVT_MENU, self._on_enablechange)

        if self._enabled:
            menu.Append(1, 'Disable Control')
        else:
            menu.Append(1, 'Enable Control')

        menu.Append(2, 'Show control info')

        self.PopupMenu(menu)
        menu.Destroy()

    def _on_enablechange(self, evt):
        """
        Called from the panel context menu. Enables/disables the control
        panel.
        """
        if self._enabled:
            self._enabled = False
        else:
            self._enabled = True

        for item in self.GetChildren():
            if (not isinstance(item, wx.StaticText) and not isinstance(item, custom_widgets.CustomValue)
                and not isinstance(item, custom_widgets.CustomEpicsValue) and not
                isinstance(item, wx.StaticBox)):
                item.Enable(self._enabled)


class AmpFrame(wx.Frame):
    """
    A lightweight amplifier frame designed to hold an arbitrary number of amps
    in an arbitrary grid pattern.
    """
    def __init__(self, mx_database, amps, shape, timer=True, dbpm=False, *args, **kwargs):
        """
        Initializes the amp frame. This frame is designed to function either as
        a stand alone application, or as part of a larger application.

        :param Mp.RecordList mx_database: The Mp database containing the amp records.

        :param list amps: The amp names in the Mp database.

        :param tuple shape: A tuple containing the shape of the motor grid.
            It is given as: (rows, cols). Note that rows*cols should be equal
            to or greater than the number of motors, but the MotorFrame doesn't
            check this. If it isn't, it will just fail to propely display the last
            few motors.

        :param bool timer: Whether or not the frame should start a timer to call
            the mx_database.wait_for_messages. I suspect this should only be done
            if this is standalone, hence why it can be turned on/off.
        """
        wx.Frame.__init__(self, *args, **kwargs)

        self.mx_database = mx_database

        self.mx_timer = wx.Timer()
        self.mx_timer.Bind(wx.EVT_TIMER, self._on_mxtimer)

        self.dbpm = dbpm

        top_sizer = self._create_layout(amps, shape)

        self.SetSizer(top_sizer)
        self.Fit()
        self.Raise()

        if timer:
            self.mx_timer.Start(1000)

    def _create_layout(self, amps, shape):
        """
        Creates the layout.

        :param list amps: The amplifier names in the Mp database.

        :param tuple shape: A tuple containing the shape of the amp grid.
            It is given as: (rows, cols). Note that rows*cols should be equal
            to or greater than the number of amps, but the AmpFrame doesn't
            check this. If it isn't, it will just fail to propely display the last
            few amps.
        """
        amp_grid = wx.FlexGridSizer(rows=shape[0], cols=shape[1], vgap=2,
            hgap=2)

        for i in range(shape[1]):
            amp_grid.AddGrowableCol(i)

        for amp in amps:
            if not self.dbpm:
                amp_panel = AmpPanel(amp, self.mx_database, self)
            else:
                amp_panel = DBPMAmpPanel(amp, self.mx_database, self)

            amp_box_sizer = wx.StaticBoxSizer(wx.StaticBox(self, label='{} Controls'.format(amp)))
            amp_box_sizer.Add(amp_panel)
            amp_grid.Add(amp_box_sizer)

        amp_panel_sizer = wx.BoxSizer(wx.HORIZONTAL)
        amp_panel_sizer.Add(amp_grid)

        return amp_panel_sizer

    def _on_mxtimer(self, evt):
        """
        Called on the mx_timer, refreshes mx values in the GUI by calling
        wait_for_messages on the database.
        """
        self.mx_database.wait_for_messages(0.01)

if __name__ == '__main__':
    try:
        # First try to get the name from an environment variable.
        database_filename = os.environ["MXDATABASE"]
    except:
        # If the environment variable does not exist, construct
        # the filename for the default MX database.
        mxdir = utils.get_mxdir()
        database_filename = os.path.join(mxdir, "etc", "mxmotor.dat")
        database_filename = os.path.normpath(database_filename)

    mx_database = mp.setup_database(database_filename)
    mx_database.set_plot_enable(2)
    mx_database.set_program_name("ampcon")

    # mx_database = None

    app = wx.App()
    # frame = AmpFrame(mx_database, ['keithley1', 'keithley2', 'keithley3', 'keithley4'],
    #     (2,2), parent=None, title='Test Amplifier Control')
    frame = AmpFrame(mx_database, ['18ID_BPM_D_'],
        (2,2), False, True, parent=None, title='Test Amplifier Control')
    frame.Show()
    app.MainLoop()
