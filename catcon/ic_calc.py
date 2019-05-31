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
import itertools
import math
import time

import wx
import numpy as np
import scipy.interpolate as interp
import scipy.constants as constants

import utils
utils.set_mppath() #This must be done before importing any Mp Modules.
import Mp as mp
import MpCa as mpca
import MpWx as mpwx
import custom_widgets


class ICCalcPanel(wx.Panel):
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

        self.energy_ctrl = wx.TextCtrl(self, size=(60, -1), style=wx.TE_PROCESS_ENTER,
            validator=utils.CharValidator('float_te'), value='12.0')
        self.gas_ctrl = wx.Choice(self, choices=['Air', 'Helium', 'Nitrogen'])
        self.gas_ctrl.SetStringSelection('Nitrogen')
        self.chamber_type = wx.Choice(self, choices=['BioCAT Standard', 'BioCAT Micro', 'Custom'])
        self.chamber_type.SetStringSelection('BioCAT Standard')
        self.chamber_length = wx.TextCtrl(self, size=(60, -1), style=wx.TE_PROCESS_ENTER,
            validator=utils.CharValidator('float_te'))
        self.chamber_length.Disable()
        self.gain = wx.Choice(self, choices=['1e2', '1e3', '1e4', '1e5', '1e6', '1e7', '1e8', '1e9', '1e10'])
        self.gain.SetStringSelection('1e5')
        self.voltage = wx.TextCtrl(self, size=(60, -1), validator=utils.CharValidator('float_te'))

        self.calculate = wx.Button(self, label='Calculate')

        # self.energy_ctrl.Bind(wx.EVT_TEXT_ENTER, self._on_energy_change)
        # self.energy_ctrl.Bind(wx.EVT_TEXT, self._on_text)
        # self.chamber_length.Bind(wx.EVT_TEXT, self._on_text)

        self.chamber_type.Bind(wx.EVT_CHOICE, self._on_chamber_type)
        self.calculate.Bind(wx.EVT_BUTTON, self._on_calc)


        calc_controls = wx.FlexGridSizer(cols=2, rows=6, vgap=5, hgap=3)

        calc_controls.Add(wx.StaticText(self, label='Energy [keV]:'),
            flag=wx.ALIGN_CENTER_VERTICAL)
        calc_controls.Add(self.energy_ctrl, flag=wx.ALIGN_CENTER_VERTICAL)
        calc_controls.Add(wx.StaticText(self, label='Gas:'),
            flag=wx.ALIGN_CENTER_VERTICAL)
        calc_controls.Add(self.gas_ctrl, flag=wx.ALIGN_CENTER_VERTICAL)
        calc_controls.Add(wx.StaticText(self, label='Chamber type:'),
            flag=wx.ALIGN_CENTER_VERTICAL)
        calc_controls.Add(self.chamber_type, flag=wx.ALIGN_CENTER_VERTICAL)
        calc_controls.Add(wx.StaticText(self, label='Chamber length [cm]:'),
            flag=wx.ALIGN_CENTER_VERTICAL)
        calc_controls.Add(self.chamber_length, flag=wx.ALIGN_CENTER_VERTICAL)
        calc_controls.Add(wx.StaticText(self, label='Amplifier Gain [V/A]:'),
            flag=wx.ALIGN_CENTER_VERTICAL)
        calc_controls.Add(self.gain, flag=wx.ALIGN_CENTER_VERTICAL)
        calc_controls.Add(wx.StaticText(self, label='Voltage [V]:'),
            flag=wx.ALIGN_CENTER_VERTICAL)
        calc_controls.Add(self.voltage, flag=wx.ALIGN_CENTER_VERTICAL)


        self.flux = wx.StaticText(self, label='')
        fsize = self.GetFont().GetPointSize()
        font = wx.Font(fsize, wx.DEFAULT, wx.NORMAL, wx.BOLD)
        self.flux.SetFont(font)

        flux_sizer = wx.StaticBoxSizer(wx.StaticBox(self, label='Flux'),
            wx.HORIZONTAL)
        flux_sizer.Add(wx.StaticText(self, label='Flux [ph/s]:'),
            flag=wx.ALIGN_CENTER_VERTICAL)
        flux_sizer.Add(self.flux, border=3, flag=wx.ALIGN_CENTER_VERTICAL|wx.LEFT)
        flux_sizer.AddStretchSpacer(1)

        control_sizer = wx.StaticBoxSizer(wx.StaticBox(self, label='Controls'),
            wx.VERTICAL)
        control_sizer.Add(calc_controls)
        control_sizer.Add(self.calculate, border=10,
            flag=wx.ALIGN_CENTER_HORIZONTAL|wx.TOP|wx.BOTTOM)

        top_sizer = wx.BoxSizer(wx.VERTICAL)
        top_sizer.Add(control_sizer)
        top_sizer.Add(flux_sizer, border=5, flag=wx.TOP|wx.EXPAND)


        self.Bind(wx.EVT_RIGHT_DOWN, self._on_rightclick)
        for item in self.GetChildren():
            if (isinstance(item, wx.StaticText) or isinstance(item, mpwx.Value)
                or isinstance(item, custom_widgets.CustomEpicsValue) or isinstance(item, wx.StaticBox)):
                item.Bind(wx.EVT_RIGHT_DOWN, self._on_rightclick)

        self.SetSizer(top_sizer)


    def _initialize(self):
        root_dir = os.path.split(__file__)[0]
        self.n2_e_data, self.n2_trans_data = np.loadtxt(os.path.join(root_dir, 'data/n2_trans.txt'), unpack=True)
        self.air_e_data, self.air_trans_data = np.loadtxt(os.path.join(root_dir, 'data/air_trans.txt'), unpack=True)
        self.he_e_data, self.he_trans_data = np.loadtxt(os.path.join(root_dir, 'data/he_trans.txt'), unpack=True)

        self.gas_values = {'Nitrogen'   : (self.n2_e_data, self.n2_trans_data),
            'Air'       : (self.air_e_data, self.air_trans_data),
            'Helium'    : (self.he_e_data, self.he_trans_data),
            }

        #Ionization energies in eV are from x-ray data booklet table 4-3: http://xdb.lbl.gov/
        self.ionization_energy = {'Nitrogen'    : 36,
            'Helium'    : 41,
            'Air'       : 34.4,
            }

        self.chambers = {'BioCAT Standard'  : '6.02',
            'BioCAT Micro'  : '1.0'}

        if self.chamber_type.GetStringSelection() == 'Custom':
            self.chamber_length.Enable()
        else:
            self.chamber_length.Disable()
            length = self.chambers[self.chamber_type.GetStringSelection()]
            self.chamber_length.SetValue(length)

    def _on_chamber_type(self, evt):
        if self.chamber_type.GetStringSelection() == 'Custom':
            self.chamber_length.Enable()
        else:
            self.chamber_length.Disable()
            length = self.chambers[self.chamber_type.GetStringSelection()]
            self.chamber_length.SetValue(length)

    def _on_calc(self, evt):
        energy = float(self.energy_ctrl.GetValue())*1000
        length = float(self.chamber_length.GetValue())
        gain = float(self.gain.GetStringSelection())
        voltage = float(self.voltage.GetValue())
        gas = self.gas_ctrl.GetStringSelection()

        gas_e_data, gas_trans_data = self.gas_values[gas]
        trans_data = np.exp(np.log(gas_trans_data)*length)
        transmission_func = interp.interp1d(gas_e_data, trans_data)

        ionization_energy = self.ionization_energy[gas]

        transmission = transmission_func(energy)

        n_electrons = voltage/gain/constants.e
        n_photons = n_electrons/(energy/ionization_energy)

        tot_photons = n_photons/(1-transmission)

        self.flux.SetLabel('{:.3e}'.format(tot_photons))


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

class ICCalcFrame(wx.Frame):
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

        ic_calc_panel = ICCalcPanel(self.name, self.mx_database, self)
        ic_calc_box_sizer = wx.StaticBoxSizer(wx.StaticBox(self, label='Ion Chamber Calculator'))
        ic_calc_box_sizer.Add(ic_calc_panel)

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
    mp.set_program_name("ic_calc")

    # mx_database = None

    app = wx.App()
    frame = ICCalcFrame(None, mx_database, parent=None, title='Test Icon Chamber Calculator')
    frame.Show()
    app.MainLoop()
