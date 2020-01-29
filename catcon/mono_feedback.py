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

import time
import logging
import logging.handlers as handlers
import sys

if __name__ != '__main__':
    logger = logging.getLogger(__name__)

import epics
import numpy as np
import wx
import os

import utils
utils.set_mppath() #This must be done before importing any Mp Modules.
import Mp as mp


def monitor_and_average(pv_list, average_time, update_rate=None):
    """
    Could I do  this more efficiently by adding a callback in this function (maybe
    a lambda function) and removing it at the end of the funciton? Then only adding
    values when the PV changes? Would have to make the auto_monitor for the PV True
    """
    start_time = time.time()

    monitor_values = []

    while time.time() - start_time < average_time:
        if update_rate is not None:
            update_start_time = time.time()

        monitor_values.append([pv.get() for pv in pv_list])

        if update_rate is not None:
            while time.time() - update_start_time < update_rate:
                time.sleep(0.001)

    monitor_values = np.array(monitor_values, dtype=np.float)

    monitor_avgs = [np.mean(monitor_values[:, i]) for i in range(len(pv_list))]

    return monitor_avgs

def position_feedback(value, target, motor, pv, step_size, min_step_size, max_step_size,
    close, timeout=0.25, average_time=0.5, osc_step=0, dark_step=0):
    abs_diff = abs(target-value)

    if abs_diff > close:
        logger.debug('Starting position %s', value)
        logger.debug('Starting distance %s', abs_diff)

        if value < target:
            logger.debug("Making positive move by %s", step_size)
            motor.move_relative(step_size)
        elif value >  target:
            logger.debug("Making negative move by %s", step_size)
            motor.move_relative(-step_size)

        while motor.is_busy():
            time.sleep(0.01)

        start_time = time.time()

        while pv.get() == value and time.time() - start_time < timeout:
            time.sleep(0.001)

        time.sleep(1)

        new_value = monitor_and_average([pv], average_time, 0.1)[0]

        new_abs_diff = abs(target-new_value)
        move_abs_diff = abs(value - new_value)

        logger.debug('Absolute moved by %s', move_abs_diff)
        logger.debug('Absolute distance to target %s', new_abs_diff)
        logger.debug('Target: %s', target)
        logger.debug('Current: %s', new_value)

        if abs(target-new_value) > close and osc_step < 3 and dark_step == 0:
            if value == new_value:
                logger.debug("Failed to change feedback value")
                #Case where we don't move at all
                new_step_size = min(abs(step_size*2), max_step_size)

                if step_size < 0:
                    new_step_size = -new_step_size

                if abs(new_step_size) == max_step_size:
                    dark_step = dark_step+1

            elif (((value < target and new_value < target) or (value > target and new_value > target))
                and new_abs_diff > abs_diff):
                #Case where we moved away from target value
                logger.debug("Moved away from target")

                new_step_size = -step_size

            elif (((value < target and new_value < target) or (value > target and new_value > target))
                and new_abs_diff <= abs_diff):
                #Case where we moved towards but not past target value
                logger.debug("Moved towards but not past target")

                new_step_size = max((new_abs_diff/move_abs_diff)*abs(step_size), min_step_size)
                new_step_size = min(new_step_size, max_step_size)

                if step_size < 0:
                    new_step_size = -new_step_size

            elif (value < target and new_value > target) or (value > target and new_value < target):
                #Case where we moved towards and past target value
                logger.debug("Moved towards and past target")

                new_step_size = max((new_abs_diff/move_abs_diff)*abs(step_size), min_step_size)
                new_step_size = min(new_step_size, max_step_size)

                if step_size < 0:
                    new_step_size = -new_step_size

                if abs(new_step_size) == min_step_size:
                    osc_step = osc_step + 1

            logger.debug("New step size: %s", new_step_size)

            position_feedback(new_value, target, motor, pv, new_step_size, min_step_size,
                max_step_size, close, timeout, average_time, osc_step)

        elif abs(target-new_value) > close:
            logger.debug('Feedback finished successfully')
        elif osc_step == 3:
            logger.debug(("Feedback failed, oscillating about position. Try "
                "reducing min_step_size."))
        elif dark_step == 1:
            logger.debug(("Feedback failed, motor not changing target value. "
                "Check if A shutter is open, and verify the correct motor "
                "is being used."))

    else:
        logger.debug('Position is already within tolerance of target, no feedback necessary.')

def intensity_feedback(value, target, motor, pv, step_size, min_step_size,
    close, timeout=0.25, average_time=0.2):
    if value < target-close:

        target = intensity_optimize(value, target, motor, pv, step_size,
            min_step_size, close, timeout, average_time)

    else:
        logger.debug('Intensity is already within tolerance of target, no feedback necessary.')

    return target

def intensity_optimize(value, start_val, motor, pv, step_size, min_step_size,
    close, timeout=0.25, average_time=0.2, osc_step=0, stop_step=0):
    logger.debug("Making move by %s", step_size)
    motor.move_relative(step_size)

    while motor.is_busy():
        time.sleep(0.01)

    start_time = time.time()

    while pv.get() == value and time.time() - start_time < timeout:
        time.sleep(0.001)

    new_value = monitor_and_average([pv], average_time, average_time/10.)[0]

    if new_value < value:
        osc_step = osc_step + 1

        if osc_step == 2:
            new_step_size = min(abs(step_size)/2., min_step_size)

            if step_size < 0:
                new_step_size = -new_step_size

            osc_step = 0

        else:
            new_step_size = step_size

        if abs(step_size) == min_step_size:
            stop_step = stop_step + 1

        new_step_size = -new_step_size

        if stop_step == 2:
            logger.debug("Making move by %s", new_step_size)
            motor.move_relative(new_step_size)

            start_time = time.time()

            while pv.get() == value and time.time() - start_time < timeout:
                time.sleep(0.001)

            final_value = monitor_and_average([pv], average_time, average_time/10.)[0]

        else:
            final_value = intensity_optimize(value, start_val, motor, pv, new_step_size, min_step_size, close,
                timeout, average_time, osc_step, stop_step)

    elif new_value == value:
        stop_step = stop_step+1

        if stop_step == 2:
            logger.debug("Making move by %s", step_size)
            motor.move_relative(step_size)

            start_time = time.time()

            while pv.get() == value and time.time() - start_time < timeout:
                time.sleep(0.001)

            final_value = monitor_and_average([pv], average_time, average_time/10.)[0]

        else:
            final_value = intensity_optimize(value, motor, pv, step_size, min_step_size, close,
                timeout, average_time, osc_step, stop_step)

    else:
        final_value = intensity_optimize(value, start_val, motor, pv, step_size, min_step_size, close,
                timeout, average_time, osc_step, stop_step)

    return final_value

def run_feedback(bpm_x_name, bpm_y_name, bpm_int_name, motor_x_name, motor_y_name,
    motor_int_name, mx_database, shutter_name, bpm_x_target=None, bpm_y_target=None):

    logger.info('Starting feedback for %s', mono)
    logger.info('X BPM PV: %s', bpm_x_name)
    logger.info('Y BPM PV: %s', bpm_y_name)
    logger.info('Intensity BPM PV: %s', bpm_int_name)
    logger.info('X motor name: %s', motor_x_name)
    logger.info('Y motor name: %s', motor_y_name)
    logger.info('Intensity motor name: %s', motor_int_name)
    logger.info('Front end shutter PV: %s', shutter_name)

    logger.debug("Connecting to PVs")
    bpm_x_pv = epics.PV(bpm_x_name, auto_monitor=False)
    bpm_y_pv = epics.PV(bpm_y_name, auto_monitor=False)
    bpm_int_pv = epics.PV(bpm_int_name, auto_monitor=False)
    shutter_pv = epics.PV(shutter_name, auto_monitor=False)
    logger.debug("Connected to PVs")

    logger.debug("Connecting to motors")
    motor_x = mx_database.get_record(motor_x_name)
    motor_y = mx_database.get_record(motor_y_name)
    motor_int = mx_database.get_record(motor_int_name)
    logger.debug("Connected to motors")

    #Initialize PVs with first get
    logger.debug("Initializing PVs")
    bpm_x_pv.get()
    bpm_y_pv.get()
    bpm_int_pv.get()
    shutter_pv.get()
    logger.debug("Initialized PVs")

    if bpm_x_target is None:
        logger.info("No X BPM target provided, using initial value")
        bpm_x_target = monitor_and_average([bpm_x_pv], 0.5, 0.05)[0]

    if bpm_y_target is None:
        logger.info("No Y BPM target provided, using initial value")
        bpm_y_target = monitor_and_average([bpm_y_pv], 0.5, 0.05)[0]


    bpm_int_start = monitor_and_average([bpm_int_pv], 0.5, 0.05)[0]

    logger.info("X BPM target: %s", bpm_x_target)
    logger.info("Y BPM target: %s", bpm_x_target)
    logger.info("Intensity BPM start: %s", bpm_int_start)

    log_time = time.time()

    while True:
        while shutter_pv.get() == 0:
            time.sleep(1)

        if time.time() - log_time > 300:
            log_time = time.time()
            log_info = True
        else:
            log_info = False

        bpm_x_val, bpm_y_val, bpm_int_val = monitor_and_average([bpm_x_pv, bpm_y_pv, bpm_int_pv], 0.5, 0.001)

        if log_info:
            logger.info("BPM X, Y, and Intensity values: %s, %s, %s", bpm_x_val,
            bpm_y_val, bpm_int_val)
        else:
            logger.debug("BPM X, Y, and Intensity values: %s, %s, %s", bpm_x_val,
                bpm_y_val, bpm_int_val)

        logger.debug("Doing X feedback")
        x_step = (bpm_x_target-bpm_x_val)*(50/0.04)
        if abs(x_step) < 1:
            if x_step > 0:
                x_step = 1
            else:
                x_step = -1

        elif abs(x_step) > 50:
            if x_step > 0:
                x_step = 50
            else:
                x_step = -50

        # position_feedback(bpm_x_val, bpm_x_target, motor_x, bpm_x_pv, x_step, 1, 50, 0.001)

        logger.debug("Doing Y feedback")
        y_step = (bpm_y_target-bpm_y_val)*(50/0.2)
        if abs(y_step) < 1:
            if y_step > 0:
                y_step = 1
            else:
                y_step = -1

        elif abs(y_step) > 50:
            if y_step > 0:
                y_step = 50
            else:
                y_step = -50

        # position_feedback(bpm_y_val, bpm_y_target, motor_y, bpm_y_pv, 10, 1, 50, 0.002)

        logger.debug("Doing Intensity feedback")
        bpm_int_start = intensity_feedback(bpm_int_val, bpm_int_start, motor_int,
            bpm_int_pv, 10, 1, 0.02)

        if log_info:
            logger.info('X motor (%s) position: %s', motor_x_name, motor_x.get_position())
            logger.info('Y motor (%s) position: %s', motor_y_name, motor_y.get_position())
            logger.info('Intensity motor (%s) position: %s', motor_int_name, motor_int.get_position())
        else:
            logger.debug('X motor (%s) position: %s', motor_x_name, motor_x.get_position())
            logger.debug('Y motor (%s) position: %s', motor_y_name, motor_y.get_position())
            logger.debug('Intensity motor (%s) position: %s', motor_int_name, motor_int.get_position())


if __name__ == '__main__':
    logger = logging.getLogger()
    logger.setLevel(logging.DEBUG)

    h1 = logging.StreamHandler(sys.stdout)
    # h1.setLevel(logging.INFO)
    h1.setLevel(logging.DEBUG)
    formatter = logging.Formatter('%(asctime)s - %(message)s')
    h1.setFormatter(formatter)
    logger.addHandler(h1)

    app = wx.App()
    standard_paths = wx.StandardPaths.Get() #Can't do this until you start the wx app
    info_dir = standard_paths.GetUserLocalDataDir()

    if not os.path.exists(info_dir):
        os.mkdir(info_dir)

    h2 = handlers.RotatingFileHandler(os.path.join(info_dir, 'mono_feedback.log'), maxBytes=10e6, backupCount=5, delay=True)
    h2.setLevel(logging.INFO)
    formatter2 = logging.Formatter('%(asctime)s - %(name)s - %(threadName)s - %(levelname)s - %(message)s')
    h2.setFormatter(formatter2)

    bpm_x_name = '18ID:BPM:CMono:X'
    bpm_y_name = '18ID:BPM:CMono:Y'
    bpm_int_name = '18ID:BPM:CMono:Intensity'

    mono = 'mono2'

    motor_x_name = '{}_x1_chi'.format(mono)
    motor_y_name = '{}_x2_perp'.format(mono)
    motor_int_name = '{}_tune'.format(mono)

    shutter_name = 'FE:18:ID:FEshutter'

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
    mx_database.set_program_name("mono_feedback")

    run_feedback(bpm_x_name, bpm_y_name, bpm_int_name, motor_x_name,
        motor_y_name, motor_int_name, mx_database, shutter_name)

