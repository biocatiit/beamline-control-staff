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

import wx
import epics, epics.wx

import utils
import custom_epics_widgets
# utils.set_mppath() #This must be done before importing any Mp Modules.
# import Mp as mp
# import MpCa as mpca
# import MpWx as mpwx
# import custom_widgets

class MainStatusPanel(wx.Panel):
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
        wx.Panel.__init__(self, parent, panel_id, name=panel_name)

        self._initialize()

        self._create_layout()

        self.SetMinSize((1600, 500))

    def _create_layout(self):
        """
        Creates the layout for the panel.
        """

        notebook = wx.Notebook(self)

        overview_page = OverviewPanel(self.pvs, notebook)
        bleps_page = BLEPSPanel(self.pvs, notebook)

        notebook.AddPage(overview_page, 'Overview')
        notebook.AddPage(bleps_page, 'BLEPS')

        top_sizer = wx.BoxSizer(wx.VERTICAL)
        top_sizer.Add(notebook, proportion=1, border=5, flag=wx.EXPAND|wx.ALL)


        self.SetSizer(top_sizer)

        # return top_sizer

    def _initialize(self):
        self.pvs = {
            'fe_shutter'        : epics.PV('FE:18:ID:FEshutter'),
            'd_shutter'         : epics.PV('PA:18ID:STA_D_SDS_OPEN_PL'),
            'fe_shutter_open'   : epics.PV('18ID:rshtr:A:OPEN'),
            'fe_shutter_close'  : epics.PV('18ID:rshtr:A:CLOSE'),
            'd_shutter_open'    : epics.PV('18ID:rshtr:D:OPEN'),
            'd_shutter_close'   : epics.PV('18ID:rshtr:D:CLOSE'),
            'current'           : epics.PV('XFD:srCurrent'),
            'aps_status'        : epics.PV('S:ActualMode'),
            'bleps_fault'       : epics.PV('18ID:BLEPS:FAULT_EXISTS'),
            'bleps_trip'        : epics.PV('18ID:BLEPS:TRIP_EXISTS'),
            'bleps_warning'     : epics.PV('18ID:BLEPS:WARNING_EXISTS'),
            'bleps_fault_reset' : epics.PV('18ID:BLEPS:FAULT_RESET'),
            'bleps_trip_reset'  : epics.PV('18ID:BLEPS:TRIP_RESET'),
            'exp_slow_shtr1'    : epics.PV('18ID:bi0:ch6'),
            'exp_slow_shtr2'    : epics.PV('18ID:bi0:ch7'),
            'exp_fast_shtr'     : epics.PV('18ID:bo0:ch9'),
            'col_vac'           : epics.PV('18ID:VAC:D:Cols'),
            'guard_vac'         : epics.PV('18ID:VAC:D:Guards'),
            'scatter_vac'       : epics.PV('18ID:VAC:D:ScatterChamber'),
            'sample_vac'        : epics.PV('18ID:VAC:D:Sample'),
            'i0'                : epics.PV('18ID:IP330_11'),
            'i1'                : epics.PV('18ID:IP330_12'),
            'gv1_status'        : epics.PV('18ID:BLEPS:GV1_OPENED_LS'),
            'gv1_both_sw'       : epics.PV('18ID:BLEPS:GV1_BOTH_SWITCH'),
            'gv1_open_sw'       : epics.PV('18ID:BLEPS:GV1_OPENED_SWITCH'),
            'gv1_close_sw'      : epics.PV('18ID:BLEPS:GV1_CLOSED_SWITCH'),
            'gv1_no_sw'         : epics.PV('18ID:BLEPS:GV1_NO_SWITCH'),
            'gv1_fail_open'     : epics.PV('18ID:BLEPS:GV1_FAIL_TO_OPEN'),
            'gv1_fail_close'    : epics.PV('18ID:BLEPS:GV1_FAIL_TO_CLOSE'),
            'gv1_fully_open'    : epics.PV('18ID:BLEPS:GV1_FULLY_OPEN'),
            'gv1_fully_close'   : epics.PV('18ID:BLEPS:GV1_FULLY_CLOSE'),
            'gv1_beam_exp'      : epics.PV('18ID:BLEPS:GV1_BEAM_EXPOSURE'),
            'gv1_open'          : epics.PV('18ID:BLEPS:GV1_EPICS_OPEN'),
            'gv1_close'         : epics.PV('18ID:BLEPS:GV1_EPICS_CLOSE'),
            'gv2_status'        : epics.PV('18ID:BLEPS:GV2_OPENED_LS'),
            'gv2_both_sw'       : epics.PV('18ID:BLEPS:GV2_BOTH_SWITCH'),
            'gv2_open_sw'       : epics.PV('18ID:BLEPS:GV2_OPENED_SWITCH'),
            'gv2_close_sw'      : epics.PV('18ID:BLEPS:GV2_CLOSED_SWITCH'),
            'gv2_no_sw'         : epics.PV('18ID:BLEPS:GV2_NO_SWITCH'),
            'gv2_fail_open'     : epics.PV('18ID:BLEPS:GV2_FAIL_TO_OPEN'),
            'gv2_fail_close'    : epics.PV('18ID:BLEPS:GV2_FAIL_TO_CLOSE'),
            'gv2_fully_open'    : epics.PV('18ID:BLEPS:GV2_FULLY_OPEN'),
            'gv2_fully_close'   : epics.PV('18ID:BLEPS:GV2_FULLY_CLOSE'),
            'gv2_beam_exp'      : epics.PV('18ID:BLEPS:GV2_BEAM_EXPOSURE'),
            'gv2_open'          : epics.PV('18ID:BLEPS:GV2_EPICS_OPEN'),
            'gv2_close'         : epics.PV('18ID:BLEPS:GV2_EPICS_CLOSE'),
            'gv3_status'        : epics.PV('18ID:BLEPS:GV3_OPENED_LS'),
            'gv3_both_sw'       : epics.PV('18ID:BLEPS:GV3_BOTH_SWITCH'),
            'gv3_open_sw'       : epics.PV('18ID:BLEPS:GV3_OPENED_SWITCH'),
            'gv3_close_sw'      : epics.PV('18ID:BLEPS:GV3_CLOSED_SWITCH'),
            'gv3_no_sw'         : epics.PV('18ID:BLEPS:GV3_NO_SWITCH'),
            'gv3_fail_open'     : epics.PV('18ID:BLEPS:GV3_FAIL_TO_OPEN'),
            'gv3_fail_close'    : epics.PV('18ID:BLEPS:GV3_FAIL_TO_CLOSE'),
            'gv3_fully_open'    : epics.PV('18ID:BLEPS:GV3_FULLY_OPEN'),
            'gv3_fully_close'   : epics.PV('18ID:BLEPS:GV3_FULLY_CLOSE'),
            'gv3_beam_exp'      : epics.PV('18ID:BLEPS:GV3_BEAM_EXPOSURE'),
            'gv3_open'          : epics.PV('18ID:BLEPS:GV3_EPICS_OPEN'),
            'gv3_close'         : epics.PV('18ID:BLEPS:GV3_EPICS_CLOSE'),
            'gv4_status'        : epics.PV('18ID:BLEPS:GV4_OPENED_LS'),
            'gv4_both_sw'       : epics.PV('18ID:BLEPS:GV4_BOTH_SWITCH'),
            'gv4_open_sw'       : epics.PV('18ID:BLEPS:GV4_OPENED_SWITCH'),
            'gv4_close_sw'      : epics.PV('18ID:BLEPS:GV4_CLOSED_SWITCH'),
            'gv4_no_sw'         : epics.PV('18ID:BLEPS:GV4_NO_SWITCH'),
            'gv4_fail_open'     : epics.PV('18ID:BLEPS:GV4_FAIL_TO_OPEN'),
            'gv4_fail_close'    : epics.PV('18ID:BLEPS:GV4_FAIL_TO_CLOSE'),
            'gv4_fully_open'    : epics.PV('18ID:BLEPS:GV4_FULLY_OPEN'),
            'gv4_fully_close'   : epics.PV('18ID:BLEPS:GV4_FULLY_CLOSE'),
            'gv4_beam_exp'      : epics.PV('18ID:BLEPS:GV4_BEAM_EXPOSURE'),
            'gv4_open'          : epics.PV('18ID:BLEPS:GV4_EPICS_OPEN'),
            'gv4_close'         : epics.PV('18ID:BLEPS:GV4_EPICS_CLOSE'),
            'gv5_status'        : epics.PV('18ID:BLEPS:GV5_OPENED_LS'),
            'gv5_both_sw'       : epics.PV('18ID:BLEPS:GV5_BOTH_SWITCH'),
            'gv5_open_sw'       : epics.PV('18ID:BLEPS:GV5_OPENED_SWITCH'),
            'gv5_close_sw'      : epics.PV('18ID:BLEPS:GV5_CLOSED_SWITCH'),
            'gv5_no_sw'         : epics.PV('18ID:BLEPS:GV5_NO_SWITCH'),
            'gv5_fail_open'     : epics.PV('18ID:BLEPS:GV5_FAIL_TO_OPEN'),
            'gv5_fail_close'    : epics.PV('18ID:BLEPS:GV5_FAIL_TO_CLOSE'),
            'gv5_fully_open'    : epics.PV('18ID:BLEPS:GV5_FULLY_OPEN'),
            'gv5_fully_close'   : epics.PV('18ID:BLEPS:GV5_FULLY_CLOSE'),
            'gv5_beam_exp'      : epics.PV('18ID:BLEPS:GV5_BEAM_EXPOSURE'),
            'gv5_open'          : epics.PV('18ID:BLEPS:GV5_EPICS_OPEN'),
            'gv5_close'         : epics.PV('18ID:BLEPS:GV5_EPICS_CLOSE'),
            'gv6_status'        : epics.PV('18ID:BLEPS:GV6_OPENED_LS'),
            'gv6_both_sw'       : epics.PV('18ID:BLEPS:GV6_BOTH_SWITCH'),
            'gv6_open_sw'       : epics.PV('18ID:BLEPS:GV6_OPENED_SWITCH'),
            'gv6_close_sw'      : epics.PV('18ID:BLEPS:GV6_CLOSED_SWITCH'),
            'gv6_no_sw'         : epics.PV('18ID:BLEPS:GV6_NO_SWITCH'),
            'gv6_fail_open'     : epics.PV('18ID:BLEPS:GV6_FAIL_TO_OPEN'),
            'gv6_fail_close'    : epics.PV('18ID:BLEPS:GV6_FAIL_TO_CLOSE'),
            'gv6_fully_open'    : epics.PV('18ID:BLEPS:GV6_FULLY_OPEN'),
            'gv6_fully_close'   : epics.PV('18ID:BLEPS:GV6_FULLY_CLOSE'),
            'gv6_beam_exp'      : epics.PV('18ID:BLEPS:GV6_BEAM_EXPOSURE'),
            'gv6_open'          : epics.PV('18ID:BLEPS:GV6_EPICS_OPEN'),
            'gv6_close'         : epics.PV('18ID:BLEPS:GV6_EPICS_CLOSE'),
            'gv7_status'        : epics.PV('18ID:BLEPS:GV7_OPENED_LS'),
            'gv7_both_sw'       : epics.PV('18ID:BLEPS:GV7_BOTH_SWITCH'),
            'gv7_open_sw'       : epics.PV('18ID:BLEPS:GV7_OPENED_SWITCH'),
            'gv7_close_sw'      : epics.PV('18ID:BLEPS:GV7_CLOSED_SWITCH'),
            'gv7_no_sw'         : epics.PV('18ID:BLEPS:GV7_NO_SWITCH'),
            'gv7_fail_open'     : epics.PV('18ID:BLEPS:GV7_FAIL_TO_OPEN'),
            'gv7_fail_close'    : epics.PV('18ID:BLEPS:GV7_FAIL_TO_CLOSE'),
            'gv7_fully_open'    : epics.PV('18ID:BLEPS:GV7_FULLY_OPEN'),
            'gv7_fully_close'   : epics.PV('18ID:BLEPS:GV7_FULLY_CLOSE'),
            'gv7_beam_exp'      : epics.PV('18ID:BLEPS:GV7_BEAM_EXPOSURE'),
            'gv7_open'          : epics.PV('18ID:BLEPS:GV7_EPICS_OPEN'),
            'gv7_close'         : epics.PV('18ID:BLEPS:GV7_EPICS_CLOSE'),
            'comm_fault'        : epics.PV('18ID:BLEPS:COMMUNICATIONS_FAULT'),
            'plc_battery_wrn'   : epics.PV('18ID:BLEPS:PLC_BATTERY_DEAD_WRN'),
            # 'ps1_wrn'           : epics.PV('18ID:BLEPS:PS_1_WARNING'),
            # 'ps2_wrn'           : epics.PV('18ID:BLEPS:PS_2_WARNING'),
            # 'or_wrn'            : epics.PV('18ID:BLEPS:OR_WARNING'),
            'biv_fail_close'    : epics.PV('18ID:BLEPS:BIV_FAIL_TO_CLOSE'),
            'fes_fail_close'    : epics.PV('18ID:BLEPS:FES_FAIL_TO_CLOSE'),
            'sds_fail_close'    : epics.PV('18ID:BLEPS:SDS_FAIL_TO_CLOSE'),
            'T1_temp'           : epics.PV('18ID:BLEPS:TEMP1_CURRENT'),
            'T1_status'         : epics.PV('18ID:BLEPS:TEMP1_STATUS'),
            'T1_setpoint'       : epics.PV('18ID:BLEPS:TEMP1_SET_POINT'),
            'T1_high'           : epics.PV('18ID:BLEPS:TEMP1_TRIP'),
            'T1_under_range'    : epics.PV('18ID:BLEPS:TEMP1_UNDER_RANGE'),
            'T2_temp'           : epics.PV('18ID:BLEPS:TEMP2_CURRENT'),
            'T2_status'         : epics.PV('18ID:BLEPS:TEMP2_STATUS'),
            'T3_temp'           : epics.PV('18ID:BLEPS:TEMP3_CURRENT'),
            'T3_status'         : epics.PV('18ID:BLEPS:TEMP3_STATUS'),
            'T3_setpoint'       : epics.PV('18ID:BLEPS:TEMP3_SET_POINT'),
            'T3_high'           : epics.PV('18ID:BLEPS:TEMP3_TRIP'),
            'T3_under_range'    : epics.PV('18ID:BLEPS:TEMP3_UNDER_RANGE'),
            'T4_temp'           : epics.PV('18ID:BLEPS:TEMP4_CURRENT'),
            'T4_status'         : epics.PV('18ID:BLEPS:TEMP4_STATUS'),
            'T4_setpoint'       : epics.PV('18ID:BLEPS:TEMP4_SET_POINT'),
            'T4_high'           : epics.PV('18ID:BLEPS:TEMP4_TRIP'),
            'T4_under_range'    : epics.PV('18ID:BLEPS:TEMP4_UNDER_RANGE'),
            'T5_temp'           : epics.PV('18ID:BLEPS:TEMP5_CURRENT'),
            'T5_status'         : epics.PV('18ID:BLEPS:TEMP5_STATUS'),
            'T6_temp'           : epics.PV('18ID:BLEPS:TEMP6_CURRENT'),
            'T6_status'         : epics.PV('18ID:BLEPS:TEMP6_STATUS'),
            'T8_temp'           : epics.PV('18ID:BLEPS:TEMP8_CURRENT'),
            'T8_status'         : epics.PV('18ID:BLEPS:TEMP8_STATUS'),
            'T9_temp'           : epics.PV('18ID:BLEPS:TEMP9_CURRENT'),
            'T9_status'         : epics.PV('18ID:BLEPS:TEMP9_STATUS'),
            'T9_setpoint'       : epics.PV('18ID:BLEPS:TEMP9_SET_POINT'),
            'T9_high'           : epics.PV('18ID:BLEPS:TEMP9_TRIP'),
            'T9_under_range'    : epics.PV('18ID:BLEPS:TEMP9_UNDER_RANGE'),
            'T10_temp'          : epics.PV('18ID:BLEPS:TEMP10_CURRENT'),
            'T10_status'        : epics.PV('18ID:BLEPS:TEMP10_STATUS'),
            'T11_temp'          : epics.PV('18ID:BLEPS:TEMP11_CURRENT'),
            'T11_status'        : epics.PV('18ID:BLEPS:TEMP11_STATUS'),
            'T11_setpoint'      : epics.PV('18ID:BLEPS:TEMP11_SET_POINT'),
            'T11_high'          : epics.PV('18ID:BLEPS:TEMP11_TRIP'),
            'T11_under_range'   : epics.PV('18ID:BLEPS:TEMP11_UNDER_RANGE'),
            'T12_temp'          : epics.PV('18ID:BLEPS:TEMP12_CURRENT'),
            'T12_status'        : epics.PV('18ID:BLEPS:TEMP12_STATUS'),
            'T12_setpoint'      : epics.PV('18ID:BLEPS:TEMP12_SET_POINT'),
            'T12_high'          : epics.PV('18ID:BLEPS:TEMP12_TRIP'),
            'T12_under_range'   : epics.PV('18ID:BLEPS:TEMP12_UNDER_RANGE'),
            'T13_temp'          : epics.PV('18ID:BLEPS:TEMP13_CURRENT'),
            'T13_status'        : epics.PV('18ID:BLEPS:TEMP13_STATUS'),
            'T14_temp'          : epics.PV('18ID:BLEPS:TEMP14_CURRENT'),
            'T14_status'        : epics.PV('18ID:BLEPS:TEMP14_STATUS'),
            'T16_temp'          : epics.PV('18ID:BLEPS:TEMP16_CURRENT'),
            'T16_status'        : epics.PV('18ID:BLEPS:TEMP16_STATUS'),
            'vac1_trip'         : epics.PV('18ID:BLEPS:VS1_TRIP'),
            'vac2_trip'         : epics.PV('18ID:BLEPS:VS2_TRIP'),
            'vac3_trip'         : epics.PV('18ID:BLEPS:VS3_TRIP'),
            'vac4_trip'         : epics.PV('18ID:BLEPS:VS4_TRIP'),
            'vac5_trip'         : epics.PV('18ID:BLEPS:VS5_TRIP'),
            'vac6_trip'         : epics.PV('18ID:BLEPS:VS6_TRIP'),
            'vac7_trip'         : epics.PV('18ID:BLEPS:VS7_TRIP'),
            'vac8_trip'         : epics.PV('18ID:BLEPS:VS8_TRIP'),
            'vac1_ip_warn'      : epics.PV('18ID:BLEPS:IP1_WARNING'),
            'vac2_ip_warn'      : epics.PV('18ID:BLEPS:IP2_WARNING'),
            'vac3_ip_warn'      : epics.PV('18ID:BLEPS:IP3_WARNING'),
            'vac4_ip_warn'      : epics.PV('18ID:BLEPS:IP4_WARNING'),
            'vac5_ip_warn'      : epics.PV('18ID:BLEPS:IP5_WARNING'),
            'vac6_ip_warn'      : epics.PV('18ID:BLEPS:IP6_WARNING'),
            'vac7_ip_warn'      : epics.PV('18ID:BLEPS:IP7_WARNING'),
            'vac8_ip_warn'      : epics.PV('18ID:BLEPS:IP8_WARNING'),
            'vac1_ip_status'    : epics.PV('18ID:BLEPS:IP1_STATUS'),
            'vac2_ip_status'    : epics.PV('18ID:BLEPS:IP2_STATUS'),
            'vac3_ip_status'    : epics.PV('18ID:BLEPS:IP3_STATUS'),
            'vac4_ip_status'    : epics.PV('18ID:BLEPS:IP4_STATUS'),
            'vac5_ip_status'    : epics.PV('18ID:BLEPS:IP5_STATUS'),
            'vac6_ip_status'    : epics.PV('18ID:BLEPS:IP6_STATUS'),
            'vac7_ip_status'    : epics.PV('18ID:BLEPS:IP7_STATUS'),
            'vac8_ip_status'    : epics.PV('18ID:BLEPS:IP8_STATUS'),
            'vac1_ig_warn'      : epics.PV('18ID:BLEPS:IG1_WARNING'),
            'vac2_ig_warn'      : epics.PV('18ID:BLEPS:IG2_WARNING'),
            'vac3_ig_warn'      : epics.PV('18ID:BLEPS:IG3_WARNING'),
            'vac4_ig_warn'      : epics.PV('18ID:BLEPS:IG4_WARNING'),
            'vac5_ig_warn'      : epics.PV('18ID:BLEPS:IG5_WARNING'),
            'vac6_ig_warn'      : epics.PV('18ID:BLEPS:IG6_WARNING'),
            'vac7_ig_warn'      : epics.PV('18ID:BLEPS:IG7_WARNING'),
            'vac8_ig_warn'      : epics.PV('18ID:BLEPS:IG8_WARNING'),
            'vac9_ig_warn'      : epics.PV('18ID:BLEPS:IG9_WARNING'),
            'vac10_ig_warn'     : epics.PV('18ID:BLEPS:IG10_WARNING'),
            'vac1_ig_status'    : epics.PV('18ID:BLEPS:IG1_STATUS'),
            'vac2_ig_status'    : epics.PV('18ID:BLEPS:IG2_STATUS'),
            'vac3_ig_status'    : epics.PV('18ID:BLEPS:IG3_STATUS'),
            'vac4_ig_status'    : epics.PV('18ID:BLEPS:IG4_STATUS'),
            'vac5_ig_status'    : epics.PV('18ID:BLEPS:IG5_STATUS'),
            'vac6_ig_status'    : epics.PV('18ID:BLEPS:IG6_STATUS'),
            'vac7_ig_status'    : epics.PV('18ID:BLEPS:IG7_STATUS'),
            'vac8_ig_status'    : epics.PV('18ID:BLEPS:IG8_STATUS'),
            'vac9_ig_status'    : epics.PV('18ID:BLEPS:IG9_STATUS'),
            'vac10_ig_status'   : epics.PV('18ID:BLEPS:IG10_STATUS'),
            'flow1_rate'        : epics.PV('18ID:BLEPS:FLOW1_CURRENT'),
            'flow1_status'      : epics.PV('18ID:BLEPS:FLOW1_STATUS'),
            'flow1_setpoint'    : epics.PV('18ID:BLEPS:FLOW1_SET_POINT'),
            'flow1_low'         : epics.PV('18ID:BLEPS:FLOW1_TRIP'),
            'flow1_over_range'  : epics.PV('18ID:BLEPS:FLOW1_OVER_RANGE'),
            'flow2_rate'        : epics.PV('18ID:BLEPS:FLOW2_CURRENT'),
            'flow2_status'      : epics.PV('18ID:BLEPS:FLOW2_STATUS'),
            'flow2_setpoint'    : epics.PV('18ID:BLEPS:FLOW2_SET_POINT'),
            'flow2_low'         : epics.PV('18ID:BLEPS:FLOW2_TRIP'),
            'flow2_over_range'  : epics.PV('18ID:BLEPS:FLOW2_OVER_RANGE'),
        }

        [self.pvs[key].get() for key in self.pvs.keys()]

class OverviewPanel(wx.Panel):
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
    def __init__(self, pvs, parent, panel_id=wx.ID_ANY, panel_name=''):
        wx.Panel.__init__(self, parent, panel_id, name=panel_name)

        self.pvs = pvs

        self._initialize()

        self._create_layout()


    def _create_layout(self):
        """
        Creates the layout for the panel.

        """

        aps_box = wx.StaticBox(self, label='APS Status')
        fsize = self.GetFont().Larger().GetPointSize()
        font = wx.Font(fsize, wx.DEFAULT, wx.NORMAL, wx.BOLD)
        aps_box.SetOwnFont(font)

        aps_status = epics.wx.PVText(aps_box, self.pvs['aps_status'],
            fg='forest green')
        beam_current = epics.wx.PVText(aps_box, self.pvs['current'],
            auto_units=True, fg='forest green')

        aps_sub_sizer = wx.BoxSizer(wx.HORIZONTAL)
        aps_sub_sizer.Add(wx.StaticText(aps_box, label='Beam current:'), border=5,
            flag=wx.RIGHT|wx.ALIGN_CENTER_VERTICAL)
        aps_sub_sizer.Add(beam_current, border=5,
            flag=wx.RIGHT|wx.ALIGN_CENTER_VERTICAL)
        aps_sub_sizer.AddSpacer(10)
        aps_sub_sizer.Add(wx.StaticText(aps_box, label='APS beam status:'),
            border=5, flag=wx.RIGHT|wx.ALIGN_CENTER_VERTICAL)
        aps_sub_sizer.Add(aps_status, border=5,
            flag=wx.ALIGN_CENTER_VERTICAL)
        aps_sub_sizer.AddStretchSpacer(1)

        aps_sizer = wx.StaticBoxSizer(aps_box, wx.VERTICAL)
        aps_sizer.Add(aps_sub_sizer, flag=wx.ALL, border=5)
        aps_sizer.AddStretchSpacer(1)
        


        bleps_box = wx.StaticBox(self, label='BLEPS Status')
        fsize = self.GetFont().Larger().GetPointSize()
        font = wx.Font(fsize, wx.DEFAULT, wx.NORMAL, wx.BOLD)
        bleps_box.SetOwnFont(font)

        bleps_fault = epics.wx.PVText(bleps_box, self.pvs['bleps_fault'],
            fg='forest green')
        bleps_trip = epics.wx.PVText(bleps_box, self.pvs['bleps_trip'],
            fg='forest green')
        bleps_warning = epics.wx.PVText(bleps_box, self.pvs['bleps_warning'],
            fg='forest green')
        bleps_fault_reset = epics.wx.PVButton(bleps_box,
            self.pvs['bleps_fault_reset'], label='Reset Fault')
        bleps_trip_reset = epics.wx.PVButton(bleps_box,
            self.pvs['bleps_trip_reset'], label='Reset Trip')

        bleps_grid_sizer = wx.GridBagSizer(vgap=5, hgap=5)
        bleps_grid_sizer.Add(wx.StaticText(bleps_box, label='BLEPS fault:'),
            pos=(0,0), flag=wx.ALIGN_CENTER_VERTICAL)
        bleps_grid_sizer.Add(bleps_fault, pos=(0,1),
            flag=wx.ALIGN_CENTER_VERTICAL)
        bleps_grid_sizer.Add((5, 0), (0,2))
        bleps_grid_sizer.Add(wx.StaticText(bleps_box, label='BLEPS trip:'),
            pos=(0,3), flag=wx.ALIGN_CENTER_VERTICAL)
        bleps_grid_sizer.Add(bleps_trip, pos=(0,4),
            flag=wx.ALIGN_CENTER_VERTICAL)
        bleps_grid_sizer.Add((5, 0), (0,5))
        bleps_grid_sizer.Add(wx.StaticText(bleps_box, label='BLEPS warning:'),
            pos=(0,6), flag=wx.ALIGN_CENTER_VERTICAL)
        bleps_grid_sizer.Add(bleps_warning, pos=(0,7),
            flag=wx.ALIGN_CENTER_VERTICAL)
        bleps_grid_sizer.Add(bleps_fault_reset, pos=(1,0), span=(0, 2),
            flag=wx.ALIGN_CENTER_VERTICAL|wx.ALIGN_CENTER_HORIZONTAL)
        bleps_grid_sizer.Add(bleps_trip_reset, pos=(1,3), span=(0, 2),
            flag=wx.ALIGN_CENTER_VERTICAL|wx.ALIGN_CENTER_HORIZONTAL)

        bleps_sizer = wx.StaticBoxSizer(bleps_box, wx.HORIZONTAL)
        bleps_sizer.Add(bleps_grid_sizer, proportion=0, flag=wx.ALL|wx.EXPAND,
            border=5)
        bleps_sizer.AddStretchSpacer(1)

        station_box = wx.StaticBox(self, label='Station Status')
        fsize = self.GetFont().Larger().GetPointSize()
        font = wx.Font(fsize, wx.DEFAULT, wx.NORMAL, wx.BOLD)
        station_box.SetOwnFont(font)

        fe_shutter = custom_epics_widgets.PVTextLabeled(station_box,
            self.pvs['fe_shutter'], fg='forest green')
        d_shutter = custom_epics_widgets.PVTextLabeled(station_box,
            self.pvs['d_shutter'], fg='forest green')
        fe_shutter_open = custom_epics_widgets.PVButton2(station_box,
            self.pvs['fe_shutter_open'], label='Open', size=(50, -1))
        fe_shutter_close = custom_epics_widgets.PVButton2(station_box,
            self.pvs['fe_shutter_close'], label='Close', size=(50, -1))
        d_shutter_open = custom_epics_widgets.PVButton2(station_box,
            self.pvs['d_shutter_open'], label='Open', size=(50, -1))
        d_shutter_close = custom_epics_widgets.PVButton2(station_box,
            self.pvs['d_shutter_close'], label='Close', size=(50, -1))

        fe_shutter.SetTranslations({'0': 'Closed', '1': 'Open'})
        d_shutter.SetTranslations({'OFF': 'Closed', 'ON': 'Open'})
        fe_shutter.SetForegroundColourTranslations({'Open': 'forest green',
            'Closed': 'red'})

        fe_shtr_ctrl = wx.BoxSizer(wx.HORIZONTAL)
        fe_shtr_ctrl.Add(fe_shutter_open, border=5, flag=wx.RIGHT)
        fe_shtr_ctrl.Add(fe_shutter_close, border=5, flag=wx.RIGHT)

        d_shtr_ctrl = wx.BoxSizer(wx.HORIZONTAL)
        d_shtr_ctrl.Add(d_shutter_open, border=5, flag=wx.RIGHT)
        d_shtr_ctrl.Add(d_shutter_close, border=5, flag=wx.RIGHT)

        station_grid_sizer = wx.GridBagSizer(vgap=5, hgap=5)
        station_grid_sizer.Add(wx.StaticText(station_box, label='D shutter:'),
            pos=(0,0), flag=wx.ALIGN_CENTER_VERTICAL)
        station_grid_sizer.Add(d_shutter, pos=(0,1),
            flag=wx.ALIGN_CENTER_VERTICAL)
        station_grid_sizer.Add(5, -1, pos=(0,2))
        station_grid_sizer.Add(wx.StaticText(station_box, label='A shutter:'),
            pos=(0,3), flag=wx.ALIGN_CENTER_VERTICAL)
        station_grid_sizer.Add(fe_shutter, pos=(0,4),
            flag=wx.ALIGN_CENTER_VERTICAL)
        station_grid_sizer.Add(fe_shtr_ctrl, pos=(1, 3), span=(0, 2),
            flag=wx.ALIGN_CENTER_VERTICAL|wx.ALIGN_CENTER_HORIZONTAL)
        station_grid_sizer.Add(d_shtr_ctrl, pos=(1, 0), span=(0, 2),
            flag=wx.ALIGN_CENTER_VERTICAL|wx.ALIGN_CENTER_HORIZONTAL)

        station_sizer = wx.StaticBoxSizer(station_box, wx.HORIZONTAL)
        station_sizer.Add(station_grid_sizer, proportion=0, flag=wx.EXPAND|wx.ALL,
            border=5)
        station_sizer.AddStretchSpacer(1)


        exp_box = wx.StaticBox(self, label='Experiment Status')
        fsize = self.GetFont().Larger().GetPointSize()
        font = wx.Font(fsize, wx.DEFAULT, wx.NORMAL, wx.BOLD)
        exp_box.SetOwnFont(font)

        exp_slow_shtr1 = custom_epics_widgets.PVTextLabeled(exp_box,
            self.pvs['exp_slow_shtr1'], fg='forest green')
        exp_slow_shtr2 = custom_epics_widgets.PVTextLabeled(exp_box,
            self.pvs['exp_slow_shtr2'], fg='forest green')
        exp_fast_shtr = custom_epics_widgets.PVTextLabeled(exp_box,
            self.pvs['exp_fast_shtr'], fg='forest green')

        exp_slow_shtr1.SetTranslations({'On': 'Open', 'Off': 'Closed'})
        exp_slow_shtr2.SetTranslations({'Off': 'Open', 'On': 'Closed'})
        exp_fast_shtr.SetTranslations({'On': 'Open', 'Off': 'Closed'})

        exp_slow_shtr1.SetForegroundColourTranslations({'Open': 'forest green', 'Closed': 'red'})
        exp_slow_shtr2.SetForegroundColourTranslations({'Open': 'forest green', 'Closed': 'red'})
        exp_fast_shtr.SetForegroundColourTranslations({'Open': 'forest green', 'Closed': 'red'})

        exp_col_vac = custom_epics_widgets.PVTextLabeled(exp_box,
            self.pvs['col_vac'], scale=1000, do_round=True)
        exp_guard_vac = custom_epics_widgets.PVTextLabeled(exp_box,
            self.pvs['guard_vac'], scale=1000, do_round=True)
        exp_scatter_vac = custom_epics_widgets.PVTextLabeled(exp_box,
            self.pvs['scatter_vac'], scale=1000, do_round=True)
        exp_sample_vac = custom_epics_widgets.PVTextLabeled(exp_box,
            self.pvs['sample_vac'], scale=1000, do_round=True)

        exp_i0 = custom_epics_widgets.PVTextLabeled(exp_box,
            self.pvs['i0'], do_round=True, sig_fig=2)
        exp_i1 = custom_epics_widgets.PVTextLabeled(exp_box,
            self.pvs['i1'], do_round=True, sig_fig=2)

        exp_grid_sizer = wx.FlexGridSizer(cols=8, hgap=5, vgap=5)
        exp_grid_sizer.Add(wx.StaticText(exp_box, label='Slow shutter 1:'),
            flag=wx.ALIGN_CENTER_VERTICAL)
        exp_grid_sizer.Add(exp_slow_shtr1, flag=wx.ALIGN_CENTER_VERTICAL)
        exp_grid_sizer.AddSpacer(5)
        exp_grid_sizer.Add(wx.StaticText(exp_box, label='Slow shutter 2:'),
            flag=wx.ALIGN_CENTER_VERTICAL)
        exp_grid_sizer.Add(exp_slow_shtr2, flag=wx.ALIGN_CENTER_VERTICAL)
        exp_grid_sizer.AddSpacer(5)
        exp_grid_sizer.Add(wx.StaticText(exp_box, label='Fast shutter:'),
            flag=wx.ALIGN_CENTER_VERTICAL)
        exp_grid_sizer.Add(exp_fast_shtr, flag=wx.ALIGN_CENTER_VERTICAL)
        exp_grid_sizer.Add(wx.StaticText(exp_box, label='Col. Vac. [mTorr]:'),
            flag=wx.ALIGN_CENTER_VERTICAL)
        exp_grid_sizer.Add(exp_col_vac, flag=wx.ALIGN_CENTER_VERTICAL)
        exp_grid_sizer.AddSpacer(5)
        exp_grid_sizer.Add(wx.StaticText(exp_box, label='Guard Vac. [mTorr]:'),
            flag=wx.ALIGN_CENTER_VERTICAL)
        exp_grid_sizer.Add(exp_guard_vac, flag=wx.ALIGN_CENTER_VERTICAL)
        exp_grid_sizer.AddSpacer(5)
        exp_grid_sizer.Add(wx.StaticText(exp_box, label='Sample Vac.[mTorr]:'),
            flag=wx.ALIGN_CENTER_VERTICAL)
        exp_grid_sizer.Add(exp_sample_vac, flag=wx.ALIGN_CENTER_VERTICAL)
        exp_grid_sizer.Add(wx.StaticText(exp_box, label='S.C. Vac.[mTorr]:'),
            flag=wx.ALIGN_CENTER_VERTICAL)
        exp_grid_sizer.Add(exp_scatter_vac, flag=wx.ALIGN_CENTER_VERTICAL)
        exp_grid_sizer.AddSpacer(5)
        exp_grid_sizer.Add(wx.StaticText(exp_box, label='I0 [V]:'),
            flag=wx.ALIGN_CENTER_VERTICAL)
        exp_grid_sizer.Add(exp_i0, flag=wx.ALIGN_CENTER_VERTICAL)
        exp_grid_sizer.AddSpacer(5)
        exp_grid_sizer.Add(wx.StaticText(exp_box, label='I1 [V]:'),
            flag=wx.ALIGN_CENTER_VERTICAL)
        exp_grid_sizer.Add(exp_i1, flag=wx.ALIGN_CENTER_VERTICAL)

        exp_sizer = wx.StaticBoxSizer(exp_box, wx.VERTICAL)
        exp_sizer.Add(exp_grid_sizer, proportion=0, flag=wx.EXPAND|wx.ALL,
            border=5)
        exp_sizer.AddStretchSpacer(1)


        grid_sizer = wx.FlexGridSizer(cols=2, vgap=5, hgap=5)
        grid_sizer.Add(aps_sizer, flag=wx.EXPAND)
        grid_sizer.Add(bleps_sizer, flag=wx.EXPAND)
        grid_sizer.Add(station_sizer, flag=wx.EXPAND)
        grid_sizer.Add(exp_sizer, flag=wx.EXPAND)
        grid_sizer.AddGrowableCol(0)
        grid_sizer.AddGrowableCol(1)

        top_sizer = wx.BoxSizer(wx.VERTICAL)
        top_sizer.Add(grid_sizer, border=5, flag=wx.ALL|wx.EXPAND)

        self.SetSizer(top_sizer)

        # return top_sizer

    def _initialize(self):
        pass

class BLEPSPanel(wx.ScrolledWindow):
    """
    """
    def __init__(self, pvs, parent, panel_id=wx.ID_ANY, panel_name=''):
        wx.ScrolledWindow.__init__(self, parent,
            style=wx.VSCROLL|wx.HSCROLL)
        self.SetScrollRate(20,20)

        self.pvs = pvs

        self._initialize()

        self._create_layout()


    def _create_layout(self):
        """
        Creates the layout for the panel.

        """

        bleps_box = wx.StaticBox(self, label='BLEPS Status')
        fsize = self.GetFont().Larger().GetPointSize()
        font = wx.Font(fsize, wx.DEFAULT, wx.NORMAL, wx.BOLD)
        bleps_box.SetOwnFont(font)

        bleps_fault = epics.wx.PVText(bleps_box, self.pvs['bleps_fault'],
            fg='forest green')
        bleps_trip = epics.wx.PVText(bleps_box, self.pvs['bleps_trip'],
            fg='forest green')
        bleps_warning = epics.wx.PVText(bleps_box, self.pvs['bleps_warning'],
            fg='forest green')
        bleps_fault_reset = epics.wx.PVButton(bleps_box,
            self.pvs['bleps_fault_reset'], label='Reset Fault')
        bleps_trip_reset = epics.wx.PVButton(bleps_box,
            self.pvs['bleps_trip_reset'], label='Reset Trip')

        bleps_grid_sizer = wx.GridBagSizer(vgap=5, hgap=5)
        bleps_grid_sizer.Add(wx.StaticText(bleps_box, label='BLEPS fault:'),
            pos=(0,0), flag=wx.ALIGN_CENTER_VERTICAL)
        bleps_grid_sizer.Add(bleps_fault, pos=(0,1),
            flag=wx.ALIGN_CENTER_VERTICAL)
        bleps_grid_sizer.Add((5, 0), (0,2))
        bleps_grid_sizer.Add(wx.StaticText(bleps_box, label='BLEPS trip:'),
            pos=(0,3), flag=wx.ALIGN_CENTER_VERTICAL)
        bleps_grid_sizer.Add(bleps_trip, pos=(0,4),
            flag=wx.ALIGN_CENTER_VERTICAL)
        bleps_grid_sizer.Add((5, 0), (0,5))
        bleps_grid_sizer.Add(wx.StaticText(bleps_box, label='BLEPS warning:'),
            pos=(0,6), flag=wx.ALIGN_CENTER_VERTICAL)
        bleps_grid_sizer.Add(bleps_warning, pos=(0,7),
            flag=wx.ALIGN_CENTER_VERTICAL)
        bleps_grid_sizer.Add(bleps_fault_reset, pos=(1,0), span=(0, 2),
            flag=wx.ALIGN_CENTER_VERTICAL|wx.ALIGN_CENTER_HORIZONTAL)
        bleps_grid_sizer.Add(bleps_trip_reset, pos=(1,3), span=(0, 2),
            flag=wx.ALIGN_CENTER_VERTICAL|wx.ALIGN_CENTER_HORIZONTAL)

        bleps_sizer = wx.StaticBoxSizer(bleps_box, wx.HORIZONTAL)
        bleps_sizer.Add(bleps_grid_sizer, proportion=0, flag=wx.ALL|wx.EXPAND,
            border=5)
        bleps_sizer.AddStretchSpacer(1)

        misc_box = wx.StaticBox(self, label='Misc. Faults/Warnings')
        fsize = self.GetFont().Larger().GetPointSize()
        font = wx.Font(fsize, wx.DEFAULT, wx.NORMAL, wx.BOLD)
        misc_box.SetOwnFont(font)
        comm_fault = epics.wx.PVText(misc_box, self.pvs['comm_fault'],
            fg='forest green')
        plc_battery_wrn = epics.wx.PVText(misc_box, self.pvs['plc_battery_wrn'],
            fg='forest green')
        # ps1_wrn = epics.wx.PVText(misc_box, self.pvs['ps1_wrn'],
        #     fg='forest green')
        # ps2_wrn = epics.wx.PVText(misc_box, self.pvs['ps2_wrn'],
        #     fg='forest green')
        # or_wrn = epics.wx.PVText(misc_box, self.pvs['or_wrn'],
        #     fg='forest green')
        biv_fail_close = epics.wx.PVText(misc_box, self.pvs['biv_fail_close'],
            fg='forest green')
        fes_fail_close = epics.wx.PVText(misc_box, self.pvs['fes_fail_close'],
            fg='forest green')
        sds_fail_close = epics.wx.PVText(misc_box, self.pvs['sds_fail_close'],
            fg='forest green')

        misc_grid = wx.FlexGridSizer(cols=11, vgap=10, hgap=5)
        misc_grid.Add(wx.StaticText(misc_box, label='Comm. fault:'),
            flag=wx.ALIGN_CENTER_VERTICAL)
        misc_grid.Add(comm_fault)
        misc_grid.AddSpacer(5)
        misc_grid.Add(wx.StaticText(misc_box, label='Battery wrn.:'),
            flag=wx.ALIGN_CENTER_VERTICAL)
        misc_grid.Add(plc_battery_wrn)
        misc_grid.AddSpacer(5)
        # misc_grid.Add(wx.StaticText(misc_box, label='P.S. 1 wrn.:'),
        #     flag=wx.ALIGN_CENTER_VERTICAL)
        # misc_grid.Add(ps1_wrn)
        # misc_grid.AddSpacer(5)
        # misc_grid.Add(wx.StaticText(misc_box, label='P.S. 2 wrn.:'),
        #     flag=wx.ALIGN_CENTER_VERTICAL)
        # misc_grid.Add(ps2_wrn)
        # misc_grid.AddSpacer(5)
        # misc_grid.Add(wx.StaticText(misc_box, label='OR Module wrn.:'),
        #     flag=wx.ALIGN_CENTER_VERTICAL)
        # misc_grid.Add(or_wrn)
        # misc_grid.AddSpacer(5)
        misc_grid.Add(wx.StaticText(misc_box, label='BIV fail to close:'),
            flag=wx.ALIGN_CENTER_VERTICAL)
        misc_grid.Add(biv_fail_close)
        misc_grid.AddSpacer(5)
        misc_grid.Add(wx.StaticText(misc_box, label='FES fail to close:'),
            flag=wx.ALIGN_CENTER_VERTICAL)
        misc_grid.Add(fes_fail_close)
        misc_grid.Add(wx.StaticText(misc_box, label='SDS fail to close:'),
            flag=wx.ALIGN_CENTER_VERTICAL)
        misc_grid.Add(sds_fail_close)

        misc_sizer = wx.StaticBoxSizer(misc_box, wx.VERTICAL)
        misc_sizer.Add(misc_grid, flag=wx.ALL|wx.EXPAND, border=5)

        gate_valve_box = wx.StaticBox(self, label='Gate Valves')
        fsize = self.GetFont().Larger().GetPointSize()
        font = wx.Font(fsize, wx.DEFAULT, wx.NORMAL, wx.BOLD)
        gate_valve_box.SetOwnFont(font)
        gate_valve_sizer = wx.StaticBoxSizer(gate_valve_box, wx.VERTICAL)

        gate_valve_layout = wx.FlexGridSizer(cols=3, vgap=5, hgap=5)
        for i in range(1, 8):
            gate_valve_layout.Add(self.make_gv_sizer(gate_valve_box, i))

        gate_valve_sizer.Add(gate_valve_layout, flag=wx.EXPAND|wx.ALL, border=5)

        temp_box = wx.StaticBox(self, label='Temperatures')
        fsize = self.GetFont().Larger().GetPointSize()
        font = wx.Font(fsize, wx.DEFAULT, wx.NORMAL, wx.BOLD)
        temp_box.SetOwnFont(font)
        temp_sizer = wx.StaticBoxSizer(temp_box, wx.VERTICAL)

        temp_layout = wx.FlexGridSizer(cols=2, vgap=5, hgap=5)
        temp_layout.Add(self.make_temp_sizer(temp_box, 1, 'Mono 1 Cryo Supply'),
            flag=wx.EXPAND)
        temp_layout.Add(self.make_temp_sizer(temp_box, 3, 'Mono 1 Compton IB'),
            flag=wx.EXPAND)
        temp_layout.Add(self.make_temp_sizer(temp_box, 4, 'Mono 1 Compton OB'),
            flag=wx.EXPAND)
        temp_layout.Add(self.make_temp_sizer(temp_box, 9, 'Mono 2 Cryo Supply'),
            flag=wx.EXPAND)
        temp_layout.Add(self.make_temp_sizer(temp_box, 11, 'Mono 2 Compton IB'),
            flag=wx.EXPAND)
        temp_layout.Add(self.make_temp_sizer(temp_box, 12, 'Mono 2 Compton OB'),
            flag=wx.EXPAND)
        temp_layout.Add(self.make_temp_sizer(temp_box, 2, 'Mono 1 Cryo Return',
            False), flag=wx.EXPAND)
        temp_layout.Add(self.make_temp_sizer(temp_box, 5, 'Mono 1 Compton Bot.',
            False), flag=wx.EXPAND)
        temp_layout.Add(self.make_temp_sizer(temp_box, 6, 'Mono 1 Copper Block',
            False), flag=wx.EXPAND)
        temp_layout.Add(self.make_temp_sizer(temp_box, 8, 'Mono 1 2nd Xtal Shield',
            False), flag=wx.EXPAND)
        temp_layout.Add(self.make_temp_sizer(temp_box, 10, 'Mono 2 Cryo Return',
            False), flag=wx.EXPAND)
        temp_layout.Add(self.make_temp_sizer(temp_box, 13, 'Mono 2 Compton Bot.',
            False), flag=wx.EXPAND)
        temp_layout.Add(self.make_temp_sizer(temp_box, 14, 'Mono 2 Copper Block',
            False), flag=wx.EXPAND)
        temp_layout.Add(self.make_temp_sizer(temp_box, 16, 'Mono 2 2nd Xtal Shield',
            False), flag=wx.EXPAND)
        temp_layout.AddGrowableCol(0)
        temp_layout.AddGrowableCol(1)

        temp_sizer.Add(temp_layout, flag=wx.EXPAND|wx.ALL, border=5)


        vac_box = wx.StaticBox(self, label='Vacuum')
        fsize = self.GetFont().Larger().GetPointSize()
        font = wx.Font(fsize, wx.DEFAULT, wx.NORMAL, wx.BOLD)
        vac_box.SetOwnFont(font)

        vac_trip_box = wx.StaticBox(self, label='Vaccum Sections')
        fsize = self.GetFont().GetPointSize()
        font = wx.Font(fsize, wx.DEFAULT, wx.NORMAL, wx.BOLD)
        vac_trip_box.SetOwnFont(font)

        vac_trip_layout = wx.FlexGridSizer(cols=4, vgap=10, hgap=10)
        for i in range(1, 9):
            vac_trip_layout.Add(self.make_vac_trip_sizer(vac_trip_box, i))

        vac_trip_sizer = wx.StaticBoxSizer(vac_trip_box, wx.VERTICAL)
        vac_trip_sizer.Add(vac_trip_layout, flag=wx.EXPAND|wx.ALL, border=5)

        vac_ip_box = wx.StaticBox(self, label='Ion Pumps')
        fsize = self.GetFont().GetPointSize()
        font = wx.Font(fsize, wx.DEFAULT, wx.NORMAL, wx.BOLD)
        vac_ip_box.SetOwnFont(font)

        vac_ip_warn_layout = wx.FlexGridSizer(cols=4, vgap=10, hgap=10)
        for i in range(1, 9):
            vac_ip_warn_layout.Add(self.make_vac_ip_warn_sizer(vac_ip_box, i))

        vac_ip_sizer = wx.StaticBoxSizer(vac_ip_box, wx.VERTICAL)
        vac_ip_sizer.Add(vac_ip_warn_layout, flag=wx.EXPAND|wx.ALL, border=5)

        vac_ig_box = wx.StaticBox(self, label='Ion Gauges')
        fsize = self.GetFont().GetPointSize()
        font = wx.Font(fsize, wx.DEFAULT, wx.NORMAL, wx.BOLD)
        vac_ig_box.SetOwnFont(font)

        vac_ig_warn_layout = wx.FlexGridSizer(cols=4, vgap=10, hgap=10)
        for i in range(1, 11):
            vac_ig_warn_layout.Add(self.make_vac_ig_warn_sizer(vac_ig_box, i))

        vac_ig_sizer = wx.StaticBoxSizer(vac_ig_box, wx.VERTICAL)
        vac_ig_sizer.Add(vac_ig_warn_layout, flag=wx.EXPAND|wx.ALL, border=5)

        vac_sizer = wx.StaticBoxSizer(vac_box, wx.VERTICAL)
        vac_sizer.Add(vac_trip_sizer, flag=wx.EXPAND|wx.ALL, border=5)
        vac_sizer.Add(vac_ip_sizer,
            flag=wx.EXPAND|wx.LEFT|wx.RIGHT|wx.BOTTOM, border=5)
        vac_sizer.Add(vac_ig_sizer,
            flag=wx.EXPAND|wx.LEFT|wx.RIGHT|wx.BOTTOM, border=5)


        flow_box = wx.StaticBox(self, label='Flows')
        fsize = self.GetFont().Larger().GetPointSize()
        font = wx.Font(fsize, wx.DEFAULT, wx.NORMAL, wx.BOLD)
        flow_box.SetOwnFont(font)
        flow_sizer = wx.StaticBoxSizer(flow_box, wx.VERTICAL)

        flow_layout = wx.FlexGridSizer(cols=2, vgap=5, hgap=5)
        flow_layout.Add(self.make_flow_sizer(flow_box, 1, 'White Beam Slits'),
            flag=wx.EXPAND)
        flow_layout.Add(self.make_flow_sizer(flow_box, 2, 'Mono 1 and 2'),
            flag=wx.EXPAND)
        flow_layout.AddGrowableCol(0)
        flow_layout.AddGrowableCol(1)

        flow_sizer.Add(flow_layout, flag=wx.EXPAND|wx.ALL, border=5)


        sub_sizer1 = wx.BoxSizer(wx.VERTICAL)
        sub_sizer1.Add(bleps_sizer, flag=wx.EXPAND|wx.BOTTOM, border=5)
        sub_sizer1.Add(gate_valve_sizer, flag=wx.EXPAND, border=5)

        sub_sizer2 = wx.BoxSizer(wx.VERTICAL)
        sub_sizer2.Add(misc_sizer, flag=wx.EXPAND|wx.BOTTOM, border=5)
        sub_sizer2.Add(temp_sizer, flag=wx.EXPAND|wx.BOTTOM, border=5)
        sub_sizer2.Add(vac_sizer, flag=wx.EXPAND|wx.BOTTOM, border=5)
        sub_sizer2.Add(flow_sizer, flag=wx.EXPAND)

        sub_sizer3 = wx.BoxSizer(wx.HORIZONTAL)
        sub_sizer3.Add(sub_sizer1, flag=wx.EXPAND|wx.RIGHT, border=5)
        sub_sizer3.Add(sub_sizer2, flag=wx.EXPAND)

        top_sizer = wx.BoxSizer(wx.VERTICAL)
        top_sizer.Add(sub_sizer3, flag=wx.EXPAND|wx.ALL, border=5)

        self.SetSizer(top_sizer)

        # return top_sizer

    def _initialize(self):
        pass

    def make_gv_sizer(self, parent, gv_num):

        gv_box = wx.StaticBox(parent, label='Gate Valve {}'.format(gv_num))
        fsize = self.GetFont().GetPointSize()
        font = wx.Font(fsize, wx.DEFAULT, wx.NORMAL, wx.BOLD)
        gv_box.SetOwnFont(font)

        gv_status = epics.wx.PVText(gv_box,
            self.pvs['gv{}_status'.format(gv_num)], fg='forest green')
        gv_both_sw = epics.wx.PVText(gv_box,
            self.pvs['gv{}_both_sw'.format(gv_num)], fg='forest green')
        gv_open_sw = epics.wx.PVText(gv_box,
            self.pvs['gv{}_open_sw'.format(gv_num)], fg='forest green')
        gv_close_sw = epics.wx.PVText(gv_box,
            self.pvs['gv{}_close_sw'.format(gv_num)], fg='forest green')
        gv_no_sw = epics.wx.PVText(gv_box,
            self.pvs['gv{}_no_sw'.format(gv_num)], fg='forest green')
        gv_fail_open = epics.wx.PVText(gv_box,
            self.pvs['gv{}_fail_open'.format(gv_num)], fg='forest green')
        gv_fail_close = epics.wx.PVText(gv_box,
            self.pvs['gv{}_fail_close'.format(gv_num)], fg='forest green')
        gv_fully_open = epics.wx.PVText(gv_box,
            self.pvs['gv{}_fully_open'.format(gv_num)], fg='forest green')
        gv_fully_close = epics.wx.PVText(gv_box,
            self.pvs['gv{}_fully_close'.format(gv_num)], fg='forest green')
        gv_beam_exp = epics.wx.PVText(gv_box,
            self.pvs['gv{}_beam_exp'.format(gv_num)], fg='forest green')

        gv_open = custom_epics_widgets.PVButton2(gv_box,
            self.pvs['gv{}_open'.format(gv_num)], label='Open', size=(50, -1))
        gv_close = custom_epics_widgets.PVButton2(gv_box,
            self.pvs['gv{}_close'.format(gv_num)], label='Close', size=(50, -1))

        gv_status_sizer = wx.BoxSizer(wx.HORIZONTAL)
        gv_status_sizer.Add(wx.StaticText(gv_box, label='Status:'), border=5,
            flag=wx.RIGHT|wx.ALIGN_CENTER_VERTICAL)
        gv_status_sizer.Add(gv_status, flag=wx.RIGHT|wx.ALIGN_CENTER_VERTICAL)
        gv_status_sizer.AddStretchSpacer(1)

        gv_ctrl_sizer = wx.BoxSizer(wx.HORIZONTAL)
        gv_ctrl_sizer.Add(gv_open, flag=wx.LEFT, border=5)
        gv_ctrl_sizer.Add(gv_close, flag=wx.LEFT, border=5)

        gv_faults = wx.FlexGridSizer(cols=2, vgap=5, hgap=5)
        gv_faults.Add(wx.StaticText(gv_box, label='Both switch:'),
            flag=wx.ALIGN_CENTER_VERTICAL)
        gv_faults.Add(gv_both_sw, flag=wx.ALIGN_CENTER_VERTICAL)
        gv_faults.Add(wx.StaticText(gv_box, label='Open switch:'),
            flag=wx.ALIGN_CENTER_VERTICAL)
        gv_faults.Add(gv_open_sw, flag=wx.ALIGN_CENTER_VERTICAL)
        gv_faults.Add(wx.StaticText(gv_box, label='Close switch:'),
            flag=wx.ALIGN_CENTER_VERTICAL)
        gv_faults.Add(gv_close_sw, flag=wx.ALIGN_CENTER_VERTICAL)
        gv_faults.Add(wx.StaticText(gv_box, label='No switch:'),
            flag=wx.ALIGN_CENTER_VERTICAL)
        gv_faults.Add(gv_no_sw, flag=wx.ALIGN_CENTER_VERTICAL)
        gv_faults.Add(wx.StaticText(gv_box, label='Fail to open:'),
            flag=wx.ALIGN_CENTER_VERTICAL)
        gv_faults.Add(gv_fail_open, flag=wx.ALIGN_CENTER_VERTICAL)
        gv_faults.Add(wx.StaticText(gv_box, label='Fail to close:'),
            flag=wx.ALIGN_CENTER_VERTICAL)
        gv_faults.Add(gv_fail_close, flag=wx.ALIGN_CENTER_VERTICAL)
        gv_faults.Add(wx.StaticText(gv_box, label='Fully open:'),
            flag=wx.ALIGN_CENTER_VERTICAL)
        gv_faults.Add(gv_fully_open, flag=wx.ALIGN_CENTER_VERTICAL)
        gv_faults.Add(wx.StaticText(gv_box, label='Fully closed:'),
            flag=wx.ALIGN_CENTER_VERTICAL)
        gv_faults.Add(gv_fully_close, flag=wx.ALIGN_CENTER_VERTICAL)
        gv_faults.Add(wx.StaticText(gv_box, label='Beam exp.:'),
            flag=wx.ALIGN_CENTER_VERTICAL)
        gv_faults.Add(gv_beam_exp, flag=wx.ALIGN_CENTER_VERTICAL)


        gv_box_sizer = wx.StaticBoxSizer(gv_box, wx.VERTICAL)
        gv_box_sizer.Add(gv_status_sizer, flag=wx.ALL|wx.EXPAND, border=5)
        gv_box_sizer.Add(gv_ctrl_sizer, border=5,
            flag=wx.LEFT|wx.RIGHT|wx.BOTTOM|wx.ALIGN_CENTER_HORIZONTAL)
        gv_box_sizer.Add(gv_faults, flag=wx.LEFT|wx.RIGHT|wx.BOTTOM, border=5)

        return gv_box_sizer

    def make_temp_sizer(self, parent, T_num, label, monitored=True):
        T_box = wx.StaticBox(parent, label=label)
        fsize = self.GetFont().GetPointSize()
        font = wx.Font(fsize, wx.DEFAULT, wx.NORMAL, wx.BOLD)
        T_box.SetOwnFont(font)

        temp = epics.wx.PVText(T_box, self.pvs['T{}_temp'.format(T_num)])
        status = epics.wx.PVText(T_box, self.pvs['T{}_status'.format(T_num)],
            fg='forest green')

        if monitored:
            setpoint = epics.wx.PVText(T_box,
                self.pvs['T{}_setpoint'.format(T_num)])
            under_range = epics.wx.PVText(T_box,
                self.pvs['T{}_under_range'.format(T_num)], fg='forest green')
            high_t = epics.wx.PVText(T_box,
                self.pvs['T{}_high'.format(T_num)], fg='forest green')

        temp_grid = wx.FlexGridSizer(cols=4, vgap=5, hgap=5)
        temp_grid.Add(wx.StaticText(T_box, label='Temp. [C]:'),
            flag=wx.ALIGN_CENTER_VERTICAL)
        temp_grid.Add(temp, flag=wx.ALIGN_CENTER_VERTICAL)
        if monitored:
            temp_grid.Add(wx.StaticText(T_box, label='Status:'))
        else:
            temp_grid.Add(wx.StaticText(T_box, label='      Status:'))
        temp_grid.Add(status, flag=wx.ALIGN_CENTER_VERTICAL)

        if monitored:
            temp_grid.Add(wx.StaticText(T_box, label='Setpoint [C]:'),
                flag=wx.ALIGN_CENTER_VERTICAL)
            temp_grid.Add(setpoint, flag=wx.ALIGN_CENTER_VERTICAL)
            temp_grid.Add(wx.StaticText(T_box, label='High T. Alarm:'),
                flag=wx.ALIGN_CENTER_VERTICAL)
            temp_grid.Add(high_t, flag=wx.ALIGN_CENTER_VERTICAL)
            temp_grid.Add(wx.StaticText(T_box, label='Under range:'),
                flag=wx.ALIGN_CENTER_VERTICAL)
            temp_grid.Add(under_range, flag=wx.ALIGN_CENTER_VERTICAL)

        temp_sizer = wx.StaticBoxSizer(T_box, wx.HORIZONTAL)
        temp_sizer.Add(temp_grid, flag=wx.ALL, border=5)
        temp_sizer.AddStretchSpacer(1)

        return temp_sizer

    def make_vac_trip_sizer(self, parent, v_num):
        vac = epics.wx.PVText(parent, self.pvs['vac{}_trip'.format(v_num)],
            fg='forest green')

        sizer = wx.BoxSizer(wx.HORIZONTAL)
        sizer.Add(wx.StaticText(parent, label='Vac. section {}:'.format(v_num)),
            flag=wx.RIGHT|wx.ALIGN_CENTER_VERTICAL, border=5)
        sizer.Add(vac, flag=wx.ALIGN_CENTER_VERTICAL)

        return sizer

    def make_vac_ip_warn_sizer(self, parent, v_num):
        vac_status = epics.wx.PVText(parent, self.pvs['vac{}_ip_status'.format(v_num)],
            fg='forest green')
        vac_warn = epics.wx.PVText(parent, self.pvs['vac{}_ip_warn'.format(v_num)],
            fg='forest green')

        sizer = wx.FlexGridSizer(cols=2, vgap=5, hgap=5)
        sizer.Add(wx.StaticText(parent, label='IP {} status:'.format(v_num)),
            flag=wx.ALIGN_CENTER_VERTICAL)
        sizer.Add(vac_status, flag=wx.ALIGN_CENTER_VERTICAL)
        sizer.Add(wx.StaticText(parent, label='IP {} warning:'.format(v_num)),
            flag=wx.ALIGN_CENTER_VERTICAL)
        sizer.Add(vac_warn, flag=wx.ALIGN_CENTER_VERTICAL)

        return sizer

    def make_vac_ig_warn_sizer(self, parent, v_num):
        vac_status = epics.wx.PVText(parent, self.pvs['vac{}_ig_status'.format(v_num)],
            fg='forest green')
        vac_warn = epics.wx.PVText(parent, self.pvs['vac{}_ig_warn'.format(v_num)],
            fg='forest green')

        sizer = wx.FlexGridSizer(cols=2, vgap=5, hgap=5)
        sizer.Add(wx.StaticText(parent, label='IG {} status:'.format(v_num)),
            flag=wx.ALIGN_CENTER_VERTICAL)
        sizer.Add(vac_status, flag=wx.ALIGN_CENTER_VERTICAL)
        sizer.Add(wx.StaticText(parent, label='IG {} warning:'.format(v_num)),
            flag=wx.ALIGN_CENTER_VERTICAL)
        sizer.Add(vac_warn, flag=wx.ALIGN_CENTER_VERTICAL)


        return sizer

    def make_flow_sizer(self, parent, f_num, label, monitored=True):
        flow_box = wx.StaticBox(parent, label=label)
        fsize = self.GetFont().GetPointSize()
        font = wx.Font(fsize, wx.DEFAULT, wx.NORMAL, wx.BOLD)
        flow_box.SetOwnFont(font)

        flow = epics.wx.PVText(flow_box, self.pvs['flow{}_rate'.format(f_num)])
        status = epics.wx.PVText(flow_box, self.pvs['flow{}_status'.format(f_num)],
            fg='forest green')

        if monitored:
            setpoint = epics.wx.PVText(flow_box,
                self.pvs['flow{}_setpoint'.format(f_num)])
            under_range = epics.wx.PVText(flow_box,
                self.pvs['flow{}_over_range'.format(f_num)], fg='forest green')
            high_t = epics.wx.PVText(flow_box,
                self.pvs['flow{}_low'.format(f_num)], fg='forest green')

        flow_grid = wx.FlexGridSizer(cols=4, vgap=5, hgap=5)
        flow_grid.Add(wx.StaticText(flow_box, label='Flow:'),
            flag=wx.ALIGN_CENTER_VERTICAL)
        flow_grid.Add(flow, flag=wx.ALIGN_CENTER_VERTICAL)
        if monitored:
            flow_grid.Add(wx.StaticText(flow_box, label='Status:'))
        else:
            flow_grid.Add(wx.StaticText(flow_box, label='      Status:'))
        flow_grid.Add(status, flag=wx.ALIGN_CENTER_VERTICAL)

        if monitored:
            flow_grid.Add(wx.StaticText(flow_box, label='Setpoint:'),
                flag=wx.ALIGN_CENTER_VERTICAL)
            flow_grid.Add(setpoint, flag=wx.ALIGN_CENTER_VERTICAL)
            flow_grid.Add(wx.StaticText(flow_box, label='Low flow alarm:'),
                flag=wx.ALIGN_CENTER_VERTICAL)
            flow_grid.Add(high_t, flag=wx.ALIGN_CENTER_VERTICAL)
            flow_grid.Add(wx.StaticText(flow_box, label='Over range:'),
                flag=wx.ALIGN_CENTER_VERTICAL)
            flow_grid.Add(under_range, flag=wx.ALIGN_CENTER_VERTICAL)

        flow_sizer = wx.StaticBoxSizer(flow_box, wx.HORIZONTAL)
        flow_sizer.Add(flow_grid, flag=wx.ALL, border=5)
        flow_sizer.AddStretchSpacer(1)

        return flow_sizer

class BeamlineStatusFrame(wx.Frame):
    """
    A lightweight amplifier frame designed to hold an arbitrary number of dios
    in an arbitrary grid pattern.
    """
    def __init__(self, *args, **kwargs):
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

        top_sizer = self._create_layout()

        # screen_two = wx.Display(1)
        # w_edge, h_edge_, screen_two_w, screen_two_h = screen_two.GetGeometry()

        # self.SetPosition((int(w_edge + (screen_two_w / 2)),
        #                            int(screen_two_h / 2)))

        self.SetSizer(top_sizer)
        self.Layout()
        self.Fit()
        # self.Raise()
        # self.PostSizeEvent()
        # wx.CallLater(5000, self.PostSizeEvent)
        # wx.CallLater(5000, self.Layout)

        size = self.GetSize()

        self.SetSize((size[0], size[1]+30))

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
        main_panel = MainStatusPanel('', None, self)

        top_sizer = wx.BoxSizer(wx.VERTICAL)
        top_sizer.Add(main_panel, proportion=1, flag=wx.EXPAND)

        return top_sizer


if __name__ == '__main__':

    app = wx.App()
    frame = BeamlineStatusFrame(parent=None, title='Test Status Page')
    frame.Show()
    app.MainLoop()
