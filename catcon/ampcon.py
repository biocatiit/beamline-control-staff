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

import utils
utils.set_mppath() #This must be done before importing any Mp Modules.
import Mp as mp
import MpWx as mpwx

class AmpPanel(wx.Panel):
    """
    .. todo::
        Eventually this should allow viewing (and setting?) of the amp
        settings, ideally through a generic GUI that works for various
        types of devices, not just amps.

    This motor panel supports standard amplifier controls, such as setting the
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

        top_sizer = self._create_layout()

        self.SetSizer(top_sizer)

    def _create_layout(self):
        """
        Creates the layout for the panel.

        :returns: wx Sizer for the panel.
        :rtype: wx.Sizer
        """
        gain_name = "{}.gain".format(self.remote_record_name)
        gain = mpwx.Choice(self, self.server_record, gain_name,
            choices=['1e+04', '1e+05', '1e+06'], function=self._Choice_update)

        offset_name = "{}.offset".format(self.remote_record_name)
        offset = mpwx.ValueEntry(self, self.server_record, offset_name)

        timec_name = "{}.time_constant".format(self.remote_record_name)
        timec = mpwx.ValueEntry(self, self.server_record, timec_name)

        control_grid = wx.FlexGridSizer(rows=4, cols=2, vgap=2, hgap=2)
        control_grid.Add(wx.StaticText(self, label='Amplifier name:'))
        control_grid.Add(wx.StaticText(self, label=self.amp.get_field('name')),
            flag=wx.EXPAND)
        control_grid.Add(wx.StaticText(self, label='Gain:'))
        control_grid.Add(gain, flag=wx.EXPAND)
        control_grid.Add(wx.StaticText(self, label='Offset:'))
        control_grid.Add(offset, flag=wx.EXPAND)
        control_grid.Add(wx.StaticText(self, label='Time constant:'))
        control_grid.Add(timec, flag=wx.EXPAND)
        control_grid.AddGrowableCol(1)

        control_sizer = wx.BoxSizer(wx.VERTICAL)
        control_sizer.Add(control_grid, 1, flag=wx.EXPAND)

        top_sizer = wx.BoxSizer(wx.VERTICAL)
        top_sizer.Add(control_sizer, flag=wx.EXPAND)

        return top_sizer

    @staticmethod
    def _Choice_update( nf, widget, args, value ):
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


class AmpFrame(wx.Frame):
    """
    A lightweight amplifier frame designed to hold an arbitrary number of amps
    in an arbitrary grid pattern.
    """
    def __init__(self, mx_database, amps, shape, timer=True, *args, **kwargs):
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
            amp_panel = AmpPanel(amp, self.mx_database, self)
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

    app = wx.App()
    frame = AmpFrame(mx_database, ['keithley1', 'keithley2', 'keithley3', 'keithley4'],
        (2,2), parent=None, title='Test Amplifier Control')
    frame.Show()
    app.MainLoop()
