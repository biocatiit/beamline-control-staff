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
import traceback

import wx
import numpy as np
import scipy.interpolate as interp
import epics, epics.wx

import utils
utils.set_mppath() #This must be done before importing any Mp Modules.
try:
    import Mp as mp
    import MpCa as mpca
    import MpWx as mpwx
    import custom_widgets
except Exception:
    traceback.print_exc()
    pass

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

    def on_close(self):
        pass


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
                or isinstance(item, wx.StaticBox)):
                item.Bind(wx.EVT_RIGHT_DOWN, self._on_rightclick)

        self.SetSizer(top_sizer)


    def _initialize(self):
        self.setting_attenuation = False
        self.current_attenuation = 1

        self.attenuator_position = [1, 2, 3, 4, 5, 6]
        self.attenuator_thickness = {1: 21.867, 2: 43.305, 3: 85.385, 4: 171.128,
            5: 346.461, 6: 676.116} #thickness in microns

        self.energy = 12    #Energy in keV

        root_dir = os.path.split(__file__)[0]

        self.atten_e_data, self.atten_len_data = np.loadtxt(os.path.join(root_dir, 'data/al_atten.txt'), unpack=True)
        self.get_atten_len = interp.interp1d(self.atten_e_data, self.atten_len_data)

        self.attenuator_combos = []

        for i in range(1, len(self.attenuator_position)+1):
            self.attenuator_combos.extend(list(itertools.combinations(self.attenuator_position, i)))

        self._calc_attens()

        self.trans_ctrl.Set(self.trans_choices)
        self.atten_ctrl.Set(self.atten_choices)
        self.energy_ctrl.ChangeValue(str(self.energy))

        if self.mx_database is not None:
            self.mx_attens = {
                1   : self.mx_database.get_record('do_0'),
                2   : self.mx_database.get_record('do_1'),
                3   : self.mx_database.get_record('do_2'),
                4   : self.mx_database.get_record('do_3'),
                5   : self.mx_database.get_record('do_4'),
                6   : self.mx_database.get_record('do_5'),
            }

            self.mx_attens_outs = {
                1   : self.mx_database.get_record('di_0'),
                2   : self.mx_database.get_record('di_1'),
                3   : self.mx_database.get_record('di_2'),
                4   : self.mx_database.get_record('di_3'),
                5   : self.mx_database.get_record('di_4'),
                6   : self.mx_database.get_record('di_5'),
            }

        self.get_atten_timer = wx.Timer()
        self.get_atten_timer.Bind(wx.EVT_TIMER, self._atten_poll)

        self.get_atten_timer.Start(1000)



    def _on_text(self, evt):
        widget = evt.GetEventObject()
        widget.SetBackgroundColour('yellow')

    def _on_energy_change(self, evt):
        self.energy = float(self.energy_ctrl.GetValue())

        self._calc_attens()

        vals = np.array(list(self.attenuations.keys()))
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
            vals = np.array(list(self.attenuations.keys()))

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
            vals = np.array(list(self.attenuations.keys()))

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
            length = 0
            for pos in combo:
                length += self.attenuator_thickness[pos]
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
                    if mx_atten.read():
                        mx_atten.write(0)
                else:
                    if not mx_atten.read():
                        mx_atten.write(1)
        else:
            for mx_atten in self.mx_attens.values():
                if not mx_atten.read():
                    mx_atten.write(1)

        time.sleep(0.5)

        self.setting_attenuation = False

    def _atten_poll(self, evt):
        if not self.setting_attenuation:
            self._get_attenuators()

    def _get_attenuators(self):
        length = 0
        for pos, atten_out in self.mx_attens_outs.items():
            if not atten_out.read():
                length += self.attenuator_thickness[pos]

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
                and not isinstance(item, wx.StaticBox)):
                item.Enable(self._enabled)

class AttenuatorPanel2(wx.Panel):
    """
    For the Huber attenuator
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

        self.callback_ids = {}

        self._initialize_pvs()
        self._create_layout()
        self._initialize()

        self._get_attenuators()
        self.atten_ctrl.SetStringSelection(self.atten_factors_reverse[self.current_attenuation])
        self.trans_ctrl.SetStringSelection(self.transmission_vals_reverse[self.current_attenuation])

    def _FromDIP(self, size):
        # This is a hack to provide easy back compatibility with wxpython < 4.1
        try:
            return self.FromDIP(size)
        except Exception:
            return size

    def on_close(self):
        for atten in self.callback_ids:
            ids_dict = self.callback_ids[atten]
            pvs_dict = self.atten_pvs[atten]

            for cb_pv_id in ids_dict:
                pv = pvs_dict[cb_pv_id]
                pv.remove_callback(ids_dict[cb_pv_id])

        for ctrl in self._single_atten_crls:
            ctrl.remove_callbacks()

    def _create_layout(self):
        """
        Creates the layout for the panel.

        """

        self._single_atten_crls = []

        atten_ctrl_box = wx.StaticBox(self, label='Attenuation')

        self.energy_ctrl = wx.TextCtrl(atten_ctrl_box, size=self._FromDIP((60, -1)),
            style=wx.TE_PROCESS_ENTER, validator=utils.CharValidator('float_te'))
        self.trans_ctrl = wx.ComboBox(atten_ctrl_box, size=self._FromDIP((120,-1)),
            style=wx.TE_PROCESS_ENTER, validator=utils.CharValidator('float_te'))
        self.atten_ctrl = wx.ComboBox(atten_ctrl_box, size=self._FromDIP((120, -1)),
            style=wx.TE_PROCESS_ENTER, validator=utils.CharValidator('float_te'))

        self.energy_ctrl.Bind(wx.EVT_TEXT_ENTER, self._on_energy_change)
        self.trans_ctrl.Bind(wx.EVT_TEXT_ENTER, self._on_trans_change)
        self.atten_ctrl.Bind(wx.EVT_TEXT_ENTER, self._on_atten_change)
        self.trans_ctrl.Bind(wx.EVT_COMBOBOX, self._on_trans_change)
        self.atten_ctrl.Bind(wx.EVT_COMBOBOX, self._on_atten_change)

        self.energy_ctrl.Bind(wx.EVT_TEXT, self._on_text)
        self.trans_ctrl.Bind(wx.EVT_TEXT, self._on_text)
        self.atten_ctrl.Bind(wx.EVT_TEXT, self._on_text)

        atten_controls = wx.FlexGridSizer(cols=2, vgap=self._FromDIP(5),
            hgap=self._FromDIP(3))

        atten_controls.Add(wx.StaticText(atten_ctrl_box, label='Energy (keV):'),
            flag=wx.ALIGN_CENTER_VERTICAL)
        atten_controls.Add(self.energy_ctrl, flag=wx.ALIGN_CENTER_VERTICAL)
        atten_controls.Add(wx.StaticText(atten_ctrl_box, label='Transmission:'),
            flag=wx.ALIGN_CENTER_VERTICAL)
        atten_controls.Add(self.trans_ctrl, flag=wx.ALIGN_CENTER_VERTICAL)
        atten_controls.Add(wx.StaticText(atten_ctrl_box, label='Attenuation factor:'),
            flag=wx.ALIGN_CENTER_VERTICAL)
        atten_controls.Add(self.atten_ctrl, flag=wx.ALIGN_CENTER_VERTICAL)

        atten_ctrl_sizer = wx.StaticBoxSizer(atten_ctrl_box, wx.VERTICAL)
        atten_ctrl_sizer.Add(atten_controls, flag=wx.ALL, border=self._FromDIP(5))


        shutter_ctrl = SingleAttenCtrl(self.atten_pvs[1], 'Shutter',
            ['Closed', 'Open'], self.calc_attenuation, self)

        self._single_atten_crls.append(shutter_ctrl)

        shutter_sizer = wx.BoxSizer(wx.VERTICAL)
        shutter_sizer.Add(shutter_ctrl)

        # Add individual attenuator controls in collapsible pane (or just visible?)
        # Add static box for attenuator?

        atten_box = wx.StaticBox(self, label='Individual attenuators')
        atten_parent = atten_box

        atten_sub_sizer = wx.FlexGridSizer(cols=2, hgap=self._FromDIP(5),
            vgap=self._FromDIP(5))

        for atten in self.attenuator_thickness:
            ctrl = SingleAttenCtrl(self.atten_pvs[atten], 'Atten. {}'.format(atten),
            ['In', 'Out'], self.calc_attenuation, atten_parent)

            self._single_atten_crls.append(ctrl)

            atten_sub_sizer.Add(ctrl)

        atten_single_sizer = wx.StaticBoxSizer(atten_box, wx.VERTICAL)
        atten_single_sizer.Add(atten_sub_sizer)

        main_sizer = wx.BoxSizer(wx.HORIZONTAL)
        main_sizer.Add(shutter_sizer)
        main_sizer.Add(atten_ctrl_sizer, flag=wx.LEFT, border=self._FromDIP(5))

        top_sizer =wx.BoxSizer(wx.VERTICAL)
        top_sizer.Add(main_sizer, flag=wx.LEFT|wx.RIGHT|wx.TOP,
            border=self._FromDIP(5))
        top_sizer.Add(atten_single_sizer, flag=wx.ALL, border=self._FromDIP(5))

        self.SetSizer(top_sizer)


    def _initialize_pvs(self):
        self.attenuator_position = [1, 2, 3, 4, 5, 6, 7, 8]
        self.atten_pvs = {}


        for atten in self.attenuator_position:
            huber_pv_list = [
                '18ID:HUBER1:A{}Out'.format(atten),
                '18ID:HUBER1:T{}'.format(atten),
                '18ID:HUBER1:L{}'.format(atten),
                ]

            self.atten_pvs[atten] = {}

            for pv_name in huber_pv_list:
                pv = epics.get_pv(pv_name)
                connected = pv.wait_for_connection(5)

                if not connected:
                    logger.error('Failed to connect to EPICS PV %s on startup', pv_name)

                else:
                    if 'Out' in pv_name:
                        self.atten_pvs[atten]['ctrl'] = pv
                        cb_id = pv.add_callback(self._on_atten_pv_callback)
                        self.callback_ids[atten] = {'ctrl' : cb_id}
                    elif 'T{}'.format(atten) in pv_name:
                        self.atten_pvs[atten]['thickness'] = pv
                    elif 'L{}'.format(atten) in pv_name:
                        self.atten_pvs[atten]['material'] = pv

        self.attenuator_thickness = {}

        for atten in self.atten_pvs:
            if self.atten_pvs[atten]['material'].get().lower() == 'al':
                self.attenuator_thickness[atten] = float(self.atten_pvs[atten]['thickness'].get())
                #thickness in microns

    def _initialize(self):
        self.setting_attenuation = False
        self.current_attenuation = 1

        atten_keys = list(self.attenuator_thickness.keys())

        self.energy = 12    #Energy in keV

        root_dir = os.path.split(__file__)[0]

        self.atten_e_data, self.atten_len_data = np.loadtxt(os.path.join(root_dir, 'data/al_atten.txt'), unpack=True)
        self.get_atten_len = interp.interp1d(self.atten_e_data, self.atten_len_data)

        self.attenuator_combos = []

        for i in range(1, len(atten_keys)+1):
            self.attenuator_combos.extend(list(itertools.combinations(atten_keys, i)))

        self._calc_attens()

        self.trans_ctrl.Set(self.trans_choices)
        self.atten_ctrl.Set(self.atten_choices)
        self.energy_ctrl.ChangeValue(str(self.energy))

        for ctrl in self._single_atten_crls:
            ctrl.set_atten()

        self.trans_ctrl.SetBackgroundColour(wx.NullColour)
        self.atten_ctrl.SetBackgroundColour(wx.NullColour)

    def _on_text(self, evt):
        widget = evt.GetEventObject()
        widget.SetBackgroundColour('yellow')

    def _on_energy_change(self, evt):
        self.energy = float(self.energy_ctrl.GetValue())

        self._calc_attens()

        vals = np.array(list(self.attenuations.keys()))
        idx = (np.abs(vals-self.current_attenuation)).argmin()
        new_attenuation = vals[idx]

        self.trans_ctrl.Set(self.trans_choices)
        self.atten_ctrl.Set(self.atten_choices)

        self.trans_ctrl.SetStringSelection(self.transmission_vals_reverse[new_attenuation])
        self.atten_ctrl.SetStringSelection(self.atten_factors_reverse[new_attenuation])

        self._set_attenuators(new_attenuation)

        widget = evt.GetEventObject()
        widget.SetBackgroundColour(wx.NullColour)

        for ctrl in self._single_atten_crls:
            ctrl.set_atten()

    def _on_atten_change(self, evt):
        atten = self.atten_ctrl.GetValue()

        if atten in self.atten_choices:
            attenuation = self.atten_factors[atten]
        else:
            trans = 1./float(atten)
            vals = np.array(list(self.attenuations.keys()))

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
            vals = np.array(list(self.attenuations.keys()))

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
            length = 0
            for pos in combo:
                length += self.attenuator_thickness[pos]
            atten = self.calc_attenuation(length)

            self.attenuations[atten] = (combo, length, atten)

        self.transmission_vals = {}
        self.atten_factors = {}
        self.transmission_vals_reverse = {}
        self.atten_factors_reverse = {}

        for atten in self.attenuations.keys():
            factor = 1./atten

            if atten > 0.1:
                trans = '{:.3f}'.format(round(atten, 3))
            elif atten > 0.01:
                trans = '{:.4f}'.format(round(atten, 4))
            else:
                trans = '{:.2e}'.format(atten)

            if factor > 100:
                factor = '{:d}'.format(int(round(factor, 0)))
            elif factor > 10:
                factor = '{:.1f}'.format(round(factor, 1))
            else:
                factor = '{:.2f}'.format(round(factor, 2))

            self.transmission_vals[trans] = atten
            self.atten_factors[factor] = atten

            self.transmission_vals_reverse[atten] = trans
            self.atten_factors_reverse[atten] = factor

        self.trans_choices = sorted(self.transmission_vals.keys(), reverse=True, key=lambda x: float(x))
        self.atten_choices = sorted(self.atten_factors.keys(), reverse=False, key=lambda x: float(x))

    def calc_attenuation(self, length):
        return math.exp(-length/self.atten_length)

    def _set_attenuators(self, attenuation):
        self.setting_attenuation = True

        self.current_attenuation = attenuation

        used_attens = self.attenuations[attenuation][0]

        if used_attens is not None:
            for atten in self.attenuator_thickness:
                pv = self.atten_pvs[atten]['ctrl']

                if atten in used_attens:
                    if not pv.get():
                        pv.put(1)
                else:
                    if pv.get():
                        pv.put(0)
        else:
            for atten in self.attenuator_thickness:
                pv = self.atten_pvs[atten]['ctrl']

                if pv.get():
                    pv.put(0)

        time.sleep(0.5)

        self.setting_attenuation = False

    def _get_attenuators(self):
        length = 0
        for atten in self.attenuator_thickness:
            pv = self.atten_pvs[atten]['ctrl']
            if pv.get():
                length += self.attenuator_thickness[atten]

        old_attenuation = self.current_attenuation
        self.current_attenuation = math.exp(-length/self.atten_length)

        if old_attenuation != self.current_attenuation:
            self.trans_ctrl.SetStringSelection(self.transmission_vals_reverse[self.current_attenuation])
            self.atten_ctrl.SetStringSelection(self.atten_factors_reverse[self.current_attenuation])

            self.trans_ctrl.SetBackgroundColour(wx.NullColour)
            self.atten_ctrl.SetBackgroundColour(wx.NullColour)

    def _on_atten_pv_callback(self, **kwargs):
        wx.CallAfter(self._get_attenuators)

class SingleAttenCtrl(wx.Panel):
    def __init__(self, pvs, name, on_off_labels, calc_callback, *args, **kwargs):
        wx.Panel.__init__(self, *args, **kwargs)

        self.pvs = pvs
        self.calc_callback = calc_callback

        self.callback_ids = {}

        self._create_layout(name, on_off_labels)
        self._initialize()



    def _FromDIP(self, size):
        # This is a hack to provide easy back compatibility with wxpython < 4.1
        try:
            return self.FromDIP(size)
        except Exception:
            return size

    def _create_layout(self, name, on_off_labels):
        box = wx.StaticBox(self, label=name)

        parent = box

        self._thickness = epics.wx.PVText(parent, self.pvs['thickness'])
        self._material = epics.wx.PVText(parent, self.pvs['material'])
        self._nom_atten = wx.StaticText(parent, size=self._FromDIP((60,-1)),
            style=wx.ST_NO_AUTORESIZE)

        indic = wx.Image(os.path.join('.', 'resources', 'red_circle.png'))
        indic.Rescale(self._FromDIP(20), self._FromDIP(20))
        indic = indic.ConvertToBitmap()

        self._indic_btm = wx.StaticBitmap(parent, bitmap=indic)

        info_sizer = wx.FlexGridSizer(cols=2, vgap=self._FromDIP(5),
            hgap=self._FromDIP(5))
        info_sizer.Add(wx.StaticText(parent, label='Material:'),
            flag=wx.ALIGN_CENTER_VERTICAL)
        info_sizer.Add(self._material)
        info_sizer.Add(wx.StaticText(parent, label='Thick. [um]:'),
            flag=wx.ALIGN_CENTER_VERTICAL)
        info_sizer.Add(self._thickness)
        info_sizer.Add(wx.StaticText(parent, label='Attenuation:'),
            flag=wx.ALIGN_CENTER_VERTICAL)
        info_sizer.Add(self._nom_atten)

        self._in = epics.wx.PVRadioButton(parent, self.pvs['ctrl'], 1,
            label=on_off_labels[0], style=wx.RB_GROUP)
        self._out = epics.wx.PVRadioButton(parent, self.pvs['ctrl'], 0,
            label=on_off_labels[1])

        self._ctrl_sizer = wx.BoxSizer(wx.VERTICAL)
        self._ctrl_sizer.Add(self._in)
        self._ctrl_sizer.Add(self._out, flag=wx.TOP, border=self._FromDIP(5))
        self._ctrl_sizer.Add(self._indic_btm, flag=wx.TOP|wx.ALIGN_CENTER_HORIZONTAL|
            wx.RESERVE_SPACE_EVEN_IF_HIDDEN,
            border=self._FromDIP(5))

        if self.pvs['ctrl'].get() == 0:
            self._ctrl_sizer.Hide(self._indic_btm)

        top_sizer = wx.StaticBoxSizer(box, wx.HORIZONTAL)
        top_sizer.Add(info_sizer)
        top_sizer.Add(self._ctrl_sizer, flag=wx.LEFT, border=self._FromDIP(5))

        self.SetSizer(top_sizer)

    def _initialize(self):
        cb_id = self.pvs['ctrl'].add_callback(self._on_atten_pv_callback)

        self.callback_ids['ctrl'] = cb_id

    def set_atten(self):
        if self.pvs['material'].get().lower() == 'al':
            atten = self.calc_callback(self.pvs['thickness'].get())

            factor = 1./atten

            if factor > 100:
                factor = '{:d}'.format(int(round(factor, 0)))
            elif factor > 10:
                factor = '{:.1f}'.format(round(factor, 1))
            else:
                factor = '{:.2f}'.format(round(factor, 2))

            self._nom_atten.SetLabel(str(factor))

        else:
            self._nom_atten.SetLabel('N/A')

    def _on_atten_pv_callback(self, **kwargs):
        wx.CallAfter(self._set_atten_indic)

    def _set_atten_indic(self):
        if self.pvs['ctrl'].get() == 0:
            self._ctrl_sizer.Hide(self._indic_btm)
        else:
            self._ctrl_sizer.Show(self._indic_btm)

    def remove_callbacks(self):
        for cb_pv_id in self.callback_ids:
            pv = self.pvs[cb_pv_id]
            pv.remove_callback(self.callback_ids[cb_pv_id])

class AttenuatorFrame(wx.Frame):
    """
    A lightweight amplifier frame designed to hold an arbitrary number of dios
    in an arbitrary grid pattern.
    """
    def __init__(self, name, mx_database, timer=True, use_new=True, *args, **kwargs):
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
        self._ctrls = []

        self.mx_database = mx_database

        self.mx_timer = wx.Timer()
        self.mx_timer.Bind(wx.EVT_TIMER, self._on_mxtimer)

        top_sizer = self._create_layout(use_new)

        self.SetSizer(top_sizer)
        self.Layout()
        self.Fit()
        self.Raise()

        if timer:
            self.mx_timer.Start(1000)

        self.Bind(wx.EVT_CLOSE, self._on_closewindow)

    def _create_layout(self, use_new):
        """
        Creates the layout.

        :param list dios: The amplifier names in the Mp database.

        :param tuple shape: A tuple containing the shape of the amp grid.
            It is given as: (rows, cols). Note that rows*cols should be equal
            to or greater than the number of dios, but the AmpFrame doesn't
            check this. If it isn't, it will just fail to propely display the last
            few dios.
        """
        atten_box = wx.StaticBox(self, label='Attenuator Controls')
        atten_box_sizer = wx.StaticBoxSizer(atten_box)

        if use_new:
            atten_panel = AttenuatorPanel2(self.name, self.mx_database, atten_box)
            atten_box_sizer.Add(atten_panel)

        else:
            atten_panel = AttenuatorPanel(self.name, self.mx_database, atten_box)
            atten_box_sizer.Add(atten_panel)

        self._ctrls.append(atten_panel)

        return atten_box_sizer

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

if __name__ == '__main__':
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
    frame = AttenuatorFrame("AttenFrame", mx_database, timer=False, use_new=True,
        parent=None, title='Test Attenuator Control')
    frame.Show()
    app.MainLoop()
