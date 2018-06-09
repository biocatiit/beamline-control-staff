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
import wx.lib.buttons as buttons

import utils
utils.set_mppath() #This must be done before importing any Mp Modules.
import Mp as mp
import MpCa as mpca
import MpWx as mpwx
import MpWxCa as mpwxca


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
        self.mtr_type = self.motor.get_field('mx_type')
        self.scale = float(self.motor.get_field('scale'))
        self.offset = float(self.motor.get_field('offset'))

        self._enabled = True

        # if platform.system() == 'Darwin':
        #     font = self.GetFont()
        # else:
        #     font = wx.Font(10, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_NORMAL)
        # # self.SetFont(font)
        font = self.GetFont()
        self.vert_size = font.GetPixelSize()[1]+5
        

        top_sizer = self._create_layout()

        if self.mtr_type == 'epics_motor':
            pv = self.motor.get_field('epics_record_name')
            self.limit_pv = mpca.PV("{}.LVIO".format(pv))
            self.callback = self.limit_pv.add_callback(mpca.DBE_VALUE, self._on_epics_limit, (self.limit_pv, self))

        self.SetSizer(top_sizer)

    def _create_layout(self):
        """
        Creates the layout for the panel.

        :returns: wx Sizer for the panel.
        :rtype: wx.Sizer
        """

        if self.mtr_type == 'network_motor':
            server_record_name = self.motor.get_field("server_record")
            server_record = self.mx_database.get_record(server_record_name)
            remote_record_name = self.motor.get_field("remote_record_name")

            pos_name = "{}.position".format(remote_record_name)
            pos = mpwx.Value(self, server_record, pos_name,
                function=self._network_value_callback, args=(self.scale, self.offset))
            # setting limits this way currently doesn't work. So making it a static text, not a text entry
            low_limit = wx.StaticText(self, label=self.motor.get_field('negative_limit'))
            high_limit = wx.StaticText(self, label=self.motor.get_field('positive_limit'))
            # local_server_record = self.mx_database.get_record('localhost')
            # low_limit = mpwx.ValueEntry(self, local_server_record, "{}.negative_limit".format(self.motor_name))
            # high_limit = mpwx.ValueEntry(self, local_server_record, "{}.positive_limit".format(self.motor_name))
            mname = wx.StaticText(self, label=self.motor.name)

        elif self.mtr_type == 'epics_motor':
            pv = self.motor.get_field('epics_record_name')

            pos = CustomEpicsValue(self, "{}.RBV".format(pv),
                self._epics_value_callback, self.scale, self.offset)
            low_limit = CustomEpicsValueEntry(self, "{}.LLM".format(pv),
                self._epics_value_callback, self.scale, self.offset, size=(-1,self.vert_size))
            high_limit = CustomEpicsValueEntry(self, "{}.HLM".format(pv),
                self._epics_value_callback, self.scale, self.offset, size=(-1,self.vert_size))
            mname = wx.StaticText(self, label='{} ({})'.format(self.motor.name, pv))


        status_grid = wx.GridBagSizer(vgap=5, hgap=5)
        status_grid.Add(wx.StaticText(self, label='Motor name:'), (0,0))
        status_grid.Add(mname, (0,1), flag=wx.EXPAND)
        status_grid.AddGrowableCol(1)

        status_sizer = wx.StaticBoxSizer(wx.StaticBox(self, label='Info'),
            wx.VERTICAL)
        status_sizer.Add(status_grid, 1, flag=wx.EXPAND)

        self.pos_ctrl = wx.TextCtrl(self, value='', size=(50,self.vert_size))
        self.mrel_ctrl = wx.TextCtrl(self, value='1.0', size=(50,self.vert_size))

        # move_btn = wx.Button(self, label='Move', size=(50, self.vert_size), style=wx.BU_EXACTFIT)
        move_btn = buttons.ThemedGenButton(self, label='Move', size=(-1, self.vert_size), style=wx.BU_EXACTFIT)
        move_btn.Bind(wx.EVT_BUTTON, self._on_moveto)
        set_btn = buttons.ThemedGenButton(self, label='Set', size=(-1, self.vert_size), style=wx.BU_EXACTFIT)
        set_btn.Bind(wx.EVT_BUTTON, self._on_setto)

        tp_btn = buttons.ThemedGenButton(self, label='+ >', size=(-1, self.vert_size),
            style=wx.BU_EXACTFIT, name='rel_move_plus')
        tm_btn = buttons.ThemedGenButton(self, label='< -', size=(-1, self.vert_size),
            style=wx.BU_EXACTFIT, name='rel_move_minus')
        tp_btn.Bind(wx.EVT_BUTTON, self._on_mrel)
        tm_btn.Bind(wx.EVT_BUTTON, self._on_mrel)

        stop_btn = buttons.ThemedGenButton(self, label='Abort', size=(-1,self.vert_size), style=wx.BU_EXACTFIT)
        stop_btn.Bind(wx.EVT_BUTTON, self._on_stop)

        pos_sizer = wx.FlexGridSizer(vgap=2, hgap=2, cols=5, rows=2)
        pos_sizer.Add(wx.StaticText(self, label='Low lim.'), flag=wx.ALIGN_CENTER_VERTICAL)
        pos_sizer.Add((1,1))
        pos_sizer.Add(wx.StaticText(self, label='Pos. ({})'.format(self.motor.get_field('units'))),
            flag=wx.ALIGN_CENTER_VERTICAL)
        pos_sizer.Add((1,1))
        pos_sizer.Add(wx.StaticText(self, label='High lim.'), flag=wx.ALIGN_CENTER_VERTICAL)
        pos_sizer.Add(low_limit, flag=wx.ALIGN_CENTER_VERTICAL)
        pos_sizer.Add((1,1))
        pos_sizer.Add(pos, flag=wx.ALIGN_CENTER_VERTICAL)
        pos_sizer.Add((1,1))
        pos_sizer.Add(high_limit, flag=wx.ALIGN_CENTER_VERTICAL)
        pos_sizer.AddGrowableCol(1)
        pos_sizer.AddGrowableCol(3)

        mabs_sizer = wx.BoxSizer(wx.HORIZONTAL)
        mabs_sizer.Add(wx.StaticText(self, label='Position:'),
            flag=wx.ALIGN_CENTER_VERTICAL)
        mabs_sizer.Add(self.pos_ctrl, 1, border=2, flag=wx.LEFT|wx.ALIGN_CENTER_VERTICAL)
        mabs_sizer.Add(move_btn, border=2, flag=wx.LEFT|wx.ALIGN_CENTER_VERTICAL)
        mabs_sizer.Add(set_btn, border=2, flag=wx.LEFT|wx.ALIGN_CENTER_VERTICAL)

        mrel_sizer = wx.BoxSizer(wx.HORIZONTAL)
        mrel_sizer.Add(wx.StaticText(self, label='Rel. Move:'),
            flag=wx.ALIGN_CENTER_VERTICAL)
        mrel_sizer.Add(tm_btn, border=2, flag=wx.LEFT|wx.ALIGN_CENTER_VERTICAL)
        mrel_sizer.Add(self.mrel_ctrl, 1, border=2, flag=wx.LEFT|wx.ALIGN_CENTER_VERTICAL)
        mrel_sizer.Add(tp_btn, border=2, flag=wx.LEFT|wx.ALIGN_CENTER_VERTICAL)


        control_sizer = wx.StaticBoxSizer(wx.StaticBox(self, label='Controls'),
            wx.VERTICAL)
        control_sizer.Add(pos_sizer, border=2, flag=wx.EXPAND|wx.BOTTOM)
        control_sizer.Add(mabs_sizer, border=2, flag=wx.EXPAND|wx.BOTTOM)
        control_sizer.Add(mrel_sizer, border=2, flag=wx.EXPAND|wx.BOTTOM|wx.TOP)
        control_sizer.Add(wx.StaticLine(self), border=10, flag=wx.EXPAND|wx.LEFT|wx.RIGHT)
        control_sizer.Add(stop_btn, border=2, flag=wx.TOP|wx.ALIGN_CENTER_HORIZONTAL)

        top_sizer = wx.BoxSizer(wx.VERTICAL)
        top_sizer.Add(status_sizer, flag=wx.EXPAND)
        top_sizer.Add(control_sizer, border=2, flag=wx.EXPAND|wx.TOP)

        self.Bind(wx.EVT_RIGHT_DOWN, self._on_rightclick)
        for item in self.GetChildren():
            if (isinstance(item, wx.StaticText) or isinstance(item, mpwx.Value)
                or isinstance(item, mpwxca.Value) or isinstance(item, wx.StaticBox)):
                item.Bind(wx.EVT_RIGHT_DOWN, self._on_rightclick)

        return top_sizer

    def _on_moveto(self, evt):
        """
        Called when the user requests an absolute move by pressing the
        "Move to" button.
        """
        pval = self.pos_ctrl.GetValue()

        if self._is_num(pval):
            try:
                self.motor.move_absolute(float(pval))
            except mp.Would_Exceed_Limit_Error as e:
                msg = str(e)
                wx.MessageBox(msg, 'Error moving motor')
        else:
            msg = 'Position has to be numeric.'
            wx.CallAfter(wx.MessageBox, msg, 'Error moving motor')

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
            btn = evt.GetEventObject().GetName()

            if btn == 'rel_move_plus':
                mult = 1
            else:
                mult = -1
            try:
                self.motor.move_relative(mult*float(pval))
            except mp.Would_Exceed_Limit_Error as e:
                msg = str(e)
                wx.MessageBox(msg, 'Error moving motor')
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

    @staticmethod
    def _on_epics_limit(callback, args):
        pv, widget = args
        value = pv.get_local()

        if value == 1:
            msg = str("Software limit hit for motor '{}'".format(widget.motor_name))
            wx.CallAfter(wx.MessageBox, msg, 'Error moving motor')

    def _on_rightclick(self, evt):
        menu = wx.Menu()
        menu.Bind(wx.EVT_MENU, self._on_enablechange)

        if self._enabled:
            menu.Append(1, 'Disable Control')
        else:
            menu.Append(1, 'Enable Control')

        self.PopupMenu(menu)
        menu.Destroy()

    def _on_enablechange(self, evt):
        if self._enabled:
            self._enabled = False
        else:
            self._enabled = True

        for item in self.GetChildren():
            if (not isinstance(item, wx.StaticText) and not isinstance(item, mpwx.Value)
                and not isinstance(item, mpwxca.Value) and not
                isinstance(item, wx.StaticBox)):
                item.Enable(self._enabled)

    @staticmethod
    def _network_value_callback(nf, widget, args, value):

        scale, offset = args

        if isinstance(value, list):
            if len(value) == 1:
                value = value[0]

        value = value*scale+offset

        if widget.base == 10:
            value = "%d" % value
        elif widget.base == 16 :
            value = "%#x" % value
        elif widget.base == 8 :
            value = "%#o" % value
        else:
            value = str(value)

        widget.SetLabel(value)
        widget.SetSize(widget.GetBestSize())
        widget.Refresh()

    @staticmethod
    def _epics_value_callback(callback, args):

        pv, widget, scale, offset = args

        value = pv.get_local()

        if isinstance(value, list):
            if len(value) == 1:
                value = value[0]

        value = value*scale+offset

        if isinstance(widget, CustomEpicsValue):
            if widget.base == 10:
                value = "%d" % value
            elif widget.base == 16:
                value = "%#x" % value
            elif widget.base == 8:
                value = "%#o" % value
            else:
                value = str(value)
        else:
            value = str(value)

        wx.PostEvent(widget, mpwxca.UpdateEvent(value))

class CustomEpicsValue(wx.StaticText):

    def __init__(self, parent, pv_name, function, scale, offset, id=-1,
        pos=wx.DefaultPosition, size=wx.DefaultSize, style=0,
        name=wx.StaticTextNameStr, base=None):

        wx.StaticText.__init__(self, parent, id=id, label="-----", pos=pos,
            size=size, style=style, name=name )

        if base != 10 and base != 16 and base != 8 and base != None:
            error_message = "Only base 8, 10, and 16 are supported."
            raise ValueError, error_message

        self.base = base
        self.pv = mpca.PV(pv_name)

        mpwxca.EVT_UPDATE(self, self.OnUpdate)

        args = (self.pv, self, scale, offset)

        self.callback = self.pv.add_callback( mpca.DBE_VALUE, function, args )

        try:
            self.pv.caget()
            function(self.callback, args)
        except mp.Not_Found_Error:
            self.SetValue("NOT FOUND")
            self.Enable(False)
            return

        mpca.poll()

        self.SetForegroundColour("blue")

    def OnUpdate(self, event):
        value = event.args

        self.SetLabel(value)
        self.SetSize(self.GetBestSize())

class CustomEpicsValueEntry(wx.TextCtrl):

    def __init__(self, parent, pv_name,function, scale, offset, id=-1, 
        pos=wx.DefaultPosition, size=wx.DefaultSize, style=0, 
        name=wx.TextCtrlNameStr, validator=wx.DefaultValidator):

        # Adding wx.TE_PROCESS_ENTER to the style causes the
        # widget to generate wx.EVT_TEXT_ENTER events when
        # the Enter key is pressed.

        style = style | wx.TE_PROCESS_ENTER

        wx.TextCtrl.__init__(self, parent, id=id, value=wx.EmptyString, 
            pos=pos, size=size, style=style, validator=validator)

        self.pv = mpca.PV(pv_name)
        self.scale = scale
        self.offset = offset

        mpwxca.EVT_UPDATE(self, self.OnUpdate)

        args = (self.pv, self, self.scale, self.offset)

        self.callback = self.pv.add_callback(mpca.DBE_VALUE, function, args)

        # Test for the existence of the PV.

        try:
            self.pv.caget()
        except mp.Not_Found_Error:
            self.SetValue("NOT FOUND")
            self.Enable(False)
            return

        # Disable the widget if the PV is read only.

        read_only = False

        if read_only:
            self.Enable(False)

        mpca.poll()

        self.Bind(wx.EVT_TEXT, self.OnText)

        self.Bind(wx.EVT_TEXT_ENTER, self.OnEnter)

    def OnText(self, event):
        self.SetBackgroundColour("yellow")

    def OnEnter(self, event):
        value = float(self.GetValue().strip())
        value = str((value-self.offset)/self.scale)
        self.pv.caput(value, wait=False)
        self.SetBackgroundColour(wx.NullColour)

    def OnUpdate(self, event):
        value = event.args
        self.SetValue(value)
        self.SetBackgroundColour(wx.NullColour)

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
