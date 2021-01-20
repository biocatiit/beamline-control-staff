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
import epics

import utils
utils.set_mppath() #This must be done before importing any Mp Modules.
import Mp as mp
import MpCa as mpca
import MpWx as mpwx
import custom_widgets

class DIOPanel(wx.Panel):
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
    def __init__(self, dio_name, mx_database, parent, panel_id=wx.ID_ANY,
        panel_name=''):
        """
        Initializes the custom panel. Important parameters here are the
        ``dio_name``, and the ``mx_database``.

        :param str dio_name: The amplifier name in the Mx database.

        :param Mp.RecordList mx_database: The database instance from Mp.

        :param wx.Window parent: Parent class for the panel.

        :param int panel_id: wx ID for the panel.

        :param str panel_name: Name for the panel.
        """
        wx.Panel.__init__(self, parent, panel_id, name=panel_name)

        self.mx_database = mx_database
        self.dio_name = dio_name
        self.dio = self.mx_database.get_record(self.dio_name)
        self.dio_class = self.dio.get_field('mx_class')
        self.dio_type = self.dio.get_field('mx_type')

        if self.dio_class == 'digital_input':
            self.is_input = True
        else:
            self.is_input = False

        if self.dio_type.startswith('epics'):
            self.is_epics = True
            pv_name = self.dio.get_field('epics_variable_name')
            self.pv = epics.PV(pv_name)

        else:
            self.is_epics = False
            server_record_name = self.amp.get_field("server_record")
            self.server_record = self.mx_database.get_record(server_record_name)
            self.remote_record_name = self.amp.get_field("remote_record_name")

        self._enabled = True

        self._create_layout()

        self._initialize()

    def _create_layout(self):
        """
        Creates the layout for the panel.

        """

        if not self.is_input:
            self.off = wx.RadioButton(self, label='Off', style=wx.RB_GROUP)
            self.on = wx.RadioButton(self, label='On')

            self.off.Bind(wx.EVT_RADIOBUTTON, self._on_output)
            self.on.Bind(wx.EVT_RADIOBUTTON, self._on_output)

            control_sizer = wx.BoxSizer(wx.VERTICAL)
            control_sizer.Add(self.off)
            control_sizer.Add(self.on, border=3, flag=wx.TOP)
        else:
            self.state = wx.StaticText(self, label='')

            control_sizer = wx.BoxSizer(wx.HORIZONTAL)
            control_sizer.Add(wx.StaticText(self, label='State:'),
                flag=wx.ALIGN_CENTER_VERTICAL)
            control_sizer.Add(self.state, border=3, flag=wx.LEFT|wx.ALIGN_CENTER_VERTICAL)

        top_sizer = wx.BoxSizer(wx.VERTICAL)
        top_sizer.Add(control_sizer)

        self.Bind(wx.EVT_RIGHT_DOWN, self._on_rightclick)
        for item in self.GetChildren():
            if (isinstance(item, wx.StaticText) or isinstance(item, mpwx.Value)
                or isinstance(item, custom_widgets.CustomEpicsValue) or isinstance(item, wx.StaticBox)):
                item.Bind(wx.EVT_RIGHT_DOWN, self._on_rightclick)

        self.SetSizer(top_sizer)

        # return top_sizer

    def _initialize(self):
        if self.is_input:
            if self.is_epics:
                # self.callback = self.pv.add_callback(mpca.DBE_VALUE, self._on_epics_input, (self.pv, self._update_status))
                self.callback = self.pv.add_callback(self._on_epics_input)

                # value = self.pv.caget()
                # self._on_epics_input(self.callback, (self.pv, self._update_status))
        else:
            if self.is_epics:
                # value = self.pv.caget()
                value = self.pv.get()

                if value:
                    self.on.SetValue(True)
                    # self.off.SetValue(False)
                else:
                    # self.on.SetValue(False)
                    self.off.SetValue(True)


    # def _on_output(self, event):
    #     if event.GetEventObject() == self.off:
    #         if self.is_epics:
    #             self.pv.caput(0, wait=False)
    #     else:
    #         if self.is_epics:
    #             self.pv.caput(1, wait=False)

    def _on_output(self, event):
        if event.GetEventObject() == self.off:
            if self.is_epics:
                self.pv.put(0, wait=False)
        else:
            if self.is_epics:
                self.pv.put(1, wait=False)

    # @staticmethod
    # def _on_epics_input(callback, args):
    #     print('in on_epics_input')
    #     pv, update_func = args

    #     value = pv.get_local()
    #     print(value)
    #     print(pv.caget())

    #     if isinstance( value, list ):
    #         if ( len(value) == 1 ):
    #             value = value[0]

    #     wx.CallAfter(update_func, value)

    def _on_epics_input(self, **kwargs):
        value = kwargs['value']
        # pv, update_func = args

        # value = pv.get_local()
        # print(value)
        # print(pv.caget())

        # if isinstance( value, list ):
        #     if ( len(value) == 1 ):
        #         value = value[0]

        wx.CallAfter(self._update_status, value)

    # def _update_status(self, value):
    #     print(value)
    #     if value:
    #         self.state.SetLabel('On')
    #     else:
    #         self.state.SetLabel('Off')

    def _update_status(self, value):
        if value:
            self.state.SetLabel('On')
        else:
            self.state.SetLabel('Off')

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

class DOButtonPanel(wx.Panel):
    """
    For digital outputs where you just want to set the variable to go, like
    for opening a gate valve or triggering one of the hutch shutters.
    """
    def __init__(self, dio_name, mx_database, parent, panel_id=wx.ID_ANY,
        panel_name=''):
        """
        Initializes the custom panel. Important parameters here are the
        ``dio_name``, and the ``mx_database``.

        :param str dio_name: The amplifier name in the Mx database.

        :param Mp.RecordList mx_database: The database instance from Mp.

        :param wx.Window parent: Parent class for the panel.

        :param int panel_id: wx ID for the panel.

        :param str panel_name: Name for the panel.
        """
        wx.Panel.__init__(self, parent, panel_id, name=panel_name)

        self.mx_database = mx_database
        self.dio_name = dio_name
        self.dio = self.mx_database.get_record(self.dio_name)
        self.dio_class = self.dio.get_field('mx_class')
        self.dio_type = self.dio.get_field('mx_type')

        self.is_input = False

        if self.dio_type.startswith('epics'):
            self.is_epics = True
            pv_name = self.dio.get_field('epics_variable_name')
            self.pv = mpca.PV(pv_name)

        else:
            self.is_epics = False
            server_record_name = self.amp.get_field("server_record")
            self.server_record = self.mx_database.get_record(server_record_name)
            self.remote_record_name = self.amp.get_field("remote_record_name")

        self._enabled = True

        self._create_layout()

        self._initialize()

    def _create_layout(self):
        """
        Creates the layout for the panel.

        """

        self.on = wx.Button(self, label='Actuate')

        self.on.Bind(wx.EVT_BUTTON, self._on_output)

        control_sizer = wx.BoxSizer(wx.VERTICAL)
        control_sizer.Add(self.on, border=5, flag=wx.ALL)

        top_sizer = wx.BoxSizer(wx.VERTICAL)
        top_sizer.Add(control_sizer)

        self.Bind(wx.EVT_RIGHT_DOWN, self._on_rightclick)
        for item in self.GetChildren():
            if (isinstance(item, wx.StaticText) or isinstance(item, mpwx.Value)
                or isinstance(item, custom_widgets.CustomEpicsValue) or isinstance(item, wx.StaticBox)):
                item.Bind(wx.EVT_RIGHT_DOWN, self._on_rightclick)

        self.SetSizer(top_sizer)

        # return top_sizer

    def _initialize(self):
        pass

    def _on_output(self, event):
        self.pv.caput(1, wait=False)

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


class DIOFrame(wx.Frame):
    """
    A lightweight amplifier frame designed to hold an arbitrary number of dios
    in an arbitrary grid pattern.
    """
    def __init__(self, mx_database, dios, shape, timer=True, *args, **kwargs):
        """
        Initializes the amp frame. This frame is designed to function either as
        a stand alone application, or as part of a larger application.

        :param Mp.RecordList mx_database: The Mp database containing the amp records.

        :param list dios: The amp names in the Mp database.

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

        top_sizer = self._create_layout(dios, shape)

        self.SetSizer(top_sizer)
        self.Layout()
        self.Fit()
        self.Raise()

        if timer:
            self.mx_timer.Start(1000)

    def _create_layout(self, dios, shape):
        """
        Creates the layout.

        :param list dios: The amplifier names in the Mp database.

        :param tuple shape: A tuple containing the shape of the amp grid.
            It is given as: (rows, cols). Note that rows*cols should be equal
            to or greater than the number of dios, but the AmpFrame doesn't
            check this. If it isn't, it will just fail to propely display the last
            few dios.
        """
        dio_grid = wx.FlexGridSizer(rows=shape[0], cols=shape[1], vgap=2,
            hgap=2)

        for i in range(shape[1]):
            dio_grid.AddGrowableCol(i)

        for dio in dios:
            dio_panel = DIOPanel(dio, self.mx_database, self)
            dio_box_sizer = wx.StaticBoxSizer(wx.StaticBox(self, label='{} Controls'.format(dio)))
            dio_box_sizer.Add(dio_panel)
            dio_grid.Add(dio_box_sizer)

        dio_panel_sizer = wx.BoxSizer(wx.HORIZONTAL)
        dio_panel_sizer.Add(dio_grid)

        return dio_panel_sizer

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
    mx_database.set_program_name("digital_ios")

    app = wx.App()
    frame = DIOFrame(mx_database, ['avme944x_in14', 'avme944x_out14'],
        (2,1), parent=None, title='Test Amplifier Control')
    frame.Show()
    app.MainLoop()
