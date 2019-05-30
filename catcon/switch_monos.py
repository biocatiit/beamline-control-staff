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

if __name__ == "__main__" and __package__ is None:
    __package__ = "catcon"

import os
import time
import threading

import wx

import utils
utils.set_mppath() #This must be done before importing any Mp Modules.
import Mp as mp
import MpCa as mpca
import MpWx as mpwx
import custom_widgets


class SWMonosPanel(wx.Panel):
    """
    .. todo::
        Eventually this should allow viewing (and setting?) of the amp
        settings, ideally through a generic GUI that works for various
        types of devices, not just amps.

    This amp panel supports standard amplifier controls, such as setting the
    gain and the offset. It is mean to be embedded in a larger application,
    and can be instanced several times, once for each amp. It communicates
    with the amps by calling ``Mp``, the python wrapper for ``MX``.
    """
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

        self._enabled = True

        self._create_layout()
        self._initialize()

    def _create_layout(self):
        """
        Creates the layout for the panel.

        """

        self.one_to_two_btn = wx.Button(self, label='Mono 1 -> Mono 2')
        self.two_to_one_btn = wx.Button(self, label='Mono 2 -> Mono 1')
        self.abort_btn = wx.Button(self, label='Abort')

        self.one_to_two_btn.Bind(wx.EVT_BUTTON, self.on_one_to_two)
        self.two_to_one_btn.Bind(wx.EVT_BUTTON, self.on_two_to_one)
        self.abort_btn.Bind(wx.EVT_BUTTON, self.on_abort)

        control_sizer=wx.BoxSizer(wx.HORIZONTAL)
        control_sizer.Add(self.one_to_two_btn, border=5, flag=wx.ALL)
        control_sizer.Add(self.two_to_one_btn, border=5, flag=wx.ALL)
        control_sizer.Add(self.abort_btn, border=5, flag=wx.ALL)

        self.output = wx.TextCtrl(self, style=wx.TE_READONLY|wx.TE_MULTILINE|wx.TE_BESTWRAP)

        top_sizer = wx.BoxSizer(wx.VERTICAL)
        top_sizer.Add(control_sizer, flag=wx.ALIGN_CENTER_HORIZONTAL)
        top_sizer.Add(self.output, proportion=1, border=5, flag=wx.ALL|wx.EXPAND)


        self.Bind(wx.EVT_RIGHT_DOWN, self._on_rightclick)
        for item in self.GetChildren():
            if (isinstance(item, wx.StaticText) or isinstance(item, mpwx.Value)
                or isinstance(item, custom_widgets.CustomEpicsValue) or isinstance(item, wx.StaticBox)):
                item.Bind(wx.EVT_RIGHT_DOWN, self._on_rightclick)

        self.SetSizer(top_sizer)

    def _initialize(self):
        self.fe_shutter_pv = mpca.PV('FE:18:ID:FEshutter')

        self.mono1_energy = mx_database.get_record('mono1_energy')
        self.mono1_normal_enabled = mx_database.get_record('mono1_normal_enabled')
        self.mono1_parallel_enabled = mx_database.get_record('mono1_parallel_enabled')
        self.mono1_theta = mx_database.get_record('mono1_theta')
        self.mono1_x1_chi = mx_database.get_record('mono1_x1_chi')

        self.mono2_energy = mx_database.get_record('mono2_energy')
        self.mono2_normal_enabled = mx_database.get_record('mono2_normal_enabled')
        self.mono2_parallel_enabled = mx_database.get_record('mono2_parallel_enabled')
        self.mono2_theta = mx_database.get_record('mono2_theta')
        self.mono2_x1_chi = mx_database.get_record('mono2_x1_chi')
        self.mono2_x2_para = mx_database.get_record('mono2_x2_para')
        self.mono2_x2_perp = mx_database.get_record('mono2_x2_perp')
        self.mono2_focus = mx_database.get_record('mono2_focus')

        self.abort_event = threading.Event()
        self.abort_event.clear()

    def on_one_to_two(self, evt):
        self.abort_event.clear()
        cont = self.check_fe_shutter()

        if cont:
            t = threading.Thread(target=self.one_to_two)
            t.daemon = True
            t.start()
            # self.one_to_two()

    def on_two_to_one(self, evt):
        self.abort_event.clear()
        cont = self.check_fe_shutter()

        if cont:
            t = threading.Thread(target=self.two_to_one)
            t.daemon = True
            t.start()
            # self.two_to_one()

    def check_fe_shutter(self):
        if self.fe_shutter_pv.caget() == 0:
            fes = False
        else:
            fes = True

        msg = "Close the front end shutter to continue, the click 'OK'."

        while fes:

            dlg = wx.MessageDialog(self, msg, "Close Front End Shutter",
                wx.ICON_EXCLAMATION|wx.STAY_ON_TOP|wx.OK|wx.CANCEL)

            result = dlg.ShowModal()

            if result == wx.ID_CANCEL:
                break

            if self.fe_shutter_pv.caget() == 0:
                fes = False
            else:
                fes = True

        if self.fe_shutter_pv.caget() == 0:
            fes = False
        else:
            fes = True

        return not fes

    def one_to_two(self):
        if self.abort_event.is_set():
            self.cleanup()
            return

        wx.CallAfter(self.output.AppendText, "Switching Mono 1 to Mono 2\n")

        # Move mono 1 to bypass position

        wx.CallAfter(self.output.AppendText, "Moving Mono 1 energy to 12 keV . . . ")
        self.mono1_energy.move_absolute(12.0)

        while self.mono1_energy.is_busy():
            if self.abort_event.is_set():
                self.mono1_energy.soft_abort()
                self.cleanup()
                return
            time.sleep(0.5)

        wx.CallAfter(self.output.AppendText, "Done!\n")

        self.mono1_normal_enabled.write(0)
        self.mono1_parallel_enabled.write(0)

        wx.CallAfter(self.output.AppendText, "Moving Mono 1 theta to 0 degrees . . . ")
        self.mono1_theta.move_absolute(0.0)

        while self.mono1_theta.is_busy():
            if self.abort_event.is_set():
                self.mono1_theta.soft_abort()
                self.cleanup()
                return
            time.sleep(0.5)

        wx.CallAfter(self.output.AppendText, "Done!\n")

        wx.CallAfter(self.output.AppendText, "Moving Mono 1 chi to 31000 urad. . . ")
        self.mono1_x1_chi.move_absolute(31000)

        while self.mono1_x1_chi.is_busy():
            if self.abort_event.is_set():
                self.mono1_x1_chi.soft_abort()
                self.cleanup()
                return
            time.sleep(0.5)

        wx.CallAfter(self.output.AppendText, "Done!\n")

        # Move mono 2 to beam position

        self.mono2_normal_enabled.write(0)
        self.mono2_parallel_enabled.write(0)

        wx.CallAfter(self.output.AppendText, "Moving Mono 2 energy 12 keV . . . ")
        self.mono2_energy.move_absolute(12.1)

        while self.mono2_energy.is_busy():
            if self.abort_event.is_set():
                self.mono2_energy.soft_abort()
                self.cleanup()
                return
            time.sleep(0.5)

        self.mono2_normal_enabled.write(1)
        self.mono2_parallel_enabled.write(1)

        self.mono2_energy.move_absolute(12.0)

        while self.mono2_energy.is_busy():
            if self.abort_event.is_set():
                self.mono2_energy.soft_abort()
                self.cleanup()
                return
            time.sleep(0.5)

        wx.CallAfter(self.output.AppendText, "Done!\n")

        wx.CallAfter(self.output.AppendText, "Moving Mono 2 chi to 0 . . . ")
        self.mono2_x1_chi.move_absolute(0)

        while self.mono2_x1_chi.is_busy():
            if self.abort_event.is_set():
                self.mono2_x1_chi.soft_abort()
                self.cleanup()
                return
            time.sleep(0.5)

        wx.CallAfter(self.output.AppendText, "Done!\n")

        wx.CallAfter(self.output.AppendText, "Mono 1 to 2 switch completed!\n\n\n")

        return

    def two_to_one(self):
        if self.abort_event.is_set():
            self.cleanup()
            return

        wx.CallAfter(self.output.AppendText, "Switching Mono 2 to Mono 1\n")

        # Move mono 2 to bypass position

        wx.CallAfter(self.output.AppendText, "Moving Mono 2 energy to 5 kev . . . ")
        self.mono2_energy.move_absolute(5)

        while self.mono2_energy.is_busy():
            if self.abort_event.is_set():
                self.mono2_energy.soft_abort()
                self.cleanup()
                return
            time.sleep(0.5)

        wx.CallAfter(self.output.AppendText, "Done!\n")

        self.mono2_normal_enabled.write(0)
        self.mono2_parallel_enabled.write(0)

        wx.CallAfter(self.output.AppendText, "Moving Mono 2 theta (mr) to 23 degrees . . . ")
        self.mono2_theta.move_absolute(23)

        while self.mono2_theta.is_busy():
            if self.abort_event.is_set():
                self.mono2_theta.soft_abort()
                self.cleanup()
                return
            time.sleep(0.5)

        wx.CallAfter(self.output.AppendText, "Done!\n")

        wx.CallAfter(self.output.AppendText, "Moving Mono 2 parallel (mtx) to 128000 um . . . ")
        self.mono2_x2_para.move_absolute(128000)

        while self.mono2_x2_para.is_busy():
            if self.abort_event.is_set():
                self.mono2_x2_para.soft_abort()
                self.cleanup()
                return
            time.sleep(0.5)

        wx.CallAfter(self.output.AppendText, "Done!\n")

        wx.CallAfter(self.output.AppendText, "Moving Mono 2 perpendicular (mty) to 20000 um . . . ")
        self.mono2_x2_perp.move_absolute(20000)

        while self.mono2_x2_perp.is_busy():
            if self.abort_event.is_set():
                self.mono2_x2_perp.soft_abort()
                self.cleanup()
                return
            time.sleep(0.5)

        wx.CallAfter(self.output.AppendText, "Done!\n")

        wx.CallAfter(self.output.AppendText, "Moving Mono 2 chi to 0 urad . . . ")
        self.mono2_x1_chi.move_absolute(0)

        while self.mono2_x1_chi.is_busy():
            if self.abort_event.is_set():
                self.mono2_x1_chi.soft_abort()
                self.cleanup()
                return
            time.sleep(0.5)

        wx.CallAfter(self.output.AppendText, "Done!\n")

        wx.CallAfter(self.output.AppendText, "Moving Mono 2 focus to 100 um . . . ")
        self.mono2_focus.move_absolute(100)

        while self.mono2_focus.is_busy():
            if self.abort_event.is_set():
                self.mono2_focus.soft_abort()
                self.cleanup()
                return
            time.sleep(0.5)

        wx.CallAfter(self.output.AppendText, "Done!\n")

        # Move mono 1 to beam position

        wx.CallAfter(self.output.AppendText, "Moving Mono 1 energy to 12 keV . . . ")
        self.mono1_energy.move_absolute(12.1)

        while self.mono1_energy.is_busy():
            if self.abort_event.is_set():
                self.mono1_energy.soft_abort()
                self.cleanup()
                return
            time.sleep(0.5)

        self.mono1_normal_enabled.write(1)
        self.mono1_parallel_enabled.write(1)

        self.mono1_energy.move_absolute(12.0)

        while self.mono1_energy.is_busy():
            if self.abort_event.is_set():
                self.mono1_energy.soft_abort()
                self.cleanup()
                return
            time.sleep(0.5)

        wx.CallAfter(self.output.AppendText, "Done!\n")

        wx.CallAfter(self.output.AppendText, "Moving Mono 1 chi to 0 urad . . . ")
        self.mono1_x1_chi.move_absolute(0)

        while self.mono1_x1_chi.is_busy():
            if self.abort_event.is_set():
                self.mono1_x1_chi.soft_abort()
                self.cleanup()
                return
            time.sleep(0.5)

        wx.CallAfter(self.output.AppendText, "Done!\n")

        wx.CallAfter(self.output.AppendText, "Mono 2 to 1 switch completed!\n\n\n")

        return

    def on_abort(self, evt):
        self.abort_event.set()

    def cleanup(self):
        self.abort_event.clear()
        wx.CallAfter(self.output.AppendText, "\n\nAborted!\n\n\n")

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

        # menu.Append(2, 'Show control info')

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
            if (not isinstance(item, wx.StaticText) and not isinstance(item, custom_widgets.CustomValue)
                and not isinstance(item, custom_widgets.CustomEpicsValue) and not
                isinstance(item, wx.StaticBox)):
                item.Enable(self._enabled)




class SWMonosFrame(wx.Frame):
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

        ic_calc_panel = SWMonosPanel(self.name, self.mx_database, self)
        ic_calc_box_sizer = wx.StaticBoxSizer(wx.StaticBox(self, label='Switch Monos'))
        ic_calc_box_sizer.Add(ic_calc_panel, proportion=1, flag=wx.EXPAND)

        return ic_calc_box_sizer

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

    # mx_database = None

    app = wx.App()
    frame = SWMonosFrame(None, mx_database, parent=None, title='Test Switch Monos')
    frame.Show()
    app.MainLoop()
