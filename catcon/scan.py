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

### Note this is the standalone version, which is the one we currently use

from __future__ import absolute_import, division, print_function, unicode_literals
from builtins import object, range, map
from io import open
import six

import multiprocessing
import queue
import tempfile
import os
import math
import threading
import time
import platform
import glob
import traceback
import copy

import wx
import wx.lib.agw.genericmessagedialog as GMD
import matplotlib
import matplotlib.figure
matplotlib.rcParams['backend'] = 'WxAgg'
from matplotlib.backends.backend_wxagg import NavigationToolbar2WxAgg
from matplotlib.backends.backend_wxagg import FigureCanvasWxAgg
import matplotlib.gridspec as gridspec
import numpy as np
import scipy.optimize
import scipy.interpolate
import epics

import utils
utils.set_mppath() #This must be done before importing any Mp Modules.
import Mp as mp

os.sys.path.append('/usr/local/beamline-control-user/biocon')
import detectorcon

class ScanProcess(multiprocessing.Process):
    """
    This is a separate Process (as opposed to Thread) that runs the ``Mp``
    scan. It has to be a Process because even in a new Thread the scan
    eats all processing resources and essentially locks the GUI while it's
    running.
    """

    def __init__(self, command_queue, return_queue, return_val_q, abort_event):
        """
        Initializes the Process.

        :param multiprocessing.Manager.Queue command_queue: This queue is used
            to pass commands to the scan process.

        :param multiprocessing.Manager.Queue return_queue: This queue is used
            to return values from the scan process.

        :param multiprocessing.Manager.Queue return_val_q: This queue is used
            to return counter values from a detector scan.

        :param multiprocessing.Manager.Event abort_event: This event is set when
            a scan needs to be aborted.
        """
        multiprocessing.Process.__init__(self)
        self.daemon = True

        self.command_queue = command_queue
        self.return_queue = return_queue
        self.return_val_q = return_val_q
        self._abort_event = abort_event
        self._stop_event = multiprocessing.Event()

        self.motor_name = ''
        self.motor_name2 = ''

        self.shutter1_name = 'do_9'
        self.shutter2_name =  'do_6'

        self.shutter1 = None
        self.shutter2 = None

        self.det = None
        self.detector=None

        self._commands = {'start_mxdb'      : self._start_mxdb,
                        'set_scan_params'   : self._set_scan_params,
                        'scan'              : self._scan,
                        'get_devices'       : self._get_devices,
                        'get_position'      : self._get_position,
                        'get_position2'     : self._get_position2,
                        'move_abs'          : self._move_abs,
                        'move_abs2'         : self._move_abs2,
                        'get_det_params'    : self._get_det_params,
                        'open_shutters'     : self._open_shutters,
                        'close_shutters'    : self._close_shutters,
                        'abort_det'         : self._abort_det,
                        }

    def run(self):
        """
        Runs the process. It waits for commands to show up in the command_queue,
        and then runs them. It is aborted if the abort_event is set. It is stopped
        when the stop_event is set, and that allows the process to end gracefully.
        """
        mp.set_user_interrupt_function(self._stop_scan)

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
                except Exception:
                    traceback.print_exc()
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
        self.mx_database.set_program_name("scancon")

    def _get_devices(self):
        """
        Gets a list of all of the relevant devices and returns them to populate
        the scan GUI.

        :param list scaler_fields: A list of the scaler record types to return.
            Defined in the mxmap_config file.
        :param list det_fields: A list of the detector record types to return.
            Defined in the mxmap_config file.
        """
        scalers = []
        timers = []
        motors = []
        detectors = []

        for r in self.mx_database.get_all_records():
            mx_class = r.get_field('mx_class')

            name = r.name.encode('utf-8')
            if mx_class == 'scaler':
                scalers.append(name)
            elif mx_class == 'timer':
                timers.append(name)
            elif mx_class == 'motor':
                motors.append(name)
            elif mx_class == 'area_detector':
                detectors.append(name)

        motors = sorted(motors, key=lambda v: v.lower())
        timers = sorted(timers, key=lambda v: v.lower())
        scalers = sorted(scalers, key=lambda v: v.lower())
        detectors = sorted(detectors, key=lambda v: v.lower())

        self.return_queue.put_nowait([motors, scalers, timers, detectors])

    def _get_position(self, motor_name):
        if motor_name != self.motor_name:
            self.motor_name = motor_name
            self.motor = self.mx_database.get_record(motor_name)

        pos = self.motor.get_position()
        self.return_queue.put_nowait([pos])

    def _get_position2(self, motor_name):
        if motor_name != self.motor_name2:
            self.motor_name2 = motor_name
            self.motor2 = self.mx_database.get_record(motor_name)

        pos = self.motor2.get_position()
        self.return_queue.put_nowait([pos])

    def _move_abs(self, position):
        self.motor.move_absolute(position)

    def _move_abs2(self, position):
        self.motor2.move_absolute(position)

    def _open_shutters(self):
        """
        WARNING: Can't open/close mx device shutters (or send any mx commands) after
        doing a scan in MX, becauseof mx related bugs. We can work around this
        by using EPICS if the shutters are in EPICS, which is the case for now.
        Need to revisit, this is probably why shutters were closed in the main
        thread after the scan
        """
        if self.shutter1 is None:
            self.shutter1 = self.mx_database.get_record(self.shutter1_name)
            shutter1_type = self.shutter1.get_field('mx_type')
            if shutter1_type.startswith('epics'):
                self.shutter1_is_epics = True
                pv_name = self.shutter1.get_field('epics_variable_name')
                self.shutter1_pv = epics.get_pv(pv_name)
        if self.shutter2 is None:
            self.shutter2 = self.mx_database.get_record(self.shutter2_name)
            shutter2_type = self.shutter2.get_field('mx_type')
            if shutter2_type.startswith('epics'):
                self.shutter2_is_epics = True
                pv_name = self.shutter2.get_field('epics_variable_name')
                self.shutter2_pv = epics.get_pv(pv_name)

        if self.shutter1_is_epics:
            self.shutter1_pv.put(1, wait=True)
        else:
            self.shutter1.write(1)

        if self.shutter2_is_epics:
            self.shutter2_pv.put(0, wait=True)
        else:
            self.shutter2.write(0)

    def _close_shutters(self):
        if self.shutter1 is None:
            self.shutter1 = self.mx_database.get_record(self.shutter1_name)
            shutter1_type = self.shutter1.get_field('mx_type')
            if shutter1_type.startswith('epics'):
                self.shutter1_is_epics = True
                pv_name = self.shutter1.get_field('epics_variable_name')
                self.shutter1_pv = epics.get_pv(pv_name)
        if self.shutter2 is None:
            self.shutter2 = self.mx_database.get_record(self.shutter2_name)
            shutter2_type = self.shutter2.get_field('mx_type')
            if shutter2_type.startswith('epics'):
                self.shutter2_is_epics = True
                pv_name = self.shutter2.get_field('epics_variable_name')
                self.shutter2_pv = epics.get_pv(pv_name)

        if self.shutter1_is_epics:
            self.shutter1_pv.put(0, wait=True)
        else:
            self.shutter1.write(0)

        if self.shutter2_is_epics:
            self.shutter2_pv.put(1, wait=True)
        else:
            self.shutter2.write(1)

    def _abort_det(self, detector):
        old_detector = copy.copy(self.detector)
        self.detector = detector

        if old_detector != self.detector:
            self._get_detector()

        if self.det is not None:
            self.det.abort()

    def _set_scan_params(self, device, start, stop, step, device2, start2,
        stop2, step2, scalers, dwell_time, timer, scan_dim='1D', detector=None,
        file_name=None, dir_path=None, scalers_raw='', open_shutter=True, **kwargs):
        """
        Sets the parameters for the scan.

        :param str device: The MX record name for motor 1.
        :param float start: The absolute start position of the scan for motor 1.
        :param float stop: The absolute stop position of the scan for motor 1.
        :param float step: The step size of the scan for motor 1.
        :param str device2: The MX record name for motor 2.
        :param float start2: The absolute start position of the scan for motor 2.
        :param float stop2: The absolute stop position of the scan for motor 2.
        :param float step2: The step size of the scan for motor 2.
        :param list scalers: A list of the scalers for the scan.
        :param float dwell_time: The count time at each point in the scan.
        :param str timer: The name of the timer to be used for the scan.
        :param str scan_dim: The scan dimension (1D or 2D).
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

        self.device2 = device2
        self.start2 = start2
        self.stop2 = stop2
        self.step2 = step2

        self.scan_dim = scan_dim
        self.scalers = scalers
        self.dwell_time = dwell_time
        self.timer = timer

        self.open_shutter = open_shutter


        self.scalers_raw = scalers_raw

        old_detector = copy.copy(self.detector)
        self.detector = detector

        if old_detector != self.detector:
            self._get_detector()

    def _get_detector(self):
        if self.detector is not None:
            if self.detector == 'Eiger2 XE 9M':
                self.det = detectorcon.EPICSEigerDetector('18ID:EIG2:',
                    use_tiff_writer=False, use_file_writer=True,
                    photon_energy=12.0, images_per_file=1)

                self.ab_burst = self.mx_database.get_record('ab_burst')
                self.cd_burst = self.mx_database.get_record('cd_burst')
                self.ef_burst = self.mx_database.get_record('ef_burst')
                self.gh_burst = self.mx_database.get_record('gh_burst')
                self.srs_trig = self.mx_database.get_record('do_10')

            else:
                self.det = self.mx_database.get_record(self.detector)
                self.det.set_trigger_mode(1)

                server_record_name = self.det.get_field('server_record')
                remote_det_name = self.det.get_field('remote_record_name')
                server_record = self.mx_database.get_record(server_record_name)
                det_datadir_name = '{}.datafile_directory'.format(remote_det_name)
                det_datafile_name = '{}.datafile_pattern'.format(remote_det_name)

                self.det_datadir = mp.Net(server_record, det_datadir_name)
                self.det_filename = mp.Net(server_record, det_datafile_name)
        else:
            self.det = None

    def _get_det_params(self):
        if self.detector == 'Eiger2 XE 9M':
            self.return_queue.put((self.det.get_data_dir(), ))
        else:
            self.return_queue.put((self.det_datadir.get(), ))

    def _scan(self):
        """
        Constructs and MX scan record and then carries out the scan. It also
        communicates with the :mod:`ScanPanel` to send the filename for live
        plotting of the scan.
        """
        if self.detector is not None:
            self._my_scan()
        else:
            self._mx_scan()

    def _my_scan(self):
        timer = self.mx_database.get_record(self.timer)
        scalers = [self.mx_database.get_record(scl) for scl in self.scalers]

        start = float(self.start)
        stop = float(self.stop)
        step = abs(float(self.step))

        if start < stop:
            mtr1_positions = np.arange(start, stop, step)
            if mtr1_positions[-1] + step == stop:
                mtr1_positions = np.concatenate((mtr1_positions, np.array([stop])))
        else:
            mtr1_positions = np.arange(stop, start, step)
            if mtr1_positions[-1] + step == start:
                mtr1_positions = np.concatenate((mtr1_positions, np.array([start])))
            mtr1_positions = mtr1_positions[::-1]

        if self.scan_dim == '2D':
            start2 = float(self.start2)
            stop2 = float(self.stop2)
            step2 = abs(float(self.step2))

            if start2 < stop2:
                mtr2_positions = np.arange(start2, stop2, step2)
                if mtr2_positions[-1] + step2 == stop2:
                    mtr2_positions = np.concatenate((mtr2_positions, np.array([stop2])))
            else:
                mtr2_positions = np.arange(stop2, start2, step2)
                if mtr2_positions[-1] + step2 == start2:
                    mtr2_positions = np.concatenate((mtr2_positions, np.array([start2])))
                mtr2_positions = mtr2_positions[::-1]

            # Makes order match MX scan
            temp = copy.copy(mtr1_positions)
            mtr1_positions = copy.copy(mtr2_positions)
            mtr2_positions = temp

        if self._abort_event.is_set():
            self.return_queue.put_nowait(['stop_live_plotting'])
            return

        self.motor.move_absolute(mtr1_positions[0])

        self.return_queue.put_nowait(('dummy',))

        if self.detector == 'Eiger2 XE 9M' and self.scan_dim == '1D':
            image_name = 'scan'

            #Internally triggered, multiple images per file
            # # self.det.set_filename(image_name)
            # # self.det.set_trigger_mode('int_enable')
            # # self.det.set_manual_trigger(1)
            # # self.det.set_num_frames(len(mtr1_positions))

            # Internally tiggered, single image per file
            # self.det.set_trigger_mode('int_trig')
            # self.det.set_num_frames(1)
            # self.det.set_exp_time(self.dwell_time)
            # self.det.set_exp_period(self.dwell_time+0.0001)
            # # self.det.arm()

            #Externally triggered
            image_name = 'scan'

            self.det.set_filename(image_name)
            self.det.set_trigger_mode('ext_enable')
            self.det.set_num_frames(len(mtr1_positions))
            self.det.set_exp_time(self.dwell_time)
            self.det.set_exp_period(self.dwell_time+0.0001)

            self.ab_burst.setup(0.000001, 0.000000, 1, 0, 1, 2)
            self.cd_burst.setup(0.000001, 0.000000, 1, 0, 1, 2)
            self.ef_burst.setup(0.000001, 0.000000, 1, 0, 1, 2)
            self.gh_burst.setup(0.000001, 0.000000, 1, 0, 1, 2)

            self.ab_burst.arm()

            self.srs_trig.write( 1 )
            time.sleep(0.01)
            self.srs_trig.write( 0 )

            while (self.ab_burst.get_status() & 0x1) != 0:
                time.sleep(0.01)

            self.ab_burst.setup(self.dwell_time+0.0001, (self.dwell_time+0.0001)*(1.-1./1000.), 1, 0, 1, 2)
            self.cd_burst.setup(self.dwell_time+0.0001, (self.dwell_time+0.0001-self.dwell_time)/10.,
                1, self.dwell_time+(self.dwell_time+0.0001-self.dwell_time)/10., 1, 2)
            self.ef_burst.setup(self.dwell_time+0.0001, self.dwell_time, 1, 0, 1, 2)
            self.gh_burst.setup(self.dwell_time+0.0001, (self.dwell_time+0.0001)/1.1, 1, 0, 1, 2)

            self.ab_burst.stop()
            self.srs_trig.write( 0 )

            self.ab_burst.get_status() #Maybe need to clear this status?
            time.sleep(0.1)
            self.det.arm()
            self.ab_burst.arm()

        if self.open_shutter:
            self._open_shutters()

        for num, mtr1_pos in enumerate(mtr1_positions):

            if self.detector == 'Eiger2 XE 9M' and self.scan_dim == '2D':
                image_name = 'scan_{:03}'.format(num+1)

                self.det.set_filename(image_name)
                self.det.set_trigger_mode('int_trig')
                self.det.set_manual_trigger(1)
                self.det.set_num_frames(len(mtr2_positions))
                self.det.set_exp_time(self.dwell_time)
                self.det.set_exp_period(self.dwell_time+0.0001)
                self.det.arm()

            if mtr1_pos != mtr1_positions[0]:
                # logger.info('Moving motor 1 position to {}'.format(mtr1_pos))
                self.motor.move_absolute(mtr1_pos)
            # mtr1.wait_for_motor_stop()
            while self.motor.is_busy():
                time.sleep(0.01)
                if self._abort_event.is_set():
                    if self.detector == 'Eiger2 XE 9M':
                        self.det.abort()
                    self.motor.stop()
                    self.return_queue.put_nowait(['stop_live_plotting'])
                    return

            if self.scan_dim == '1D':
                self._measure(scalers, timer, mtr1_pos, num)

                if self._abort_event.is_set():
                    if self.detector == 'Eiger2 XE 9M':
                        self.det.abort()
                    self.return_queue.put_nowait(['stop_live_plotting'])
                    return

            elif self.scan_dim == '2D':
                self.motor2.move_absolute(mtr2_positions[0])

                for num2, mtr2_pos in enumerate(mtr2_positions):
                    if mtr2_pos != mtr2_positions[0]:
                        self.motor2.move_absolute(mtr2_pos)
                    # mtr1.wait_for_motor2_stop()
                    while self.motor2.is_busy():
                        time.sleep(0.01)
                        if self._abort_event.is_set():
                            if self.detector == 'Eiger2 XE 9M':
                                self.det.abort()
                            self.motor2.stop()
                            self.return_queue.put_nowait(['stop_live_plotting'])
                            return

                    self._measure(scalers, timer, mtr1_pos, num, mtr2_pos, num2)

                    if self._abort_event.is_set():
                        if self.detector == 'Eiger2 XE 9M':
                            self.det.abort()
                        self.return_queue.put_nowait(['stop_live_plotting'])
                        return

            if self._abort_event.is_set():
                if self.detector == 'Eiger2 XE 9M':
                    self.det.abort()
                self.return_queue.put_nowait(['stop_live_plotting'])
                return

        if self.open_shutter:
            self._close_shutters()

        if self.detector == 'Eiger2 XE 9M':
            while self.det.get_status() != 0:
                time.sleep(.01)
                if self._abort_event.is_set():
                    if self.detector == 'Eiger2 XE 9M':
                        self.det.abort()
                    # self.return_queue.put_nowait(['stop_live_plotting'])
                    return

        self.return_queue.put_nowait(['stop_live_plotting'])
        return

    def _measure(self, scalers, timer, mtr1_pos, num, mtr2_pos=0, num2=0):

        if self.scan_dim == '1D':
            image_name = 'scan_{:03}.tif'.format(num+1)

        elif self.scan_dim == '2D':
            image_name = 'scan_{:03}_{:03}.tif'.format(num+1, num2+1)

        if self.detector != 'Eiger2 XE 9M':
            self.det_filename.put(image_name)
        else:
            image_name = image_name.rstrip('.tif')

        for scaler in scalers:
            scaler.clear()

        timer.clear()

        if timer.is_busy():
            timer.stop()

        if self.detector == 'Eiger2 XE 9M':
            # Internally triggered
            # Sending manual triggers, multiple images per series
            # # self.det.trigger(wait=False)

            # Internally triggered, one image per series
            # self.det.set_filename(image_name)
            # self.det.arm()

            #Externally triggered
            self.srs_trig.write(1)
            time.sleep(0.01)
            self.srs_trig.write(0)

        timer.start(self.dwell_time)

        while timer.is_busy() != 0:
            time.sleep(.01)
            if self._abort_event.is_set():
                if self.detector == 'Eiger2 XE 9M':
                    self.det.abort()
                timer.stop()
                # self.return_queue.put_nowait(['stop_live_plotting'])
                return

        # # Internally triggered, when taking 1 image per series
        # if self.detector == 'Eiger2 XE 9M':
        #     while self.det.get_status() != 0:
        #         time.sleep(.01)
        #         if self._abort_event.is_set():
        #             if self.detector == 'Eiger2 XE 9M':
        #                 self.det.abort()
        #             # self.return_queue.put_nowait(['stop_live_plotting'])
        #             return

        # Externally triggered
        while True:
            status = self.ab_burst.get_status()
            if (status & 0x1) == 0:
                break
            else:
                time.sleep(0.1)

            if self._abort_event.is_set():
                if self.detector == 'Eiger2 XE 9M':
                    self.det.abort()
                return


        result = [str(scaler.read()) for scaler in scalers]

        if self.scalers_raw == 'i1/i0':
            ret_val = float(result[1])/float(result[0])
        else:
            ret_val = float(result[0])

        if self.scan_dim == '1D':
            self.return_val_q.put_nowait((mtr1_pos, ret_val))
        elif self.scan_dim == '2D':
            self.return_val_q.put_nowait((mtr1_pos, mtr2_pos, ret_val))

        print('Position 1: {}'.format(mtr1_pos))
        if self.scan_dim == '2D':
            print('Position 2: {}'.format(mtr2_pos))

        if self.scalers_raw == 'i1/i0':
            print('Intensity: {}'.format(result[1]/result[0]))
        else:
            print('Intensity: {}'.format(', '.join(result)))

        print('Image name: {}\n'.format(image_name))

    def _mx_scan(self):
        if self.open_shutter:
            self._open_shutters()

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

        if self.scan_dim == '1D':
            num_motors = 1
        elif self.scan_dim == '2D':
            num_motors = 2

        num_independent_variables = num_motors

        if self.scan_dim == '1D':
            description = description + ("{} {} {} {} ".format(num_scans,
                num_independent_variables, num_motors, str(self.device)))

        elif self.scan_dim == '2D':
            description = description + ("{} {} {} {} {} ".format(num_scans,
                num_independent_variables, num_motors, str(self.device2),
                str(self.device)))

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
            fname=os.path.normpath(os.path.expanduser('~/{}'.format(os.path.split(fname)[-1])))
        else:
            fname = os.path.join(self.out_path, self.out_name)

        datafile_description = "sff"
        datafile_name = fname
        plot_description = "none"
        plot_arguments = "$f[0]"

        description = description + (
                "%s %s %s %s " % (datafile_description, datafile_name, plot_description, plot_arguments))

        if self.scan_dim == '1D':
            description = description + ("{} {} ".format(self.start, self.step))

            num_measurements = int(abs(math.floor((self.stop - self.start)/self.step)))+1
            description = description + ("{} ".format(num_measurements))

        elif self.scan_dim == '2D':
            description = description + ("{} {} {} {} ".format(self.start2,
                self.start, self.step2, self.step))

            num_measurements = int(abs(math.floor((self.stop - self.start)/self.step)))+1
            num_measurements2 = int(abs(math.floor((self.stop2 - self.start2)/self.step2)))+1

            description = description + ("{} {} ".format(num_measurements2,
                num_measurements))

        self.mx_database.create_record_from_description(description)

        scan = self.mx_database.get_record(scan_name)

        scan.finish_record_initialization()

        self.return_queue.put_nowait([datafile_name])

        try:
            scan.perform_scan()
        except Exception:
            pass

        # Can't do close shutters in ehre because can't send mx commands
        # after doing a scan. Hence why it's done possibly twice in the main
        # thread
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
    def __init__(self, mx_database, *args, **kwargs):
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

        self.mx_database = mx_database

        self.manager = multiprocessing.Manager()
        self.cmd_q = self.manager.Queue()
        self.return_q = self.manager.Queue()
        self.return_val_q = self.manager.Queue()
        self.abort_event = self.manager.Event()
        self.scan_proc = ScanProcess(self.cmd_q, self.return_q, self.return_val_q,
            self.abort_event)
        self.scan_proc.start()

        self.scan_timer = wx.Timer()
        self.scan_timer.Bind(wx.EVT_TIMER, self._on_scantimer)

        self.update_timer = wx.Timer()
        self.update_timer.Bind(wx.EVT_TIMER, self._on_updatetimer)

        self.live_plt_evt = threading.Event()

        self._start_scan_mxdb()
        self._get_devices()
        self._initialize_variables()
        self._create_layout()

        self.Layout()

        self.cid = self.canvas.mpl_connect('draw_event', self._ax_redraw)

    def _FromDIP(self, size):
        # This is a hack to provide easy back compatibility with wxpython < 4.1
        try:
            return self.FromDIP(size)
        except Exception:
            return size

    def _create_layout(self):
        """Creates the layout of both the controls and the plots."""

        self.motor = wx.Choice(self, choices=self.motors)
        self.motor.Bind(wx.EVT_CHOICE, self._on_motorchoice)

        self.pos = wx.StaticText(self, label='')
        self.pos_label = wx.StaticText(self, label='Current position:')

        self.motor2 = wx.Choice(self, choices=self.motors)
        self.motor2.Bind(wx.EVT_CHOICE, self._on_motorchoice)

        self.pos2 = wx.StaticText(self, label='')
        self.pos_label2 = wx.StaticText(self, label='Current position:')

        info_grid = wx.FlexGridSizer(cols=2, vgap=self._FromDIP(5),
            hgap=self._FromDIP(5))
        info_grid.Add(wx.StaticText(self, label='Device 1:'),
            flag=wx.ALIGN_CENTER_VERTICAL)
        info_grid.Add(self.motor, flag=wx.ALIGN_CENTER_VERTICAL)
        info_grid.Add(self.pos_label, flag=wx.ALIGN_CENTER_VERTICAL)
        info_grid.Add(self.pos, flag=wx.ALIGN_CENTER_VERTICAL)

        self.info_grid2 = wx.FlexGridSizer(cols=2, vgap=self._FromDIP(5),
            hgap=self._FromDIP(5))
        self.info_grid2.Add(wx.StaticText(self, label='Device 2:'))
        self.info_grid2.Add(self.motor2)
        self.info_grid2.Add(self.pos_label2)
        self.info_grid2.Add(self.pos2)

        self.info_sizer = wx.StaticBoxSizer(wx.StaticBox(self, label='Info'),
            wx.VERTICAL)
        self.info_sizer.Add(info_grid, flag=wx.EXPAND|wx.ALL,
            border=self._FromDIP(5))
        self.info_sizer.Add(self.info_grid2, flag=wx.EXPAND|wx.ALL,
            border=self._FromDIP(5))
        self.info_sizer.Hide(self.info_grid2, recursive=True)

        self.scan_type = wx.Choice(self, choices=['Absolute', 'Relative'])
        self.scan_type.SetSelection(1)
        self.scan_dim = wx.Choice(self, choices=['1D', '2D'])
        self.scan_dim.SetSelection(0)
        self.scan_dim.Bind(wx.EVT_CHOICE, self._on_dimension)
        self.start = wx.TextCtrl(self, value='', size=self._FromDIP((80, -1)))
        self.stop = wx.TextCtrl(self, value='', size=self._FromDIP((80, -1)))
        self.step = wx.TextCtrl(self, value='', size=self._FromDIP((80, -1)))
        self.start2 = wx.TextCtrl(self, value='', size=self._FromDIP((80, -1)))
        self.stop2 = wx.TextCtrl(self, value='', size=self._FromDIP((80, -1)))
        self.step2 = wx.TextCtrl(self, value='', size=self._FromDIP((80, -1)))
        self.count_time = wx.TextCtrl(self, value='0.1')
        self.scaler = wx.Choice(self, choices=self.scalers)
        self.timer = wx.Choice(self, choices=self.timers)
        self.detector = wx.Choice(self, choices=self.detectors)

        if six.PY3:
            for i in range(len(self.scalers)):
                self.scalers[i] = self.scalers[i].decode()

            for i in range(len(self.timers)):
                self.timers[i] = self.timers[i].decode()

        if 'i0' in self.scalers:
            self.scaler.SetStringSelection('i0')
        if 'joerger_timer' in self.timers:
            self.timer.SetStringSelection('joerger_timer')
        self.detector.SetStringSelection('None')

        type_sizer =wx.BoxSizer(wx.HORIZONTAL)
        type_sizer.Add(wx.StaticText(self, label='Scan type:'),
            flag=wx.ALIGN_CENTER_VERTICAL)
        type_sizer.Add(self.scan_type, border=self._FromDIP(5),
            flag=wx.LEFT|wx.ALIGN_CENTER_VERTICAL)
        type_sizer.Add(self.scan_dim, border=self._FromDIP(5),
            flag=wx.LEFT|wx.ALIGN_CENTER_VERTICAL)

        mv_grid = wx.FlexGridSizer(cols=4, vgap=self._FromDIP(5),
            hgap=self._FromDIP(5))
        mv_grid.AddSpacer(1)
        mv_grid.Add(wx.StaticText(self, label='Start'),
            flag=wx.ALIGN_CENTER_VERTICAL)
        mv_grid.Add(wx.StaticText(self, label='Stop'),
            flag=wx.ALIGN_CENTER_VERTICAL)
        mv_grid.Add(wx.StaticText(self, label='Step'),
            flag=wx.ALIGN_CENTER_VERTICAL)
        mv_grid.Add(wx.StaticText(self, label='1:'),
            flag=wx.ALIGN_CENTER_VERTICAL)
        mv_grid.Add(self.start, flag=wx.ALIGN_CENTER_VERTICAL)
        mv_grid.Add(self.stop, flag=wx.ALIGN_CENTER_VERTICAL)
        mv_grid.Add(self.step, flag=wx.ALIGN_CENTER_VERTICAL)

        self.mv_grid2 = wx.FlexGridSizer(cols=4, vgap=self._FromDIP(5),
            hgap=self._FromDIP(5))
        self.mv_grid2.Add(wx.StaticText(self, label='2:'),
            flag=wx.ALIGN_CENTER_VERTICAL)
        self.mv_grid2.Add(self.start2, flag=wx.ALIGN_CENTER_VERTICAL)
        self.mv_grid2.Add(self.stop2, flag=wx.ALIGN_CENTER_VERTICAL)
        self.mv_grid2.Add(self.step2, flag=wx.ALIGN_CENTER_VERTICAL)


        count_grid = wx.FlexGridSizer(cols=2, vgap=self._FromDIP(5),
            hgap=self._FromDIP(5))
        count_grid.Add(wx.StaticText(self, label='Count time (s):'),
            flag=wx.ALIGN_CENTER_VERTICAL)
        count_grid.Add(self.count_time, flag=wx.ALIGN_CENTER_VERTICAL)
        count_grid.Add(wx.StaticText(self, label='Timer:'),
            flag=wx.ALIGN_CENTER_VERTICAL)
        count_grid.Add(self.timer, flag=wx.ALIGN_CENTER_VERTICAL)
        count_grid.Add(wx.StaticText(self, label='Scaler:'),
            flag=wx.ALIGN_CENTER_VERTICAL)
        count_grid.Add(self.scaler, flag=wx.ALIGN_CENTER_VERTICAL)
        count_grid.Add(wx.StaticText(self, label='Detector:'),
            flag=wx.ALIGN_CENTER_VERTICAL)
        count_grid.Add(self.detector, flag=wx.ALIGN_CENTER_VERTICAL)
        count_grid.AddGrowableCol(1)


        self.shutter = wx.CheckBox(self, label='Scan actuates shutter')
        self.shutter.SetValue(True)

        self.start_btn = wx.Button(self, label='Start')
        self.start_btn.Bind(wx.EVT_BUTTON, self._on_start)

        self.stop_btn = wx.Button(self, label='Stop')
        self.stop_btn.Bind(wx.EVT_BUTTON, self._on_stop)
        self.stop_btn.Disable()

        ctrl_btn_sizer = wx.BoxSizer(wx.HORIZONTAL)
        ctrl_btn_sizer.Add(self.start_btn, flag=wx.ALIGN_CENTER_VERTICAL)
        ctrl_btn_sizer.Add(self.stop_btn, border=self._FromDIP(5),
            flag=wx.LEFT|wx.ALIGN_CENTER_VERTICAL)

        self.ctrl_sizer = wx.StaticBoxSizer(wx.StaticBox(self, label='Scan Controls'),
            wx.VERTICAL)
        self.ctrl_sizer.Add(type_sizer)
        self.ctrl_sizer.Add(mv_grid, border=self._FromDIP(5),
            flag=wx.EXPAND|wx.TOP)
        self.ctrl_sizer.Add(self.mv_grid2, border=self._FromDIP(5),
            flag=wx.EXPAND|wx.TOP)
        self.ctrl_sizer.Add(count_grid, border=self._FromDIP(5),
            flag=wx.EXPAND|wx.TOP)
        self.ctrl_sizer.Add(self.shutter, border=self._FromDIP(5),
            flag=wx.EXPAND|wx.TOP)
        self.ctrl_sizer.Add(ctrl_btn_sizer, border=self._FromDIP(5),
            flag=wx.ALIGN_CENTER_HORIZONTAL|wx.TOP)

        self.ctrl_sizer.Hide(self.mv_grid2, recursive=True)


        self.show_der = wx.CheckBox(self, label='Show derivative')
        self.show_der.SetValue(False)
        self.show_der.Bind(wx.EVT_CHECKBOX, self._on_showder)

        self.flip_der = wx.CheckBox(self, label='Flip derivative')
        self.flip_der.SetValue(False)
        self.flip_der.Bind(wx.EVT_CHECKBOX, self._on_flipder)

        der_ctrl_sizer = wx.BoxSizer(wx.HORIZONTAL)
        der_ctrl_sizer.Add(self.show_der, flag=wx.ALIGN_CENTER_VERTICAL)
        der_ctrl_sizer.Add(self.flip_der, border=self._FromDIP(5),
            flag=wx.LEFT|wx.ALIGN_CENTER_VERTICAL)

        self.plt_fit = wx.Choice(self, choices=['None', 'Gaussian'])
        self.der_fit = wx.Choice(self, choices=['None', 'Gaussian'])
        self.plt_fit.SetSelection(0)
        self.der_fit.SetSelection(0)
        self.plt_fit.Bind(wx.EVT_CHOICE, self._on_fitchoice)
        self.der_fit.Bind(wx.EVT_CHOICE, self._on_fitchoice)

        self.fit_sizer = wx.FlexGridSizer(cols=2, vgap=self._FromDIP(5),
            hgap=self._FromDIP(5))
        self.fit_sizer.Add(wx.StaticText(self, label='Counts Fit:'),
            flag=wx.ALIGN_CENTER_VERTICAL)
        self.fit_sizer.Add(self.plt_fit, flag=wx.ALIGN_CENTER_VERTICAL)
        self.fit_sizer.Add(wx.StaticText(self, label='Derivative Fit:'),
            flag=wx.ALIGN_CENTER_VERTICAL)
        self.fit_sizer.Add(self.der_fit, flag=wx.ALIGN_CENTER_VERTICAL)

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

        calc_sizer = wx.FlexGridSizer(cols=2, vgap=self._FromDIP(5),
            hgap=self._FromDIP(5))
        calc_sizer.Add(self.show_fwhm, flag=wx.ALIGN_CENTER_VERTICAL)
        calc_sizer.Add(self.show_der_fwhm, flag=wx.ALIGN_CENTER_VERTICAL)
        calc_sizer.Add(self.show_com, flag=wx.ALIGN_CENTER_VERTICAL)
        calc_sizer.Add(self.show_der_com, flag=wx.ALIGN_CENTER_VERTICAL)

        plt_ctrl_sizer = wx.StaticBoxSizer(wx.StaticBox(self, label='Plot Controls'),
            wx.VERTICAL)
        plt_ctrl_sizer.Add(der_ctrl_sizer)
        plt_ctrl_sizer.Add(self.fit_sizer, border=self._FromDIP(5), flag=wx.TOP)
        plt_ctrl_sizer.Add(calc_sizer, border=self._FromDIP(5), flag=wx.TOP)


        self.disp_fwhm = wx.StaticText(self, label='',
            size=self._FromDIP((60, -1)))
        self.disp_fwhm_pos = wx.StaticText(self, label='',
            size=self._FromDIP((60, -1)))
        self.disp_com = wx.StaticText(self, label='',
            size=self._FromDIP((60, -1)))

        self.disp_fit_label1 = wx.StaticText(self, label='Fit param. 1:')
        self.disp_fit_label2 = wx.StaticText(self, label='Fit param. 2:')
        self.disp_fit_p1 = wx.StaticText(self, label='')
        self.disp_fit_p2 = wx.StaticText(self, label='')

        scan_results = wx.FlexGridSizer(cols=4, vgap=self._FromDIP(5), hgap=2)
        scan_results.Add(wx.StaticText(self, label='FWHM:'),
            flag=wx.ALIGN_CENTER_VERTICAL)
        scan_results.Add(self.disp_fwhm, flag=wx.ALIGN_CENTER_VERTICAL)
        scan_results.Add(wx.StaticText(self, label='FWHM cen.:'),
            flag=wx.ALIGN_CENTER_VERTICAL)
        scan_results.Add(self.disp_fwhm_pos, flag=wx.ALIGN_CENTER_VERTICAL)
        scan_results.Add(wx.StaticText(self, label='COM pos.:'),
            flag=wx.ALIGN_CENTER_VERTICAL)
        scan_results.Add(self.disp_com, flag=wx.ALIGN_CENTER_VERTICAL)
        scan_results.Add((1,1))
        scan_results.Add((1,1))
        scan_results.Add(self.disp_fit_label1, flag=wx.ALIGN_CENTER_VERTICAL)
        scan_results.Add(self.disp_fit_p1, flag=wx.ALIGN_CENTER_VERTICAL)
        scan_results.Add(self.disp_fit_label2, flag=wx.ALIGN_CENTER_VERTICAL)
        scan_results.Add(self.disp_fit_p2, flag=wx.ALIGN_CENTER_VERTICAL)

        self.disp_der_fwhm = wx.StaticText(self, label='',
            size=self._FromDIP((60, -1)))
        self.disp_der_fwhm_pos = wx.StaticText(self, label='',
            size=self._FromDIP((60, -1)))
        self.disp_der_com = wx.StaticText(self, label='',
            size=self._FromDIP((60, -1)))
        self.disp_der_fit_label1 = wx.StaticText(self, label='Fit param.:')
        self.disp_der_fit_label2 = wx.StaticText(self, label='Fit param.:')
        self.disp_der_fit_p1 = wx.StaticText(self, label='')
        self.disp_der_fit_p2 = wx.StaticText(self, label='')

        der_results = wx.FlexGridSizer(cols=4, vgap=self._FromDIP(5), hgap=2)
        der_results.Add(wx.StaticText(self, label='FWHM:'),
            flag=wx.RESERVE_SPACE_EVEN_IF_HIDDEN|wx.ALIGN_CENTER_VERTICAL)
        der_results.Add(self.disp_der_fwhm,
            flag=wx.RESERVE_SPACE_EVEN_IF_HIDDEN|wx.ALIGN_CENTER_VERTICAL)
        der_results.Add(wx.StaticText(self, label='FWHM cen.:'),
            flag=wx.RESERVE_SPACE_EVEN_IF_HIDDEN|wx.ALIGN_CENTER_VERTICAL)
        der_results.Add(self.disp_der_fwhm_pos,
            flag=wx.RESERVE_SPACE_EVEN_IF_HIDDEN|wx.ALIGN_CENTER_VERTICAL)
        der_results.Add(wx.StaticText(self, label='COM pos.:'),
            flag=wx.RESERVE_SPACE_EVEN_IF_HIDDEN|wx.ALIGN_CENTER_VERTICAL)
        der_results.Add(self.disp_der_com,
            flag=wx.RESERVE_SPACE_EVEN_IF_HIDDEN|wx.ALIGN_CENTER_VERTICAL)
        der_results.Add((1,1),
            flag=wx.RESERVE_SPACE_EVEN_IF_HIDDEN|wx.ALIGN_CENTER_VERTICAL)
        der_results.Add((1,1),
            flag=wx.RESERVE_SPACE_EVEN_IF_HIDDEN|wx.ALIGN_CENTER_VERTICAL)
        der_results.Add(self.disp_der_fit_label1,
            flag=wx.RESERVE_SPACE_EVEN_IF_HIDDEN|wx.ALIGN_CENTER_VERTICAL)
        der_results.Add(self.disp_der_fit_p1,
            flag=wx.RESERVE_SPACE_EVEN_IF_HIDDEN|wx.ALIGN_CENTER_VERTICAL)
        der_results.Add(self.disp_der_fit_label2,
            flag=wx.RESERVE_SPACE_EVEN_IF_HIDDEN|wx.ALIGN_CENTER_VERTICAL)
        der_results.Add(self.disp_der_fit_p2,
            flag=wx.RESERVE_SPACE_EVEN_IF_HIDDEN|wx.ALIGN_CENTER_VERTICAL)

        self.der_results_sizer = wx.BoxSizer(wx.VERTICAL)
        self.der_results_sizer.Add(wx.StaticText(self, label='Derivative:'),
            flag=wx.RESERVE_SPACE_EVEN_IF_HIDDEN)
        self.der_results_sizer.Add(der_results, border=self._FromDIP(5),
            flag=wx.TOP|wx.RESERVE_SPACE_EVEN_IF_HIDDEN)

        self.move_to = wx.Choice(self, choices=['FWHM center', 'COM position'])
        self.move_to.SetSelection(0)
        self.move = wx.Button(self, label='Move')
        self.move.Bind(wx.EVT_BUTTON, self._on_moveto)

        move_to_sizer = wx.BoxSizer(wx.HORIZONTAL)
        move_to_sizer.Add(wx.StaticText(self, label='Move to:'),
            flag=wx.ALIGN_CENTER_VERTICAL)
        move_to_sizer.Add(self.move_to, border=self._FromDIP(5),
            flag=wx.LEFT|wx.ALIGN_CENTER_VERTICAL)
        move_to_sizer.Add(self.move, border=self._FromDIP(5),
            flag=wx.LEFT|wx.ALIGN_CENTER_VERTICAL)

        save_btn = wx.Button(self, label='Save Scan Results')
        save_btn.Bind(wx.EVT_BUTTON, self._on_saveresults)


        self.scan_results_sizer = wx.StaticBoxSizer(wx.StaticBox(self, label='Scan Results'),
            wx.VERTICAL)
        self.scan_results_sizer.Add(wx.StaticText(self, label='Scan:'))
        self.scan_results_sizer.Add(scan_results, border=self._FromDIP(5),
            flag=wx.TOP|wx.BOTTOM)
        self.scan_results_sizer.Add(wx.StaticLine(self, style=wx.LI_HORIZONTAL),
            border=10, flag=wx.LEFT|wx.RIGHT|wx.EXPAND)
        self.scan_results_sizer.Add(self.der_results_sizer, border=self._FromDIP(5),
            flag=wx.TOP|wx.BOTTOM|wx.RESERVE_SPACE_EVEN_IF_HIDDEN)
        self.scan_results_sizer.Add(wx.StaticLine(self, style=wx.LI_HORIZONTAL),
            border=10, flag=wx.LEFT|wx.RIGHT|wx.EXPAND)
        self.scan_results_sizer.Add(move_to_sizer, border=self._FromDIP(5), flag=wx.TOP)
        self.scan_results_sizer.Add(save_btn, border=self._FromDIP(5),
            flag=wx.TOP|wx.BOTTOM|wx.ALIGN_CENTER_HORIZONTAL)

        self.scan_results_sizer.Hide(self.der_results_sizer, recursive=True)


        scan_sizer = wx.BoxSizer(wx.VERTICAL)
        scan_sizer.Add(self.info_sizer, flag=wx.EXPAND)
        scan_sizer.Add(self.ctrl_sizer, flag=wx.EXPAND)
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
        self.plot.set_xlabel('Position')

        self.der_plot = self.fig.add_subplot(self.plt_gs2[1], title='Derivative', sharex=self.plot)
        self.der_plot.set_ylabel('Derivative')
        self.der_plot.set_xlabel('Position')

        self.fig.subplots_adjust(left = 0.16, bottom = 0.07, right = 0.93,
            top = 0.95, hspace = 0.26)

        self.der_plot.set_visible(False)
        self.plot.set_position(self.plt_gs[0].get_position(self.fig))

        self.plot.set_zorder(2)
        self.der_plot.set_zorder(1)

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
        self.plt_image = None
        self.plt_x = None
        self.plt_y = None
        self.plt_z = None
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

        self.det_scan = False
        self.scan_dimension = 1

        self.motor_name = ''
        self.motor_name2 = ''

        self.current_scan_params = None

    def _get_devices(self):
        self.cmd_q.put_nowait(['get_devices', [], {}])
        self.motors, self.scalers, self.timers, self.detectors = self.return_q.get()
        self.detectors.insert(0, 'None')
        self.detectors.append('Eiger2 XE 9M')

        if (('i0' in self.scalers and 'i1' in self.scalers)
            or (b'i0' in self.scalers and b'i1' in self.scalers)):
            self.scalers.append('i1/i0'.encode('utf-8'))
            self.scalers = sorted(self.scalers, key=lambda v: v.lower())

    def _on_motorchoice(self, evt):
        if evt.GetEventObject() == self.motor:
            self.motor_name = self.motor.GetStringSelection()
        elif evt.GetEventObject() == self.motor2:
            self.motor_name2 = self.motor2.GetStringSelection()

        if not self.update_timer.IsRunning() and not self.scan_timer.IsRunning():
            self.update_timer.Start(100)

    def _on_dimension(self, evt):
        choice = self.scan_dim.GetStringSelection()

        if choice == '1D':
            self.info_sizer.Hide(self.info_grid2, recursive=True)
            self.ctrl_sizer.Hide(self.mv_grid2, recursive=True)
        elif choice == '2D':
            self.info_sizer.Show(self.info_grid2, recursive=True)
            self.ctrl_sizer.Show(self.mv_grid2, recursive=True)

        self.Layout()

    def _on_updatetimer(self, evt):
        if self.motor_name != '':
            self.cmd_q.put_nowait(['get_position', [self.motor_name], {}])
            pos = self.return_q.get()[0]

            self.pos.SetLabel(str(pos))

        if self.motor_name2 != '':
            self.cmd_q.put_nowait(['get_position2', [self.motor_name2], {}])
            pos = self.return_q.get()[0]

            self.pos2.SetLabel(str(pos))

    def _on_start(self, evt):
        """
        Called when the start scan button is pressed. It gets the scan
        parameters and then puts the scan in the ``cmd_q``.
        """
        scan_params = self._get_params()

        if scan_params is not None:
            self.start_btn.Disable()
            self.stop_btn.Enable()
            self.update_timer.Stop()

            while True:
                try:
                    self.return_q.get_nowait()
                except queue.Empty:
                    break

            while True:
                try:
                    self.cmd_q.get_nowait()
                except queue.Empty:
                    break

            if scan_params['scan_dim'] == '2D':
                self.scan_dimension = 2
            else:
                self.scan_dimension = 1

            if self.scan_dimension == 1:
                if scan_params['start'] < scan_params['stop']:
                    self.plot.set_xlim(scan_params['start'], scan_params['stop'])
                else:
                    self.plot.set_xlim(scan_params['stop'], scan_params['start'])

                self.plot.set_ylabel('Position')
                self.plot.set_ylabel('Scaler counts')

            else:
                start = scan_params['start']
                step = scan_params['step']
                stop = scan_params['stop']
                num_pos = int(abs(math.floor((stop - start)/step)))+1

                start2 = scan_params['start2']
                step2 = scan_params['step2']
                stop2 = scan_params['stop2']
                num_pos2 = int(abs(math.floor((stop2 - start2)/step2)))+1

                if start < stop:
                    self.x_pos = np.array([start+i*step for i in range(num_pos+1)]) #Need 1 extra point for pcolormesh
                else:
                    self.x_pos = np.array([stop-i*step for i in range(num_pos+1)])

                if start2 < stop2:
                    self.y_pos = np.array([start2+i*step2 for i in range(num_pos2+1)])
                else:
                    self.y_pos = np.array([stop2-i*step2 for i in range(num_pos2+1)])

                self.x_pos = self.x_pos - step/2.
                self.y_pos = self.y_pos - step2/2.

                self.plot.set_xlim(self.x_pos[0], self.x_pos[-1])
                self.plot.set_ylim(self.y_pos[0], self.y_pos[-1])

                self.plot.set_xlabel('Position 1')
                self.plot.set_ylabel('Position 2')

                self.grid = np.meshgrid(self.x_pos, self.y_pos)
                self.total_points = num_pos*num_pos2
                self.x_points = num_pos
                self.y_points = num_pos2

            if scan_params['detector'] is not None:
                self.det_scan = True
                self.det_name = scan_params['detector']
            else:
                self.det_scan = False
                self.det_name = None

            self.cmd_q.put_nowait(['set_scan_params', [], scan_params])
            # time.sleep(2)

            if self.det_scan:
                self.cmd_q.put_nowait(['get_det_params', [], {}])
                det_dir = self.return_q.get()
                cont = self._check_data_dir(det_dir[0])
            else:
                cont = True

            if cont:
                self.initial_position = float(self.pos.GetLabel())
                if self.scan_dimension == 2:
                    self.initial_position2 = float(self.pos2.GetLabel())
                self.scan_timer.Start(10)

                # if self.shutter.IsChecked():
                #     self.cmd_q.put_nowait(['open_shutters', [], {}])

                self.cmd_q.put_nowait(['scan', [], {}])

            else:
                self.start_btn.Enable()
                self.stop_btn.Disable()
                self.update_timer.Start()

    def _on_stop(self, evt):
        """
        Called when the stop button is pressed. Aborts the scan and live
        plotting
        """
        self.abort_event.set()

    def _get_params(self):
        """
        Gets the scan parameters from the GUI and returns them.

        :returns: A dictionary of the scan parameters.
        :rtype: dict
        """
        if self.scan_type.GetStringSelection() == 'Absolute':
            offset = 0
            offset2 = 0
        else:
            try:
                offset = float(self.pos.GetLabel())
            except ValueError:
                offset = 0
            try:
                offset2 = float(self.pos2.GetLabel())
            except ValueError:
                offset2 = 0

        scan_dim = self.scan_dim.GetStringSelection()

        try:
            start = float(self.start.GetValue())+offset
            stop = float(self.stop.GetValue())+offset

            if start < stop:
                step = abs(float(self.step.GetValue()))
            else:
                step = -abs(float(self.step.GetValue()))

            if scan_dim == '2D':
                start2 = float(self.start2.GetValue())+offset2
                stop2 = float(self.stop2.GetValue())+offset2

                if start2 < stop2:
                    step2 = abs(float(self.step2.GetValue()))
                else:
                    step2 = -abs(float(self.step2.GetValue()))
            else:
                start2 = 0
                stop2 = 0
                step2 = 0

            scan_params = {'device'     : self.motor_name,
                        'device2'       : self.motor_name2,
                        'start'         : start,
                        'stop'          : stop,
                        'step'          : step,
                        'start2'        : start2,
                        'stop2'         : stop2,
                        'step2'         : step2,
                        'scalers'       : [self.scaler.GetStringSelection()],
                        'scalers_raw'   : self.scaler.GetStringSelection(),
                        'dwell_time'    : float(self.count_time.GetValue()),
                        'timer'         : self.timer.GetStringSelection(),
                        'detector'      : self.detector.GetStringSelection(),
                        'scan_dim'      : scan_dim,
                        'open_shutter'  : self.shutter.IsChecked(),
                        }

        except ValueError:
            msg = 'All of start, stop, step, and count time must be numbers.'
            wx.MessageBox(msg, "Failed to start scan", wx.OK)
            return None

        if self.motor_name == '':
            msg = ('Must select a device to scan.')
            wx.MessageBox(msg, 'Failed to start scan', wx.OK)
            return None

        if self.motor_name2 == '' and scan_dim == '2D':
            msg = ('Must select a second device to scan.')
            wx.MessageBox(msg, 'Failed to start scan', wx.OK)
            return None

        if scan_params['detector'] == 'None':
            scan_params['detector'] = None

        if 'i1/i0' in scan_params['scalers']:
            scan_params['scalers'] = ['i0', 'i1']

        self.current_scan_params = scan_params

        return scan_params

    def _start_scan_mxdb(self):
        """Loads the mx database in the scan process"""
        self.cmd_q.put_nowait(['start_mxdb', [self.mx_database], {}])

    def _check_data_dir(self, det_datadir):
        scan_prefix = 'scan'
        print(det_datadir)

        if self.detector.GetStringSelection() == 'Eiger2 XE 9M':
            # det_datadir = det_datadir.replace('/nas_data', '/nas_data/Eiger2x')
            pass
        else:
            det_datadir = det_datadir.replace('/nas_data', '/nas_data/Pilatus1M')

        files = glob.glob(os.path.join(det_datadir, scan_prefix)+'*')

        if len(files) > 0:
            msg = ('Warning, there are other scan files in the selected '
                'directory ({}) that may be overwritten by this scan. '
                'Please select an action.'.format(det_datadir))

            dialog = GMD.GenericMessageDialog(self, msg, 'Scan images already exist',
                agwStyle=wx.ICON_EXCLAMATION|wx.YES_NO|wx.CANCEL, wrap=500)
            dialog.SetYesNoCancelLabels('Overwrite', 'Remove old scan', 'Abort')
            result = dialog.ShowModal()

            if result == wx.ID_YES:
                cont = True
                if self.detector.GetStringSelection() == 'Eiger2 XE 9M':
                    for f in files:
                        os.remove(f)
            elif result == wx.ID_NO:
                cont = True
                for f in files:
                    os.remove(f)
            else:
                cont = False

            return cont
        else:
            return True

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
            self._start_live_plot(scan_return)

        elif scan_return == 'stop_live_plotting':
            self.scan_timer.Stop()
            self.live_plt_evt.set()
            self._update_results()
            self._save_log()

            #This is a hack
            self.scan_proc.stop()
            self.cmd_q = self.manager.Queue()
            self.return_q = self.manager.Queue()
            self.return_val_q = self.manager.Queue()
            self.abort_event = self.manager.Event()
            self.scan_proc = ScanProcess(self.cmd_q, self.return_q, self.return_val_q,
                self.abort_event)
            self.scan_proc.start()
            self._start_scan_mxdb()

            if self.shutter.IsChecked():
                self.cmd_q.put_nowait(['close_shutters', [], {}])

            self.cmd_q.put_nowait(['get_position', [self.motor_name], {}])
            pos = self.return_q.get()[0]

            self.cmd_q.put_nowait(['move_abs', [self.initial_position], {}])

            if self.scan_dimension == 2:
                self.cmd_q.put_nowait(['get_position2', [self.motor_name2], {}])
                pos = self.return_q.get()[0]

                self.cmd_q.put_nowait(['move_abs2', [self.initial_position2], {}])

            if self.det_scan:
                self.cmd_q.put_nowait(['abort_det', [self.det_name], {}])

            self.start_btn.Enable()
            self.stop_btn.Disable()
            self.update_timer.Start(100)

    def _ax_redraw(self, widget=None):
        """Redraw plots on window resize event."""

        self.background = self.canvas.copy_from_bbox(self.plot.bbox)
        self.der_background = self.canvas.copy_from_bbox(self.der_plot.bbox)

        self.update_plot(False)

    def safe_draw(self):
        """A safe draw call that doesn 't endlessly recurse."""
        self.canvas.mpl_disconnect(self.cid)
        self.canvas.draw()
        self.cid = self.canvas.mpl_connect('draw_event', self._ax_redraw)

    def update_plot(self, rescale=True):
        """
        Updates the plot. Is long and complicated because there are many plot
        elements and we blit all of them. It also accounts for the derivative
        plot sometimes being shown and sometimes not.
        """

        if self.scan_dimension == 1:
            self._update_plot_1d(rescale)
        elif self.scan_dimension == 2:
            self._update_plot_2d(rescale)

    def _update_plot_1d(self, rescale=True):
        get_plt_bkg = False
        get_der_bkg = False

        if self.plt_image is not None:
            self.plt_image.remove()
            self.plt_image = None

        if self.plt_line is None:
            if (self.plt_x is not None and self.plt_y is not None and
                len(self.plt_x) == len(self.plt_y)) and len(self.plt_x) > 0:

                self.plt_pts, = self.plot.plot(self.plt_x, self.plt_y, 'bo', animated=True, picker=10)
                self.plt_line, = self.plot.plot(self.plt_x, self.plt_y, 'b-', animated=True)

                get_plt_bkg = True

        if self.der_line is None:
            if (self.plt_x is not None and self.der_y is not None and
                len(self.plt_x) == len(self.der_y) and len(self.plt_x) > 1):

                self.der_pts, = self.der_plot.plot(self.plt_x, self.der_y, 'bo', animated=True, picker=10)
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
                    facecolor='g', alpha=0.5, animated=True)

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
            self.safe_draw()

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
                x0 = self.fwhm[1]
                fwhm = self.fwhm[0]
                self.fwhm_line.set_x(x0)
                self.fwhm_line.set_width(fwhm)
            except ValueError:
                self.fwhm_line.remove()
                self.fwhm_line = None

        if self.der_fwhm_line is not None:
            try:
                x0 = self.der_fwhm[1]
                fwhm = self.der_fwhm[0]
                self.der_fwhm_line.set_x(x0)
                self.der_fwhm_line.set_width(fwhm)
            except ValueError:
                self.der_fwhm_line.remove()
                self.der_fwhm_line = None

        if self.com_line is not None:
            self.com_line.set_xdata([self.com, self.com])

        if self.der_com_line is not None:
            self.der_com_line.set_xdata([self.der_com, self.der_com])

        redraw = False

        if rescale:
            redraw = self.autoscale_plot()

        if redraw:
            self.safe_draw()

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

        try:
            self.canvas.blit(self.plot.bbox)

            if self.show_der.GetValue():
                self.canvas.blit(self.der_plot.bbox)
        except Exception:
            pass # Prevents a weird error on startup

    def _update_plot_2d(self, rescale=True):

        self.z_grid_data = copy.copy(self.plt_z)
        extra_vals = self.total_points - len(self.z_grid_data)

        if extra_vals != 0:
            self.z_grid_data.extend([np.nan for i in range(extra_vals)])

        #This should work but it doesn't
        # if self.plt_image is None:
        #     self.z_grid_data = np.array(self.z_grid_data, dtype=float).reshape((self.y_points, self.x_points))

        #     self.plt_image = self.plot.pcolormesh(self.grid[0], self.grid[1],
        #         self.z_grid_data, animated=True)

        #     self.safe_draw()
        #     self.background = self.canvas.copy_from_bbox(self.plot.bbox)
        # else:
        #     self.plt_image.set_array(np.array(self.z_grid_data, dtype=float))

        # self.canvas.restore_region(self.background)
        # self.plot.draw_artist(self.plt_image)
        # self.canvas.blit(self.plot.bbox)

        self.z_grid_data = np.array(self.z_grid_data, dtype=float).reshape((self.y_points, self.x_points))

        if self.current_scan_params['start'] > self.current_scan_params['stop']:
            self.z_grid_data = self.z_grid_data[:,::-1]
        if self.current_scan_params['start2'] > self.current_scan_params['stop2']:
            self.z_grid_data = self.z_grid_data[::-1,:]

        if self.plt_image is not None:
            self.plt_image.remove()
            self.plt_image = None

        self.plt_image = self.plot.pcolormesh(self.grid[0], self.grid[1],
                self.z_grid_data)

        if rescale:
            self.autoscale_plot()

        self.safe_draw()

    def autoscale_plot(self):
        if self.scan_dimension == 1:
            redraw = self._autoscale_plot_1d()
        elif self.scan_dimension == 2:
            redraw = self._autoscale_plot_2d()

        return redraw

    def _autoscale_plot_1d(self):
        redraw = False

        old_xlim = self.plot.get_xlim()
        old_ylim = self.plot.get_ylim()

        old_der_xlim = self.der_plot.get_xlim()
        old_der_ylim = self.der_plot.get_ylim()

        if self.current_scan_params is not None:
            if self.current_scan_params['start'] < self.current_scan_params['stop']:
                self.plot.set_xlim(self.current_scan_params['start'], self.current_scan_params['stop'])
            else:
                self.plot.set_xlim(self.current_scan_params['stop'], self.current_scan_params['start'])

            if (self.plt_x is not None and self.plt_y is not None and
                len(self.plt_x) == len(self.plt_y)) and len(self.plt_x) > 0:

                self.plot.set_ylim(min(self.plt_y)*0.98, max(self.plt_y)*1.02)


            if self.show_der.GetValue():

                if self.current_scan_params['start'] < self.current_scan_params['stop']:
                    self.der_plot.set_xlim(self.current_scan_params['start'],
                        self.current_scan_params['stop'])
                else:
                    self.der_plot.set_xlim(self.current_scan_params['stop'],
                        self.current_scan_params['start'])

                if (self.plt_x is not None and self.der_y is not None and
                    len(self.plt_x) == len(self.der_y) and len(self.plt_x) > 1):

                    self.der_plot.set_ylim(min(self.der_y)*0.98, max(self.der_y)*1.02)


        if (old_xlim != self.plot.get_xlim() or old_ylim != self.plot.get_ylim()
            or old_der_xlim != self.der_plot.get_xlim() or old_der_ylim != self.der_plot.get_ylim()):
            redraw = True

        return redraw

    def _autoscale_plot_2d(self):
        redraw = False

        old_xlim = self.plot.get_xlim()
        old_ylim = self.plot.get_ylim()

        old_der_xlim = self.der_plot.get_xlim()
        old_der_ylim = self.der_plot.get_ylim()

        if self.current_scan_params is not None:
            self.plot.set_xlim(self.x_pos[0], self.x_pos[-1])
            self.plot.set_ylim(self.y_pos[0], self.y_pos[-1])


            # if self.show_der.GetValue():

            #     if self.current_scan_params['start'] < self.current_scan_params['stop']:
            #         self.der_plot.set_xlim(self.current_scan_params['start'],
            #             self.current_scan_params['stop'])
            #     else:
            #         self.der_plot.set_xlim(self.current_scan_params['stop'],
            #             self.current_scan_params['start'])

            #     if (self.plt_x is not None and self.der_y is not None and
            #         len(self.plt_x) == len(self.der_y) and len(self.plt_x) > 1):

            #         self.der_plot.set_ylim(min(self.der_y)*0.98, max(self.der_y)*1.02)


        if (old_xlim != self.plot.get_xlim() or old_ylim != self.plot.get_ylim()
            or old_der_xlim != self.der_plot.get_xlim() or old_der_ylim != self.der_plot.get_ylim()):
            redraw = True

        return redraw

    def _start_live_plot(self, filename):
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

        if self.plt_image is not None:
            self.plt_image.remove()
            self.plt_image = None

        self.plt_x = []
        self.plt_y = []
        self.plt_z = []
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

        self.update_plot()
        self._update_results()
        wx.Yield()

        self.live_plt_evt.clear()
        self.live_thread = threading.Thread(target=self.live_plot, args=(filename,))
        self.live_thread.daemon = True
        self.live_thread.start()

    def live_plot(self, filename):
        """
        This does the live plotting. It is intended to be run in its own
        thread. It first clears all of the plot related variables and clears
        the plot. It then enters a loop where it reads from the scan file
        and plots the points as they come in, until the scan ends.

        :param str filename: The filename of the scan file to live plot.
        """

        start_time = time.time()
        while not os.path.exists(filename):
            time.sleep(0.1)
            if time.time() - start_time > 5:
                break
        time.sleep(2)

        if self.current_scan_params['scalers_raw'] == 'i1/i0':
            ratio = True
        else:
            ratio = False

        if not self.det_scan:
            with open(filename) as thefile:
                data = utils.file_follow(thefile, self.live_plt_evt)
                for val in data:
                    if self.live_plt_evt.is_set():
                        break
                    if val.startswith('#'):
                        self.scan_header = self.scan_header + val
                    else:
                        if self.scan_dimension == 1:
                            if not ratio:
                                x, y = val.strip().split()
                            else:
                                x, y1, y2 = val.strip().split()
                                y = float(y2)/float(y1)

                            self._update_plot_vals(x, y)

                        elif self.scan_dimension == 2:
                            if not ratio:
                                x, y, z = val.strip().split()
                            else:
                                x, y, z1, z2 = val.strip().split()
                                z = float(z2)/float(z1)

                            self._update_plot_vals(x, y, z)
        else:
            while True:
                if self.live_plt_evt.is_set():
                    break
                try:
                    val = self.return_val_q.get_nowait()
                except queue.Empty:
                    val = None

                if val is not None:
                    if self.scan_dimension == 1:
                        x, y = val
                        self._update_plot_vals(x, y)
                    else:
                        x, y, z = val
                        self._update_plot_vals(x, y, z)

        if not self.det_scan:
            os.remove(filename)

    def _update_plot_vals(self, x, y, z=None):
        self.plt_x.append(float(x))
        self.plt_y.append(float(y))

        if z is not None:
            self.plt_z.append(float(z))

        if self.scan_dimension == 1:
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

    def _on_mousemotion(self, event):
        """
        Called on mouse motion in the plot. If the mouse is in the plot the
        location is shown in the plot toolbar.
        """
        if event.inaxes:
            x, y = event.xdata, event.ydata

            if self.scan_dimension == 1:
                self.toolbar.set_status('x={}, y={}'.format(x, y))
            else:
                try:
                    all_xs = np.arange(len(self.x_pos))
                    ind_x = min(all_xs, key=lambda i: abs(x-self.x_pos[i]))

                    all_ys = np.arange(len(self.y_pos))
                    ind_y = min(all_ys, key=lambda i: abs(y-self.y_pos[i]))

                    if self.x_pos[ind_x] > x:
                        ind_x -= 1
                    if self.y_pos[ind_y] > y:
                        ind_y -= 1

                    if ind_y < self.y_points and ind_x < self.x_points and ind_y>=0 and ind_x>=0:
                        z = self.z_grid_data[ind_y, ind_x]
                    else:
                        z = ''
                except TypeError:
                    z = ''

                self.toolbar.set_status('x={}, y={}, z={}'.format(x, y, z))

        else:
            self.toolbar.set_status('')

    def exit(self):
        self.update_timer.Stop()
        self.scan_timer.Stop()
        self.scan_proc.stop()

        self.scan_proc.join()

    def _on_pickevent(self, event):
        """
        Called when a point on the plot is clicked on. If the click is a right
        click, it opens a context menu.
        """
        artist = event.artist
        button = event.mouseevent.button

        if button == 3 and self.scan_dimension ==1:
            x = artist.get_xdata()
            ind = event.ind
            position = x[ind[0]]
            wx.CallAfter(self._show_popupmenu, position)

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
        self.cmd_q.put_nowait(['move_abs', [position], {}])

    def _on_showder(self, event):
        """
        Toggles wehre the derivative plot is show, and whether the calculated
        parameters (fit, FWHM, COM) are shown.
        """
        if event.IsChecked():
            self.der_plot.set_visible(True)
            self.plot.set_position(self.plt_gs2[0].get_position(self.fig))
            self.der_plot.set_position(self.plt_gs2[1].get_position(self.fig))
            # self.plot.xaxis.label.set_visible(False)
            # for label in self.plot.get_xticklabels():
            #     label.set_visible(False)

            self.scan_results_sizer.Show(self.der_results_sizer, recursive=True)

            self.move_to.Set(['FWHM center', 'COM position', 'Der. FWHM center',
                'Der. COM position'])
        else:
            self.der_plot.set_visible(False)
            self.plot.set_position(self.plt_gs[0].get_position(self.fig))
            # self.plot.xaxis.label.set_visible(True)
            # self.plot.xaxis.set_major_formatter(matplotlib.ticker.ScalarFormatter())
            # for label in self.plot.get_xticklabels():
            #     label.set_visible(True)

            self.scan_results_sizer.Hide(self.der_results_sizer, recursive=True)

            self.move_to.Set(['FWHM center', 'COM position'])

        self.safe_draw()
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
        self._calc_com('der', True)

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
            self.disp_fwhm.SetLabel(str(round(self.fwhm[0], 5)))
            self.disp_fwhm_pos.SetLabel(str(round(((self.fwhm[2]+self.fwhm[1])/2.), 5)))

        if self.com is not None:
            self.disp_com.SetLabel(str(round(self.com, 5)))

        if self.der_fwhm is not None:
            self.disp_der_fwhm.SetLabel(str(round(self.der_fwhm[0], 5)))
            self.disp_der_fwhm_pos.SetLabel(str(round(((self.der_fwhm[2]+self.der_fwhm[1])/2.), 5)))

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

    def _save_log(self):
        if self.current_scan_params['detector'] is not None:
            try:
                self.return_q.get_nowait()
            except Exception:
                pass

            self.cmd_q.put_nowait(['get_det_params', [], {}])
            det_datadir = self.return_q.get()[0]

            scan_prefix = 'scan'

            if self.detector.GetStringSelection() == 'Eiger2 XE 9M':
                # det_datadir = det_datadir.replace('/nas_data', '/nas_data/Eiger2xe9M')
                pass
            else:
                det_datadir = det_datadir.replace('/nas_data', '/nas_data/Pilatus1M')

            start = float(self.current_scan_params['start'])
            stop = float(self.current_scan_params['stop'])
            step = abs(float(self.current_scan_params['step']))

            if start < stop:
                mtr1_positions = np.arange(start, stop+step, step)
            else:
                mtr1_positions = np.arange(stop, start+step, step)
                mtr1_positions = mtr1_positions[::-1]

            if self.current_scan_params['scan_dim'] == '2D':
                start2 = float(self.current_scan_params['start2'])
                stop2 = float(self.current_scan_params['stop2'])
                step2 = abs(float(self.current_scan_params['step2']))

                if start2 < stop2:
                    mtr2_positions = np.arange(start2, stop2+step2, step2)
                else:
                    mtr2_positions = np.arange(stop2, start2+step2, step2)

            counters = self.current_scan_params['scalers_raw']

            counters = counters = counters.upper()

            if self.current_scan_params['scan_dim'] != '2D':
                log_file = os.path.join(det_datadir, '{}.log'.format(scan_prefix))

                with open(log_file, 'w') as f:
                    f.write('#Filename\t{}_pos\t{}\n'.format(self.current_scan_params['device'],
                        '\t'.join(counters.split())))

                    for i in range(len(self.plt_x)):
                        f.write('scan_{:06}.tif\t{}\t{}\n'.format(i, self.plt_x[i], self.plt_y[i]))

            else:

                for i in range(len(mtr1_positions)):
                    log_file = os.path.join(det_datadir, '{}_{:03}.log'.format(scan_prefix, i))

                    with open(log_file, 'w') as f:
                        f.write('#Filename\t{}_pos\t{}_pos\t{}\n'.format(self.current_scan_params['device'],
                            self.current_scan_params['device2'], '\t'.join(counters.split())))

                        for j in range(len(mtr2_positions)):
                            num = i*len(mtr2_positions)+j
                            if num < len(self.plt_x):
                                f.write('scan_{:03}_{:06}.tif\t{}\t{}\t{}\n'.format(i, j, self.plt_x[num],
                                    self.plt_y[num], self.plt_z[num]))


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
            self.cmd_q.put_nowait(['move_abs', [pos], {}])

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

            if self.scan_dimension == 1:
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

                    f.write('# scan_x, scan_y')
                    if self.show_der.IsChecked():
                        f.write(', der_y\n')
                    else:
                        f.write('\n')

                    for i in range(len(results[0])):
                        data = ', '.join([str(results[j][i]) for j in range(len(results))])
                        f.write('{}\n'.format(data))
            else:
                results = [self.plt_x, self.plt_y, self.plt_z]

                with open(path, 'w') as f:
                    f.write('# Scan Results\n')
                    f.write(self.scan_header)

                    f.write('# scan_x, scan_y, scan_i\n')
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
        self.parent = parent

        self.AddControl(self.status)

    def set_status(self, status):
        """
        Called to set the status text in the toolbar, i.e. the cursor position
        on the plot.
        """
        self.status.SetLabel(status)

    def home(self, *args, **kwargs):
        self.parent.update_plot(True)


class ScanFrame(wx.Frame):
    """
    A lightweight scan frame that holds the :mod:`ScanPanel`.
    """
    def __init__(self, mx_database, *args, **kwargs):
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

        self._create_layout(mx_database)

        self.SetSizeHints(self._FromDIP(-1), self._FromDIP(750))

        utils.set_best_size(self)

        current_size = self.GetSize()
        current_size.SetHeight(current_size.GetHeight()+self._FromDIP(40))
        self.SetSize(current_size)

        self.Bind(wx.EVT_CLOSE, self._on_close)

    def _FromDIP(self, size):
        # This is a hack to provide easy back compatibility with wxpython < 4.1
        try:
            return self.FromDIP(size)
        except Exception:
            return size

    def _create_layout(self, mx_database):
        """
        Creates the layout, by calling mod:`ScanPanel`.

        :param str device_name: The MX record name of the device.
        :param Mp.Record device: The Mp record (i.e. the device)
        :param Mp.Record server_record: The Mp record for the server that the
            device is located on.
        :param Mp.RecordList mx_database: The Mp record list representing the
            MX database being used.
        """
        self.scan_panel = ScanPanel(mx_database, parent=self)

        top_sizer = wx.BoxSizer(wx.HORIZONTAL)
        top_sizer.Add(self.scan_panel, 1, wx.EXPAND)

        self.SetSizer(top_sizer)

    def _on_close(self, evt):
        self.scan_panel.exit()
        self.Destroy()


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

    app = wx.App()

    frame = ScanFrame(database_filename, parent=None, title='Scan Control')
    frame.Show()
    app.MainLoop()

