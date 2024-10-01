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
import subprocess
import pathlib

import wx
import epics, epics.wx

import utils

class EPICSLauncherPanel(wx.Panel):
    """
    """
    def __init__(self, *args, **kwargs):
        """
        """
        wx.Panel.__init__(self, *args, **kwargs)

        self._base_path = pathlib.Path(__file__).parent.resolve()
        self._epics_path = self._base_path  / '..' / 'epics_screens' / 'medm_start_scripts'
        self._epics_path = self._epics_path.resolve()

        print(self._base_path)
        print(self._epics_path)

        self._create_layout()

        self._initialize()

        self.SendSizeEvent()

    def on_close(self):
        pass

    def _create_layout(self):
        """
        Creates the layout for the panel.
        """
        parent = self
        labjack1_button = wx.Button(parent, label='LabJack 1')

        labjack1_button.Bind(wx.EVT_BUTTON, self._on_labjack1_button)

        top_sizer = wx.BoxSizer(wx.VERTICAL)
        top_sizer.Add(labjack1_button)

        self.SetSizer(top_sizer)

    def _initialize(self):
        pass

    def _on_labjack1_button(self, evt):
        script = self._epics_path / 'start_labjack_screen.sh'
        cmd = '{} 1'.format(script)
        process = subprocess.Popen(cmd, shell=True, cwd=self._epics_path)
        output, error = process.communicate()
        print(output)
        print(error)


class EPICSLauncherFrame(wx.Frame):
    """
    A lightweight amplifier frame designed to hold the EPICS launcher panel.
    """
    def __init__(self, *args, **kwargs):
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


        self._create_layout()

        self.Layout()
        self.Fit()
        self.Raise()

    def _create_layout(self):
        """
        Creates the layout.

        :param list dios: The amplifier names in the Mp database.

        :param tuple shape: A tuple containing the shape of the amp grid.
            It is given as: (rows, cols). Note that rows*cols should be equal
            to or greater than the number of dios, but the AmpFrame doesn't
            check this. If it isn't, it will just fail to propely display the last
            few dios.
        """
        top_sizer = wx.BoxSizer(wx.VERTICAL)

        epics_panel = EPICSLauncherPanel(self)

        top_sizer.Add(epics_panel, flag=wx.EXPAND, proportion=1)

        self.SetSizer(top_sizer)

if __name__ == '__main__':

    app = wx.App()
    frame = EPICSLauncherFrame(parent=None, title='Test EPICS Launcher')
    frame.Show()
    app.MainLoop()
