# coding: utf-8
#
#    Project: BioCAT user beamline control software (BioCON)
#             https://github.com/biocatiit/beamline-control-user
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
from builtins import object, range, map
from io import open

import threading
import time
from collections import deque, OrderedDict
import logging
import sys
import copy
import platform
import math

if __name__ != '__main__':
    logger = logging.getLogger(__name__)

import numpy as np
import wx
# import zaber.serial as zaber
try:
    import epics
    import epics.wx
    from epics.wx.wxlib import EpicsFunction
except Exception:
    pass
try:
    import motorcon
except Exception:
    pass

import utils
import custom_epics_widgets

class MonoTunePanel(wx.Panel):
    def __init__(self, name, mx_database, parent, panel_id=wx.ID_ANY,
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

        # Converts from biocon to catcon style settings, yes kind of stupid
        self.settings = default_mono_tune_settings
        self.settings['device_data'] = self.settings.pop('device_init')[0]

        self._callbacks = []

        self._init_pvs()

        self._create_layout()

        self._initialize()

    def _FromDIP(self, size):
        # This is a hack to provide easy back compatibility with wxpython < 4.1
        try:
            return self.FromDIP(size)
        except Exception:
            return size

    def _init_pvs(self):
        # Happens before create layout
        self.ao_pv, connected = self._initialize_pv('{}.VAL'.format(
            self.settings['device_data']['kwargs']['output']))
        self.ao_low_lim_pv, connected = self._initialize_pv('{}.LOPR'.format(
            self.settings['device_data']['kwargs']['output']))
        self.ao_high_lim_pv, connected = self._initialize_pv('{}.HOPR'.format(
            self.settings['device_data']['kwargs']['output']))

        self.i0_pv, connected = self._initialize_pv('{}.VAL'.format(
            self.settings['device_data']['kwargs']['i0']))
        self.i0_gain_mult_pv, connected = self._initialize_pv('{}.VAL'.format(
            self.settings['device_data']['kwargs']['i0_gain_mult']))
        self.i0_gain_unit_pv, connected = self._initialize_pv('{}.VAL'.format(
            self.settings['device_data']['kwargs']['i0_gain_unit']))
        self.c_hutch_x_pv, connected = self._initialize_pv('{}.VAL'.format(
            self.settings['device_data']['kwargs']['c_hutch_x_pos']))
        self.c_hutch_y_pv, connected = self._initialize_pv('{}.VAL'.format(
            self.settings['device_data']['kwargs']['c_hutch_y_pos']))
        self.c_hutch_int_pv, connected = self._initialize_pv('{}.VAL'.format(
            self.settings['device_data']['kwargs']['c_hutch_int']))

        self.fe_shutter_status_pv, connected = self._initialize_pv(self.settings['fe_shutter'])
        self.fe_shutter_open_pv, connected = self._initialize_pv(self.settings['fe_shutter_open'])
        self.fe_shutter_close_pv, connected = self._initialize_pv(self.settings['fe_shutter_close'])
        self.d_shutter_status_pv, connected = self._initialize_pv(self.settings['d_shutter'])
        self.d_shutter_open_pv, connected = self._initialize_pv(self.settings['d_shutter_open'])
        self.d_shutter_close_pv, connected = self._initialize_pv(self.settings['d_shutter_close'])
        self.exp_shutter_pv, connected = self._initialize_pv(self.settings['exp_slow_shtr1'])

    def _initialize_pv(self, pv_name):
        pv = epics.get_pv(pv_name)
        connected = pv.wait_for_connection(5)

        if not connected:
            logger.error('Failed to connect to EPICS PV %s on startup', pv_name)

        return pv, connected

    def _create_layout(self):
        """Creates the layout"""

        ctrl_sizer = self._create_ctrl_layout(self)
        readout_sizer = self._create_readout_layout(self)
        shutter_sizer = self._create_shutter_layout(self)

        top_sizer = wx.BoxSizer(wx.VERTICAL)
        top_sizer.Add(readout_sizer, flag=wx.ALL|wx.EXPAND, border=self._FromDIP(5))
        top_sizer.Add(ctrl_sizer, flag=wx.LEFT|wx.RIGHT|wx.BOTTOM|wx.EXPAND,
            border=self._FromDIP(5))
        top_sizer.Add(shutter_sizer, flag=wx.LEFT|wx.RIGHT|wx.BOTTOM|wx.EXPAND,
            border=self._FromDIP(5))


        self.SetSizer(top_sizer)

    def _create_readout_layout(self, parent):
        readout_box = wx.StaticBox(parent, label='Readout')
        parent = readout_box

        self.i0_rbv = epics.wx.PVText(parent, self.i0_pv)
        self.c_hutch_x_rbv = epics.wx.PVText(parent, self.c_hutch_x_pv)
        self.c_hutch_y_rbv = epics.wx.PVText(parent, self.c_hutch_y_pv)
        self.c_hutch_int_rbv = epics.wx.PVText(parent, self.c_hutch_int_pv)

        self.i0_gain = wx.StaticText(parent)

        sub_sizer = wx.FlexGridSizer(cols=2, hgap=self._FromDIP(5),
            vgap=self._FromDIP(5))
        sub_sizer.Add(wx.StaticText(parent, label='I0 [V]:'),
            flag=wx.ALIGN_CENTER_VERTICAL)
        sub_sizer.Add(self.i0_rbv,
            flag=wx.ALIGN_CENTER_VERTICAL|wx.EXPAND|wx.LEFT)
        sub_sizer.Add(wx.StaticText(parent, label='I0 gain:'),
            flag=wx.ALIGN_CENTER_VERTICAL)
        sub_sizer.Add(self.i0_gain,
            flag=wx.ALIGN_CENTER_VERTICAL|wx.EXPAND|wx.LEFT)
        sub_sizer.Add(wx.StaticText(parent, label='C BPM Intensity [nA]:'),
            flag=wx.ALIGN_CENTER_VERTICAL)
        sub_sizer.Add(self.c_hutch_int_rbv,
            flag=wx.ALIGN_CENTER_VERTICAL|wx.EXPAND|wx.LEFT)
        sub_sizer.Add(wx.StaticText(parent, label='C BPM X [Arb.]:'),
            flag=wx.ALIGN_CENTER_VERTICAL)
        sub_sizer.Add(self.c_hutch_x_rbv,
            flag=wx.ALIGN_CENTER_VERTICAL|wx.EXPAND|wx.LEFT)
        sub_sizer.Add(wx.StaticText(parent, label='C BPM X [Arb.]:'),
            flag=wx.ALIGN_CENTER_VERTICAL)
        sub_sizer.Add(self.c_hutch_y_rbv,
            flag=wx.ALIGN_CENTER_VERTICAL|wx.EXPAND|wx.LEFT)

        readout_sizer = wx.StaticBoxSizer(readout_box, wx.HORIZONTAL)
        readout_sizer.Add(sub_sizer, flag=wx.ALL, border=self._FromDIP(5))
        readout_sizer.AddStretchSpacer(1)

        return readout_sizer

    def _create_ctrl_layout(self, parent):
        ctrl_box = wx.StaticBox(parent, label='Control')
        parent = ctrl_box

        self.ao_float_ctrl = utils.FloatSpinCtrl(parent, TextLength=80)
        self.ao_float_ctrl.Bind(utils.EVT_MY_SPIN, self._on_ao_float_ctrl)

        self.ao_float_rbv = epics.wx.PVText(parent, self.ao_pv)

        self.ao_coarse_ctrl = utils.FloatSlider(parent, wx.ID_ANY, 0, 0, 1, 1e-4,
            style=wx.SL_HORIZONTAL|wx.SL_AUTOTICKS)
        self.ao_fine_ctrl = utils.FloatSlider(parent, wx.ID_ANY, 0, 0.0001, 0.9999, 1e-5,
            style=wx.SL_HORIZONTAL|wx.SL_AUTOTICKS)
        self.ao_superfine_ctrl = utils.FloatSlider(parent, wx.ID_ANY, 0, 0.00001, .09999, 1e-6,
            style=wx.SL_HORIZONTAL|wx.SL_AUTOTICKS)

        self.ao_coarse_ctrl.Bind(utils.EVT_MY_SCROLL, self._on_coarse_scroll)
        self.ao_fine_ctrl.Bind(utils.EVT_MY_SCROLL, self._on_fine_scroll)
        self.ao_superfine_ctrl.Bind(utils.EVT_MY_SCROLL, self._on_superfine_scroll)

        ao_low_lim = self.ao_low_lim_pv.get()
        ao_high_lim = self.ao_high_lim_pv.get()

        ao_float_sizer = wx.BoxSizer(wx.HORIZONTAL)
        ao_float_sizer.Add(wx.StaticText(parent, label='Voltage output [V]:'),
            flag=wx.ALIGN_CENTER_VERTICAL)
        ao_float_sizer.Add(self.ao_float_ctrl, flag=wx.ALIGN_CENTER_VERTICAL|wx.LEFT,
            border=self._FromDIP(5))
        ao_float_sizer.Add(self.ao_float_rbv, flag=wx.ALIGN_CENTER_VERTICAL|wx.LEFT,
            border=self._FromDIP(5))

        ao_sizer = wx.FlexGridSizer(cols=5, hgap=self._FromDIP(2), vgap=self._FromDIP(5))
        ao_sizer.Add(wx.StaticText(parent, label='Coarse adjust:'),
            flag=wx.ALIGN_CENTER_VERTICAL)
        ao_sizer.AddSpacer(self._FromDIP(5))
        ao_sizer.Add(wx.StaticText(parent, label=str(ao_low_lim)), flag=wx.ALIGN_CENTER_VERTICAL|wx.ALIGN_RIGHT)
        ao_sizer.Add(self.ao_coarse_ctrl, flag=wx.ALIGN_CENTER_VERTICAL|wx.EXPAND)
        ao_sizer.Add(wx.StaticText(parent, label=str(ao_high_lim)), flag=wx.ALIGN_CENTER_VERTICAL)
        ao_sizer.Add(wx.StaticText(parent, label='Fine adjust:'),
            flag=wx.ALIGN_CENTER_VERTICAL)
        ao_sizer.AddSpacer(self._FromDIP(5))
        ao_sizer.Add(wx.StaticText(parent, label='0.00'), flag=wx.ALIGN_CENTER_VERTICAL|wx.ALIGN_RIGHT)
        ao_sizer.Add(self.ao_fine_ctrl, flag=wx.ALIGN_CENTER_VERTICAL|wx.EXPAND)
        ao_sizer.Add(wx.StaticText(parent, label='1.00'), flag=wx.ALIGN_CENTER_VERTICAL)
        ao_sizer.Add(wx.StaticText(parent, label='Superfine adjust:'),
            flag=wx.ALIGN_CENTER_VERTICAL)
        ao_sizer.AddSpacer(self._FromDIP(5))
        ao_sizer.Add(wx.StaticText(parent, label='0.00'), flag=wx.ALIGN_CENTER_VERTICAL|wx.ALIGN_RIGHT)
        ao_sizer.Add(self.ao_superfine_ctrl, flag=wx.ALIGN_CENTER_VERTICAL|wx.EXPAND)
        ao_sizer.Add(wx.StaticText(parent, label='0.10'), flag=wx.ALIGN_CENTER_VERTICAL)
        ao_sizer.AddGrowableCol(3)

        ctrl_sizer = wx.StaticBoxSizer(ctrl_box, wx.VERTICAL)
        ctrl_sizer.Add(ao_float_sizer, flag=wx.ALL, border=self._FromDIP(5))
        ctrl_sizer.Add(ao_sizer, flag=wx.EXPAND|wx.LEFT|wx.RIGHT|wx.BOTTOM,
            border=self._FromDIP(5))

        return ctrl_sizer

    def _create_shutter_layout(self, parent):
        shutter_box = wx.StaticBox(parent, label='Shutters')
        parent = shutter_box

        fe_shutter = custom_epics_widgets.PVTextLabeled(parent,
            self.fe_shutter_status_pv, fg='forest green')
        d_shutter = custom_epics_widgets.PVTextLabeled(parent,
            self.d_shutter_status_pv, fg='forest green')
        fe_shutter_open = custom_epics_widgets.PVButton2(parent,
            self.fe_shutter_open_pv, label='Open', size=(50, -1))
        fe_shutter_close = custom_epics_widgets.PVButton2(parent,
            self.fe_shutter_close_pv, label='Close', size=(50, -1))
        d_shutter_open = custom_epics_widgets.PVButton2(parent,
            self.d_shutter_open_pv, label='Open', size=(50, -1))
        d_shutter_close = custom_epics_widgets.PVButton2(parent,
            self.d_shutter_close_pv, label='Close', size=(50, -1))

        fe_shutter.SetTranslations({'OFF': 'Closed', 'ON': 'Open'})
        d_shutter.SetTranslations({'OFF': 'Closed', 'ON': 'Open'})
        fe_shutter.SetForegroundColourTranslations({'Open': 'forest green',
            'Closed': 'red'})

        fe_shtr_ctrl = wx.BoxSizer(wx.HORIZONTAL)
        fe_shtr_ctrl.Add(fe_shutter_open, border=5, flag=wx.RIGHT)
        fe_shtr_ctrl.Add(fe_shutter_close, border=5, flag=wx.RIGHT)

        d_shtr_ctrl = wx.BoxSizer(wx.HORIZONTAL)
        d_shtr_ctrl.Add(d_shutter_open, border=5, flag=wx.RIGHT)
        d_shtr_ctrl.Add(d_shutter_close, border=5, flag=wx.RIGHT)

        station_grid_sizer = wx.GridBagSizer(vgap=5, hgap=5)
        station_grid_sizer.Add(wx.StaticText(parent, label='D shutter:'),
            pos=(0,0), flag=wx.ALIGN_CENTER_VERTICAL)
        station_grid_sizer.Add(d_shutter, pos=(0,1),
            flag=wx.ALIGN_CENTER_VERTICAL)
        station_grid_sizer.Add(5, -1, pos=(0,2))
        station_grid_sizer.Add(wx.StaticText(parent, label='A shutter:'),
            pos=(0,3), flag=wx.ALIGN_CENTER_VERTICAL)
        station_grid_sizer.Add(fe_shutter, pos=(0,4),
            flag=wx.ALIGN_CENTER_VERTICAL)
        station_grid_sizer.Add(fe_shtr_ctrl, pos=(1, 3), span=(0, 2),
            flag=wx.ALIGN_CENTER_VERTICAL|wx.ALIGN_CENTER_HORIZONTAL)
        station_grid_sizer.Add(d_shtr_ctrl, pos=(1, 0), span=(0, 2),
            flag=wx.ALIGN_CENTER_VERTICAL|wx.ALIGN_CENTER_HORIZONTAL)



        exp_shutter_in = epics.wx.PVRadioButton(parent, self.exp_shutter_pv, 0,
            label='Closed', style=wx.RB_GROUP)
        exp_shutter_out = epics.wx.PVRadioButton(parent, self.exp_shutter_pv, 1,
            label='Open')

        exp_shutter_sizer = wx.BoxSizer(wx.VERTICAL)
        exp_shutter_sizer.Add(wx.StaticText(parent, label='I0 shutter:'))
        exp_shutter_sizer.Add(exp_shutter_in, flag=wx.TOP, border=self._FromDIP(5))
        exp_shutter_sizer.Add(exp_shutter_out, flag=wx.TOP, border=self._FromDIP(5))


        shutter_sizer = wx.StaticBoxSizer(shutter_box, wx.HORIZONTAL)
        shutter_sizer.Add(exp_shutter_sizer, flag=wx.ALL, border=self._FromDIP(5))
        shutter_sizer.Add(station_grid_sizer, flag=wx.ALL, border=self._FromDIP(5))

        return shutter_sizer

    @EpicsFunction
    def _initialize(self):
        ao_ll = self.ao_low_lim_pv.get()
        ao_hl = self.ao_high_lim_pv.get()

        self.ao_coarse_ctrl.SetRange(ao_ll, ao_hl)
        self.ao_float_ctrl.SetRange((ao_ll, ao_hl))

        ao_val = self.ao_pv.get()

        self.set_ao_vals(ao_val)

        cbid = self.ao_pv.add_callback(self._on_ao_change)
        self._callbacks.append((self.ao_pv, cbid))

        self.set_gain()

        cbid = self.i0_gain_mult_pv.add_callback(self._on_gain_change)
        self._callbacks.append((self.i0_gain_mult_pv, cbid))

        cbid = self.i0_gain_unit_pv.add_callback(self._on_gain_change)
        self._callbacks.append((self.i0_gain_unit_pv, cbid))

    def set_ao_vals(self, ao_val):
        if ao_val < 0:
            fine_val = abs(ao_val - math.ceil(ao_val))
            sf_val = abs(10*ao_val - math.ceil(10*ao_val))/10
        else:
            fine_val = ao_val - math.floor(ao_val)
            sf_val = (10*ao_val - math.floor(10*ao_val))/10

        self.ao_float_ctrl.SafeSetValue(ao_val)
        self.ao_coarse_ctrl.SetValue(ao_val)
        self.ao_fine_ctrl.SetValue(fine_val)
        self.ao_superfine_ctrl.SetValue(sf_val)

    @EpicsFunction
    def set_gain(self):
        gain_mult = self.i0_gain_mult_pv.get(as_string=True)
        gain_unit = self.i0_gain_unit_pv.get(as_string=True)

        if gain_unit == 'pA/V':
            gain_base = 1e-12
        elif gain_unit == 'nA/V':
            gain_base = 1e-9
        elif gain_unit == 'uA/V':
            gain_base = 1e-6
        elif gain_unit == 'mA/V':
            gain_base = 1e-3
        else:
            gain_base = None

        if gain_base is not None:
            gain = 1/(float(gain_mult)*gain_base)

            self.i0_gain.SetLabel('{:.0e}'.format(gain))

    @EpicsFunction
    def _on_ao_float_ctrl(self, evt):
        val = evt.GetValue()
        self.ao_pv.put(val)

    @EpicsFunction
    def _on_coarse_scroll(self, evt):
        val = evt.GetValue()
        self.ao_pv.put(val)

    @EpicsFunction
    def _on_fine_scroll(self, evt):
        val = evt.GetValue()
        ao_val = self.ao_pv.get()

        if ao_val < 0:
            new_val = math.ceil(ao_val) - val
        else:
            new_val = math.floor(ao_val) + val

        self.ao_pv.put(new_val)

    @EpicsFunction
    def _on_superfine_scroll(self, evt):
        val = evt.GetValue()
        ao_val = self.ao_pv.get()

        if ao_val < 0:
            new_val = (math.ceil(10*ao_val) - val*10)/10
        else:
            new_val = (math.floor(10*ao_val) + val*10)/10

        self.ao_pv.put(new_val)

    @EpicsFunction
    def _on_ao_change(self, **kwargs):
        value = kwargs['value']

        try:
            voltage = float(value)
        except Exception:
            voltage = None

        if voltage is not None:
            wx.CallAfter(self.set_ao_vals, voltage)

    @EpicsFunction
    def _on_gain_change(self, **kwargs):
        wx.CallAfter(self.set_gain)

    def on_close(self):
        """Device specific stuff goes here"""
        for pv, cbid in self._callbacks:
            pv.remove_callback(cbid)

    def on_exit(self):
        self.close()


class MonoTuneFrame(wx.Frame):
    """
    A lightweight amplifier frame designed to hold an arbitrary number of dios
    in an arbitrary grid pattern.
    """
    def __init__(self, name, mx_database, timer=True, *args, **kwargs):
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

        self.name = name
        self._ctrls = []

        self.mx_database = mx_database

        self.mx_timer = wx.Timer()
        self.mx_timer.Bind(wx.EVT_TIMER, self._on_mxtimer)

        top_sizer = self._create_layout()

        self.SetSizer(top_sizer)
        self.Layout()
        self.Fit()
        self.Raise()

        if timer:
            self.mx_timer.Start(1000)

        self.Bind(wx.EVT_CLOSE, self._on_closewindow)

    def _FromDIP(self, size):
        # This is a hack to provide easy back compatibility with wxpython < 4.1
        try:
            return self.FromDIP(size)
        except Exception:
            return size

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
        mono_tune_box = wx.StaticBox(self, label='Mono Tune Controls')
        mono_tune_box_sizer = wx.StaticBoxSizer(mono_tune_box)

        mono_tune_panel = MonoTunePanel(self.name, self.mx_database, mono_tune_box)
        mono_tune_box_sizer.Add(mono_tune_panel, flag=wx.ALL|wx.EXPAND,
            border=self._FromDIP(5), proportion=1)

        self._ctrls.append(mono_tune_panel)

        return mono_tune_box_sizer

    def _on_mxtimer(self, evt):
        """
        Called on the mx_timer, refreshes mx values in the GUI by calling
        wait_for_messages on the database.
        """
        self.mx_database.wait_for_messages(0.01)

    def _on_closewindow(self, evt):
        """
        Closes the window. In an attempt to minimize trouble with MX it
        stops and then restarts the MX timer while it destroys the controls.
        """
        for ctrl in self._ctrls:
            ctrl.on_close()

        self.Destroy()

#Settings
default_mono_tune_settings = {
    'device_init'           : [
        {'name': 'Mono Tune', 'args': [], 'kwargs': {
            'output'        : '18ID:USB1608G_2AO_1:Ao1',
            'i0'            : '18ID:USB1608G_2:Ai7',
            'i0_gain_mult'  : '18ID:SR570:1:asyn_1sens_num',
            'i0_gain_unit'  : '18ID:SR570:1:asyn_1sens_unit',
            'c_hutch_x_pos' : '18ID:C_Mono_BPM:PosX:MeanValue_RBV',
            'c_hutch_y_pos' : '18ID:C_Mono_BPM:PosY:MeanValue_RBV',
            'c_hutch_int'   : '18ID:C_Mono_BPM:SumAll:MeanValue_RBV',
            }
        },
        ], # Compatibility with the standard format
    'fe_shutter'        : 'PA:18ID:STA_A_FES_OPEN_PL',
    'd_shutter'         : 'PA:18ID:STA_D_SDS_OPEN_PL',
    'fe_shutter_open'   : '18ID:rshtr:A:OPEN',
    'fe_shutter_close'  : '18ID:rshtr:A:CLOSE',
    'd_shutter_open'    : '18ID:rshtr:D:OPEN',
    'd_shutter_close'   : '18ID:rshtr:D:CLOSE',
    'exp_slow_shtr1'    : '18ID:LJT4:3:Bi6',
    }


if __name__ == '__main__':
    # try:
    #     # First try to get the name from an environment variable.
    #     database_filename = os.environ["MXDATABASE"]
    # except:
    #     # If the environment variable does not exist, construct
    #     # the filename for the default MX database.
    #     mxdir = utils.get_mxdir()
    #     database_filename = os.path.join(mxdir, "etc", "mxmotor.dat")
    #     database_filename = os.path.normpath(database_filename)

    # mx_database = mp.setup_database(database_filename)
    # mx_database.set_plot_enable(2)
    # mx_database.set_program_name("attenuators")

    mx_database = None

    app = wx.App()
    frame = MonoTuneFrame("MonoTuneFrame", mx_database, timer=False,
        parent=None, title='Test Mono Tune Control')
    frame.Show()
    app.MainLoop()


