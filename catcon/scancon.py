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
import threading
import time
import platform

import wx
import matplotlib
matplotlib.rcParams['backend'] = 'WxAgg'
from matplotlib.backends.backend_wxagg import NavigationToolbar2WxAgg
from matplotlib.backends.backend_wxagg import FigureCanvasWxAgg
import matplotlib.gridspec as gridspec
import numpy as np
import scipy.optimize
import scipy.interpolate

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
            fname=os.path.normpath('./{}'.format(os.path.split(fname)[-1]))
        else:
            fname = os.path.join(self.out_path, self.out_name)

        datafile_description = "sff"
        datafile_name = fname
        plot_description = "none"
        plot_arguments = "$f[0]"

        description = description + (
                "%s %s %s %s " % (datafile_description, datafile_name, plot_description, plot_arguments))

        description = description + ("{} {} ".format(self.start, self.step))

        num_measurements = int(abs(math.floor((self.stop - self.start)/self.step)))+1
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

        self.manager = multiprocessing.Manager()
        self.cmd_q = self.manager.Queue()
        self.return_q = self.manager.Queue()
        self.abort_event = self.manager.Event()
        self.scan_proc = ScanProcess(self.cmd_q, self.return_q, self.abort_event)
        self.scan_proc.start()

        self.scan_timer = wx.Timer()
        self.scan_timer.Bind(wx.EVT_TIMER, self._on_scantimer)

        self.plt_line = None
        self.der_line = None
        self.plt_y = None
        self.plt_x = None
        self.der_y = None

        self.plt_fit_line = None
        self.der_fit_line = None
        self.plt_fit_x = None
        self.plt_fit_y = None
        self.der_fit_y = None
        self.plt_fitparams = None
        self.der_fitparams = None

        self.fwhm = None
        self.der_fwhm = None
        self.fwhm_line = None
        self.der_fwhm_line = None

        self.com_line = None
        self.der_com_line = None
        self.com = None
        self.der_com = None

        self.live_plt_evt = threading.Event()

        self.Bind(wx.EVT_CLOSE, self._on_closewindow)

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
        info_grid.Add(wx.StaticText(self, label='Current position ({}):'.format(self.device.get_field('units'))))
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

        self.scan_type = wx.Choice(self, choices=['Absolute', 'Relative'])
        self.scan_type.SetSelection(1)
        self.start = wx.TextCtrl(self, value='-2')
        self.stop = wx.TextCtrl(self, value='2')
        self.step = wx.TextCtrl(self, value='0.5')
        self.count_time = wx.TextCtrl(self, value='0.1')
        self.scaler = wx.Choice(self, choices=scalers)
        self.timer = wx.Choice(self, choices=timers)
        self.detector = wx.Choice(self, choices=detectors)

        type_sizer =wx.BoxSizer(wx.HORIZONTAL)
        type_sizer.Add(wx.StaticText(self, label='Scan type:'))
        type_sizer.Add(self.scan_type, border=5, flag=wx.LEFT)

        mv_grid = wx.FlexGridSizer(rows=2, cols=3, vgap=5, hgap=5)
        mv_grid.Add(wx.StaticText(self, label='Start'))
        mv_grid.Add(wx.StaticText(self, label='Stop'))
        mv_grid.Add(wx.StaticText(self, label='Step'))
        mv_grid.Add(self.start)
        mv_grid.Add(self.stop)
        mv_grid.Add(self.step)


        count_grid = wx.FlexGridSizer(rows=4, cols=2, vgap=5, hgap=5)
        count_grid.Add(wx.StaticText(self, label='Count time (s):'))
        count_grid.Add(self.count_time)
        count_grid.Add(wx.StaticText(self, label='Timer:'))
        count_grid.Add(self.timer)
        count_grid.Add(wx.StaticText(self, label='Scaler:'))
        count_grid.Add(self.scaler)
        count_grid.Add(wx.StaticText(self, label='Detector:'))
        count_grid.Add(self.detector)
        count_grid.AddGrowableCol(1)

        self.start_btn = wx.Button(self, label='Start')
        self.start_btn.Bind(wx.EVT_BUTTON, self._on_start)

        ctrl_sizer = wx.StaticBoxSizer(wx.StaticBox(self, label='Scan Controls'),
            wx.VERTICAL)
        ctrl_sizer.Add(type_sizer)
        ctrl_sizer.Add(mv_grid, border=5, flag=wx.EXPAND|wx.TOP)
        ctrl_sizer.Add(count_grid, border=5, flag=wx.EXPAND|wx.TOP)
        ctrl_sizer.Add(self.start_btn, border=5, flag=wx.ALIGN_CENTER_HORIZONTAL|wx.TOP)


        self.show_der = wx.CheckBox(self, label='Show derivative')
        self.show_der.SetValue(False)
        self.show_der.Bind(wx.EVT_CHECKBOX, self._on_showder)

        self.plt_fit = wx.Choice(self, choices=['None', 'Gaussian'])
        self.der_fit = wx.Choice(self, choices=['None', 'Gaussian'])
        self.plt_fit.SetSelection(0)
        self.der_fit.SetSelection(0)
        self.plt_fit.Bind(wx.EVT_CHOICE, self._on_fitchoice)
        self.der_fit.Bind(wx.EVT_CHOICE, self._on_fitchoice)

        self.fit_sizer = wx.FlexGridSizer(rows=2, cols=2, vgap=5, hgap=5)
        self.fit_sizer.Add(wx.StaticText(self, label='Counts Fit:'))
        self.fit_sizer.Add(self.plt_fit)
        self.fit_sizer.Add(wx.StaticText(self, label='Derivative Fit:'))
        self.fit_sizer.Add(self.der_fit)

        self.show_fwhm = wx.CheckBox(self, label='Show FWHM')
        self.show_fwhm.SetValue(False)
        self.show_fwhm.Bind(wx.EVT_CHECKBOX, self._on_showfwhm)

        self.show_der_fwhm = wx.CheckBox(self, label='Show derivative FWHM')
        self.show_der_fwhm.SetValue(False)
        self.show_der_fwhm.Bind(wx.EVT_CHECKBOX, self._on_showfwhm)

        self.show_com = wx.CheckBox(self, label='Show COM')
        self.show_com.SetValue(False)
        self.show_com.Bind(wx.EVT_CHECKBOX, self._on_showcom)

        self.show_der_com = wx.CheckBox(self, label='Show derivative COM')
        self.show_der_com.SetValue(False)
        self.show_der_com.Bind(wx.EVT_CHECKBOX, self._on_showcom)

        calc_sizer = wx.FlexGridSizer(rows=2, cols=2, vgap=5, hgap=5)
        calc_sizer.Add(self.show_fwhm)
        calc_sizer.Add(self.show_der_fwhm)
        calc_sizer.Add(self.show_com)
        calc_sizer.Add(self.show_der_com)

        plt_ctrl_sizer = wx.StaticBoxSizer(wx.StaticBox(self, label='Plot Controls'),
            wx.VERTICAL)
        plt_ctrl_sizer.Add(self.show_der)
        plt_ctrl_sizer.Add(self.fit_sizer, border=5, flag=wx.TOP)
        plt_ctrl_sizer.Add(calc_sizer, border=5, flag=wx.TOP)


        self.disp_fwhm = wx.StaticText(self, label='', size=(60, -1))
        self.disp_fwhm_pos = wx.StaticText(self, label='', size=(60, -1))
        self.disp_com = wx.StaticText(self, label='', size=(60, -1))

        self.disp_fit_label1 = wx.StaticText(self, label='Fit param. 1:')
        self.disp_fit_label2 = wx.StaticText(self, label='Fit param. 2:')
        self.disp_fit_p1 = wx.StaticText(self, label='')
        self.disp_fit_p2 = wx.StaticText(self, label='')

        scan_results = wx.FlexGridSizer(rows=3, cols=4, vgap=5, hgap=2)
        scan_results.Add(wx.StaticText(self, label='FWHM:'))
        scan_results.Add(self.disp_fwhm)
        scan_results.Add(wx.StaticText(self, label='FWHM pos.:'))
        scan_results.Add(self.disp_fwhm_pos)
        scan_results.Add(wx.StaticText(self, label='COM pos.:'))
        scan_results.Add(self.disp_com)
        scan_results.Add((1,1))
        scan_results.Add((1,1))
        scan_results.Add(self.disp_fit_label1)
        scan_results.Add(self.disp_fit_p1)
        scan_results.Add(self.disp_fit_label2)
        scan_results.Add(self.disp_fit_p2)

        self.disp_der_fwhm = wx.StaticText(self, label='', size=(60, -1))
        self.disp_der_fwhm_pos = wx.StaticText(self, label='', size=(60, -1))
        self.disp_der_com = wx.StaticText(self, label='', size=(60, -1))
        self.disp_der_fit_label1 = wx.StaticText(self, label='Fit param. 1:')
        self.disp_der_fit_label2 = wx.StaticText(self, label='Fit param. 2:')
        self.disp_der_fit_p1 = wx.StaticText(self, label='')
        self.disp_der_fit_p2 = wx.StaticText(self, label='')

        der_results = wx.FlexGridSizer(rows=3, cols=4, vgap=5, hgap=2)
        der_results.Add(wx.StaticText(self, label='FWHM:'), flag=wx.RESERVE_SPACE_EVEN_IF_HIDDEN)
        der_results.Add(self.disp_der_fwhm, flag=wx.RESERVE_SPACE_EVEN_IF_HIDDEN)
        der_results.Add(wx.StaticText(self, label='FWHM pos.:'), flag=wx.RESERVE_SPACE_EVEN_IF_HIDDEN)
        der_results.Add(self.disp_der_fwhm_pos, flag=wx.RESERVE_SPACE_EVEN_IF_HIDDEN)
        der_results.Add(wx.StaticText(self, label='COM pos.:'), flag=wx.RESERVE_SPACE_EVEN_IF_HIDDEN)
        der_results.Add((1,1), flag=wx.RESERVE_SPACE_EVEN_IF_HIDDEN)
        der_results.Add((1,1), flag=wx.RESERVE_SPACE_EVEN_IF_HIDDEN)
        der_results.Add(self.disp_der_com, flag=wx.RESERVE_SPACE_EVEN_IF_HIDDEN)
        der_results.Add(self.disp_der_fit_label1, flag=wx.RESERVE_SPACE_EVEN_IF_HIDDEN)
        der_results.Add(self.disp_der_fit_p1, flag=wx.RESERVE_SPACE_EVEN_IF_HIDDEN)
        der_results.Add(self.disp_der_fit_label2, flag=wx.RESERVE_SPACE_EVEN_IF_HIDDEN)
        der_results.Add(self.disp_der_fit_p2, flag=wx.RESERVE_SPACE_EVEN_IF_HIDDEN)

        self.der_results_sizer = wx.BoxSizer(wx.VERTICAL)
        self.der_results_sizer.Add(wx.StaticText(self, label='Derivative:'), flag=wx.RESERVE_SPACE_EVEN_IF_HIDDEN)
        self.der_results_sizer.Add(der_results, border=5, flag=wx.TOP|wx.RESERVE_SPACE_EVEN_IF_HIDDEN)

        self.scan_results_sizer = wx.StaticBoxSizer(wx.StaticBox(self, label='Scan Results'),
            wx.VERTICAL)
        self.scan_results_sizer.Add(wx.StaticText(self, label='Scan:'))
        self.scan_results_sizer.Add(scan_results, border=5, flag=wx.TOP)
        self.scan_results_sizer.Add(self.der_results_sizer, border=5, flag=wx.TOP|wx.RESERVE_SPACE_EVEN_IF_HIDDEN)

        self.scan_results_sizer.Hide(self.der_results_sizer, recursive=True)


        scan_sizer = wx.BoxSizer(wx.VERTICAL)
        scan_sizer.Add(info_sizer)
        scan_sizer.Add(ctrl_sizer)
        scan_sizer.Add(plt_ctrl_sizer)
        scan_sizer.Add(self.scan_results_sizer)


        self.fig = matplotlib.figure.Figure()
        self.canvas = FigureCanvasWxAgg(self, -1, self.fig)
        self.canvas.SetBackgroundColour('white')
        self.toolbar = CustomPlotToolbar(self, self.canvas)
        self.toolbar.Realize()

        self.plt_gs = gridspec.GridSpec(1, 1)
        self.plt_gs2 = gridspec.GridSpec(2,1)

        self.plot = self.fig.add_subplot(self.plt_gs2[0], title='Scan')
        self.plot.set_ylabel('Scaler counts')
        self.plot.set_xlabel('Position ({})'.format(self.device.get_field('units')))

        self.der_plot = self.fig.add_subplot(self.plt_gs2[1], title='Derivative', sharex=self.plot)
        self.der_plot.set_ylabel('Derivative')
        self.der_plot.set_xlabel('Position ({})'.format(self.device.get_field('units')))

        self.der_plot.set_visible(False)
        self.plot.set_position(self.plt_gs[0].get_position(self.fig))

        self.cid = self.canvas.mpl_connect('draw_event', self._ax_redraw)
        self.canvas.callbacks.connect('motion_notify_event', self._on_mousemotion)
        self.canvas.callbacks.connect('pick_event', self._on_pickevent)

        plot_sizer = wx.BoxSizer(wx.VERTICAL)
        plot_sizer.Add(self.canvas, 1, flag=wx.EXPAND)
        plot_sizer.Add(self.toolbar, 0, flag=wx.EXPAND)

        top_sizer = wx.BoxSizer(wx.HORIZONTAL)
        top_sizer.Add(scan_sizer)
        top_sizer.Add(plot_sizer, 1, flag=wx.EXPAND)

        self.SetSizer(top_sizer)

    def _on_start(self ,evt):
        scan_params = self._get_params()

        self.plot.set_xlim(scan_params['start'], scan_params['stop'])
        print(scan_params)

        self.initial_position = self.device.get_position()
        self.scan_timer.Start(10)

        self.cmd_q.put_nowait(['set_scan_params', [], scan_params])
        self.cmd_q.put_nowait(['scan', [], {}])

    def _get_params(self):
        if self.scan_type.GetStringSelection() == 'Absolute':
            offset = 0
        else:
            offset = self.device.get_position()

        scan_params = {'device'     : self.device_name,
                    'start'         : float(self.start.GetValue())+offset,
                    'stop'          : float(self.stop.GetValue())+offset,
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
            self.live_plt_evt.clear()
            self.live_thread = threading.Thread(target=self.live_plot, args=(scan_return,))
            self.live_thread.daemon = True
            self.live_thread.start()
        elif scan_return == 'stop_live_plotting':
            self.scan_timer.Stop()
            self.live_plt_evt.set()
            self._update_results()
            self.device.move_absolute(self.initial_position)
            #This is a hack
            self.scan_proc.stop()
            self.scan_proc = ScanProcess(self.cmd_q, self.return_q, self.abort_event)
            self.scan_proc.start()
            self._start_scan_mxdb()

    def _ax_redraw(self, widget=None):
        ''' Redraw plots on window resize event '''

        self.background = self.canvas.copy_from_bbox(self.plot.bbox)
        self.der_background = self.canvas.copy_from_bbox(self.der_plot.bbox)

        self.update_plot()

    def _safe_draw(self):
        self.canvas.mpl_disconnect(self.cid)
        self.canvas.draw()
        self.cid = self.canvas.mpl_connect('draw_event', self._ax_redraw)

    def update_plot(self):
        get_plt_bkg = False
        get_der_bkg = False

        if self.plt_line is None:
            if (self.plt_x is not None and self.plt_y is not None and
                len(self.plt_x) == len(self.plt_y)) and len(self.plt_x) > 0:

                self.plt_pts, = self.plot.plot(self.plt_x, self.plt_y, 'bo', animated=True, picker=5)
                self.plt_line, = self.plot.plot(self.plt_x, self.plt_y, 'b-', animated=True)

                get_plt_bkg = True

        if self.der_line is None:
            if (self.plt_x is not None and self.der_y is not None and
                len(self.plt_x) == len(self.der_y) and len(self.plt_x) > 1):

                self.der_pts, = self.der_plot.plot(self.plt_x, self.der_y, 'bo', animated=True, picker=5)
                self.der_line, = self.der_plot.plot(self.plt_x, self.der_y, 'b-', animated=True)

                get_der_bkg = True

        if self.plt_fit_line is None:
            if (self.plt_fit_y is not None and len(self.plt_fit_x) == len(self.plt_fit_y)
                and len(self.plt_fit_y) > 0):

                self.plt_fit_line, = self.plot.plot(self.plt_fit_x, self.plt_fit_y, 'r-', animated=True)

                get_plt_bkg = True

        if self.der_fit_line is None:
            if (self.der_fit_y is not None and len(self.plt_fit_x) == len(self.der_fit_y)
                and len(self.der_fit_y) > 1):

                self.der_fit_line, = self.der_plot.plot(self.plt_fit_x, self.der_fit_y, 'r-', animated=True)

                get_der_bkg = True

        if self.fwhm_line is None:
            if self.fwhm is not None and self.show_fwhm.IsChecked() and self.fwhm[1] != self.fwhm[2]:
                self.fwhm_line = self.plot.axvspan(self.fwhm[1], self.fwhm[2],
                    facecolor='g', alpha=0., animated=True)

                get_plt_bkg = True

        if self.der_fwhm_line is None:
            if (self.der_fwhm is not None and self.show_der_fwhm.IsChecked()
                and self.der_fwhm[1] != self.der_fwhm[2]):
                self.der_fwhm_line = self.der_plot.axvspan(self.der_fwhm[1],
                    self.der_fwhm[2], facecolor='g', alpha=0.5, animated=True)

                get_der_bkg = True

        if self.com_line is None:
            if self.com is not None and self.show_com.IsChecked():
                self.com_line = self.plot.axvline(self.com, color='k',
                    linestyle='dashed', animated=True)

                get_plt_bkg = True

        if self.der_com_line is None:
            if self.der_com is not None and self.show_der_com.IsChecked():
                self.der_com_line = self.der_plot.axvline(self.der_com, color='k',
                    linestyle='dashed', animated=True)

                get_der_bkg = True

        if get_plt_bkg or get_der_bkg:
            self._safe_draw()

            if get_plt_bkg:
                self.background = self.canvas.copy_from_bbox(self.plot.bbox)
            if get_der_bkg:
                self.der_background = self.canvas.copy_from_bbox(self.der_plot.bbox)


        if self.plt_line is not None:
            self.plt_pts.set_xdata(self.plt_x)
            self.plt_pts.set_ydata(self.plt_y)
            self.plt_line.set_xdata(self.plt_x)
            self.plt_line.set_ydata(self.plt_y)

        if self.der_line is not None:
            self.der_pts.set_xdata(self.plt_x)
            self.der_pts.set_ydata(self.der_y)
            self.der_line.set_xdata(self.plt_x)
            self.der_line.set_ydata(self.der_y)

        if self.plt_fit_line is not None:
            self.plt_fit_line.set_xdata(self.plt_fit_x)
            self.plt_fit_line.set_ydata(self.plt_fit_y)

        if self.der_fit_line is not None:
            self.der_fit_line.set_xdata(self.plt_fit_x)
            self.der_fit_line.set_ydata(self.der_fit_y)

        if self.fwhm_line is not None:
            try:
                pts = self.fwhm_line.get_xy()
                x0 = self.fwhm[1]
                x1 = self.fwhm[2]
                pts[:,0] = [x0, x0, x1, x1, x0]
                self.fwhm_line.set_xy(pts)
            except ValueError:
                self.fwhm_line.remove()
                self.fwhm_line = None

        if self.der_fwhm_line is not None:
            try:
                pts = self.der_fwhm_line.get_xy()
                x0 = self.der_fwhm[1]
                x1 = self.der_fwhm[2]
                pts[:,0] = [x0, x0, x1, x1, x0]
                self.der_fwhm_line.set_xy(pts)
            except ValueError:
                self.der_fwhm_line.remove()
                self.der_fwhm_line = None

        if self.com_line is not None:
            self.com_line.set_xdata([self.com, self.com])

        if self.der_com_line is not None:
            self.der_com_line.set_xdata([self.der_com, self.der_com])

        redraw = False

        if self.plt_line is not None:
            oldx = self.plot.get_xlim()
            oldy = self.plot.get_ylim()

            self.plot.relim()
            self.plot.autoscale_view()

            newx = self.plot.get_xlim()
            newy = self.plot.get_ylim()

            if newx != oldx or newy != oldy:
                redraw = True

        if self.der_line is not None and self.show_der.GetValue():
            oldx = self.der_plot.get_xlim()
            oldy = self.der_plot.get_ylim()

            self.der_plot.relim()
            self.der_plot.autoscale_view()

            newx = self.der_plot.get_xlim()
            newy = self.der_plot.get_ylim()

            if newx != oldx or newy != oldy:
                redraw = True

        if redraw:
            self.canvas.mpl_disconnect(self.cid)
            self.canvas.draw()
            self.cid = self.canvas.mpl_connect('draw_event', self._ax_redraw)


        if self.plt_line is not None:
            self.canvas.restore_region(self.background)
            self.plot.draw_artist(self.plt_line)
            self.plot.draw_artist(self.plt_pts)

        if self.der_line is not None and self.show_der.GetValue():
            self.canvas.restore_region(self.der_background)
            self.der_plot.draw_artist(self.der_line)
            self.der_plot.draw_artist(self.der_pts)

        if self.plt_fit_line is not None:
            self.plot.draw_artist(self.plt_fit_line)

        if self.der_fit_line is not None and self.show_der.GetValue():
            self.der_plot.draw_artist(self.der_fit_line)

        if self.fwhm_line is not None:
            self.plot.draw_artist(self.fwhm_line)

        if self.der_fwhm_line is not None and self.show_der.GetValue():
            self.der_plot.draw_artist(self.der_fwhm_line)

        if self.com_line is not None:
            self.plot.draw_artist(self.com_line)

        if self.der_com_line is not None and self.show_der.GetValue():
            self.der_plot.draw_artist(self.der_com_line)


        self.canvas.blit(self.plot.bbox)

        if self.show_der.GetValue():
            self.canvas.blit(self.der_plot.bbox)

    def live_plot(self, filename):
        if self.plt_line is not None:
            self.plt_line.remove()
            self.plt_line = None
            self.plt_pts.remove()
            self.plt_pts = None

        if self.der_line is not None:
            self.der_line.remove()
            self.der_line = None
            self.der_pts.remove()
            self.der_pts = None

        if self.plt_fit_line is not None:
            self.plt_fit_line.remove()
            self.plt_fit_line = None

        if self.der_fit_line is not None:
            self.der_fit_line.remove()
            self.der_fit_line = None

        if self.fwhm_line is not None:
            self.fwhm_line.remove()
            self.fwhm_line = None

        if self.der_fwhm_line is not None:
            self.der_fwhm_line.remove()
            self.der_fwhm_line = None

        if self.com_line is not None:
            self.com_line.remove()
            self.com_line = None

        if self.der_com_line is not None:
            self.der_com_line.remove()
            self.der_com_line = None

        self.plt_x = []
        self.plt_y = []
        self.der_y = []
        self.plt_fit_x = []
        self.plt_fit_y = []
        self.der_fit_y = []

        self.fwhm = None
        self.der_fwhm = None
        self.plt_fitparams = None
        self.der_fitparams = None
        self.com = None
        self.der_com = None

        self.update_plot() #Is this threadsafe?
        wx.CallAfter(self._update_results)
        wx.Yield()

        if not os.path.exists(filename):
            time.sleep(0.01)

        with open(filename) as thefile:
            data = utils.file_follow(thefile, self.live_plt_evt)
            for val in data:
                if self.live_plt_evt.is_set():
                    break
                if not val.startswith('#'):
                    x, y = val.strip().split()
                    self.plt_x.append(float(x))
                    self.plt_y.append(float(y))
                    self._calc_fit('plt', self.plt_fit.GetStringSelection(), False)
                    self._calc_fwhm('plt', False)
                    self._calc_com('plt', False)

                    if len(self.plt_y) > 1:
                        self.der_y = np.gradient(self.plt_y, self.plt_x)
                        self.der_y[np.isnan(self.der_y)] = 0
                        self._calc_fit('der', self.der_fit.GetStringSelection(), False)
                        self._calc_fwhm('der', False)
                        self._calc_com('der', False)

                    self.update_plot() #Is this threadsafe?
                    wx.CallAfter(self._update_results)
                    wx.Yield()

        os.remove(filename)

    def _on_mousemotion(self, event):
        if event.inaxes:
            x, y = event.xdata, event.ydata
            self.toolbar.set_status('x={}, y={}'.format(x, y))
        else:
            self.toolbar.set_status('')

    def _on_closewindow(self, event):
        print('in _on_closewindow!!!!!\n\n\n\n\n\n')
        self.scan_timer.Stop()
        self.scan_proc.stop()

        while self.scan_proc.is_alive():
            print('here')
            time.sleep(.01)

        self.Destroy()

    def _on_pickevent(self, event):
        artist = event.artist
        button = event.mouseevent.button

        if button == 3:
            x = artist.get_xdata()
            ind = event.ind
            position = x[ind[0]]

            if int(wx.__version__.split('.')[0]) >= 3 and platform.system() == 'Darwin':
                wx.CallAfter(self._show_popupmenu, position)
            else:
                self._show_popupmenu(position)

    def _show_popupmenu(self, position):
        menu = wx.Menu()

        menu.Append(1, 'Move to {}'.format(position))
        self.Bind(wx.EVT_MENU, lambda event: self._on_popupmenu_choice(event, position))
        self.PopupMenu(menu)

        menu.Destroy()

    def _on_popupmenu_choice(self, event, position):
        self.device.move_absolute(position)

    def _on_showder(self, event):
        if event.IsChecked():
            self.der_plot.set_visible(True)
            self.plot.set_position(self.plt_gs2[0].get_position(self.fig))
            self.der_plot.set_position(self.plt_gs2[1].get_position(self.fig))
            self.plot.xaxis.label.set_visible(False)
            for label in self.plot.get_xticklabels():
                label.set_visible(False)

            self.scan_results_sizer.Show(self.der_results_sizer, recursive=True)
        else:
            self.der_plot.set_visible(False)
            self.plot.set_position(self.plt_gs[0].get_position(self.fig))
            self.plot.xaxis.label.set_visible(True)
            self.plot.xaxis.set_major_formatter(matplotlib.ticker.ScalarFormatter())
            for label in self.plot.get_xticklabels():
                label.set_visible(True)

            self.scan_results_sizer.Hide(self.der_results_sizer, recursive=True)

        self._safe_draw()
        self.update_plot()

    def _on_fitchoice(self, event):
        fit = event.GetString()

        if event.GetEventObject() == self.plt_fit:
            plot = 'plt'
        else:
            plot = 'der'

        self._calc_fit(plot, fit)

    def _calc_fit(self, plot, fit, update_plot=True):
        if plot == 'plt':
            ydata = self.plt_y
        else:
            ydata = self.der_y

        if fit == 'Gaussian':
            if self.plt_x is not None and len(self.plt_x) > 2:
                npts = int(100*(self.plt_x[-1] - self.plt_x[0])/(self.plt_x[1] - self.plt_x[0]))
                self.plt_fit_x = np.linspace(self.plt_x[0], self.plt_x[-1], npts)

                try:
                    opt, cov = scipy.optimize.curve_fit(gaussian, self.plt_x, ydata)
                    if plot == 'plt':
                        self.plt_fit_y = gaussian(self.plt_fit_x, opt[0], opt[1], opt[2])
                        self.plt_fitparams = [opt, cov]
                    else:
                        self.der_fit_y = gaussian(self.plt_fit_x, opt[0], opt[1], opt[2])
                        self.der_fitparams = [opt, cov]

                except RuntimeError:
                    if plot == 'plt':
                        self.plt_fit_y = np.zeros_like(self.plt_fit_x)
                    else:
                        self.der_fit_y = np.zeros_like(self.plt_fit_x)


        elif fit == 'None':
            if plot == 'plt':
                if self.plt_fit_line is not None:
                    self.plt_fit_line.remove()
                    self.plt_fit_line = None
                    self.plt_fit_y = []
            else:
                if self.der_fit_line is not None:
                    self.der_fit_line.remove()
                    self.der_fit_line = None
                    self.der_fit_y = []

        if update_plot:
            self.update_plot()
            wx.CallAfter(self._update_results)

    def _on_showfwhm(self, event):
        if event.GetEventObject() == self.show_fwhm:
            plot = 'plt'
        else:
            plot = 'der'

        self._calc_fwhm(plot)

    def _calc_fwhm(self, plot, update_plot=True):
        if plot == 'plt':
            ydata = self.plt_y
        else:
            ydata = self.der_y

        if self.plt_x is not None and len(self.plt_x)>3:
            if self.plt_x[0]>self.plt_x[1]:
                spline = scipy.interpolate.UnivariateSpline(self.plt_x[::-1], ydata[::-1], s=0)
            else:
                spline = scipy.interpolate.UnivariateSpline(self.plt_x, ydata, s=0)

            try:
                roots = spline.roots()
                if roots.size == 2:
                    r1 = roots[0]
                    r2 = roots[1]
                elif roots.size>2:
                    rmax = np.argmax(abs(np.diff(roots)))
                    r1 = roots[rmax]
                    r2 = roots[rmax+1]
                else:
                    r1 = 0
                    r2 = 0
            except Exception:
              r1 = 0
              r2 = 0

            fwhm = np.fabs(r2-r1)

            if plot == 'plt':
                if r1 < r2:
                    self.fwhm = (fwhm, r1, r2)
                else:
                    self.fwhm = (fwhm, r2, r1)

                if not self.show_fwhm.IsChecked() and self.fwhm_line is not None:
                    self.fwhm_line.remove()
                    self.fwhm_line = None
            else:
                if r1 < r2:
                    self.der_fwhm = (fwhm, r1, r2)
                else:
                    self.der_fwhm = (fwhm, r2, r1)
                if not self.show_der_fwhm.IsChecked() and self.der_fwhm_line is not None:
                    self.der_fwhm_line.remove()
                    self.der_fwhm_line = None

        if update_plot:
            self.update_plot()
            wx.CallAfter(self._update_results)

    def _on_showcom(self, event):
        if event.GetEventObject() == self.show_com:
            plot = 'plt'
        else:
            plot = 'der'

        self._calc_com(plot)

    def _calc_com(self, plot, update_plot=True):
        if plot == 'plt':
            ydata = self.plt_y
        else:
            ydata = self.der_y

        if self.plt_x is not None and len(self.plt_x)>0:
            ydata = np.array(ydata)
            xdata = np.array(self.plt_x)
            scale = 1/ydata.sum()
            if not np.isfinite(scale):
                scale = 1
            com = (scale)*(np.sum(xdata*ydata))

            if plot == 'plt':
                self.com = com

                if not self.show_com.IsChecked() and self.com_line is not None:
                    self.com_line.remove()
                    self.com_line = None

            else:
                self.der_com = com

                if not self.show_der_com.IsChecked() and self.der_com_line is not None:
                    self.der_com_line.remove()
                    self.der_com_line = None

        if update_plot:
            self.update_plot()
            wx.CallAfter(self._update_results)

    def _update_results(self):

        if self.fwhm is not None:
            self.disp_fwhm.SetLabel(str(round(self.fwhm[0], 4)))
            self.disp_fwhm_pos.SetLabel(str(round(((self.fwhm[1]-self.fwhm[0])/2.), 4)))

        if self.com is not None:
            self.disp_com.SetLabel(str(round(self.com, 4)))

        if self.der_fwhm is not None:
            self.disp_der_fwhm.SetLabel(str(round(self.der_fwhm[0], 4)))
            self.disp_der_fwhm_pos.SetLabel(str(round(((self.der_fwhm[1]-self.der_fwhm[0])/2.), 4)))

        if self.der_com is not None:
            self.disp_der_com.SetLabel(str(round(self.der_com, 4)))

        if self.plt_fit.GetStringSelection() == 'None':
            self.disp_fit_label1.SetLabel('Fit param. 1:')
            self.disp_fit_label2.SetLabel('Fit param. 2:')
            self.disp_fit_p1.SetLabel('')
            self.disp_fit_p2.SetLabel('')

        elif self.plt_fit.GetStringSelection() == 'Gaussian':
            self.disp_fit_label1.SetLabel('Fit Center:')
            self.disp_fit_label2.SetLabel('Fit Std.:')
            self.disp_fit_p1.SetLabel(str(round(self.plt_fitparams[0][1],4)))
            self.disp_fit_p2.SetLabel(str(round(self.plt_fitparams[0][2],4)))

        if self.der_fit.GetStringSelection() == 'None':
            self.disp_der_fit_label1.SetLabel('Fit param. 1:')
            self.disp_der_fit_label2.SetLabel('Fit param. 2:')
            self.disp_der_fit_p1.SetLabel('')
            self.disp_der_fit_p2.SetLabel('')

        elif self.der_fit.GetStringSelection() == 'Gaussian':
            self.disp_der_fit_label1.SetLabel('Fit Center:')
            self.disp_der_fit_label2.SetLabel('Fit Std.:')
            self.disp_der_fit_p1.SetLabel(str(round(self.der_fitparams[0][1],4)))
            self.disp_der_fit_p2.SetLabel(str(round(self.der_fitparams[0][2],4)))


def gaussian(x, A, cen, std):
    return A*np.exp(-(x-cen)**2/(2*std**2))

class CustomPlotToolbar(NavigationToolbar2WxAgg):
    def __init__(self, parent, canvas):
        NavigationToolbar2WxAgg.__init__(self, canvas)

        self.status = wx.StaticText(self, label='')

        self.AddControl(self.status)

    def set_status(self, status):
        self.status.SetLabel(status)


class ScanFrame(wx.Frame):
    def __init__(self, device, mx_database, *args, **kwargs):
        wx.Frame.__init__(self, *args, **kwargs)

        self._create_layout(device, mx_database)

        self.Fit()

    def _create_layout(self, device, mx_database):
        scan_panel = ScanPanel(device, mx_database, parent=self)

        top_sizer = wx.BoxSizer(wx.HORIZONTAL)
        top_sizer.Add(scan_panel, 1, wx.EXPAND)

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

