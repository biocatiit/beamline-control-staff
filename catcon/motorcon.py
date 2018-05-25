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

import os

import wx

import utils
utils.set_mppath() #This must be done before importing any Mp Modules.
import Mp as mp
import MpWx as mpwx


class MotorPanel(wx.Panel):
    """
    .. todo::
        Eventually this should allow viewing (and setting?) of the motor
        settings, ideally through a generic GUI that works for various
        types of devices, not just motors.

    This motor panel supports standard motor controls, such as moving to a fixed
    position, redefining the current position value, and relative moves.
    It is mean to be embedded in a larger application, and can be instanced
    several times, once for each motor. It communicates with the motors by
    calling ``Mp``, the python wrapper for ``MX``.
    """
    def __init__(self, motor_name, mx_database, parent, panel_id=wx.ID_ANY,
        panel_name=''):
        """
        Initializes the custom panel. Important parameters here are the
        ``motor_name``, and the ``mx_database``.

        :param str motor_name: The motor name in the Mx database.

        :param Mp.RecordList mx_database: The database instance from Mp.

        :param wx.Window parent: Parent class for the panel.

        :param int panel_id: wx ID for the panel.

        :param str panel_name: Name for the panel.
        """
        wx.Panel.__init__(self, parent, panel_id, name=panel_name)

        self.mx_database = mx_database
        self.motor_name = motor_name
        self.motor = self.mx_database.get_record(self.motor_name)
        server_record_name = self.motor.get_field("server_record")
        self.server_record = self.mx_database.get_record(server_record_name)
        self.remote_record_name = self.motor.get_field("remote_record_name")

        top_sizer = self._create_layout()

        self.SetSizer(top_sizer)

    def _create_layout(self):
        """
        Creates the layout for the panel.

        :returns: wx Sizer for the panel.
        :rtype: wx.Sizer
        """
        pos_name = "{}.position".format(self.remote_record_name)
        pos = mpwx.Value(self, self.server_record, pos_name)


        status_grid = wx.GridBagSizer(vgap=2, hgap=2)
        status_grid.Add(wx.StaticText(self, label='Motor name:'), (0,0))
        status_grid.Add(wx.StaticText(self, label=self.motor.name), (0,1), span=(1,2), flag=wx.EXPAND)
        status_grid.Add(wx.StaticText(self, label='Current position:'), (1,0))
        status_grid.Add(pos, (1,1), flag=wx.EXPAND)
        status_grid.Add(wx.StaticText(self, label=self.motor.get_field('units')), (1,2))
        status_grid.AddGrowableCol(1)

        status_sizer = wx.StaticBoxSizer(wx.StaticBox(self, label='Info'),
            wx.VERTICAL)
        status_sizer.Add(status_grid, 1, flag=wx.EXPAND)

        self.pos_ctrl = wx.TextCtrl(self, value='')
        self.mrel_ctrl = wx.TextCtrl(self, value='1.0')

        move_btn = wx.Button(self, label='Move to')
        move_btn.Bind(wx.EVT_BUTTON, self._on_moveto)
        set_btn = wx.Button(self, label='Set to')
        set_btn.Bind(wx.EVT_BUTTON, self._on_setto)

        tp_btn = wx.Button(self, label='Step +')
        tm_btn = wx.Button(self, label='Step -')
        tp_btn.Bind(wx.EVT_BUTTON, self._on_mrel)
        tm_btn.Bind(wx.EVT_BUTTON, self._on_mrel)

        stop_btn = wx.Button(self, label='Stop')
        stop_btn.Bind(wx.EVT_BUTTON, self._on_stop)

        control_grid = wx.GridBagSizer(vgap=2,hgap=2)
        control_grid.Add(wx.StaticText(self, label='Position ({}):'.format(self.motor.get_field('units'))),
            (0,0))
        control_grid.Add(self.pos_ctrl, (0,1), flag=wx.EXPAND)
        control_grid.Add(move_btn, (1,0),flag=wx.ALIGN_RIGHT)
        control_grid.Add(set_btn, (1,1), flag=wx.ALIGN_LEFT)
        control_grid.Add(wx.StaticLine(self), (2,0), span=(1,2), border=10,
            flag=wx.EXPAND|wx.ALIGN_CENTER_HORIZONTAL)
        control_grid.Add(wx.StaticText(self, label='Relative step ({}):'.format(self.motor.get_field('units'))),
            (3,0))
        control_grid.Add(self.mrel_ctrl, (3,1), flag=wx.EXPAND)
        control_grid.Add(tm_btn, (4,0), flag=wx.ALIGN_RIGHT)
        control_grid.Add(tp_btn, (4,1), flag=wx.ALIGN_LEFT)

        control_sizer = wx.StaticBoxSizer(wx.StaticBox(self, label='Controls'),
            wx.VERTICAL)
        control_sizer.Add(control_grid, 1, flag=wx.EXPAND)
        control_grid.Add(wx.StaticLine(self), (5,0), span=(1,2), border=10,
            flag=wx.EXPAND|wx.ALIGN_CENTER_HORIZONTAL)
        control_grid.Add(stop_btn, (6,0), span=(1,2), flag=wx.ALIGN_CENTER_HORIZONTAL)


        top_sizer = wx.BoxSizer(wx.VERTICAL)
        top_sizer.Add(status_sizer, flag=wx.EXPAND)
        top_sizer.Add(control_sizer, flag=wx.EXPAND)

        return top_sizer

    def _on_moveto(self, evt):
        """
        Called when the user requests an absolute move by pressing the
        "Move to" button.
        """
        pval = self.pos_ctrl.GetValue()

        if self._is_num(pval):
            self.motor.move_absolute(float(pval))
        else:
            msg = 'Position has to be numeric.'
            wx.MessageBox(msg, 'Error moving motor')

    def _on_setto(self, evt):
        """
        Called when the user requests to set the motor position by pressing the
        "Set to" button.
        """
        pval = self.pos_ctrl.GetValue()

        if self._is_num(pval):
            self.motor.set_position(float(pval))
        else:
            msg = 'Position has to be numeric.'
            wx.MessageBox(msg, 'Error setting position')

    def _on_mrel(self, evt):
        """
        Called when the user requests a relative move by pressing the
        "Step +" or "Step -" button.
        """
        pval = self.mrel_ctrl.GetValue()

        if self._is_num(pval):
            btn = evt.GetEventObject().GetLabel()

            if btn == 'Step +':
                mult = 1
            else:
                mult = -1
            self.motor.move_relative(mult*float(pval))

        else:
            msg = 'Step size has to be numeric.'
            wx.MessageBox(msg, 'Error moving motor')

    def _on_stop(self, evt):
        """
        Called when the user clicks the "Stop" button. Does a soft abort"""
        self.motor.soft_abort()

    def _is_num(self, val):
        """
        Convenience function to check where motor move/set values are numbers.

        :param val: Parameter to check whether or not it is a number.

        :returns: ``True`` if val is a number. ``False`` otherwise.
        :rtype: bool
        """
        try:
            float(val)
            return True
        except ValueError:
            return False

class MotorFrame(wx.Frame):
    """
    A lightweight motor frame designed to hold an arbitrary number of motors
    in an arbitrary grid pattern.
    """
    def __init__(self, mx_database, motors, shape, timer=True, *args, **kwargs):
        """
        Initializes the motor frame. This frame is designed to function either as
        a stand alone application, or as part of a larger application.

        :param Mp.RecordList mx_database: The Mp database containing the motor records.

        :param list motors: The motor names in the Mp database.

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

        top_sizer = self._create_layout(motors, shape)

        self.SetSizer(top_sizer)
        self.Fit()
        self.Raise()

        if timer:
            self.mx_timer.Start(100)

    def _create_layout(self, motors, shape):
        """
        Creates the layout.

        :param list motors: The motor names in the Mp database.

        :param tuple shape: A tuple containing the shape of the motor grid.
            It is given as: (rows, cols). Note that rows*cols should be equal
            to or greater than the number of motors, but the MotorFrame doesn't
            check this. If it isn't, it will just fail to propely display the last
            few motors.
        """
        motor_grid = wx.FlexGridSizer(rows=shape[0], cols=shape[1], vgap=2,
            hgap=2)

        for i in range(shape[1]):
            motor_grid.AddGrowableCol(i)

        for motor in motors:
            motor_panel = MotorPanel(motor, self.mx_database, self)
            mtr_box_sizer = wx.StaticBoxSizer(wx.StaticBox(self, label='{} Controls'.format(motor)))
            mtr_box_sizer.Add(motor_panel)
            motor_grid.Add(mtr_box_sizer)

        motor_panel_sizer = wx.BoxSizer(wx.HORIZONTAL)
        motor_panel_sizer.Add(motor_grid)

        return motor_panel_sizer

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
    frame = MotorFrame(mx_database, ['mtr1', 'mtr2', 'mtr3', 'mtr4'],
        (2,2), parent=None, title='Test Motor Control')
    frame.Show()
    app.MainLoop()