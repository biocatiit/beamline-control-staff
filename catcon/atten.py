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

import utils
utils.set_mppath() #This must be done before importing any Mp Modules.
import Mp as mp
import MpCa as mpca
import MpWx as mpwx
import custom_widgets


class AttenuatorPanel(wx.Panel):
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

        if self.mx_database is not None:
            self._get_attenuators()
            self.atten_ctrl.SetStringSelection(self.atten_factors_reverse[self.current_attenuation])
            self.trans_ctrl.SetStringSelection(self.transmission_vals_reverse[self.current_attenuation])


    def _create_layout(self):
        """
        Creates the layout for the panel.

        """

        self.energy_ctrl = wx.TextCtrl(self, size=(60, -1), style=wx.TE_PROCESS_ENTER,
            validator=utils.CharValidator('float_te'))
        self.trans_ctrl = wx.ComboBox(self, size=(120,-1), style=wx.TE_PROCESS_ENTER,
            validator=utils.CharValidator('float_te'))
        self.atten_ctrl = wx.ComboBox(self, size=(120, -1), style=wx.TE_PROCESS_ENTER,
            validator=utils.CharValidator('float_te'))

        self.energy_ctrl.Bind(wx.EVT_TEXT_ENTER, self._on_energy_change)
        self.trans_ctrl.Bind(wx.EVT_TEXT_ENTER, self._on_trans_change)
        self.atten_ctrl.Bind(wx.EVT_TEXT_ENTER, self._on_atten_change)
        self.trans_ctrl.Bind(wx.EVT_COMBOBOX, self._on_trans_change)
        self.atten_ctrl.Bind(wx.EVT_COMBOBOX, self._on_atten_change)

        self.energy_ctrl.Bind(wx.EVT_TEXT, self._on_text)
        self.trans_ctrl.Bind(wx.EVT_TEXT, self._on_text)
        self.atten_ctrl.Bind(wx.EVT_TEXT, self._on_text)

        atten_controls = wx.FlexGridSizer(cols=2, rows=3, vgap=5, hgap=3)

        atten_controls.Add(wx.StaticText(self, label='Energy (keV):'))
        atten_controls.Add(self.energy_ctrl)
        atten_controls.Add(wx.StaticText(self, label='Transmission:'))
        atten_controls.Add(self.trans_ctrl)
        atten_controls.Add(wx.StaticText(self, label='Attenuation factor:'))
        atten_controls.Add(self.atten_ctrl)

        top_sizer = wx.BoxSizer(wx.VERTICAL)
        top_sizer.Add(atten_controls)


        self.Bind(wx.EVT_RIGHT_DOWN, self._on_rightclick)
        for item in self.GetChildren():
            if (isinstance(item, wx.StaticText) or isinstance(item, mpwx.Value)
                or isinstance(item, custom_widgets.CustomEpicsValue) or isinstance(item, wx.StaticBox)):
                item.Bind(wx.EVT_RIGHT_DOWN, self._on_rightclick)

        self.SetSizer(top_sizer)


    def _initialize(self):
        self.setting_attenuation = False
        self.current_attenuation = 1

        self.attenuator_thickness = [1, 2, 4, 8, 16, 32]
        self.energy = 12    #Energy in keV

        root_dir = os.path.split(__file__)[0]

        self.atten_e_data, self.atten_len_data = np.loadtxt(os.path.join(root_dir, 'data/al_atten.txt'), unpack=True)
        self.get_atten_len = interp.interp1d(self.atten_e_data, self.atten_len_data)

        self.attenuator_combos = []

        for i in range(1, len(self.attenuator_thickness)+1):
            self.attenuator_combos.extend(list(itertools.combinations(self.attenuator_thickness, i)))

        self._calc_attens()

        self.trans_ctrl.Set(self.trans_choices)
        self.atten_ctrl.Set(self.atten_choices)
        self.energy_ctrl.ChangeValue(str(self.energy))

        if self.mx_database is not None:
            self.mx_attens = {
                1   : self.mx_database.get_record('avme944x_out0'),
                2   : self.mx_database.get_record('avme944x_out1'),
                4   : self.mx_database.get_record('avme944x_out2'),
                8   : self.mx_database.get_record('avme944x_out3'),
                16  : self.mx_database.get_record('avme944x_out4'),
                32  : self.mx_database.get_record('avme944x_out5'),
            }

            self.mx_attens_outs = {
                1   : self.mx_database.get_record('avme944x_in8'),
                2   : self.mx_database.get_record('avme944x_in1'),
                4   : self.mx_database.get_record('avme944x_in2'),
                8   : self.mx_database.get_record('avme944x_in3'),
                16  : self.mx_database.get_record('avme944x_in4'),
                32  : self.mx_database.get_record('avme944x_in5'),
            }

            # for atten_out in self.mx_attens_outs.values():
            #     dio_type = atten_out.get_field('mx_type')

            #     if dio_type.startswith('epics'):
            #         self.callback_pvs = []
            #         self.callbacks = []

            #         pv_name = atten_out.get_field('epics_variable_name')
            #         pv = mpca.PV(pv_name)
            #         self.callback_pvs.append(pv)

            #         callback = pv.add_callback(mpca.DBE_VALUE, self._atten_callback, pv)
            #         self.callbacks.append(callback)

            #         try:
            #             pv.caget()
            #         except mp.Not_Found_Error:
            #             pass

            #         mpca.poll()

        self.get_atten_timer = wx.Timer()
        self.get_atten_timer.Bind(wx.EVT_TIMER, self._atten_poll)

        self.get_atten_timer.Start(1000)



    def _on_text(self, evt):
        widget = evt.GetEventObject()
        widget.SetBackgroundColour('yellow')

    def _on_energy_change(self, evt):
        self.energy = float(self.energy_ctrl.GetValue())

        self._calc_attens()

        vals = np.array(self.attenuations.keys())
        idx = (np.abs(vals-self.current_attenuation)).argmin()
        new_attenuation = vals[idx]

        self.trans_ctrl.Set(self.trans_choices)
        self.atten_ctrl.Set(self.atten_choices)

        self.trans_ctrl.SetStringSelection(self.transmission_vals_reverse[new_attenuation])
        self.atten_ctrl.SetStringSelection(self.atten_factors_reverse[new_attenuation])

        self._set_attenuators(new_attenuation)

        widget = evt.GetEventObject()
        widget.SetBackgroundColour(wx.NullColour)

    def _on_atten_change(self, evt):
        atten = self.atten_ctrl.GetValue()

        if atten in self.atten_choices:
            attenuation = self.atten_factors[atten]
        else:
            trans = 1./float(atten)
            vals = np.array(self.attenuations.keys())

            idx = (np.abs(vals-trans)).argmin()

            attenuation = vals[idx]

            self.atten_ctrl.SetStringSelection(self.atten_factors_reverse[attenuation])

        self.trans_ctrl.SetStringSelection(self.transmission_vals_reverse[attenuation])

        self._set_attenuators(attenuation)

        self.trans_ctrl.SetBackgroundColour(wx.NullColour)
        self.atten_ctrl.SetBackgroundColour(wx.NullColour)

    def _on_trans_change(self, evt):
        trans = self.trans_ctrl.GetValue()

        if trans in self.trans_choices:
            attenuation = self.transmission_vals[trans]
        else:
            trans = float(trans)
            vals = np.array(self.attenuations.keys())

            idx = (np.abs(vals-trans)).argmin()

            attenuation = vals[idx]

            self.trans_ctrl.SetStringSelection(self.transmission_vals_reverse[attenuation])

        self.atten_ctrl.SetStringSelection(self.atten_factors_reverse[attenuation])

        self._set_attenuators(attenuation)

        self.trans_ctrl.SetBackgroundColour(wx.NullColour)
        self.atten_ctrl.SetBackgroundColour(wx.NullColour)

    def _calc_attens(self):
        self.atten_length = self.get_atten_len(self.energy*1000)

        self.attenuations = {1.0 : (None, 0, 0)}

        for combo in self.attenuator_combos:
            length = sum(combo)*20 #length in microns
            atten = math.exp(-length/self.atten_length)

            self.attenuations[atten] = (combo, length, atten)

        self.transmission_vals = {}
        self.atten_factors = {}
        self.transmission_vals_reverse = {}
        self.atten_factors_reverse = {}

        for atten in self.attenuations.keys():
            factor = 1./atten

            if atten > 0.1:
                trans = '{}'.format(round(atten, 3))
            elif atten > 0.01:
                trans = '{}'.format(round(atten, 4))
            else:
                trans = '{}'.format(round(atten, 5))

            if factor > 100:
                factor = '{}'.format(round(factor, 0))
            elif factor > 10:
                factor = '{}'.format(round(factor, 1))
            else:
                factor = '{}'.format(round(factor, 2))

            self.transmission_vals[trans] = atten
            self.atten_factors[factor] = atten

            self.transmission_vals_reverse[atten] = trans
            self.atten_factors_reverse[atten] = factor

        self.trans_choices = sorted(self.transmission_vals.keys(), reverse=True, key=lambda x: float(x))
        self.atten_choices = sorted(self.atten_factors.keys(), reverse=False, key=lambda x: float(x))

    def _set_attenuators(self, attenuation):
        self.setting_attenuation = True

        self.current_attenuation = attenuation

        used_attens = self.attenuations[attenuation][0]

        if used_attens is not None:
            for foil, mx_atten in self.mx_attens.items():
                if foil in used_attens:
                    mx_atten.write(0)
                else:
                    mx_atten.write(1)
        else:
            for mx_atten in self.mx_attens.values():
                mx_atten.write(1)

        time.sleep(0.5)

        self.setting_attenuation = False

    def _atten_poll(self, evt):
        if not self.setting_attenuation:
            self._get_attenuators()

    def _get_attenuators(self):
        length = 0
        for foil, atten_out in self.mx_attens_outs.items():
            if not atten_out.read():
                length = length + foil

        length = length*20
        old_attenuation = self.current_attenuation
        self.current_attenuation = math.exp(-length/self.atten_length)

        if old_attenuation != self.current_attenuation:
            self.trans_ctrl.SetStringSelection(self.transmission_vals_reverse[self.current_attenuation])
            self.atten_ctrl.SetStringSelection(self.atten_factors_reverse[self.current_attenuation])

            self.trans_ctrl.SetBackgroundColour(wx.NullColour)
            self.atten_ctrl.SetBackgroundColour(wx.NullColour)


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

class AttenuatorFrame(wx.Frame):
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

        atten_panel = AttenuatorPanel(self.name, self.mx_database, self)
        atten_box_sizer = wx.StaticBoxSizer(wx.StaticBox(self, label='Attenuator Controls'))
        atten_box_sizer.Add(atten_panel)

        return atten_box_sizer

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
    mp.set_program_name("attenuators")

    # mx_database = None

    app = wx.App()
    frame = AttenuatorFrame(None, mx_database, parent=None, title='Test Attenuator Control')
    frame.Show()
    app.MainLoop()
