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

class ScanProcess(multiprocessing.Process):
    """
    This is a separate Process (as opposed to Thread) that runs the ``Mp``
    scan. It has to be a Process because even in a new Thread the scan
    eats all processing resources and essentially locks the GUI while it's
    running.
    """

    def __init__(self, command_queue, return_queue, abort_event):
        """
        Initializes the Process.

        :param multiprocessing.Manager.Queue command_queue: This queue is used
            to pass commands to the scan process.

        :param multiprocessing.Manager.Queue return_queue: This queue is used
            to return values from the scan process.

        :param multiprocessing.Manager.Event abort_event: This event is set when
            a scan needs to be aborted.
        """
        multiprocessing.Process.__init__(self)
        self.daemon = True

        self.command_queue = command_queue
        self.return_queue = return_queue
        self._abort_event = abort_event
        self._stop_event = multiprocessing.Event()

        mp.set_user_interrupt_function(self._stop_scan)

        self._commands = {'start_mxdb'      : self._start_mxdb,
                        'set_scan_params'   : self._set_scan_params,
                        'scan'              : self._scan,
                        }

    def run(self):
        """
        Runs the process. It waits for commands to show up in the command_queue,
        and then runs them. It is aborted if the abort_event is set. It is stopped
        when the stop_event is set, and that allows the process to end gracefully.
        """
        while True:
            try:
                cmd, args, kwargs = self.command_queue.get_nowait()
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

        if self._stop_event.is_set():
            self._stop_event.clear()
        else:
            self._abort()

    def _start_mxdb(self, db_path):
        """
        Starts the MX database

        :param str db_path: The path to the MX database.
        """
        self.db_path = db_path
        self.mx_database = mp.setup_database(self.db_path)
        self.mx_database.set_plot_enable(2)

    def _set_scan_params(self, device, start, stop, step, scalers,
        dwell_time, timer, detector=None, file_name=None, dir_path=None):
        """
        Sets the parameters for the scan.

        :param str device: The MX record name.
        :param float start: The absolute start position of the scan.
        :param float stop: The absolute stop position of the scan.
        :param float step: The step size of the scan.
        :param list scalers: A list of the scalers for the scan.
        :param float dwell_time: The count time at each point in the scan.
        :param str timer: The name of the timer to be used for the scan.
        :param str detector: Currently not used. The name of the detector
            to be used for the scan.
        :param str file_name: The scan name (and output name) for the scan.
            Currently not used.
        :param str dir_path: The directory path where the scan file will be
            saved. Currently not used.
        """
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
        Constructs and MX scan record and then carries out the scan. It also
        communicates with the :mod:`ScanPanel` to send the filename for live
        plotting of the scan.
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

        self.mx_database.create_record_from_description(description)

        scan = self.mx_database.get_record(scan_name)

        scan.finish_record_initialization()

        self.return_queue.put_nowait([datafile_name])

        scan.perform_scan()

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

    def _stop_scan(self):
        """
        This function is used Mp to abort the scan.

        :returns: Returns 1 if the abort event is set, and that causes Mp to
            abort the running scan. Returns 0 otherwise, which doesn't abort
            anything.
        :rtype: int
        """
        return int(self._abort_event.is_set())

class ScanPanel(wx.Panel):
    """
    This creates the scan panel with both scan controls and the live plot. It
    allows both relative and absolute scans. THe user defines the start, stop,
    and step. It allows the user to define the counter (scaler) and count time.
    It also allows the user to fit the scan or derivative. Finally, it calculates
    various parameters (COM, FWHM), and allows the user to move to those positions
    or to any point in the scan.
    """
    def __init__(self, device_name, device, server_record, mx_database, *args, **kwargs):
        """
        Initializes the scan panel. Accepts the usual wx.Panel arguments plus
        the following.

        :param str device_name: The MX record name of the device.
        :param Mp.Record device: The Mp record (i.e. the device)
        :param Mp.Record server_record: The Mp record for the server that the
            device is located on.
        :param Mp.RecordList mx_database: The Mp record list representing the
            MX database being used.
        """
        wx.Panel.__init__(self, *args, **kwargs)

        self.device_name = device_name
        self.mx_database = mx_database
        self.device = device
        self.server_record = server_record
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

        self.live_plt_evt = threading.Event()

        self.Bind(wx.EVT_CLOSE, self._on_closewindow)

        self._initialize_variables()
        self._create_layout()

        self._start_scan_mxdb()

    def _create_layout(self):
        """Creates the layout of both the controls and the plots."""

        if self.type == 'network_motor':
            # server_record_name = self.device.get_field("server_record")
            # server_record = self.mx_database.get_record(server_record_name) #Invokes MX bug
            remote_record_name = self.device.get_field("remote_record_name")

            pos_name = "{}.position".format(remote_record_name)
            pos = custom_widgets.CustomValue(self, self.server_record, pos_name,
                function=custom_widgets.network_value_callback, args=(self.scale, self.offset))
            dname = wx.StaticText(self, label=self.device_name)

        elif self.type == 'epics_motor':
            pv = self.device.get_field('epics_record_name')

            pos = custom_widgets.CustomEpicsValue(self, "{}.RBV".format(pv),
                custom_widgets.epics_value_callback, self.scale, self.offset)
            self.pos = wx.StaticText(self, label='{}'.format(self.device.get_position()))
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
        self.start = wx.TextCtrl(self, value='', size=(80, -1))
        self.stop = wx.TextCtrl(self, value='', size=(80, -1))
        self.step = wx.TextCtrl(self, value='', size=(80, -1))
        self.count_time = wx.TextCtrl(self, value='0.1')
        self.scaler = wx.Choice(self, choices=scalers)
        self.timer = wx.Choice(self, choices=timers)
        # self.detector = wx.Choice(self, choices=detectors)

        if 'i0' in scalers:
            self.scaler.SetStringSelection('i0')
        if 'timer1' in timers:
            self.timer.SetStringSelection('timer1')

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
        # count_grid.Add(wx.StaticText(self, label='Detector:'))
        # count_grid.Add(self.detector)
        count_grid.AddGrowableCol(1)

        self.start_btn = wx.Button(self, label='Start')
        self.start_btn.Bind(wx.EVT_BUTTON, self._on_start)

        self.stop_btn = wx.Button(self, label='Stop')
        self.stop_btn.Bind(wx.EVT_BUTTON, self._on_stop)
        self.stop_btn.Disable()

        ctrl_btn_sizer = wx.BoxSizer(wx.HORIZONTAL)
        ctrl_btn_sizer.Add(self.start_btn)
        ctrl_btn_sizer.Add(self.stop_btn, border=5, flag=wx.LEFT)

        ctrl_sizer = wx.StaticBoxSizer(wx.StaticBox(self, label='Scan Controls'),
            wx.VERTICAL)
        ctrl_sizer.Add(type_sizer)
        ctrl_sizer.Add(mv_grid, border=5, flag=wx.EXPAND|wx.TOP)
        ctrl_sizer.Add(count_grid, border=5, flag=wx.EXPAND|wx.TOP)
        ctrl_sizer.Add(ctrl_btn_sizer, border=5, flag=wx.ALIGN_CENTER_HORIZONTAL|wx.TOP)


        self.show_der = wx.CheckBox(self, label='Show derivative')
        self.show_der.SetValue(False)
        self.show_der.Bind(wx.EVT_CHECKBOX, self._on_showder)

        self.flip_der = wx.CheckBox(self, label='Flip derivative')
        self.flip_der.SetValue(False)
        self.flip_der.Bind(wx.EVT_CHECKBOX, self._on_flipder)

        der_ctrl_sizer = wx.BoxSizer(wx.HORIZONTAL)
        der_ctrl_sizer.Add(self.show_der)
        der_ctrl_sizer.Add(self.flip_der, border=5, flag=wx.LEFT)

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
        plt_ctrl_sizer.Add(der_ctrl_sizer)
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
        scan_results.Add(wx.StaticText(self, label='FWHM cen.:'))
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
        self.disp_der_fit_label1 = wx.StaticText(self, label='Fit param.:')
        self.disp_der_fit_label2 = wx.StaticText(self, label='Fit param.:')
        self.disp_der_fit_p1 = wx.StaticText(self, label='')
        self.disp_der_fit_p2 = wx.StaticText(self, label='')

        der_results = wx.FlexGridSizer(rows=3, cols=4, vgap=5, hgap=2)
        der_results.Add(wx.StaticText(self, label='FWHM:'), flag=wx.RESERVE_SPACE_EVEN_IF_HIDDEN)
        der_results.Add(self.disp_der_fwhm, flag=wx.RESERVE_SPACE_EVEN_IF_HIDDEN)
        der_results.Add(wx.StaticText(self, label='FWHM cen.:'), flag=wx.RESERVE_SPACE_EVEN_IF_HIDDEN)
        der_results.Add(self.disp_der_fwhm_pos, flag=wx.RESERVE_SPACE_EVEN_IF_HIDDEN)
        der_results.Add(wx.StaticText(self, label='COM pos.:'), flag=wx.RESERVE_SPACE_EVEN_IF_HIDDEN)
        der_results.Add(self.disp_der_com, flag=wx.RESERVE_SPACE_EVEN_IF_HIDDEN)
        der_results.Add((1,1), flag=wx.RESERVE_SPACE_EVEN_IF_HIDDEN)
        der_results.Add((1,1), flag=wx.RESERVE_SPACE_EVEN_IF_HIDDEN)
        der_results.Add(self.disp_der_fit_label1, flag=wx.RESERVE_SPACE_EVEN_IF_HIDDEN)
        der_results.Add(self.disp_der_fit_p1, flag=wx.RESERVE_SPACE_EVEN_IF_HIDDEN)
        der_results.Add(self.disp_der_fit_label2, flag=wx.RESERVE_SPACE_EVEN_IF_HIDDEN)
        der_results.Add(self.disp_der_fit_p2, flag=wx.RESERVE_SPACE_EVEN_IF_HIDDEN)

        self.der_results_sizer = wx.BoxSizer(wx.VERTICAL)
        self.der_results_sizer.Add(wx.StaticText(self, label='Derivative:'), flag=wx.RESERVE_SPACE_EVEN_IF_HIDDEN)
        self.der_results_sizer.Add(der_results, border=5, flag=wx.TOP|wx.RESERVE_SPACE_EVEN_IF_HIDDEN)

        self.move_to = wx.Choice(self, choices=['FWHM center', 'COM position'])
        self.move_to.SetSelection(0)
        self.move = wx.Button(self, label='Move')
        self.move.Bind(wx.EVT_BUTTON, self._on_moveto)

        move_to_sizer = wx.BoxSizer(wx.HORIZONTAL)
        move_to_sizer.Add(wx.StaticText(self, label='Move to:'))
        move_to_sizer.Add(self.move_to, border=5, flag=wx.LEFT)
        move_to_sizer.Add(self.move, border=5, flag=wx.LEFT)

        save_btn = wx.Button(self, label='Save Scan Results')
        save_btn.Bind(wx.EVT_BUTTON, self._on_saveresults)


        self.scan_results_sizer = wx.StaticBoxSizer(wx.StaticBox(self, label='Scan Results'),
            wx.VERTICAL)
        self.scan_results_sizer.Add(wx.StaticText(self, label='Scan:'))
        self.scan_results_sizer.Add(scan_results, border=5, flag=wx.TOP|wx.BOTTOM)
        self.scan_results_sizer.Add(wx.StaticLine(self, style=wx.LI_HORIZONTAL),
            border=10, flag=wx.LEFT|wx.RIGHT|wx.EXPAND)
        self.scan_results_sizer.Add(self.der_results_sizer, border=5,
            flag=wx.TOP|wx.BOTTOM|wx.RESERVE_SPACE_EVEN_IF_HIDDEN)
        self.scan_results_sizer.Add(wx.StaticLine(self, style=wx.LI_HORIZONTAL),
            border=10, flag=wx.LEFT|wx.RIGHT|wx.EXPAND)
        self.scan_results_sizer.Add(move_to_sizer, border=5, flag=wx.TOP)
        self.scan_results_sizer.Add(save_btn, border=5, flag=wx.TOP|wx.ALIGN_CENTER_HORIZONTAL)

        self.scan_results_sizer.Hide(self.der_results_sizer, recursive=True)


        scan_sizer = wx.BoxSizer(wx.VERTICAL)
        scan_sizer.Add(info_sizer, flag=wx.EXPAND)
        scan_sizer.Add(ctrl_sizer, flag=wx.EXPAND)
        scan_sizer.Add(plt_ctrl_sizer, flag=wx.EXPAND)
        scan_sizer.Add(self.scan_results_sizer, flag=wx.EXPAND)


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
        self.canvas.mpl_connect('motion_notify_event', self._on_mousemotion)
        self.canvas.mpl_connect('pick_event', self._on_pickevent)

        plot_sizer = wx.BoxSizer(wx.VERTICAL)
        plot_sizer.Add(self.canvas, 1, flag=wx.EXPAND)
        plot_sizer.Add(self.toolbar, 0, flag=wx.EXPAND)

        top_sizer = wx.BoxSizer(wx.HORIZONTAL)
        top_sizer.Add(scan_sizer)
        top_sizer.Add(plot_sizer, 1, flag=wx.EXPAND)

        self.SetSizer(top_sizer)

    def _initialize_variables(self):
        """Initializes the variables related to plotting and fitting."""
        self.plt_line = None
        self.der_line = None
        self.plt_y = None
        self.plt_x = None
        self.der_y_orig = None
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

    def _on_start(self, evt):
        """
        Called when the start scan button is pressed. It gets the scan
        parameters and then puts the scan in the ``cmd_q``.
        """
        self.start_btn.Disable()
        self.stop_btn.Enable()
        scan_params = self._get_params()

        if scan_params is not None:
            if scan_params['start'] < scan_params['stop']:
                self.plot.set_xlim(scan_params['start'], scan_params['stop'])
            else:
                self.plot.set_xlim(scan_params['stop'], scan_params['start'])

            self.initial_position = self.device.get_position()
            self.scan_timer.Start(10)

            self.cmd_q.put_nowait(['set_scan_params', [], scan_params])
            self.cmd_q.put_nowait(['scan', [], {}])

    def _on_stop(self, evt):
        """
        Called when the stop button is pressed. Aborts the scan and live
        plotting
        """
        self.abort_event.set()
        time.sleep(0.5) #Wait for the process to abort before trying to reload the db
        self.return_q.put_nowait(['stop_live_plotting'])

    def _get_params(self):
        """
        Gets the scan parameters from the GUI and returns them.

        :returns: A dictionary of the scan parameters.
        :rtype: dict
        """
        if self.scan_type.GetStringSelection() == 'Absolute':
            offset = 0
        else:
            offset = self.device.get_position()
        try:
            start = float(self.start.GetValue())+offset
            stop = float(self.stop.GetValue())+offset

            if start < stop:
                step = abs(float(self.step.GetValue()))
            else:
                step = -abs(float(self.step.GetValue()))
            scan_params = {'device'     : self.device_name,
                        'start'         : start,
                        'stop'          : stop,
                        'step'          : step,
                        'scalers'       : [self.scaler.GetStringSelection()],
                        'dwell_time'    : float(self.count_time.GetValue()),
                        'timer'         : self.timer.GetStringSelection(),
                        # 'detector'      : self.detector.GetStringSelection(),
                        'detector'      : 'None'
                        }
        except ValueError:
            msg = 'All of start, stop, step, and count time must be numbers.'
            wx.MessageBox(msg, "Failed to start scan", wx.OK)
            return None

        if scan_params['detector'] == 'None':
            scan_params['detector'] = None

        return scan_params

    def _start_scan_mxdb(self):
        """Loads the mx database in the scan process"""
        mxdir = utils.get_mxdir()
        database_filename = os.path.join(mxdir, "etc", "mxmotor.dat")
        database_filename = os.path.normpath(database_filename)
        self.cmd_q.put_nowait(['start_mxdb', [database_filename], {}])

    def _on_scantimer(self, evt):
        """
        .. todo::
            Once the MP bug is fixed, remove the hack that restarts the scan
            process after the end of every scan.

        Called while the scan is running. It starts the live plotting at the
        start of the scan, and stops the live plotting at the end. Also at
        the end it moves the motor back to the initial position, restarts
        the scan process (needed because of an MP bug), and enables/disables
        the start/stop buttons as appropriate.
        """
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

            self.start_btn.Enable()
            self.stop_btn.Disable()

    def _ax_redraw(self, widget=None):
        """Redraw plots on window resize event."""

        self.background = self.canvas.copy_from_bbox(self.plot.bbox)
        self.der_background = self.canvas.copy_from_bbox(self.der_plot.bbox)

        self.update_plot()

    def _safe_draw(self):
        """A safe draw call that doesn 't endlessly recurse."""
        self.canvas.mpl_disconnect(self.cid)
        self.canvas.draw()
        self.cid = self.canvas.mpl_connect('draw_event', self._ax_redraw)

    def update_plot(self):
        """
        Updates the plot. Is long and complicated because there are many plot
        elements and we blit all of them. It also accounts for the derivative
        plot sometimes being shown and sometimes not.
        """
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
        """
        This does the live plotting. It is intended to be run in its own
        thread. It first clears all of the plot related variables and clears
        the plot. It then enters a loop where it reads from the scan file
        and plots the points as they come in, until the scan ends.

        :param str filename: The filename of the scan file to live plot.
        """
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
        self.der_y_orig = []
        self.der_y = []
        self.plt_fit_x = []
        self.plt_fit_y = []
        self.der_fit_y = []

        self.scan_header = ''

        self.fwhm = None
        self.der_fwhm = None
        self.plt_fitparams = None
        self.der_fitparams = None
        self.com = None
        self.der_com = None

        wx.CallAfter(self.update_plot)
        wx.CallAfter(self._update_results)
        wx.Yield()

        if not os.path.exists(filename):
            time.sleep(0.1)

        with open(filename) as thefile:
            data = utils.file_follow(thefile, self.live_plt_evt)
            for val in data:
                if self.live_plt_evt.is_set():
                    break
                if val.startswith('#'):
                    self.scan_header = self.scan_header + val
                else:
                    x, y = val.strip().split()
                    self.plt_x.append(float(x))
                    self.plt_y.append(float(y))
                    self._calc_fit('plt', self.plt_fit.GetStringSelection(), False)
                    self._calc_fwhm('plt', False)
                    self._calc_com('plt', False)

                    if len(self.plt_y) > 1:
                        self.der_y_orig = np.gradient(self.plt_y, self.plt_x)
                        self.der_y_orig[np.isnan(self.der_y_orig)] = 0
                        if self.flip_der.IsChecked():
                            self.der_y = self.der_y_orig*-1
                        else:
                            self.der_y = self.der_y_orig
                        self._calc_fit('der', self.der_fit.GetStringSelection(), False)
                        self._calc_fwhm('der', False)
                        self._calc_com('der', False)

                    wx.CallAfter(self.update_plot)
                    wx.CallAfter(self._update_results)
                    wx.Yield()

        os.remove(filename)

    def _on_mousemotion(self, event):
        """
        Called on mouse motion in the plot. If the mouse is in the plot the
        location is shown in the plot toolbar.
        """
        if event.inaxes:
            x, y = event.xdata, event.ydata
            self.toolbar.set_status('x={}, y={}'.format(x, y))
        else:
            self.toolbar.set_status('')

    def _on_closewindow(self, event):
        """
        .. todo:: This doesn't seem to work as expected. Investigate.

        Called when the scan window is closed.
        """
        print('in _on_closewindow!!!!!\n\n\n\n\n\n')
        self.scan_timer.Stop()
        self.scan_proc.stop()

        while self.scan_proc.is_alive():
            print('here')
            time.sleep(.01)

        self.Destroy()

    def _on_pickevent(self, event):
        """
        Called when a point on the plot is clicked on. If the click is a right
        click, it opens a context menu.
        """
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
        """
        Shows a context menu when users right click on a plot point. It allows
        the user to move to the selected point.

        :param float position: The position the user selected.
        """
        menu = wx.Menu()

        menu.Append(1, 'Move to {}'.format(position))
        self.Bind(wx.EVT_MENU, lambda event: self._on_popupmenu_choice(event, position))
        self.PopupMenu(menu)

        menu.Destroy()

    def _on_popupmenu_choice(self, event, position):
        """
        Moves the device to the selected plot point.

        :param float position: The position the user selected.
        """
        self.device.move_absolute(position)

    def _on_showder(self, event):
        """
        Toggles wehre the derivative plot is show, and whether the calculated
        parameters (fit, FWHM, COM) are shown.
        """
        if event.IsChecked():
            self.der_plot.set_visible(True)
            self.plot.set_position(self.plt_gs2[0].get_position(self.fig))
            self.der_plot.set_position(self.plt_gs2[1].get_position(self.fig))
            self.plot.xaxis.label.set_visible(False)
            for label in self.plot.get_xticklabels():
                label.set_visible(False)

            self.scan_results_sizer.Show(self.der_results_sizer, recursive=True)

            self.move_to.Set(['FWHM center', 'COM position', 'Der. FWHM center',
                'Der. COM position'])
        else:
            self.der_plot.set_visible(False)
            self.plot.set_position(self.plt_gs[0].get_position(self.fig))
            self.plot.xaxis.label.set_visible(True)
            self.plot.xaxis.set_major_formatter(matplotlib.ticker.ScalarFormatter())
            for label in self.plot.get_xticklabels():
                label.set_visible(True)

            self.scan_results_sizer.Hide(self.der_results_sizer, recursive=True)

            self.move_to.Set(['FWHM center', 'COM position'])

        self._safe_draw()
        self._ax_redraw()

    def _on_flipder(self, event):
        """Flips the derivative plot upside down (multiplication by -1)."""
        if event.IsChecked():
            if self.der_y_orig is not None and len(self.der_y_orig)>0:
                self.der_y = self.der_y_orig*-1
        else:
            if self.der_y_orig is not None and len(self.der_y_orig)>0:
                self.der_y = self.der_y_orig

        self._calc_fit('der', self.der_fit.GetStringSelection(), False)
        self._calc_fwhm('der', False)
        self._calc_com('der', False)

        self.update_plot()

    def _on_fitchoice(self, event):
        """
        Called when the fit choice is changed for either the main plot or the
        derivative plot. Calculates the fit as aproprite.
        """
        fit = event.GetString()

        if event.GetEventObject() == self.plt_fit:
            plot = 'plt'
        else:
            plot = 'der'

        self._calc_fit(plot, fit)

    def _calc_fit(self, plot, fit, update_plot=True):
        """
        Calculates the selected fit.

        :param str plot: A string indicating which plot the fit should be done on.
            Should be either 'plt' or 'der'.
        :param str fit: A string indicating the fit type (currently only Gaussian
            or None supported)
        :param bool update_plot: If True, the plot will be updated. If False it
            won't be updated.
        """
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
        """
        Called when the user decides to show/hide the FWHM on the plot.
        """
        if event.GetEventObject() == self.show_fwhm:
            plot = 'plt'
        else:
            plot = 'der'

        self._calc_fwhm(plot)

    def _calc_fwhm(self, plot, update_plot=True):
        """
        Calculates the FWHM of the scan or the derivative.

        :param str plot: A string indicating which plot the fit should be done on.
            Should be either 'plt' or 'der'.
        :param bool update_plot: If True, the plot will be updated. If False it
            won't be updated.
        """
        if plot == 'plt':
            ydata = self.plt_y
        else:
            ydata = self.der_y

        if self.plt_x is not None and len(self.plt_x)>3:
            y = ydata - np.max(ydata)/2
            if self.plt_x[0]>self.plt_x[1]:
                spline = scipy.interpolate.UnivariateSpline(self.plt_x[::-1], y[::-1], s=0)
            else:
                spline = scipy.interpolate.UnivariateSpline(self.plt_x, y, s=0)

            try:
                roots = spline.roots()
                if roots.size == 2:
                    r1 = roots[0]
                    r2 = roots[1]

                    if self.plt_x[1]>self.plt_x[0]:
                        if r1>r2:
                            index1 = np.searchsorted(self.plt_x, r1, side='right')
                            index2 = np.searchsorted(self.plt_x, r2, side='right')
                        else:
                            index1 = np.searchsorted(self.plt_x, r2, side='right')
                            index2 = np.searchsorted(self.plt_x, r1, side='right')

                        mean = np.mean(y[index1:index2])
                    else:
                        if r1>r2:
                            index1 = np.searchsorted(self.plt_x[::-1], r1, side='right')
                            index2 = np.searchsorted(self.plt_x[::-1], r2, side='right')
                        else:
                            index1 = np.searchsorted(self.plt_x[::-1], r2, side='right')
                            index2 = np.searchsorted(self.plt_x[::-1], r1, side='right')

                        mean = np.mean(y[::-1][index1:index2])

                    if mean<=0:
                        r1 = 0
                        r2 = 0

                elif roots.size>2:
                    max_diffs = np.argsort(abs(np.diff(roots)))[::-1]
                    for rmax in max_diffs:
                        r1 = roots[rmax]
                        r2 = roots[rmax+1]

                        if self.plt_x[1]>self.plt_x[0]:
                            if r1<r2:
                                index1 = np.searchsorted(self.plt_x, r1, side='right')
                                index2 = np.searchsorted(self.plt_x, r2, side='right')
                            else:
                                index1 = np.searchsorted(self.plt_x, r2, side='right')
                                index2 = np.searchsorted(self.plt_x, r1, side='right')

                            mean = np.mean(y[index1:index2])
                        else:
                            if r1<r2:
                                index1 = np.searchsorted(self.plt_x[::-1], r1, side='right')
                                index2 = np.searchsorted(self.plt_x[::-1], r2, side='right')
                            else:
                                index1 = np.searchsorted(self.plt_x[::-1], r2, side='right')
                                index2 = np.searchsorted(self.plt_x[::-1], r1, side='right')

                            mean = np.mean(y[::-1][index1:index2])

                        if mean>0:
                            break
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
        """
        Called when the user decides to show/hide the COM on the scan or der plot.
        """
        if event.GetEventObject() == self.show_com:
            plot = 'plt'
        else:
            plot = 'der'

        self._calc_com(plot)

    def _calc_com(self, plot, update_plot=True):
        """
        Calculates the COM of the scan or the derivative.

        :param str plot: A string indicating which plot the fit should be done on.
            Should be either 'plt' or 'der'.
        :param bool update_plot: If True, the plot will be updated. If False it
            won't be updated.
        """
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
        """Updates the results section of the GUI."""

        if self.fwhm is not None:
            self.disp_fwhm.SetLabel(str(round(self.fwhm[0], 4)))
            self.disp_fwhm_pos.SetLabel(str(round(((self.fwhm[2]+self.fwhm[1])/2.), 4)))

        if self.com is not None:
            self.disp_com.SetLabel(str(round(self.com, 4)))

        if self.der_fwhm is not None:
            self.disp_der_fwhm.SetLabel(str(round(self.der_fwhm[0], 4)))
            self.disp_der_fwhm_pos.SetLabel(str(round(((self.der_fwhm[2]+self.der_fwhm[1])/2.), 4)))

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

    def _on_moveto(self, event):
        """
        Called when the move to button is pressed. Moves the motor to the
        chosen position. One of: FWHM center, COM position, Der. FWHM position,
        Der. COM position.
        """
        choice = self.move_to.GetStringSelection()
        pos = None

        if choice == 'FWHM center':
            if self.fwhm is not None:
                pos = (self.fwhm[2]+self.fwhm[1])/2.

        elif choice == 'COM position':
            if self.com is not None:
                pos = self.com

        elif choice == 'Der. FWHM center':
            if self.fwhm is not None:
                pos = (self.der_fwhm[2]+self.der_fwhm[1])/2.

        elif choice == 'Der. COM position':
            if self.com is not None:
                pos = self.der_com

        if pos is not None:
            self.device.move_absolute(pos)

    def _on_saveresults(self, event):
        """
        Called when the save button is pressed. Saves the results, both of the
        scan and the fitting.
        """
        if self.plt_x is None or len(self.plt_x) == 0:
            wx.MessageBox('There are no scan results to save.', 'Failed to save results', wx.OK)
        else:
            path = os.path.normpath('./')
            msg = "Please select save directory and enter save file name"
            filters = 'Comma Separated Files (*.csv)|*.csv'
            dialog = wx.FileDialog(self, message = msg, style = wx.FD_SAVE,
                defaultDir = path, wildcard = filters, defaultFile='scan_results.csv')

            if dialog.ShowModal() == wx.ID_OK:
                path = dialog.GetPath()
            else:
                return
            dialog.Destroy()

            path=os.path.splitext(path)[0]+'.csv'

            results = [self.plt_x, self.plt_y]

            if self.show_der.IsChecked():
                results.append(self.der_y)

            with open(path, 'w') as f:
                f.write('# Scan Results\n')
                f.write(self.scan_header)
                f.write('# Scan FWHM: {}\n'.format(self.fwhm[0]))
                f.write('# Scan FWHM center: {}\n'.format((self.fwhm[2]+self.fwhm[1])/2.))
                f.write('# Scan COM: {}\n'.format(self.com))

                if self.plt_fit.GetStringSelection() == 'Gaussian':
                    f.write('# Scan fit type: Gaussian\n')
                    f.write('# Scan fit equation: A*exp(-(x-cen)**2/(2*std**2)\n')
                    f.write('# Scan fit A: {}\n'.format(self.plt_fitparams[0][0]))
                    f.write('# Scan fit cen: {}\n'.format(self.plt_fitparams[0][1]))
                    f.write('# Scan fit std: {}\n'.format(self.plt_fitparams[0][2]))

                if self.show_der.IsChecked():
                    f.write('# Derivative FWHM: {}\n'.format(self.der_fwhm[0]))
                    f.write('# Derivative FWHM center: {}\n'.format((self.der_fwhm[2]+self.der_fwhm[1])/2.))
                    f.write('# Derivative COM: {}\n'.format(self.der_com))

                if self.der_fit.GetStringSelection() == 'Gaussian':
                    f.write('# Derivative fit type: Gaussian\n')
                    f.write('# Derivative fit equation: A*exp(-(x-cen)**2/(2*std**2)\n')
                    f.write('# Derivative fit A: {}\n'.format(self.der_fitparams[0][0]))
                    f.write('# Derivative fit cen: {}\n'.format(self.der_fitparams[0][1]))
                    f.write('# Derivative fit std: {}\n'.format(self.der_fitparams[0][2]))

                f.write('scan_x, scan_y')
                if self.show_der.IsChecked():
                    f.write(', der_y\n')
                else:
                    f.write('\n')

                for i in range(len(results[0])):
                    data = ', '.join([str(results[j][i]) for j in range(len(results))])
                    f.write('{}\n'.format(data))

        return


def gaussian(x, A, cen, std):
    """
    The gaussian function used for fitting.

    :param float A: The overall scale factor of the gaussian
    :param float cen: The center position of the gaussian
    :param float std: The standard deviation of the gaussian
    """
    return A*np.exp(-(x-cen)**2/(2*std**2))

class CustomPlotToolbar(NavigationToolbar2WxAgg):
    """
    A custom plot toolbar that displays the cursor position on the plot
    in addition to the usual controls.
    """
    def __init__(self, parent, canvas):
        """
        Initializes the toolbar.

        :param wx.Window parent: The parent window
        :param matplotlib.Canvas: The canvas associated with the toolbar.
        """
        NavigationToolbar2WxAgg.__init__(self, canvas)

        self.status = wx.StaticText(self, label='')

        self.AddControl(self.status)

    def set_status(self, status):
        """
        Called to set the status text in the toolbar, i.e. the cursor position
        on the plot.
        """
        self.status.SetLabel(status)


class ScanFrame(wx.Frame):
    """
    A lightweight scan frame that holds the :mod:`ScanPanel`.
    """
    def __init__(self, device_name, device, server_record, mx_database, *args, **kwargs):
        """
        Initializes the scan frame. Takes all the usual wx.Frame arguments and
        also the following.

        :param str device_name: The MX record name of the device.
        :param Mp.Record device: The Mp record (i.e. the device)
        :param Mp.Record server_record: The Mp record for the server that the
            device is located on.
        :param Mp.RecordList mx_database: The Mp record list representing the
            MX database being used.
        """
        wx.Frame.__init__(self, *args, **kwargs)

        self._create_layout(device_name, device, server_record, mx_database)

        self.Fit()

    def _create_layout(self, device_name, device, server_record, mx_database):
        """
        Creates the layout, by calling mod:`ScanPanel`.

        :param str device_name: The MX record name of the device.
        :param Mp.Record device: The Mp record (i.e. the device)
        :param Mp.Record server_record: The Mp record for the server that the
            device is located on.
        :param Mp.RecordList mx_database: The Mp record list representing the
            MX database being used.
        """
        scan_panel = ScanPanel(device_name, device, server_record, mx_database, parent=self)

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
    device = mx_database.get_record('mtr1')
    if device.get_field('mx_type') == 'network_motor':
        server_record_name = device.get_field("server_record")
        server_record = mx_database.get_record(server_record_name)
    else:
        server_record = None

    app = wx.App()

    frame = ScanFrame('mtr1', device, server_record, mx_database, parent=None, title='Test Scan Control')
    frame.Show()
    app.MainLoop()

