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

class AIOPanel(wx.Panel):
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
        self.aio_name = dio_name
        self.aio = self.mx_database.get_record(self.aio_name)
        self.aio_class = self.aio.get_field('mx_class')
        self.aio_type = self.aio.get_field('mx_type')

        if self.aio_class == 'analog_input':
            self.is_input = True
        else:
            self.is_input = False

        if self.aio_type.startswith('epics'):
            self.is_epics = True
            pv_name = self.aio.get_field('epics_variable_name')
            self.pv = epics.PV(pv_name)
            self.pv.get()

        else:
            self.is_epics = False
            server_record_name = self.amp.get_field("server_record")
            self.server_record = self.mx_database.get_record(server_record_name)
            self.remote_record_name = self.amp.get_field("remote_record_name")

        self._enabled = True

        self._create_layout()

        self._initialize()

        self.SendSizeEvent()

    def on_close(self):
        pass

    def _create_layout(self):
        """
        Creates the layout for the panel.

        """

        if self.is_input:
            if not self.is_epics:
                ai_name = "{}.value".format(self.remote_record_name)
                ai = mpwx.Value(self, self.server_record, ai_name)

            else:
                ai = epics.wx.PVText(self, self.pv)

            control_sizer = wx.BoxSizer(wx.HORIZONTAL)
            control_sizer.Add(wx.StaticText(self, label='Input:'), border=5,
                flag=wx.RIGHT|wx.ALIGN_CENTER_VERTICAL)
            control_sizer.Add(ai, flag=wx.ALIGN_CENTER_VERTICAL)
            control_sizer.AddStretchSpacer(1)

        else:
            if not self.is_epics:
                ao_name = "{}.value".format(self.remote_record_name)
                ao = mpwx.ValueEntry(self, self.server_record, ao_name)
            else:
                ao = epics.wx.PVFloatCtrl(self, self.pv)

            control_sizer = wx.BoxSizer(wx.HORIZONTAL)
            control_sizer.Add(wx.StaticText(self, label='Output:'),
                flag=wx.ALIGN_CENTER_VERTICAL)
            control_sizer.Add(ao, border=3, flag=wx.LEFT|wx.ALIGN_CENTER_VERTICAL)
            control_sizer.AddStretchSpacer(1)

        top_sizer = wx.BoxSizer(wx.VERTICAL)
        top_sizer.Add(control_sizer, flag=wx.EXPAND)

        self.Bind(wx.EVT_RIGHT_DOWN, self._on_rightclick)
        for item in self.GetChildren():
            if ((isinstance(item, wx.StaticText) or isinstance(item, mpwx.Value)
                or isinstance(item, wx.StaticBox)) 
                and not (isinstance(item, epics.wx.PVText) or isinstance(item, epics.wx.PVFloatCtrl))
                ):

                item.Bind(wx.EVT_RIGHT_DOWN, self._on_rightclick)

        self.SetSizer(top_sizer)

        # return top_sizer

    def _initialize(self):
        pass

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
                and not isinstance(item, wx.StaticBox)):
                item.Enable(self._enabled)


class AIOFrame(wx.Frame):
    """
    A lightweight amplifier frame designed to hold an arbitrary number of aios
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

    def _create_layout(self, aios, shape):
        """
        Creates the layout.

        :param list dios: The amplifier names in the Mp database.

        :param tuple shape: A tuple containing the shape of the amp grid.
            It is given as: (rows, cols). Note that rows*cols should be equal
            to or greater than the number of dios, but the AmpFrame doesn't
            check this. If it isn't, it will just fail to propely display the last
            few dios.
        """
        aio_grid = wx.FlexGridSizer(rows=shape[0], cols=shape[1], vgap=2,
            hgap=2)

        for i in range(shape[1]):
            aio_grid.AddGrowableCol(i)

        for aio in aios:
            aio_panel = AIOPanel(aio, self.mx_database, self)
            aio_box_sizer = wx.StaticBoxSizer(wx.StaticBox(self, label='{} Controls'.format(aio)))
            aio_box_sizer.Add(aio_panel, 1, flag=wx.EXPAND)
            aio_grid.Add(aio_box_sizer, flag=wx.EXPAND)

        aio_panel_sizer = wx.BoxSizer(wx.HORIZONTAL)
        aio_panel_sizer.Add(aio_grid, 1, flag=wx.EXPAND)

        return aio_panel_sizer

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
    frame = AIOFrame(mx_database, ['ai_0', 'ao_0'],
        (2,1), parent=None, title='Test AIO Control')
    frame.Show()
    app.MainLoop()
