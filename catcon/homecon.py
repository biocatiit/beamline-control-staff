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
import logging
import sys
import copy
import traceback
import pathlib
import os
import json
import statistics

if __name__ != '__main__':
    logger = logging.getLogger(__name__)

import wx

try:
    import epics
    import epics.wx
    from epics.wx.wxlib import EpicsFunction
except Exception:
    pass
    traceback.print_exc()

try:
    import motorcon
except Exception:
    pass
    traceback.print_exc()

import utils

class HomeMotorController(object):
    def __init__(self):

        self._home_abort_evt = threading.Event()
        self._home_abort_evt.clear()
        self._home_motor_thread = None
        self._home_error = False

        self.motor = None
        self.llimit_pv = None
        self.hlimit_pv = None
        self.at_soft_lim_pv = None
        self._soft_limits = {
            'low_lim'   : 0.,
            'high_lim'  : 0.,
            }

        self._home_settings = {}

        self._status = 'Done'

        self._status_callbacks = []

    def add_status_callback(self, func):
        if func not in self._status_callbacks:
            self._status_callbacks.append(func)

    def remove_status_callback(self, func):
        if func in self._status_callbacks:
            self._status_callbacks.remove(func)

    def get_status(self):
        return self._status

    def _update_status(self, status):
        self._status = status

        for func in copy.copy(self._status_callbacks):
            func(status)

    def start_home(self, motor, home_to, final_pos, offset, step, speed, cycles,
        move_off, ignore_lim):

        if self._home_motor_thread is not None and self._home_motor_thread.is_alive():
            logger.error('Homing already running, not starting another home sequence')
            return

        self.motor = motor

        self._home_settings = {
            'home_to'   : home_to,
            'final_pos' : final_pos,
            'offset'    : offset,
            'step'      : step,
            'speed'     : speed,
            'cycles'    : cycles,
            'move_off'  : move_off,
            'ignore_lim': ignore_lim
        }

        self._home_error = False
        self._home_abort_evt.clear()
        self._home_motor_thread = threading.Thread(target=self._home_motor)
        self._home_motor_thread.daemon = True
        self._home_motor_thread.start()

    def abort_home(self):
        logger.info('Aborting motor homing')

        self._home_abort_evt.set()

        if self._home_motor_thread is not None:
            self.motor.stop()
            self._home_motor_thread.join(5)

            if self._home_motor_thread.is_alive():
                logger.warning("Home thread still running after abort")

    def _on_home_finish(self):
        self.motor.stop() #Make sure motor is stopped

        self._restore_soft_lims()

        if self._home_error:
            status = 'Error'
        elif self._home_abort_evt.is_set():
            status = 'Aborted'
        else:
            status = 'Done'

        self._update_status(status)

        logger.info('Motor homing finished')

    def _home_motor(self):
        try:
            logger.info('Starting motor homing')
            self._update_status('Homing')

            home_to = self._home_settings['home_to']
            final_pos = self._home_settings['final_pos']
            home_offset = self._home_settings['offset']
            self.at_soft_lim_pv = self.motor.PV('LVIO')

            if self._home_settings['ignore_lim']:
                self.llimit_pv = self.motor.PV('LLM')
                self.hlimit_pv = self.motor.PV('HLM')

                self._soft_limits['low_lim'] = self.llimit_pv.get()
                self._soft_limits['high_lim'] = self.hlimit_pv.get()

                self.llimit_pv.put(-1e9)
                self.hlimit_pv.put(1e9)

            if home_to == 'center':
                logger.info('Home to center')
                plus_lim = self._inner_home_to_limit(1)

                if not self._home_abort_evt.is_set():
                    minus_lim = self._inner_home_to_limit(-1)
                else:
                    minus_lim = None

                if plus_lim is not None and minus_lim is not None:
                    home_pos = (plus_lim+minus_lim)/2
                else:
                    home_pos = None

            elif home_to == 'plus':
                logger.info('Home to positive limit')
                home_pos = self._inner_home_to_limit(1)

            elif home_to == 'minus':
                logger.info('Home to negative limit')
                home_pos = self._inner_home_to_limit(-1)

            else:
                home_pos = None

            if home_pos is not None:
                home_pos += home_offset

                logger.info('Found new home position: %s', home_pos)

                if not self._home_abort_evt.is_set():
                    self.motor.move_absolute(home_pos)

                    start = time.monotonic()

                    while not self.motor.is_moving() and time.monotonic()-start < 1:
                        time.sleep(0.05)
                        abort = self._home_abort_evt.is_set()

                    abort = self._home_abort_evt.is_set()

                    while self.motor.is_moving() and not abort:
                            time.sleep(0.05)
                            abort = self._home_abort_evt.is_set()

                    if not abort:
                        logger.info('Set home position: %s set to %s', home_pos, final_pos)
                        self.motor.position = final_pos

        except Exception:
            logger.exception('Homing failed')
            self._home_error = True

        finally:
            self._on_home_finish()


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
            lim_check = self.motor.on_high_limit
        else:
            jog_dir = 'negative'
            lim_check = self.motor.on_low_limit

        step_off = -1*direction*step
        move_off = -1*direction*move_off

        for i in range(cycles):
            abort = self._home_abort_evt.is_set()

            if abort:
                break

            if i != 0:
                logger.info('Moving off %s limit by %s', jog_dir, move_off)
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

            on_lim = lim_check()

            if not on_lim and not abort:
                logger.info('Moving to %s limit', jog_dir)
                self.motor.jog(jog_dir, True)

            while not on_lim and not abort:
                on_lim = lim_check()

                if not on_lim and self.at_soft_lim_pv.get() == 1:
                    if self._home_settings['ignore_lim']:
                        if direction == 1:
                            high_lim = self.hlimit_pv.get()
                            if high_lim > 0:
                                high_lim *= 2
                            else:
                                high_lim *= -1
                            self.hlimit_pv.put(high_lim)
                        else:
                            low_lim = self.llimit_pv.get()
                            if low_lim < 0:
                                low_lim *= 2
                            else:
                                low_lim *= -1
                            self.llimit_pv.put(low_lim)
                    else:
                        logger.error('Hit soft limit, aborting homing')
                        self._home_abort_evt.set()

                time.sleep(0.05)
                abort = self._home_abort_evt.is_set()

            logger.info('Hit %s limit', jog_dir)

            self.motor.jog(jog_dir, False)

            while on_lim and not abort:
                logger.info('Stepping off %s limit by %s', jog_dir, step_off)

                self.motor.move_relative(step_off, wait=True)

                time.sleep(0.05)

                while self.motor.is_moving() and not abort:
                    time.sleep(0.05)
                    abort = self._home_abort_evt.is_set()

                on_lim = lim_check()

            if not abort:
                motor_pos = self.motor.position
                logger.info('%s limit position found: %s', jog_dir.capitalize(), motor_pos)
            else:
                motor_pos = None
                logger.info('%s limit position not found', jog_dir.capitalize())

            if motor_pos is not None:
                lim_pos_list.append(motor_pos)

        lim_pos = None

        if not abort:
            if len(lim_pos_list) == cycles and all(pos is not None for pos in lim_pos_list):
                lim_pos = statistics.mean(lim_pos_list)
                logger.info('%s average limit position: %s', jog_dir.capitalize(), lim_pos)

        self.motor.stop() #Make sure motor is stopped, even in event of abort

        return lim_pos

    def _restore_soft_lims(self):
        if self._home_settings['ignore_lim']:
            if self.llimit_pv is not None:
                self.llimit_pv.put(self._soft_limits['low_lim'])
            if self.hlimit_pv is not None:
                self.hlimit_pv.put(self._soft_limits['high_lim'])


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

        self._home_controller = HomeMotorController()

        self._motor_panel = None
        self._selected_pv = None
        self._motor_parent = None

        self._initialize()

        self._create_layout()

        self._initialize_gui()

        self._home_controller.add_status_callback(self._on_status_update)

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

        self._base_path = pathlib.Path(__file__).parent.resolve().parent / 'motor_home'
        self._last_path = self._base_path
        self._last_path = str(self._last_path)

    def _initialize_gui(self):
        self._set_home_settings(self.settings)

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


        home_settings_box = wx.StaticBox(parent, label='Home settings')
        home_settings_parent = home_settings_box

        self._home_to = wx.Choice(home_settings_parent, choices=['plus', 'minus', 'center'])
        self._home_to.SetSelection(0)
        self._final_pos = wx.TextCtrl(home_settings_parent, value='0', size=self._FromDIP((60, -1)),
            validator=utils.CharValidator('float_neg'))
        self._offset = wx.TextCtrl(home_settings_parent, value='0', size=self._FromDIP((60, -1)),
            validator=utils.CharValidator('float_neg'))
        self._speed = wx.TextCtrl(home_settings_parent, value='1', size=self._FromDIP((60, -1)),
            validator=utils.CharValidator('float_neg'))
        self._cycles = wx.TextCtrl(home_settings_parent, value='3', size=self._FromDIP((60, -1)),
            validator=utils.CharValidator('int'))
        self._move_off = wx.TextCtrl(home_settings_parent, value='2', size=self._FromDIP((60, -1)),
            validator=utils.CharValidator('float'))
        self._step = wx.TextCtrl(home_settings_parent, value='0.05', size=self._FromDIP((60, -1)),
            validator=utils.CharValidator('float'))
        self._ignore_soft_limits = wx.CheckBox(home_settings_parent, label='Ignore soft limits')
        self._ignore_soft_limits.SetValue(True)

        home_ctrl_sizer = wx.FlexGridSizer(cols=2, hgap=self._FromDIP(5),
            vgap=self._FromDIP(5))
        home_ctrl_sizer.Add(wx.StaticText(home_settings_parent, label='Home direction:'),
            flag=wx.ALIGN_CENTER_VERTICAL)
        home_ctrl_sizer.Add(self._home_to, flag=wx.ALIGN_CENTER_VERTICAL)
        home_ctrl_sizer.Add(wx.StaticText(home_settings_parent, label='Offset from limit/center:'),
            flag=wx.ALIGN_CENTER_VERTICAL)
        home_ctrl_sizer.Add(self._offset, flag=wx.ALIGN_CENTER_VERTICAL)
        home_ctrl_sizer.Add(wx.StaticText(home_settings_parent, label='Home position value:'),
            flag=wx.ALIGN_CENTER_VERTICAL)
        home_ctrl_sizer.Add(self._final_pos, flag=wx.ALIGN_CENTER_VERTICAL)
        home_ctrl_sizer.Add(wx.StaticText(home_settings_parent, label='Home speed:'),
            flag=wx.ALIGN_CENTER_VERTICAL)
        home_ctrl_sizer.Add(self._speed, flag=wx.ALIGN_CENTER_VERTICAL)
        home_ctrl_sizer.Add(wx.StaticText(home_settings_parent, label='Limit cycles:'),
            flag=wx.ALIGN_CENTER_VERTICAL)
        home_ctrl_sizer.Add(self._cycles, flag=wx.ALIGN_CENTER_VERTICAL)
        home_ctrl_sizer.Add(wx.StaticText(home_settings_parent, label='Limit move off:'),
            flag=wx.ALIGN_CENTER_VERTICAL)
        home_ctrl_sizer.Add(self._move_off, flag=wx.ALIGN_CENTER_VERTICAL)
        home_ctrl_sizer.Add(wx.StaticText(home_settings_parent, label='Push off step:'),
            flag=wx.ALIGN_CENTER_VERTICAL)
        home_ctrl_sizer.Add(self._step, flag=wx.ALIGN_CENTER_VERTICAL)

        save_settings_btn = wx.Button(home_settings_parent, label='Save Settings')
        save_settings_btn.Bind(wx.EVT_BUTTON, self._on_save_settings)
        load_settings_btn = wx.Button(home_settings_parent, label='Load Settings')
        load_settings_btn.Bind(wx.EVT_BUTTON, self._on_load_settings)

        settings_btn_sizer = wx.BoxSizer(wx.HORIZONTAL)
        settings_btn_sizer.Add(save_settings_btn)
        settings_btn_sizer.Add(load_settings_btn, flag=wx.LEFT, border=self._FromDIP(5))

        home_settings_sizer = wx.StaticBoxSizer(home_settings_box, wx.VERTICAL)
        home_settings_sizer.Add(home_ctrl_sizer, flag=wx.ALL, border=self._FromDIP(5))
        home_settings_sizer.Add(self._ignore_soft_limits, flag=wx.LEFT|wx.RIGHT|wx.BOTTOM,
            border=self._FromDIP(5))
        home_settings_sizer.Add(settings_btn_sizer, flag=wx.LEFT|wx.RIGHT|wx.BOTTOM,
            border=self._FromDIP(5))


        home_ctrl_box = wx.StaticBox(parent, label='Home controls')
        home_ctrl_parent = home_ctrl_box

        self._home_status = wx.StaticText(home_ctrl_parent, label='Done')
        self._start_home_btn = wx.Button(home_ctrl_parent, label='Start Homing')
        self._stop_home_btn = wx.Button(home_ctrl_parent, label='Abort Homing')
        self._start_home_btn.Bind(wx.EVT_BUTTON, self._on_start_home)
        self._stop_home_btn.Bind(wx.EVT_BUTTON, self._on_stop_home)
        self._stop_home_btn.Disable()

        ctrl_status_sizer = wx.BoxSizer(wx.HORIZONTAL)
        ctrl_status_sizer.Add(wx.StaticText(home_ctrl_parent, label='Status:'))
        ctrl_status_sizer.Add(self._home_status, flag=wx.LEFT, border=self._FromDIP(5))

        ctrl_btn_sizer = wx.BoxSizer(wx.HORIZONTAL)
        ctrl_btn_sizer.Add(self._start_home_btn)
        ctrl_btn_sizer.Add(self._stop_home_btn, flag=wx.LEFT, border=self._FromDIP(5))

        home_ctrl_sizer = wx.StaticBoxSizer(home_ctrl_box, wx.VERTICAL)
        home_ctrl_sizer.Add(ctrl_status_sizer, flag=wx.ALL, border=self._FromDIP(5))
        home_ctrl_sizer.Add(ctrl_btn_sizer, flag=wx.LEFT|wx.RIGHT|wx.BOTTOM,
            border=self._FromDIP(5))

        home_sizer = wx.BoxSizer(wx.VERTICAL)
        home_sizer.Add(home_settings_sizer)
        home_sizer.Add(home_ctrl_sizer, flag=wx.TOP, border=self._FromDIP(5))

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
        self._change_pv()

    @EpicsFunction
    def _change_pv(self):
        self._selected_pv = self._pv_choice.GetStringSelection()

        self._motor = motorcon.EpicsMotor('home_motor', self._selected_pv)

        self._motor_sizer.Detach(self._motor_panel)
        self._motor_panel.Destroy()
        self._motor_panel = self._create_motor_layout()
        self._motor_sizer.Add(self._motor_panel, flag=wx.TOP, border=self._FromDIP(5))

        self.Layout()
        self.Fit()

    def _get_home_settings(self):
        home_to = self._home_to.GetStringSelection()
        final_pos = float(self._final_pos.GetValue())
        offset = float(self._offset.GetValue())
        speed = float(self._speed.GetValue())
        cycles = int(self._cycles.GetValue())
        move_off = float(self._move_off.GetValue())
        step = float(self._step.GetValue())
        ignore_lim = self._ignore_soft_limits.GetValue()

        home_settings = {
            'home_to'   : home_to,
            'final_pos' : final_pos,
            'offset'    : offset,
            'step'      : step,
            'speed'     : speed,
            'cycles'    : cycles,
            'move_off'  : move_off,
            'ignore_lim': ignore_lim,
        }

        return home_settings

    def _set_home_settings(self, home_settings):
        self._home_to.SetStringSelection(home_settings['home_to'])
        self._final_pos.SetValue(str(home_settings['final_pos']))
        self._offset.SetValue(str(home_settings['offset']))
        self._speed.SetValue(str(home_settings['speed']))
        self._cycles.SetValue(str(home_settings['cycles']))
        self._move_off.SetValue(str(home_settings['move_off']))
        self._step.SetValue(str(home_settings['step']))
        self._ignore_soft_limits.SetValue(home_settings['ignore_lim'])

    def _validate_home_settings(self, home_settings):
        errors = []

        if home_settings['step'] <= 0:
            errors.append('Step must be > 0')

        if home_settings['speed'] <= 0:
            errors.append('Speed must be > 0')

        if home_settings['move_off'] <= 0:
            errors.append('Move off must be > 0')

        if home_settings['cycles'] < 1:
            errors.append('Cycles must be >=1')

        if len(errors) > 0:
            valid = False
        else:
            valid = True

        return valid, errors

    @EpicsFunction
    def _save_settings(self, save_name):
        save_settings = {
            'pv'    : self._pv_choice.GetStringSelection(),
            'desc'  : self._motor_panel.epics_motor.get_pv('DESC').get(),
        }

        home_settings = self._get_home_settings()

        save_settings.update(home_settings)

        settings = json.dumps(save_settings, indent = 4)

        with open(save_name, 'w') as f:
            f.write(settings)

    def _load_settings(self, filename):
        with open(filename, 'r') as f:
            settings = json.load(f)

        self._set_home_settings(settings)
        self._pv_choice.SetStringSelection(settings['pv'])

        self._change_pv()

    @EpicsFunction
    def _on_save_settings(self, evt):
        desc = self._motor_panel.epics_motor.get_pv('DESC').get()

        fname = self._create_file_dialog(wx.FD_SAVE, desc)

        if fname is not None:
            if os.path.splitext(fname)[1] != '.json':
                fname = fname + '.json'

            self._last_path = str(pathlib.Path(fname).parent.resolve())

            wx.CallAfter(self._save_settings, fname)

    def _on_load_settings(self, evt):
        fname = self._create_file_dialog(wx.FD_OPEN, '')

        if fname is not None:
            self._last_path = str(pathlib.Path(fname).parent.resolve())

            wx.CallAfter(self._load_settings, fname)

    def _create_file_dialog(self, mode, desc, name='Motor homing files',
        ext='*.json'):

        f = None

        if mode == wx.FD_OPEN:
            filters = name + ' (' + ext + ')|' + ext + '|All files (*.*)|*.*'
            dialog = wx.FileDialog( None, style = mode, wildcard = filters,
                defaultDir = self._last_path)

        elif mode == wx.FD_SAVE:
            desc = desc.replace('/', '_')
            filters = name + ' ('+ext+')|'+ext
            dialog = wx.FileDialog(None, style=mode|wx.FD_OVERWRITE_PROMPT,
                wildcard=filters, defaultDir=self._last_path,
                defaultFile=desc+'.json')

        # Show the dialog and get user input
        if dialog.ShowModal() == wx.ID_OK:
            f = dialog.GetPath()

        # Destroy the dialog
        dialog.Destroy()

        return f

    def _on_start_home(self, evt):
        self._start_home()

    def _on_stop_home(self, evt):
        self._stop_home()

    def _start_home(self):
        home_settings = self._get_home_settings()

        valid, errors = self._validate_home_settings(home_settings)

        if valid:
            self._start_home_btn.Disable()
            self._stop_home_btn.Enable()

            motor = self._motor_panel.epics_motor

            self._home_controller.start_home(motor, **home_settings)

        else:
            err_str = ('The following errors were found in homing settings. '
                'Correct these errors and then start the homing again:\n- ')
            err_str += '\n- '.join(errors)

            wx.MessageBox(err_str, 'Errors in homing settings',wx.OK, self)

    def _stop_home(self):
        self._home_controller.abort_home()

    def _on_status_update(self, status):
        wx.CallAfter(self._update_status, status)

    def _update_status(self, status):
        self._home_status.SetLabel(status)

        if status.lower() in ('done', 'aborted', 'error'):
            self._on_home_done()

    def _on_home_done(self):
        self._start_home_btn.Enable()
        self._stop_home_btn.Disable()

    def on_close(self):
        """Device specific stuff goes here"""
        self._home_controller.remove_status_callback(self._on_status_update)

    def on_exit(self):
        self.Close()


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
    'home_to'       : 'plus',
    'final_pos'     : 0.,
    'offset'        : 0.,
    'speed'         : 1.,
    'cycles'        : 3,
    'move_off'      : 1.,
    'step'          : 0.05,
    'ignore_lim'    : True,
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


