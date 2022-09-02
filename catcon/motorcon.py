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
from builtins import object, range, map, str
from io import open

import os

import wx
import wx.lib.buttons as buttons
import epics, epics.wx
from epics.wx.wxlib import EpicsFunction

import scancon
import custom_widgets
import custom_epics_widgets
import utils
utils.set_mppath() #This must be done before importing any Mp Modules.
import Mp as mp
import MpCa as mpca
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
        self.mtr_type = self.motor.get_field('mx_type')
        self.scale = float(self.motor.get_field('scale'))
        self.offset = float(self.motor.get_field('offset'))

        self._enabled = True
        self.scan_frame = None

        # if platform.system() == 'Darwin':
        #     font = self.GetFont()
        # else:
        #     font = wx.Font(10, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_NORMAL)
        # # self.SetFont(font)
        font = self.GetFont()
        self.vert_size = font.GetPixelSize()[1]+5

        self.is_epics = False
        self.is_slit_mtr = False

        self.epics_motor = None

        if self.mtr_type == 'epics_motor':
            self.is_epics = True

            self.epics_pv_name = self.motor.get_field('epics_record_name')

            self.epics_motor = epics.Motor(self.epics_pv_name)

            self.pos_pv = self.epics_motor.PV('RBV')

            # self.limit_pv = mpca.PV("{}.LVIO".format(self.epics_pv_name))
            # self.callback = self.limit_pv.add_callback(mpca.DBE_VALUE,
            #     custom_widgets.on_epics_limit, (self.limit_pv, self))
            # self.limit_pv = self.epics_motor.PV('LVIO')

            if self.scale > 0:
                nlimit = "LLM"
                plimit = "HLM"
            else:
                nlimit = "HLM"
                plimit = "LLM"

            self.nlimit_pv = self.epics_motor.PV(nlimit)
            self.plimit_pv = self.epics_motor.PV(plimit)

            self.set_pv = self.epics_motor.PV('SET')

            self.pos_pv.get()
            # self.limit_pv.get()
            self.nlimit_pv.get()
            self.plimit_pv.get()
            self.set_pv.get()

            self.epics_motor.add_callback('LVIO', self._on_epics_soft_limit)
            self.epics_motor.add_callback('HLS', self._on_epics_hard_limit)
            self.epics_motor.add_callback('LLS', self._on_epics_hard_limit)
            self.epics_motor.add_callback('SPMG', self._on_epics_disable)

        if self.mtr_type == 'network_motor':
            self.server_record_name = self.motor.get_field('server_record')
            self.remote_record_name = self.motor.get_field('remote_record_name')
            self.server_record = self.mx_database.get_record(self.server_record_name)

            self.remote_offset = mp.Net(self.server_record, '{}.offset'.format(self.remote_record_name))
            self.remote_scale = mp.Net(self.server_record, '{}.scale'.format(self.remote_record_name))

            remote_type_name = '{}.mx_type'.format(self.remote_record_name)
            remote_type = mp.Net(self.server_record, remote_type_name)

            slit_names = ['jjc_v', 'jjc_h', 'jj1v', 'jj1h', 'xenocsv',
                'xenocsh', 'xenocs_colv', 'xenocs_colh', 'wbv', 'wbh']

            r_type = remote_type.get()
            print(r_type)
            try:
                str(r_type)
            except Exception:
                r_type = ''

            #if r_type == 'slit_motor':
            #    self.is_slit_mtr = True

            for name in slit_names:
                if self.remote_record_name.startswith(name):
                    self.is_slit_mtr =  True
                    break

        top_sizer = self._create_layout()

        self.SetSizer(top_sizer)

    def _create_layout(self):
        """
        Creates the layout for the panel.

        :returns: wx Sizer for the panel.
        :rtype: wx.Sizer
        """
        if self.mtr_type == 'network_motor':
            pos_name = "{}.position".format(self.remote_record_name)
            pos = mpwx.Value(self, self.server_record, pos_name,
                function=custom_widgets.network_value_callback, args=(self.scale, self.offset))
            # # setting limits this way currently doesn't work. So making it a static text, not a text entry
            # self.low_limit = wx.StaticText(self, label=self.motor.get_field('negative_limit'))
            # self.high_limit = wx.StaticText(self, label=self.motor.get_field('positive_limit'))
            #
            if self.scale*self.remote_scale.get() > 0:
                nlimit = "{}.raw_negative_limit".format(self.remote_record_name)
                plimit = "{}.raw_positive_limit".format(self.remote_record_name)
            else:
                nlimit = "{}.raw_positive_limit".format(self.remote_record_name)
                plimit = "{}.raw_negative_limit".format(self.remote_record_name)

            self.low_limit = custom_widgets.CustomLimitValueEntry(self,
                self.server_record, nlimit,
                function=custom_widgets.limit_network_value_callback,
                args=(self.scale, self.offset, self.remote_scale.get(),
                    self.remote_offset.get()),
                validator=utils.CharValidator('float_neg')
                )

            self.high_limit = custom_widgets.CustomLimitValueEntry(self,
                self.server_record, plimit,
                function=custom_widgets.limit_network_value_callback,
                args=(self.scale, self.offset, self.remote_scale.get(),
                    self.remote_offset.get()),
                validator=utils.CharValidator('float_neg')
                )

            mname = wx.StaticText(self, label=self.motor.name)

        elif self.is_epics:
            # pv = self.motor.get_field('epics_record_name')
            # self.sever_record = None #Needed to get around some MP bugs
            # pos = custom_widgets.CustomEpicsValue(self, "{}.RBV".format(pv),
            #     custom_widgets.epics_value_callback, self.scale, self.offset)

            # if self.scale > 0:
            #     nlimit = "{}.LLM".format(pv)
            #     plimit = "{}.HLM".format(pv)
            # else:
            #     nlimit = "{}.HLM".format(pv)
            #     plimit = "{}.LLM".format(pv)

            # self.low_limit = custom_widgets.CustomEpicsValueEntry(self, nlimit,
            #     custom_widgets.epics_value_callback, self.scale, self.offset, size=(-1,self.vert_size))
            # self.high_limit = custom_widgets.CustomEpicsValueEntry(self, plimit,
            #     custom_widgets.epics_value_callback, self.scale, self.offset, size=(-1,self.vert_size))

            pos = custom_epics_widgets.PVTextLabeled(self, self.pos_pv, scale=self.scale,
                offset=self.offset)
            self.low_limit = custom_epics_widgets.PVTextCtrl2(self, self.nlimit_pv,
                dirty_timeout=None, scale=self.scale, offset=self.offset,
                validator=utils.CharValidator('float_neg'))
            self.high_limit = custom_epics_widgets.PVTextCtrl2(self, self.plimit_pv,
                dirty_timeout=None, scale=self.scale, offset=self.offset,
                validator=utils.CharValidator('float_neg'))

            mname = wx.StaticText(self, label='{} ({})'.format(self.motor.name,
                self.epics_pv_name))


        status_grid = wx.GridBagSizer(vgap=5, hgap=5)
        status_grid.Add(wx.StaticText(self, label='Motor name:'), (0,0))
        status_grid.Add(mname, (0,1), flag=wx.EXPAND)
        status_grid.AddGrowableCol(1)

        status_sizer = wx.StaticBoxSizer(wx.StaticBox(self, label='Info'),
            wx.VERTICAL)
        status_sizer.Add(status_grid, 1, flag=wx.EXPAND)

        self.pos_ctrl = wx.TextCtrl(self, value='', size=(50,self.vert_size),
            validator=utils.CharValidator('float_neg'))
        self.mrel_ctrl = wx.TextCtrl(self, value='1.0', size=(50,self.vert_size),
            validator=utils.CharValidator('float_neg'))

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

        # scan_btn = buttons.ThemedGenButton(self, label='Scan', size=(-1, self.vert_size), style=wx.BU_EXACTFIT)
        # scan_btn.Bind(wx.EVT_BUTTON, self._on_scan)

        if self.is_epics:
            more_btn = buttons.ThemedGenButton(self, label='More', size=(-1,self.vert_size), style=wx.BU_EXACTFIT)
            more_btn.Bind(wx.EVT_BUTTON, self._on_more)

        pos_sizer = wx.FlexGridSizer(vgap=2, hgap=2, cols=5, rows=2)
        pos_sizer.Add(wx.StaticText(self, label='Low lim.'), flag=wx.ALIGN_CENTER_VERTICAL)
        pos_sizer.Add((1,1))
        pos_sizer.Add(wx.StaticText(self, label='Pos. ({})'.format(self.motor.get_field('units'))),
            flag=wx.ALIGN_CENTER_VERTICAL)
        pos_sizer.Add((1,1))
        pos_sizer.Add(wx.StaticText(self, label='High lim.'), flag=wx.ALIGN_CENTER_VERTICAL)
        pos_sizer.Add(self.low_limit, flag=wx.ALIGN_CENTER_VERTICAL)
        pos_sizer.Add((1,1))
        pos_sizer.Add(pos, flag=wx.ALIGN_CENTER_VERTICAL)
        pos_sizer.Add((1,1))
        pos_sizer.Add(self.high_limit, flag=wx.ALIGN_CENTER_VERTICAL)
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

        ctrl_btn_sizer = wx.BoxSizer(wx.HORIZONTAL)
        # ctrl_btn_sizer.Add(scan_btn, flag=wx.ALIGN_LEFT)
        if self.is_epics:
            ctrl_btn_sizer.Add(more_btn, flag=wx.ALIGN_LEFT)
        ctrl_btn_sizer.AddStretchSpacer(1)
        ctrl_btn_sizer.Add(stop_btn, border=5, flag=wx.LEFT|wx.ALIGN_RIGHT)


        control_sizer = wx.StaticBoxSizer(wx.StaticBox(self, label='Controls'),
            wx.VERTICAL)
        control_sizer.Add(pos_sizer, border=2, flag=wx.EXPAND|wx.BOTTOM)
        control_sizer.Add(mabs_sizer, border=2, flag=wx.EXPAND|wx.BOTTOM)
        control_sizer.Add(mrel_sizer, border=2, flag=wx.EXPAND|wx.BOTTOM|wx.TOP)
        control_sizer.Add(wx.StaticLine(self), border=10, flag=wx.EXPAND|wx.LEFT|wx.RIGHT)
        control_sizer.Add(ctrl_btn_sizer, border=2, flag=wx.TOP|wx.EXPAND)

        top_sizer = wx.BoxSizer(wx.VERTICAL)
        top_sizer.Add(status_sizer, flag=wx.EXPAND)
        top_sizer.Add(control_sizer, border=2, flag=wx.EXPAND|wx.TOP)

        self.Bind(wx.EVT_RIGHT_DOWN, self._on_rightclick)
        for item in self.GetChildren():
            if ((isinstance(item, wx.StaticText) or isinstance(item, mpwx.Value)
                or isinstance(item, custom_widgets.CustomEpicsValue) 
                or isinstance(item, wx.StaticBox))
                and not (isinstance(item, custom_epics_widgets.PVTextLabeled) 
                or isinstance(item, custom_epics_widgets.PVTextCtrl2))
                ):
                item.Bind(wx.EVT_RIGHT_DOWN, self._on_rightclick)

        return top_sizer

    def _on_moveto(self, evt):
        """
        Called when the user requests an absolute move by pressing the
        "Move to" button.
        """
        pval = self.pos_ctrl.GetValue()

        if self._is_num(pval):
            pval = float(pval)

            if self.is_epics:
                wx.CallAfter(self._move_epics_position, pval)

            else:
                try:
                    self.motor.move_absolute(pval)
                except mp.Would_Exceed_Limit_Error as e:
                    msg = str(e)
                    msg1, msg2 = msg.split('to')
                    pos, msg2 = msg2.split('would')
                    msg2 = msg2.split('limit')[0]

                    pos = float(pos.strip())
                    pos = pos*self.remote_scale.get() + self.remote_offset.get()
                    pos = pos*self.scale + self.offset

                    msg = msg1 + ' {} '.format(pos) + msg2 + 'limit.'
                    wx.MessageBox(msg, 'Error moving motor')
        else:
            msg = 'Position has to be numeric.'
            wx.CallAfter(wx.MessageBox, msg, 'Error moving motor')

    @EpicsFunction
    def _move_epics_position(self, pval):
        pval = (float(pval) - self.offset)*self.scale
        self.epics_motor.put('SET', 0, wait=True)
        self.epics_motor.move(pval)

    def _on_setto(self, evt):
        """
        Called when the user requests to set the motor position by pressing the
        "Set to" button.
        """
        pval = self.pos_ctrl.GetValue()

        if self._is_num(pval):
            pval = float(pval)
        else:
            msg = 'Position has to be numeric.'
            wx.MessageBox(msg, 'Error setting position')
            return

        if self.is_epics:
            wx.CallAfter(self._set_epics_position, pval)

        else:
            current_pos = float(self.motor.get_position())

            if self.is_slit_mtr:
                remote_offset = float(self.remote_offset.get())

                remote_current_pos = (current_pos-self.offset)/self.scale
                remote_target_pos = (pval-self.offset)/self.scale

                delta =  remote_target_pos - remote_current_pos
                new_remote_offset = remote_offset + delta

                self.remote_offset.put(new_remote_offset)

            else:
                self.motor.set_position(pval)

            if self.mtr_type == 'network_motor':
                pos_change = pval - current_pos

                low_lim = float(self.low_limit.GetValue())
                new_low_lim = low_lim + pos_change

                high_lim = float(self.high_limit.GetValue())
                new_high_lim = high_lim + pos_change

                self.low_limit.SetValue(str(new_low_lim))
                self.high_limit.SetValue(str(new_high_lim))

                self.low_limit.OnEnter(None)
                self.high_limit.OnEnter(None)

        return

    @EpicsFunction
    def _set_epics_position(self, pval):
        pval = (float(pval) - self.offset)*self.scale
        self.epics_motor.set_position(pval)

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

            if self.is_epics:
                wx.CallAfter(self._tweak_epics_position, pval, mult)

            else:
                pval = mult*float(pval)

                try:
                    self.motor.move_relative(pval)
                except mp.Would_Exceed_Limit_Error as e:
                    msg = str(e)
                    msg1, msg2 = msg.split('to')
                    pos, msg2 = msg2.split('would')
                    msg2 = msg2.split('limit')[0]

                    pos = float(pos.strip())
                    pos = pos*self.remote_scale.get() + self.remote_offset.get()
                    pos = pos*self.scale + self.offset

                    if 'negative' in msg:
                        limit_val = self.low_limit.GetValue()
                    else:
                        limit_val = self.high_limit.GetValue()
                    msg = msg1 + ' {} '.format(pos) + msg2 + 'limit of {}.'.format(limit_val)
                    wx.MessageBox(msg, 'Error moving motor')
        else:
            msg = 'Step size has to be numeric.'
            wx.MessageBox(msg, 'Error moving motor')

    @EpicsFunction
    def _tweak_epics_position(self, pval, mult):
        pval = float(pval)/self.scale

        self.epics_motor.tweak_val = pval

        if mult > 0:
            self.epics_motor.tweak()
        else:
            self.epics_motor.tweak('rev')

    def _on_stop(self, evt):
        """
        Called when the user clicks the "Stop" button. Does a soft abort"""

        if self.is_epics:
            wx.CallAfter(self._stop_epics_motor)
        else:
            self.motor.soft_abort()

    @EpicsFunction
    def _stop_epics_motor(self):
        self.epics_motor.stop()

    def _on_epics_soft_limit(self, value, **kwargs):
        if value == 1:
            msg = str("Software limit hit for motor '{}'".format(self.motor_name))
            wx.CallAfter(wx.MessageBox, msg, 'Error moving motor')

    def _on_epics_hard_limit(self, value, **kwargs):
        if value != 0:
            if 'HLS' in kwargs['pvname']:
                msg = str("Hardware high limit hit for motor '{}'".format(self.motor_name))
            else:
                msg = str("Hardware low limit hit for motor '{}'".format(self.motor_name))

            wx.CallAfter(wx.MessageBox, msg, 'Error moving motor')

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
            if (not isinstance(item, wx.StaticText) and not isinstance(item, mpwx.Value)
                and not isinstance(item, custom_widgets.CustomEpicsValue) and not
                isinstance(item, wx.StaticBox)):
                item.Enable(self._enabled)

        if self.is_epics:
            wx.CallAfter(self._epics_enablechange)

    @EpicsFunction
    def _epics_enablechange(self):
        if self._enabled:
            self.epics_motor.stop_go = 3
        else:
            self.epics_motor.stop_go = 0

    def _on_epics_disable(self, value, **kwargs):
        if value == 0:
            self._enabled = True
            self._on_enablechange(None)

        elif value == 3:
            self._enabled = False
            self._on_enablechange(None)

    def _on_scan(self, evt):
        """
        .. todo::
            Due to the problesm with MP, you can't open a scan window for the same
            control twice. Ideally this would check whether a window was open,
            if so it would highlight it/bring it to the current window. If not it
            would open/reopen one.

        Called when the user requests a scan. Opens a scan window.
        """
        # if self.scan_frame is not None:
        #     try:
        #         self.scan_frame.Close()
        #     except Exception as e:
        #         print(e)
        #     self.scan_frame = scancon.ScanFrame(self.motor_name, self.motor,
        #         self.server_record, self.mx_database, parent=None,
        #         title='{} Scan Control'.format(self.motor_name))
        #     self.scan_frame.Show()
        # else:
        #     self.scan_frame = scancon.ScanFrame(self.motor_name, self.motor,
        #         self.server_record, self.mx_database, parent=None,
        #         title='{} Scan Control'.format(self.motor_name))
        #     self.scan_frame.Show()

        frame = scancon.ScanFrame(self.motor_name, self.motor, self.server_record,
            self.mx_database, parent=None, title='{} Scan Control'.format(self.motor_name))
        frame.Show()

    def _on_more(self, evt):
        if self.epics_motor is not None:
            wx.CallAfter(epics.wx.motordetailframe.MotorDetailFrame, parent=self, motor=self.epics_motor)



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
    mx_database.set_program_name("motorcon")

    app = wx.App()
    frame = MotorFrame(mx_database, ['mtr1','mtr2','mtr3','mtr4'],
        (2,2), parent=None, title='Test Motor Control')
    frame.Show()
    app.MainLoop()
