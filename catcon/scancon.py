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

import multiprocessing
import queue
import tempfile
import os
import math

import wx

import custom_widgets
import utils
utils.set_mppath() #This must be done before importing any Mp Modules.
import Mp as mp
import MpCa as mpca
import MpWx as mpwx
import MpWxCa as mpwxca


class ScanProcess(multiprocessing.Process):

    def __init__(self, command_queue, return_queue, abort_event):
        multiprocessing.Process.__init__(self)
        self.daemon = True

        self.command_queue = command_queue
        self.return_queue = return_queue
        self._abort_event = abort_event
        self._stop_event = multiprocessing.Event()

        self._commands = {'start_mxdb'      : self._start_mxdb,
                        'set_scan_params'   : self._set_scan_params,
                        'scan'              : self._scan,
                        }

    def run(self):
        while True:
            try:
                cmd, args, kwargs = self.command_queue.get_nowait()
                print(cmd)
            except queue.Empty:
                cmd = None

            if self._abort_event.is_set():
                self._abort()
                cmd = None

            if self._stop_event.is_set():
                self._abort()
                break

            if cmd is not None:
                try:
                    self.working=True
                    self._commands[cmd](*args, **kwargs)
                    self.working=False
                except Exception as e:
                    self.working=False
                    print('What was that? Sorry, I could not run that command.')
                    print(e)

        if self._stop_event.is_set():
            self._stop_event.clear()
        else:
            self._abort()

    def _start_mxdb(self, db_path):
        self.db_path = db_path
        print("MX Database : %s is being downloaded..."%(self.db_path))
        self.mx_database = mp.setup_database(self.db_path)
        self.mx_database.set_plot_enable(2)
        print("Database has been set up")

    def _set_scan_params(self, device, start, stop, step, scalers,
        dwell_time, timer, detector=None, file_name=None, dir_path=None):
        self.out_path = dir_path
        self.out_name = file_name

        self.device = device
        self.start = start
        self.stop = stop
        self.step = step

        self.scalers = scalers
        self.dwell_time = dwell_time
        self.timer = timer
        self.detector = detector

    def _scan(self):
        """
        scan a record
        """
        all_names = [r.name for r in self.mx_database.get_all_records()]

        if self.out_name is not None:
            scan_name = self.out_name
        else:
            scan_name = self.device
            i=1
            while scan_name in all_names:
                if i == 1:
                    scan_name = "{}_{}".format(scan_name, str(i).zfill(2))
                else:
                    scan_name = "{}_{}".format(scan_name[:-2], str(i).zfill(2))
                i=i+1

        print("Scanning %s" % (scan_name))

        description = ('{} scan linear_scan motor_scan "" "" '.format(scan_name))

        num_scans = 1
        num_motors = 1
        num_independent_variables = num_motors

        description = description + ("{} {} {} {} ".format(num_scans,
            num_independent_variables, num_motors, str(self.device)))

        scalers_detector = list(self.scalers)

        if self.detector is not None:
            scalers_detector.append(self.detector['name'])

        description = description + ("{} ".format(len(scalers_detector)))

        for j in range(len(scalers_detector)):
            description = description + ("{} ".format(scalers_detector[j]))

        scan_flags = 0x0
        settling_time = 0.0
        measurement_type = "preset_time"
        measurement_time = self.dwell_time

        description = description + (
                '%x %f %s "%f %s" ' % (scan_flags, settling_time, measurement_type, measurement_time, self.timer))

        if self.out_path is None:
            standard_paths = wx.StandardPaths.Get()
            tmpdir = standard_paths.GetTempDir()
            fname = tempfile.NamedTemporaryFile(dir=tmpdir).name
        else:
            fname = os.path.join(self.out_path, self.out_name)

        datafile_description = "sff"
        datafile_name = fname
        plot_description = "none"
        plot_arguments = "$f[0]"

        description = description + (
                "%s %s %s %s " % (datafile_description, datafile_name, plot_description, plot_arguments))

        description = description + ("{} {} ".format(self.start, self.step))

        num_measurements = int(abs(math.floor((self.stop - self.start)/self.step)))
        description = description + ("{} ".format(num_measurements))

        print("Description = %s" % (description))

        self.mx_database.create_record_from_description(description)

        scan = self.mx_database.get_record(scan_name)

        scan.finish_record_initialization()

        self.return_queue.put_nowait([datafile_name])
        print(datafile_name)

        scan.perform_scan()

        print("%s has been performed" % (scan_name))

        self.return_queue.put_nowait(['stop_live_plotting'])

    def _abort(self):
        """Clears the ``command_queue`` and aborts all current actions."""
        while True:
            try:
                self.command_queue.get_nowait()
            except queue.Empty:
                break

        self._abort_event.clear()

    def stop(self):
        """Stops the thread cleanly."""
        self._stop_event.set()


class ScanPanel(wx.Panel):
    def __init__(self, device_name, mx_database, *args, **kwargs):
        wx.Panel.__init__(self, *args, **kwargs)

        self.device_name = device_name
        self.mx_database = mx_database
        self.device = self.mx_database.get_record(self.device_name)
        self.type = self.device.get_field('mx_type')
        self.scale = float(self.device.get_field('scale'))
        self.offset = float(self.device.get_field('offset'))

        self.cmd_q = multiprocessing.Queue()
        self.return_q = multiprocessing.Queue()
        self.abort_event = multiprocessing.Event()
        self.scan_proc = ScanProcess(self.cmd_q, self.return_q, self.abort_event)
        self.scan_proc.start()

        self.scan_timer = wx.Timer()
        self.scan_timer.Bind(wx.EVT_TIMER, self._on_scantimer)

        self._create_layout()

        self._start_scan_mxdb()

    def _create_layout(self):

        if self.type == 'network_motor':
            server_record_name = self.device.get_field("server_record")
            server_record = self.mx_database.get_record(server_record_name)
            remote_record_name = self.device.get_field("remote_record_name")

            pos_name = "{}.position".format(remote_record_name)
            pos = mpwx.Value(self, server_record, pos_name,
                function=custom_widgets.network_value_callback, args=(self.scale, self.offset))
            dname = wx.StaticText(self, label=self.device_name)

        elif self.type == 'epics_motor':
            pv = self.device.get_field('epics_record_name')

            pos = custom_widgets.CustomEpicsValue(self, "{}.RBV".format(pv),
                custom_widgets.epics_value_callback, self.scale, self.offset)
            dname = wx.StaticText(self, label='{} ({})'.format(self.device_name, pv))

        info_grid = wx.FlexGridSizer(rows=2, cols=2, vgap=5, hgap=5)
        info_grid.Add(wx.StaticText(self, label='Device name:'))
        info_grid.Add(dname)
        info_grid.Add(wx.StaticText(self, label='Current position:'))
        info_grid.Add(pos)

        info_sizer = wx.StaticBoxSizer(wx.StaticBox(self, label='Info'),
            wx.VERTICAL)
        info_sizer.Add(info_grid, wx.EXPAND)

        scalers = []
        timers = []
        detectors = ['None']
        for r in self.mx_database.get_all_records():
            mx_class = r.get_field('mx_class')

            if mx_class == 'scaler':
                scalers.append(r.name)
            elif mx_class == 'timer':
                timers.append(r.name)
            elif mx_class == 'area_detector':
                detectors.append(r.name)

        self.start = wx.TextCtrl(self)
        self.stop = wx.TextCtrl(self)
        self.step = wx.TextCtrl(self)
        self.count_time = wx.TextCtrl(self)
        self.scaler = wx.Choice(self, choices=scalers)
        self.timer = wx.Choice(self, choices=timers)
        self.detector = wx.Choice(self, choices=detectors)

        ctrl_grid = wx.FlexGridSizer(rows=7, cols=2, vgap=5, hgap=5)
        ctrl_grid.Add(wx.StaticText(self, label='Start:'))
        ctrl_grid.Add(self.start)
        ctrl_grid.Add(wx.StaticText(self, label='Stop:'))
        ctrl_grid.Add(self.stop)
        ctrl_grid.Add(wx.StaticText(self, label='Step size:'))
        ctrl_grid.Add(self.step)
        ctrl_grid.Add(wx.StaticText(self, label='Scaler:'))
        ctrl_grid.Add(self.scaler)
        ctrl_grid.Add(wx.StaticText(self, label='Count time:'))
        ctrl_grid.Add(self.count_time)
        ctrl_grid.Add(wx.StaticText(self, label='Timer:'))
        ctrl_grid.Add(self.timer)
        ctrl_grid.Add(wx.StaticText(self, label='Detector:'))
        ctrl_grid.Add(self.detector)
        ctrl_grid.AddGrowableCol(1)

        self.start_btn = wx.Button(self, label='Start')
        self.start_btn.Bind(wx.EVT_BUTTON, self._on_start)

        ctrl_sizer = wx.StaticBoxSizer(wx.StaticBox(self, label='Scan Controls'),
            wx.VERTICAL)
        ctrl_sizer.Add(ctrl_grid, flag=wx.EXPAND)
        ctrl_sizer.Add(self.start_btn, border=5, flag=wx.ALIGN_CENTER_HORIZONTAL|wx.TOP)

        top_sizer = wx.BoxSizer(wx.VERTICAL)
        top_sizer.Add(info_sizer)
        top_sizer.Add(ctrl_sizer)

        self.SetSizer(top_sizer)

    def _on_start(self ,evt):
        scan_params = self._get_params()

        print(scan_params)

        self.initial_position = self.device.get_position()
        self.scan_timer.Start(100)

        self.cmd_q.put_nowait(['set_scan_params', [], scan_params])
        self.cmd_q.put_nowait(['scan', [], {}])

    def _get_params(self):
        scan_params = {'device'     : self.device_name,
                    'start'         : float(self.start.GetValue()),
                    'stop'          : float(self.stop.GetValue()),
                    'step'          : float(self.step.GetValue()),
                    'scalers'       : [self.scaler.GetStringSelection()],
                    'dwell_time'    : float(self.count_time.GetValue()),
                    'timer'         : self.timer.GetStringSelection(),
                    'detector'      : self.detector.GetStringSelection(),
                    }

        if scan_params['detector'] == 'None':
            scan_params['detector'] = None

        return scan_params

    def _start_scan_mxdb(self):
        mxdir = utils.get_mxdir()
        database_filename = os.path.join(mxdir, "etc", "mxmotor.dat")
        database_filename = os.path.normpath(database_filename)
        self.cmd_q.put_nowait(['start_mxdb', [database_filename], {}])

    def _on_scantimer(self, evt):
        try:
            scan_return = self.return_q.get_nowait()[0]
        except queue.Empty:
            scan_return = None

        if scan_return is not None and scan_return != 'stop_live_plotting':
            # print(scan_return)
            # self.plot_panel.plot(scan_return)
            # wx.Yield()
            pass
        elif scan_return == 'stop_live_plotting':
            self.scan_timer.Stop()
            self.device.move_absolute(self.initial_position)



class ScanFrame(wx.Frame):
    def __init__(self, device, mx_database, *args, **kwargs):
        wx.Frame.__init__(self, *args, **kwargs)

        self._create_layout(device, mx_database)

        self.Fit()

    def _create_layout(self, device, mx_database):
        scan_panel = ScanPanel(device, mx_database, parent=self)

        top_sizer = wx.BoxSizer(wx.HORIZONTAL)
        top_sizer.Add(scan_panel)

        self.SetSizer(top_sizer)


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
    frame = ScanFrame('mtr1', mx_database, parent=None, title='Test Scan Control')
    frame.Show()
    app.MainLoop()

