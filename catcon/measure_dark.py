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

class MeasureDarkPanel(wx.Panel):
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
        self.settings = copy.deepcopy(default_mono_tune_settings)
        self.settings['device_data'] = self.settings.pop('device_init')[0]

        self._callbacks = []

        self.abort_dark = threading.Event()
        self.meas_thread = None

        self._init_pvs()

        self._create_layout()

        # self.SetMinSize(self._FromDIP((450, -1)))
        self.Layout()
        self.Refresh()

    def _FromDIP(self, size):
        # This is a hack to provide easy back compatibility with wxpython < 4.1
        try:
            return self.FromDIP(size)
        except Exception:
            return size

    def _init_pvs(self):
        # Happens before create layout
        self.scaler_pvs = {}
        for prefix in self.settings['device_data']['kwargs']['scalers']:
            self.scaler_pvs[prefix] = {}

            ct_time_pv, _ = self._initialize_pv('{}scaler1.TP'.format(prefix))
            self.scaler_pvs[prefix]['ct_time'] = ct_time_pv

            ct_start_pv, _ = self._initialize_pv('{}scaler1.CNT'.format(prefix))
            self.scaler_pvs[prefix]['ct_start'] = ct_start_pv

            for i in range(1,9):
                ct_pv, _ = self._initialize_pv('{}scaler1.S{}'.format(prefix, i))
                calc_pv, _ = self._initialize_pv('{}scaler1_calc{}.VAL'.format(prefix, i))
                dark_pv, _ = self._initialize_pv('{}Dark{}.VAL'.format(prefix, i))

                self.scaler_pvs[prefix]['chan{}'.format(i)] = [ct_pv, calc_pv, dark_pv]

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

        sub_sizer = wx.BoxSizer(wx.VERTICAL)

        sub_sizer.Add(ctrl_sizer, flag=wx.LEFT|wx.RIGHT|wx.BOTTOM|wx.EXPAND,
            border=self._FromDIP(5))
        sub_sizer.Add(shutter_sizer, flag=wx.LEFT|wx.RIGHT|wx.BOTTOM|wx.EXPAND,
            border=self._FromDIP(5))

        top_sizer = wx.BoxSizer(wx.HORIZONTAL)
        top_sizer.Add(sub_sizer, flag=wx.ALL|wx.EXPAND, border=self._FromDIP(5))
        top_sizer.Add(readout_sizer, flag=wx.TOP|wx.BOTTOM|wx.RIGHT|wx.EXPAND,
            border=self._FromDIP(5))

        self.SetSizer(top_sizer)

    def _create_readout_layout(self, parent):
        readout_box = wx.StaticBox(parent, label='Dark counts')
        parent = readout_box

        dark_grid = wx.FlexGridSizer(
            cols=len(self.settings['device_data']['kwargs']['scalers'])+1,
            hgap=self._FromDIP(5), vgap=self._FromDIP(5))

        dark_grid.AddSpacer(1)

        for prefix in self.settings['device_data']['kwargs']['scalers']:
            dark_grid.Add(wx.StaticText(parent, label=prefix))

        for i in range(1,9):
            dark_grid.Add(wx.StaticText(parent, label='Dark {} [ct/s]:'.format(i)))
            for prefix in self.settings['device_data']['kwargs']['scalers']:
                dark_grid.Add(epics.wx.PVText(parent, self.scaler_pvs[prefix]['chan{}'.format(i)][2]))


        readout_sizer = wx.StaticBoxSizer(readout_box, wx.HORIZONTAL)
        readout_sizer.Add(dark_grid, flag=wx.ALL, border=self._FromDIP(5))

        return readout_sizer

    def _create_ctrl_layout(self, parent):
        ctrl_box = wx.StaticBox(parent, label='Control')
        parent = ctrl_box

        self.dark_time = wx.TextCtrl(parent, value='0.5',
            validator=utils.CharValidator('float'), size=self._FromDIP((80, -1)))
        self.dark_num = wx.TextCtrl(parent, value='20',
            validator=utils.CharValidator('int'), size=self._FromDIP((80, -1)))
        self.status = wx.StaticText(parent, label='Done', size=self._FromDIP((160, -1)))
        self.start_btn = wx.Button(parent, label='Start')
        self.start_btn.Bind(wx.EVT_BUTTON, self._on_start_button)
        self.stop_btn = wx.Button(parent, label='Stop')
        self.stop_btn.Bind(wx.EVT_BUTTON, self._on_stop_button)

        self.stop_btn.Disable()

        ctrl_grid = wx.FlexGridSizer(cols=2, hgap=self._FromDIP(5),
            vgap=self._FromDIP(5))
        ctrl_grid.Add(wx.StaticText(parent, label='Count time [s]:'),
            flag=wx.ALIGN_CENTER_VERTICAL)
        ctrl_grid.Add(self.dark_time, flag=wx.ALIGN_CENTER_VERTICAL)
        ctrl_grid.Add(wx.StaticText(parent, label='Repeats:'),
            flag=wx.ALIGN_CENTER_VERTICAL)
        ctrl_grid.Add(self.dark_num, flag=wx.ALIGN_CENTER_VERTICAL)
        ctrl_grid.Add(wx.StaticText(parent, label='Status:'),
            flag=wx.ALIGN_CENTER_VERTICAL)
        ctrl_grid.Add(self.status, flag=wx.ALIGN_CENTER_VERTICAL)

        ctrl_btn = wx.BoxSizer(wx.HORIZONTAL)
        ctrl_btn.Add(self.start_btn, flag=wx.RIGHT, border=self._FromDIP(5))
        ctrl_btn.Add(self.stop_btn)


        ctrl_sizer = wx.StaticBoxSizer(ctrl_box, wx.VERTICAL)
        ctrl_sizer.Add(ctrl_grid, flag=wx.ALL, border=self._FromDIP(5))
        ctrl_sizer.Add(ctrl_btn, flag=wx.LEFT|wx.RIGHT|wx.BOTTOM|
            wx.ALIGN_CENTER_HORIZONTAL, border=self._FromDIP(5))

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



        exp_shutter_in = epics.wx.PVRadioButton(parent, self.exp_shutter_pv, 1,
            label='Closed', style=wx.RB_GROUP)
        exp_shutter_out = epics.wx.PVRadioButton(parent, self.exp_shutter_pv, 0,
            label='Open')

        exp_shutter_sizer = wx.BoxSizer(wx.VERTICAL)
        exp_shutter_sizer.Add(wx.StaticText(parent, label='I0 shutter:'))
        exp_shutter_sizer.Add(exp_shutter_in, flag=wx.TOP, border=self._FromDIP(5))
        exp_shutter_sizer.Add(exp_shutter_out, flag=wx.TOP, border=self._FromDIP(5))


        shutter_sizer = wx.StaticBoxSizer(shutter_box, wx.HORIZONTAL)
        shutter_sizer.Add(exp_shutter_sizer, flag=wx.ALL, border=self._FromDIP(5))
        shutter_sizer.Add(station_grid_sizer, flag=wx.ALL, border=self._FromDIP(5))

        return shutter_sizer

    def _on_start_button(self, evt):
        self.abort_dark.clear()

        ct_time = self.dark_time.GetValue()
        repeats = self.dark_num.GetValue()

        try:
            ct_time = float(ct_time)
        except Exception:
            self.status.SetLabel('Error in settings')
            return

        try:
            repeats = int(repeats)
        except Exception:
            self.status.SetLabel('Error in settings')
            return

        self.start_btn.Disable()
        self.stop_btn.Enable()
        self.meas_thread = threading.Thread(target=self._measure_dark,
            args=(ct_time, repeats))
        self.meas_thread.daemon = True
        self.meas_thread.start()

    def _on_stop_button(self, evt):
        self.abort_dark.set()
        self.meas_thread.join(2)
        self.start_btn.Enable()
        self.stop_btn.Disable()
        self.status.SetLabel('Aborted')

    def _measure_dark(self, ct_time, repeats):
        self.dark_cts = {}
        self.ct_times = {}

        if self.abort_dark.is_set():
            return

        for prefix in self.settings['device_data']['kwargs']['scalers']:
            self.scaler_pvs[prefix]['ct_time'].put(ct_time, wait=True)
            self.dark_cts[prefix] = [[] for i in range(8)]
            self.ct_times[prefix] = []

        if self.abort_dark.is_set():
            return

        for i in range(repeats):
            wx.CallAfter(self.status.SetLabel, 'Measuring {} of {}'.format(i+1, repeats))
            for prefix in self.settings['device_data']['kwargs']['scalers']:
                self.scaler_pvs[prefix]['ct_start'].put(1, wait=False)

            time.sleep(ct_time/5)

            while True:
                if self.abort_dark.is_set():
                    for prefix in self.settings['device_data']['kwargs']['scalers']:
                        self.scaler_pvs[prefix]['ct_start'].put(0, wait=False)
                    return

                all_done = [not self.scaler_pvs[prefix]['ct_start'].get() for prefix
                    in self.settings['device_data']['kwargs']['scalers']]

                if all(all_done):
                    break
                else:
                    time.sleep(0.05)

            for prefix in self.settings['device_data']['kwargs']['scalers']:
                calc_pv = self.scaler_pvs[prefix]['chan1'][1]
                self.ct_times[prefix].append(calc_pv.get())

                for i in range(1,9):
                    ct_pv = self.scaler_pvs[prefix]['chan{}'.format(i)][0]
                    self.dark_cts[prefix][i-1].append(ct_pv.get())

        for prefix in self.settings['device_data']['kwargs']['scalers']:
            real_ct_time = np.mean(self.ct_times[prefix])
            for i in range(1,9):
                dark_cts = np.mean(self.dark_cts[prefix][i-1])
                dark_pv = self.scaler_pvs[prefix]['chan{}'.format(i)][2]
                dark_pv.put(dark_cts/real_ct_time)

        wx.CallAfter(self.status.SetLabel, 'Done')

    def on_close(self):
        """Device specific stuff goes here"""

        if self.meas_thread is not None:
            self.abort_dark.set()
            self.meas_thread.join(2)

        for pv, cbid in self._callbacks:
            pv.remove_callback(cbid)

    def on_exit(self):
        self.close()


class MeasureDarkFrame(wx.Frame):
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
        measure_dark_box = wx.StaticBox(self, label='Measure Dark Controls')
        measure_dark_box_sizer = wx.StaticBoxSizer(measure_dark_box)

        measure_dark_panel = MeasureDarkPanel(self.name, self.mx_database, measure_dark_box)
        measure_dark_box_sizer.Add(measure_dark_panel, flag=wx.ALL|wx.EXPAND,
            border=self._FromDIP(5), proportion=1)

        self._ctrls.append(measure_dark_panel)

        return measure_dark_box_sizer

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
            'scalers'   : ['18ID:USBCTR08:1:', '18ID:USBCTR08:2:'],
            }
        },
        ], # Compatibility with the standard format
    'fe_shutter'        : 'PA:18ID:STA_A_FES_OPEN_PL',
    'd_shutter'         : 'PA:18ID:STA_D_SDS_OPEN_PL',
    'fe_shutter_open'   : '18ID:rshtr:A:OPEN',
    'fe_shutter_close'  : '18ID:rshtr:A:CLOSE',
    'd_shutter_open'    : '18ID:rshtr:D:OPEN',
    'd_shutter_close'   : '18ID:rshtr:D:CLOSE',
    'exp_slow_shtr1'    : '18ID:LJT4:2:Bo6',
    }


if __name__ == '__main__':
    logger = logging.getLogger()
    logger.setLevel(logging.DEBUG)
    h1 = logging.StreamHandler(sys.stdout)
    h1.setLevel(logging.INFO)
    # h1.setLevel(logging.DEBUG)
    # h1.setLevel(logging.ERROR)

    # formatter = logging.Formatter('%(asctime)s - %(message)s')
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(threadName)s - %(levelname)s - %(message)s')
    h1.setFormatter(formatter)
    logger.addHandler(h1)

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
    frame = MeasureDarkFrame("MeasureDarkFrame", mx_database, timer=False,
        parent=None, title='Test Measure Dark Control')
    frame.Show()
    app.MainLoop()


