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
import traceback

if __name__ != '__main__':
    logger = logging.getLogger(__name__)

import numpy as np
import wx

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
    traceback.print_exc()

import utils
import custom_epics_widgets

class HomeMotorController(object):
    def __init__(self):

        self._home_abort_evt = threading.Event()
        self._home_abort_evt.clear()
        self._home_motor_thread = None

        self.motor = None

        self._home_settings = {}

    def start_home(self, motor, home_to, final_pos, offset, step, speed, cycles,
        move_off):

        self.motor = motor

        self._home_settings = {
            'home_to'   : home_to,
            'final_pos' : final_pos,
            'offset'    : offset,
            'step'      : step,
            'speed'     : speed,
            'cycles'    : cycles,
            'move_off'  : move_off,
        }

        self._home_abort_evt.clear()
        self._home_motor_thread = threading.Thread(target=self._home_motor)
        self._home_motor_thread.daemon = True
        self._home_motor_thread.start()

    def abort_home(self):
        self._home_abort_evt.set()

        if self._home_motor_thread is not None:
            self.motor.stop()
            self._home_motor_thread.join(5)

    def _home_motor(self):
        logger.info('Starting motor homing')
        home_to = self._home_settings['home_to']
        final_pos = self._home_settings['final_pos']
        home_offset = self._home_settings['offset']

        if home_to == 'center':
            logger.debug('Home to center')
            plus_lim = self._inner_home_to_limit(1)

            if self._home_abort_evt.is_set():
                return

            minus_lim = self._inner_home_to_limit(-1)

            if self._home_abort_evt.is_set():
                return

            if plus_lim is not None and minus_lim is not None:
                home_pos = (plus_lim+minus_lim)/2
            else:
                home_pos = None

        elif home_to == 'plus':
            logger.debug('Home to positive limit')
            home_pos = self._inner_home_to_limit(1)

        elif home_to == 'minus':
            logger.debug('Home to negative limit')
            home_pos = self._inner_home_to_limit(-1)

        else:
            home_pos = None

        if home_pos is not None:
            logger.debug('Found new home position: %s', home_pos)

            if self._home_abort_evt.is_set():
                return

            home_pos += home_offset

            self.motor.move_absolute(home_pos)

            start = time.monotonic()

            while not self.motor.is_moving() and time.monotonic()-start < 1:
                time.sleep(0.05)
                abort = self._home_abort_evt.is_set()

            abort = self._home_abort_evt.is_set()

            while self.motor.is_moving() and not abort:
                    time.sleep(0.05)
                    abort = self._home_abort_evt.is_set()

            if abort:
                return

            logger.info('Set home position: %s set to %s', home_pos, final_pos)

            self.motor.position = final_pos

        wx.CallAfter(self._on_home_finish)


    def _inner_home_to_limit(self, direction):
        abort = False

        step = self._home_settings['step']
        speed = self._home_settings['speed']
        cycles = self._home_settings['cycles']
        move_off = self._home_settings['move_off']

        lim_pos_list = []

        self.motor.set_jog_speed(speed)

        if direction == 1:
            jog_dir = 'positive'
        else:
            jog_dir = 'negative'

        step_off = -1*direction*step
        move_off = -1*direction*move_off

        for i in range(cycles):
            abort = self._home_abort_evt.is_set()

            if abort:
                break

            if i != 0:
                logger.debug('Moving off %s limit by %s', jog_dir, move_off)
                self.motor.move_relative(move_off)

                start = time.monotonic()

                while not self.motor.is_moving() and time.monotonic() - start < 1:
                    time.sleep(0.05)

                while self.motor.is_moving() and not abort:
                    time.sleep(0.05)
                    abort = self._home_abort_evt.is_set()

            abort = self._home_abort_evt.is_set()

            if abort:
                break

            if direction == 1:
                on_lim = self.motor.on_high_limit()
            else:
                on_lim = self.motor.on_low_limit()

            if not on_lim and not abort:
                logger.debug('Moving to %s limit', jog_dir)
                self.motor.jog(jog_dir, True)

            while not on_lim and not abort:
                if direction == 1:
                    on_lim = self.motor.on_high_limit()
                else:
                    on_lim = self.motor.on_low_limit()

                time.sleep(0.05)
                abort = self._home_abort_evt.is_set()

            logger.debug('Hit %s limit', jog_dir)

            self.motor.jog(jog_dir, False)

            while on_lim and not abort:
                logger.debug('Stepping off %s limit by %s', jog_dir, step_off)

                self.motor.move_relative(step_off, wait=True)

                time.sleep(0.05)

                while self.motor.is_moving():
                    time.sleep(0.05)
                    abort = self._home_abort_evt.is_set()

                if direction == 1:
                    on_lim = self.motor.on_high_limit()
                else:
                    on_lim = self.motor.on_low_limit()

            if not abort:
                motor_pos = self.motor.position
                logger.debug('%s limit position found: %s', jog_dir.capitalize(), motor_pos)
            else:
                motor_pos = None
                logger.debug('%s limit position not found', jog_dir.capitalize())

            if motor_pos is not None:
                lim_pos_list.append(motor_pos)

        lim_pos = None

        if not abort:
            if all([pos is not None for pos in lim_pos_list]):
                lim_pos = statistics.mean(lim_pos_list)
                logger.debug('%s average limit position: %s', jog_dir.capitalize(), lim_pos)

        return lim_pos


class HomeMotorPanel(wx.Panel):
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
        self.settings = copy.deepcopy(default_home_settings)

        self._callbacks = []

        self._home_controller = HomeMotorController()

        self._motor_panel = None
        self._selected_pv = None
        self._motor_parent = None

        self._initialize()

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

    def _initialize(self):
        SHOW_C_MOTORS = True

        self._motor_list = []

        controllers = [
            ['18ID_DMC_E01:', 1, 8],
            ['18ID_DMC_E02:', 9, 16],
            ['18ID_DMC_E03:', 17, 24],
            ['18ID_DMC_E04:', 25, 32],
            ['18ID_DMC_E05:', 33, 40],
            ['18ID_DMC_A01:A', 1, 8],
            ]

        if SHOW_C_MOTORS:
            controllers.append(['18ID_DMC_E06:C', 1, 8])
            controllers.append(['18ID_DMC_E07:C', 9, 16])
            controllers.append(['18ID_DMC_E08:C', 17, 24])

        for item in controllers:
            prefix, start, end = item

            for mnum in range(start, end+1):
                pv = '{}{}'.format(prefix, mnum)
                self._motor_list.append(pv)

        self._selected_pv = self._motor_list[0]
        self._motor = motorcon.EpicsMotor('home_motor', self._selected_pv)

    def _initialize_pv(self, pv_name):
        pv = epics.get_pv(pv_name)
        connected = pv.wait_for_connection(5)

        if not connected:
            logger.error('Failed to connect to EPICS PV %s on startup', pv_name)

        return pv, connected

    def _create_layout(self):
        """Creates the layout"""

        parent = self

        self._pv_choice = wx.Choice(parent, choices=self._motor_list)
        self._pv_choice.SetStringSelection(self._selected_pv)
        self._pv_choice.Bind(wx.EVT_CHOICE, self._on_pv_change)

        pv_sel_sizer = wx.BoxSizer(wx.HORIZONTAL)
        pv_sel_sizer.Add(wx.StaticText(parent, label='Motor PV:'),
            flag=wx.ALIGN_CENTER_VERTICAL|wx.RIGHT, border=self._FromDIP(5))
        pv_sel_sizer.Add(self._pv_choice, flag=wx.ALIGN_CENTER_VERTICAL)

        self._motor_parent = parent
        self._motor_panel = self._create_motor_layout()

        self._motor_sizer = wx.BoxSizer(wx.VERTICAL)
        self._motor_sizer.Add(pv_sel_sizer)
        self._motor_sizer.Add(self._motor_panel, flag=wx.TOP, border=self._FromDIP(5))


        home_box = wx.StaticBox(parent, label='Home settings')
        home_parent = home_box

        self._home_to = wx.Choice(home_parent, choices=['plus', 'minus', 'center'])
        self._home_to.SetSelection(0)
        self._final_pos = wx.TextCtrl(home_parent, value='0', size=self._FromDIP((60, -1)),
            validator=utils.CharValidator('float_neg'))
        self._offset = wx.TextCtrl(home_parent, value='0', size=self._FromDIP((60, -1)),
            validator=utils.CharValidator('float_neg'))
        self._speed = wx.TextCtrl(home_parent, value='1', size=self._FromDIP((60, -1)),
            validator=utils.CharValidator('float_neg'))
        self._cycles = wx.TextCtrl(home_parent, value='3', size=self._FromDIP((60, -1)),
            validator=utils.CharValidator('int'))
        self._move_off = wx.TextCtrl(home_parent, value='1', size=self._FromDIP((60, -1)),
            validator=utils.CharValidator('float'))

        home_ctrl_sizer = wx.FlexGridSizer(cols=2, hgap=self._FromDIP(5),
            vgap=self._FromDIP(5))
        home_ctrl_sizer.Add(wx.StaticText(home_parent, label='Home direction:'),
            flag=wx.ALIGN_CENTER_VERTICAL)
        home_ctrl_sizer.Add(self._home_to, flag=wx.ALIGN_CENTER_VERTICAL)
        home_ctrl_sizer.Add(wx.StaticText(home_parent, label='Offset from limit/center:'),
            flag=wx.ALIGN_CENTER_VERTICAL)
        home_ctrl_sizer.Add(self._offset, flag=wx.ALIGN_CENTER_VERTICAL)
        home_ctrl_sizer.Add(wx.StaticText(home_parent, label='Home position value:'),
            flag=wx.ALIGN_CENTER_VERTICAL)
        home_ctrl_sizer.Add(self._final_pos, flag=wx.ALIGN_CENTER_VERTICAL)
        home_ctrl_sizer.Add(wx.StaticText(home_parent, label='Home speed:'),
            flag=wx.ALIGN_CENTER_VERTICAL)
        home_ctrl_sizer.Add(self._speed, flag=wx.ALIGN_CENTER_VERTICAL)
        home_ctrl_sizer.Add(wx.StaticText(home_parent, label='Limit cycles:'),
            flag=wx.ALIGN_CENTER_VERTICAL)
        home_ctrl_sizer.Add(self._cycles, flag=wx.ALIGN_CENTER_VERTICAL)
        home_ctrl_sizer.Add(wx.StaticText(home_parent, label='Limit move off:'),
            flag=wx.ALIGN_CENTER_VERTICAL)
        home_ctrl_sizer.Add(self._move_off, flag=wx.ALIGN_CENTER_VERTICAL)

        home_sizer = wx.StaticBoxSizer(home_box, wx.VERTICAL)
        home_sizer.Add(home_ctrl_sizer)


        top_sizer = wx.BoxSizer(wx.HORIZONTAL)
        top_sizer.Add(self._motor_sizer, flag=wx.ALL|wx.EXPAND, border=self._FromDIP(5))
        top_sizer.Add(home_sizer, flag=wx.RIGHT|wx.TOP|wx.BOTTOM|wx.EXPAND,
            border=self._FromDIP(5))

        self.SetSizer(top_sizer)

    def _create_motor_layout(self):
        motor_panel = motorcon.EpicsMXMotorPanel(self._selected_pv,
            None, self._motor_parent)

        return motor_panel

    def _on_pv_change(self, evt):
        self._selected_pv = self._pv_choice.GetStringSelection()

        self._motor = motorcon.EpicsMotor('home_motor', self._selected_pv)

        self._motor_sizer.Detach(self._motor_panel)
        self._motor_panel.Destroy()
        self._motor_panel = self._create_motor_layout()
        self._motor_sizer.Add(self._motor_panel, flag=wx.TOP, border=self._FromDIP(5))

        self.Layout()
        self.Fit()

    def on_close(self):
        """Device specific stuff goes here"""

        for pv, cbid in self._callbacks:
            pv.remove_callback(cbid)

    def on_exit(self):
        self.close()


class HomeMotorFrame(wx.Frame):
    """
    A lightweight frame designed to hold an arbitrary number of instances.
    """
    def __init__(self, name, mx_database, timer=True, *args, **kwargs):
        """
        :param Mp.RecordList mx_database: The Mp database containing the amp records.

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
        """
        home_box = wx.StaticBox(self, label='Home Motor Controls')
        home_box_sizer = wx.StaticBoxSizer(home_box)

        home_panel = HomeMotorPanel(self.name, self.mx_database, home_box)
        home_box_sizer.Add(home_panel, flag=wx.ALL|wx.EXPAND,
            border=self._FromDIP(5), proportion=1)

        self._ctrls.append(home_panel)

        return home_box_sizer

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
default_home_settings = {
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
    frame = HomeMotorFrame("HomeMotorFrame", mx_database, timer=False,
        parent=None, title='Test Home Motor')
    frame.Show()
    app.MainLoop()


