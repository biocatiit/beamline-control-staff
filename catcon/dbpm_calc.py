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



class DBPMCalcPanel(wx.Panel):
    """
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

    def on_close(self):
        pass

    def _FromDIP(self, size):
        # This is a hack to provide easy back compatibility with wxpython < 4.1
        try:
            return self.FromDIP(size)
        except Exception:
            return size

    def _create_layout(self):
        """
        Creates the layout for the panel.

        """

        self.energy_ctrl = wx.TextCtrl(self, size=self._FromDIP((60, -1)),
            style=wx.TE_PROCESS_ENTER, validator=utils.CharValidator('float_te'),
            value='12.0')
        self.dbpm_type = wx.Choice(self, choices=['BioCAT D hutch', 'BioCAT C hutch', 'Custom'])
        self.dbpm_type.SetStringSelection('BioCAT D hutch')
        self.diamond_thickness = wx.TextCtrl(self, size=self._FromDIP((60, -1)),
            style=wx.TE_PROCESS_ENTER, validator=utils.CharValidator('float_te'))
        self.diamond_thickness.Disable()
        self.gain = wx.Choice(self, choices=['1e2', '1e3', '1e4', '1e5', '1e6', '1e7', '1e8', '1e9', '1e10'])
        self.gain.SetStringSelection('1e5')
        self.voltage = wx.TextCtrl(self, size=self._FromDIP((60, -1)),
            validator=utils.CharValidator('float_te'))

        self.calculate = wx.Button(self, label='Calculate')

        # self.energy_ctrl.Bind(wx.EVT_TEXT_ENTER, self._on_energy_change)
        # self.energy_ctrl.Bind(wx.EVT_TEXT, self._on_text)
        # self.diamond_thickness.Bind(wx.EVT_TEXT, self._on_text)

        self.dbpm_type.Bind(wx.EVT_CHOICE, self._on_dbpm_type)
        self.calculate.Bind(wx.EVT_BUTTON, self._on_calc)


        calc_controls = wx.FlexGridSizer(cols=2, vgap=self._FromDIP(5),
            hgap=self._FromDIP(3))

        calc_controls.Add(wx.StaticText(self, label='Energy [keV]:'),
            flag=wx.ALIGN_CENTER_VERTICAL)
        calc_controls.Add(self.energy_ctrl, flag=wx.ALIGN_CENTER_VERTICAL)
        calc_controls.Add(wx.StaticText(self, label='Diamond BPM type:'),
            flag=wx.ALIGN_CENTER_VERTICAL)
        calc_controls.Add(self.dbpm_type, flag=wx.ALIGN_CENTER_VERTICAL)
        calc_controls.Add(wx.StaticText(self, label='Diamond thickness [um]:'),
            flag=wx.ALIGN_CENTER_VERTICAL)
        calc_controls.Add(self.diamond_thickness, flag=wx.ALIGN_CENTER_VERTICAL)
        calc_controls.Add(wx.StaticText(self, label='Amplifier Gain [V/A]:'),
            flag=wx.ALIGN_CENTER_VERTICAL)
        calc_controls.Add(self.gain, flag=wx.ALIGN_CENTER_VERTICAL)
        calc_controls.Add(wx.StaticText(self, label='Voltage [V]:'),
            flag=wx.ALIGN_CENTER_VERTICAL)
        calc_controls.Add(self.voltage, flag=wx.ALIGN_CENTER_VERTICAL)


        self.flux = wx.StaticText(self, label='')
        font = self.GetFont().Bold()
        self.flux.SetFont(font)

        flux_sizer = wx.StaticBoxSizer(wx.StaticBox(self, label='Flux'),
            wx.HORIZONTAL)
        flux_sizer.Add(wx.StaticText(self, label='Flux [ph/s]:'),
            flag=wx.ALIGN_CENTER_VERTICAL|wx.ALL, border=self._FromDIP(3))
        flux_sizer.Add(self.flux, border=self._FromDIP(3), flag=wx.ALIGN_CENTER_VERTICAL|wx.ALL)
        flux_sizer.AddStretchSpacer(1)

        control_sizer = wx.StaticBoxSizer(wx.StaticBox(self, label='Controls'),
            wx.VERTICAL)
        control_sizer.Add(calc_controls)
        control_sizer.Add(self.calculate, border=self._FromDIP(10),
            flag=wx.ALIGN_CENTER_HORIZONTAL|wx.TOP|wx.BOTTOM)

        top_sizer = wx.BoxSizer(wx.VERTICAL)
        top_sizer.Add(control_sizer)
        top_sizer.Add(flux_sizer, border=self._FromDIP(5), flag=wx.TOP|wx.EXPAND)


        self.Bind(wx.EVT_RIGHT_DOWN, self._on_rightclick)
        for item in self.GetChildren():
            if (isinstance(item, wx.StaticText) or isinstance(item, wx.StaticBox)):
                item.Bind(wx.EVT_RIGHT_DOWN, self._on_rightclick)

        self.SetSizer(top_sizer)


    def _initialize(self):
        root_dir = os.path.split(__file__)[0]
        self.atten_e_data, self.atten_len_data = np.loadtxt(os.path.join(root_dir, 'data/c_atten.txt'), unpack=True)
        self.get_atten_len = interp.interp1d(self.atten_e_data, self.atten_len_data)



        #Ionization energies in eV are from x-ray data booklet table 4-3: http://xdb.lbl.gov/
        #Ionization energies in eV from Sydor, consistent with Bohon et al. 2010, JSR
        self.ionization_energy = 13.3

        self.dbpms = {'BioCAT D hutch'  : '62.80',
            'BioCAT C hutch'  : '12'}

        if self.dbpm_type.GetStringSelection() == 'Custom':
            self.diamond_thickness.Enable()
        else:
            self.diamond_thickness.Disable()
            length = self.dbpms[self.dbpm_type.GetStringSelection()]
            self.diamond_thickness.SetValue(length)

    def _on_dbpm_type(self, evt):
        if self.dbpm_type.GetStringSelection() == 'Custom':
            self.diamond_thickness.Enable()
        else:
            self.diamond_thickness.Disable()
            length = self.dbpms[self.dbpm_type.GetStringSelection()]
            self.diamond_thickness.SetValue(length)

    def _on_calc(self, evt):
        energy = float(self.energy_ctrl.GetValue())*1000
        length = float(self.diamond_thickness.GetValue())
        gain = float(self.gain.GetStringSelection())
        voltage = float(self.voltage.GetValue())

        atten_length = self.get_atten_len(energy)
        transmission = math.exp(-length/atten_length)

        n_electrons = voltage/gain/constants.e
        n_photons = n_electrons/(energy/self.ionization_energy)

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
            if (not isinstance(item, wx.StaticText) and not isinstance(item, wx.StaticBox)):
                item.Enable(self._enabled)

class DBPMCalcFrame(wx.Frame):
    """
    A lightweight amplifier frame designed to hold an arbitrary number of dios
    in an arbitrary grid pattern.
    """
    def __init__(self, name, mx_database, *args, **kwargs):
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

        top_sizer = self._create_layout()

        self.SetSizer(top_sizer)
        self.Layout()
        self.Fit()
        self.Raise()


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

        ic_calc_panel = DBPMCalcPanel(self.name, self.mx_database, self)
        ic_calc_box_sizer = wx.StaticBoxSizer(wx.StaticBox(self, label='DBPM Calculator'))
        ic_calc_box_sizer.Add(ic_calc_panel)

        return ic_calc_box_sizer

if __name__ == '__main__':

    mx_database = None

    app = wx.App()
    frame = DBPMCalcFrame(None, mx_database, parent=None, title='Test DBPM Calculator')
    frame.Show()
    app.MainLoop()
