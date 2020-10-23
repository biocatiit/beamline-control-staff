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

import platform
import math

import wx
import epics, epics.wx
import matplotlib
from matplotlib.backends.backend_wxagg import FigureCanvasWxAgg
from matplotlib.figure import Figure

matplotlib.rcParams['backend'] = 'WxAgg'

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
        aps_page = APSPanel(self.pvs, notebook)
        station_page = StationPanel(self.pvs, notebook)
        exp_page = ExpPanel(self.pvs, notebook)

        notebook.AddPage(overview_page, 'Overview')
        notebook.AddPage(bleps_page, 'BLEPS')
        notebook.AddPage(aps_page, 'APS')
        notebook.AddPage(station_page, 'Beamline')
        notebook.AddPage(exp_page, 'Experiment')

        top_sizer = wx.BoxSizer(wx.VERTICAL)
        top_sizer.Add(notebook, proportion=1, border=5, flag=wx.EXPAND|wx.ALL)

        self.SetSizer(top_sizer)

    def _initialize(self):
        self.pvs = {
            'fe_shutter'        : epics.PV('FE:18:ID:FEshutter'),
            'd_shutter'         : epics.PV('PA:18ID:STA_D_SDS_OPEN_PL'),
            'fe_shutter_open'   : epics.PV('18ID:rshtr:A:OPEN'),
            'fe_shutter_close'  : epics.PV('18ID:rshtr:A:CLOSE'),
            'd_shutter_open'    : epics.PV('18ID:rshtr:D:OPEN'),
            'd_shutter_close'   : epics.PV('18ID:rshtr:D:CLOSE'),
            'u_gap'             : epics.PV('ID18:Gap'),
            'u_energy'          : epics.PV('ID18:Energy'),
            'u_target_gap'      : epics.PV('ID18:GapSet'),
            'u_target_energy'   : epics.PV('ID18:EnergySet'),
            'u_start'           : epics.PV('ID18:Start'),

            'A_door_1'          : epics.PV('PA:18ID:STA_A_DR1_CLOSE_LS'),
            'A_user_key'        : epics.PV('PA:18ID:STA_A_USER_KEY_SW'),
            'A_aps_key_a'       : epics.PV('PA:18ID:STA_A_APS_ENBLE_PL'),
            'A_searched_a'      : epics.PV('PA:18ID:STA_A_SEARCHED_PL'),
            'A_beam_ready'      : epics.PV('PA:18ID:STA_A_BEAMREADY_PL'),
            'A_beam_active'     : epics.PV('PA:18ID:STA_A_NO_ACCESS'),
            'A_crash_1'         : epics.PV('PA:18ID:STA_A_CB1'),
            'C_door_1'          : epics.PV('PA:18ID:STA_C_DR1_CLOSE_LS'),
            'C_door_2'          : epics.PV('PA:18ID:STA_C_DR2_CLOSE_LS'),
            'C_user_key'        : epics.PV('PA:18ID:STA_C_USER_KEY_SW'),
            'C_aps_key_a'       : epics.PV('PA:18ID:STA_C_APS_ENBLE_PL'),
            'C_searched_a'      : epics.PV('PA:18ID:STA_C_SEARCHED_PL'),
            'C_beam_ready'      : epics.PV('PA:18ID:STA_C_BEAMREADY_PL'),
            'C_beam_active'     : epics.PV('PA:18ID:STA_C_NO_ACCESS'),
            'C_crash_1'         : epics.PV('PA:18ID:STA_C_CB1'),
            'C_crash_2'         : epics.PV('PA:18ID:STA_C_CB2'),
            'D_door_1'          : epics.PV('PA:18ID:STA_D_DR1_CLOSE_LS'),
            'D_door_2'          : epics.PV('PA:18ID:STA_D_DR2_CLOSE_LS'),
            'D_door_3'          : epics.PV('PA:18ID:STA_D_DR3_CLOSE_LS'),
            'D_door_4'          : epics.PV('PA:18ID:STA_D_DR4_CLOSE_LS'),
            'D_user_key'        : epics.PV('PA:18ID:STA_D_USER_KEY_SW'),
            'D_aps_key_a'       : epics.PV('PA:18ID:STA_D_APS_ENBLE_PL'),
            'D_searched_a'      : epics.PV('PA:18ID:STA_D_SEARCHED_PL'),
            'D_beam_ready'      : epics.PV('PA:18ID:STA_D_BEAMREADY_PL'),
            'D_beam_active'     : epics.PV('PA:18ID:STA_D_NO_ACCESS'),
            'D_crash_1'         : epics.PV('PA:18ID:STA_D_CB1'),
            'D_crash_2'         : epics.PV('PA:18ID:STA_D_CB2'),
            'D_crash_3'         : epics.PV('PA:18ID:STA_D_CB3'),

            'current'           : epics.PV('XFD:srCurrent'),
            'aps_status'        : epics.PV('S:ActualMode'),
            'aps_nominal'       : epics.PV('S:DesiredMode'),
            'aps_shutter_permit': epics.PV('ACIS:ShutterPermit'),
            'aps_msg1'          : epics.PV('XFD:message4'),
            'aps_msg2'          : epics.PV('XFD:message14'),
            'aps_msg3'          : epics.PV('XFD:message15'),
            'aps_update_msg'    : epics.PV('XFD:message18'),
            'aps_bc_time'       : epics.PV('S:SRtimeCP'),
            'aps_bc_current'    : epics.PV('S:SRcurrentCP'),
            'rf_bpm_18b_p0_x'   : epics.PV('S18B:P0:ms:x:InUseBO'),
            'rf_bpm_18b_p1_x'   : epics.PV('S18B:P1:ms:x:InUseBO'),
            'rf_bpm_19a_p0_x'   : epics.PV('S19A:P0:ms:x:InUseBO'),
            'rf_bpm_19a_p1_x'   : epics.PV('S19A:P1:ms:x:InUseBO'),
            'rf_bpm_18b_p0_y'   : epics.PV('S18B:P0:ms:y:InUseBO'),
            'rf_bpm_18b_p1_y'   : epics.PV('S18B:P1:ms:y:InUseBO'),
            'rf_bpm_19a_p0_y'   : epics.PV('S19A:P0:ms:y:InUseBO'),
            'rf_bpm_19a_p1_y'   : epics.PV('S19A:P1:ms:y:InUseBO'),
            'x_bpm_p1_x'        : epics.PV('S18ID:P1:ms:x:InUseBO'),
            'x_bpm_p2_x'        : epics.PV('S18ID:P2:ms:x:InUseBO'),
            'x_bpm_p1_y'        : epics.PV('S18ID:P1:ms:y:InUseBO'),
            'x_bpm_p2_y'        : epics.PV('S18ID:P2:ms:y:InUseBO'),

            'exp_slow_shtr1'    : epics.PV('18ID:bi0:ch6'),
            'exp_slow_shtr2'    : epics.PV('18ID:bi0:ch7'),
            'exp_fast_shtr'     : epics.PV('18ID:bo0:ch9'),
            'col_vac'           : epics.PV('18ID:VAC:D:Cols'),
            'guard_vac'         : epics.PV('18ID:VAC:D:Guards'),
            'scatter_vac'       : epics.PV('18ID:VAC:D:ScatterChamber'),
            'sample_vac'        : epics.PV('18ID:VAC:D:Sample'),
            'vs1_vac'           : epics.PV('18ID:VAC:D:Vac1'),
            'vs2_vac'           : epics.PV('18ID:VAC:D:Vac2'),
            'i0'                : epics.PV('18ID:IP330_11'),
            'i1'                : epics.PV('18ID:IP330_12'),
            'atten_1'           : epics.PV('18ID:bi0:ch8'),
            'atten_2'           : epics.PV('18ID:bi0:ch1'),
            'atten_4'           : epics.PV('18ID:bi0:ch2'),
            'atten_8'           : epics.PV('18ID:bi0:ch3'),
            'atten_16'          : epics.PV('18ID:bi0:ch4'),
            'atten_32'          : epics.PV('18ID:bi0:ch5'),

            'bleps_fault'       : epics.PV('18ID:BLEPS:FAULT_EXISTS'),
            'bleps_trip'        : epics.PV('18ID:BLEPS:TRIP_EXISTS'),
            'bleps_warning'     : epics.PV('18ID:BLEPS:WARNING_EXISTS'),
            'bleps_fault_reset' : epics.PV('18ID:BLEPS:FAULT_RESET'),
            'bleps_trip_reset'  : epics.PV('18ID:BLEPS:TRIP_RESET'),
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
            'fault1_num'        : epics.PV('18ID:BLEPS:FAULT_NUMBER_01'),
            'fault1_year'       : epics.PV('18ID:BLEPS:FAULT_YEAR_01'),
            'fault1_month'      : epics.PV('18ID:BLEPS:FAULT_MONTH_01'),
            'fault1_day'        : epics.PV('18ID:BLEPS:FAULT_DAY_01'),
            'fault1_hour'       : epics.PV('18ID:BLEPS:FAULT_HOUR_01'),
            'fault1_mi'         : epics.PV('18ID:BLEPS:FAULT_MINUTE_01'),
            'fault1_sec'        : epics.PV('18ID:BLEPS:FAULT_SECOND_01'),
            'fault2_num'        : epics.PV('18ID:BLEPS:FAULT_NUMBER_02'),
            'fault2_year'       : epics.PV('18ID:BLEPS:FAULT_YEAR_02'),
            'fault2_month'      : epics.PV('18ID:BLEPS:FAULT_MONTH_02'),
            'fault2_day'        : epics.PV('18ID:BLEPS:FAULT_DAY_02'),
            'fault2_hour'       : epics.PV('18ID:BLEPS:FAULT_HOUR_02'),
            'fault2_mi'         : epics.PV('18ID:BLEPS:FAULT_MINUTE_02'),
            'fault2_sec'        : epics.PV('18ID:BLEPS:FAULT_SECOND_02'),
            'fault3_num'        : epics.PV('18ID:BLEPS:FAULT_NUMBER_03'),
            'fault3_year'       : epics.PV('18ID:BLEPS:FAULT_YEAR_03'),
            'fault3_month'      : epics.PV('18ID:BLEPS:FAULT_MONTH_03'),
            'fault3_day'        : epics.PV('18ID:BLEPS:FAULT_DAY_03'),
            'fault3_hour'       : epics.PV('18ID:BLEPS:FAULT_HOUR_03'),
            'fault3_mi'         : epics.PV('18ID:BLEPS:FAULT_MINUTE_03'),
            'fault3_sec'        : epics.PV('18ID:BLEPS:FAULT_SECOND_03'),
            'fault4_num'        : epics.PV('18ID:BLEPS:FAULT_NUMBER_04'),
            'fault4_year'       : epics.PV('18ID:BLEPS:FAULT_YEAR_04'),
            'fault4_month'      : epics.PV('18ID:BLEPS:FAULT_MONTH_04'),
            'fault4_day'        : epics.PV('18ID:BLEPS:FAULT_DAY_04'),
            'fault4_hour'       : epics.PV('18ID:BLEPS:FAULT_HOUR_04'),
            'fault4_mi'         : epics.PV('18ID:BLEPS:FAULT_MINUTE_04'),
            'fault4_sec'        : epics.PV('18ID:BLEPS:FAULT_SECOND_04'),
            'fault5_num'        : epics.PV('18ID:BLEPS:FAULT_NUMBER_05'),
            'fault5_year'       : epics.PV('18ID:BLEPS:FAULT_YEAR_05'),
            'fault5_month'      : epics.PV('18ID:BLEPS:FAULT_MONTH_05'),
            'fault5_day'        : epics.PV('18ID:BLEPS:FAULT_DAY_05'),
            'fault5_hour'       : epics.PV('18ID:BLEPS:FAULT_HOUR_05'),
            'fault5_mi'         : epics.PV('18ID:BLEPS:FAULT_MINUTE_05'),
            'fault5_sec'        : epics.PV('18ID:BLEPS:FAULT_SECOND_05'),
            'fault6_num'        : epics.PV('18ID:BLEPS:FAULT_NUMBER_06'),
            'fault6_year'       : epics.PV('18ID:BLEPS:FAULT_YEAR_06'),
            'fault6_month'      : epics.PV('18ID:BLEPS:FAULT_MONTH_06'),
            'fault6_day'        : epics.PV('18ID:BLEPS:FAULT_DAY_06'),
            'fault6_hour'       : epics.PV('18ID:BLEPS:FAULT_HOUR_06'),
            'fault6_mi'         : epics.PV('18ID:BLEPS:FAULT_MINUTE_06'),
            'fault6_sec'        : epics.PV('18ID:BLEPS:FAULT_SECOND_06'),
            'fault7_num'        : epics.PV('18ID:BLEPS:FAULT_NUMBER_07'),
            'fault7_year'       : epics.PV('18ID:BLEPS:FAULT_YEAR_07'),
            'fault7_month'      : epics.PV('18ID:BLEPS:FAULT_MONTH_07'),
            'fault7_day'        : epics.PV('18ID:BLEPS:FAULT_DAY_07'),
            'fault7_hour'       : epics.PV('18ID:BLEPS:FAULT_HOUR_07'),
            'fault7_mi'         : epics.PV('18ID:BLEPS:FAULT_MINUTE_07'),
            'fault7_sec'        : epics.PV('18ID:BLEPS:FAULT_SECOND_07'),
            'fault8_num'        : epics.PV('18ID:BLEPS:FAULT_NUMBER_08'),
            'fault8_year'       : epics.PV('18ID:BLEPS:FAULT_YEAR_08'),
            'fault8_month'      : epics.PV('18ID:BLEPS:FAULT_MONTH_08'),
            'fault8_day'        : epics.PV('18ID:BLEPS:FAULT_DAY_08'),
            'fault8_hour'       : epics.PV('18ID:BLEPS:FAULT_HOUR_08'),
            'fault8_mi'         : epics.PV('18ID:BLEPS:FAULT_MINUTE_08'),
            'fault8_sec'        : epics.PV('18ID:BLEPS:FAULT_SECOND_08'),
            'fault9_num'        : epics.PV('18ID:BLEPS:FAULT_NUMBER_09'),
            'fault9_year'       : epics.PV('18ID:BLEPS:FAULT_YEAR_09'),
            'fault9_month'      : epics.PV('18ID:BLEPS:FAULT_MONTH_09'),
            'fault9_day'        : epics.PV('18ID:BLEPS:FAULT_DAY_09'),
            'fault9_hour'       : epics.PV('18ID:BLEPS:FAULT_HOUR_09'),
            'fault9_mi'         : epics.PV('18ID:BLEPS:FAULT_MINUTE_09'),
            'fault9_sec'        : epics.PV('18ID:BLEPS:FAULT_SECOND_09'),
            'fault10_num'       : epics.PV('18ID:BLEPS:FAULT_NUMBER_10'),
            'fault10_year'      : epics.PV('18ID:BLEPS:FAULT_YEAR_10'),
            'fault10_month'     : epics.PV('18ID:BLEPS:FAULT_MONTH_10'),
            'fault10_day'       : epics.PV('18ID:BLEPS:FAULT_DAY_10'),
            'fault10_hour'      : epics.PV('18ID:BLEPS:FAULT_HOUR_10'),
            'fault10_mi'        : epics.PV('18ID:BLEPS:FAULT_MINUTE_10'),
            'fault10_sec'       : epics.PV('18ID:BLEPS:FAULT_SECOND_10'),
            'trip1_num'         : epics.PV('18ID:BLEPS:TRIP_NUMBER_01'),
            'trip1_year'        : epics.PV('18ID:BLEPS:TRIP_YEAR_01'),
            'trip1_month'       : epics.PV('18ID:BLEPS:TRIP_MONTH_01'),
            'trip1_day'         : epics.PV('18ID:BLEPS:TRIP_DAY_01'),
            'trip1_hour'        : epics.PV('18ID:BLEPS:TRIP_HOUR_01'),
            'trip1_mi'          : epics.PV('18ID:BLEPS:TRIP_MINUTE_01'),
            'trip1_sec'         : epics.PV('18ID:BLEPS:TRIP_SECOND_01'),
            'trip2_num'         : epics.PV('18ID:BLEPS:TRIP_NUMBER_02'),
            'trip2_year'        : epics.PV('18ID:BLEPS:TRIP_YEAR_02'),
            'trip2_month'       : epics.PV('18ID:BLEPS:TRIP_MONTH_02'),
            'trip2_day'         : epics.PV('18ID:BLEPS:TRIP_DAY_02'),
            'trip2_hour'        : epics.PV('18ID:BLEPS:TRIP_HOUR_02'),
            'trip2_mi'          : epics.PV('18ID:BLEPS:TRIP_MINUTE_02'),
            'trip2_sec'         : epics.PV('18ID:BLEPS:TRIP_SECOND_02'),
            'trip3_num'         : epics.PV('18ID:BLEPS:TRIP_NUMBER_03'),
            'trip3_year'        : epics.PV('18ID:BLEPS:TRIP_YEAR_03'),
            'trip3_month'       : epics.PV('18ID:BLEPS:TRIP_MONTH_03'),
            'trip3_day'         : epics.PV('18ID:BLEPS:TRIP_DAY_03'),
            'trip3_hour'        : epics.PV('18ID:BLEPS:TRIP_HOUR_03'),
            'trip3_mi'          : epics.PV('18ID:BLEPS:TRIP_MINUTE_03'),
            'trip3_sec'         : epics.PV('18ID:BLEPS:TRIP_SECOND_03'),
            'trip4_num'         : epics.PV('18ID:BLEPS:TRIP_NUMBER_04'),
            'trip4_year'        : epics.PV('18ID:BLEPS:TRIP_YEAR_04'),
            'trip4_month'       : epics.PV('18ID:BLEPS:TRIP_MONTH_04'),
            'trip4_day'         : epics.PV('18ID:BLEPS:TRIP_DAY_04'),
            'trip4_hour'        : epics.PV('18ID:BLEPS:TRIP_HOUR_04'),
            'trip4_mi'          : epics.PV('18ID:BLEPS:TRIP_MINUTE_04'),
            'trip4_sec'         : epics.PV('18ID:BLEPS:TRIP_SECOND_04'),
            'trip5_num'         : epics.PV('18ID:BLEPS:TRIP_NUMBER_05'),
            'trip5_year'        : epics.PV('18ID:BLEPS:TRIP_YEAR_05'),
            'trip5_month'       : epics.PV('18ID:BLEPS:TRIP_MONTH_05'),
            'trip5_day'         : epics.PV('18ID:BLEPS:TRIP_DAY_05'),
            'trip5_hour'        : epics.PV('18ID:BLEPS:TRIP_HOUR_05'),
            'trip5_mi'          : epics.PV('18ID:BLEPS:TRIP_MINUTE_05'),
            'trip5_sec'         : epics.PV('18ID:BLEPS:TRIP_SECOND_05'),
            'trip6_num'         : epics.PV('18ID:BLEPS:TRIP_NUMBER_06'),
            'trip6_year'        : epics.PV('18ID:BLEPS:TRIP_YEAR_06'),
            'trip6_month'       : epics.PV('18ID:BLEPS:TRIP_MONTH_06'),
            'trip6_day'         : epics.PV('18ID:BLEPS:TRIP_DAY_06'),
            'trip6_hour'        : epics.PV('18ID:BLEPS:TRIP_HOUR_06'),
            'trip6_mi'          : epics.PV('18ID:BLEPS:TRIP_MINUTE_06'),
            'trip6_sec'         : epics.PV('18ID:BLEPS:TRIP_SECOND_06'),
            'trip7_num'         : epics.PV('18ID:BLEPS:TRIP_NUMBER_07'),
            'trip7_year'        : epics.PV('18ID:BLEPS:TRIP_YEAR_07'),
            'trip7_month'       : epics.PV('18ID:BLEPS:TRIP_MONTH_07'),
            'trip7_day'         : epics.PV('18ID:BLEPS:TRIP_DAY_07'),
            'trip7_hour'        : epics.PV('18ID:BLEPS:TRIP_HOUR_07'),
            'trip7_mi'          : epics.PV('18ID:BLEPS:TRIP_MINUTE_07'),
            'trip7_sec'         : epics.PV('18ID:BLEPS:TRIP_SECOND_07'),
            'trip8_num'         : epics.PV('18ID:BLEPS:TRIP_NUMBER_08'),
            'trip8_year'        : epics.PV('18ID:BLEPS:TRIP_YEAR_08'),
            'trip8_month'       : epics.PV('18ID:BLEPS:TRIP_MONTH_08'),
            'trip8_day'         : epics.PV('18ID:BLEPS:TRIP_DAY_08'),
            'trip8_hour'        : epics.PV('18ID:BLEPS:TRIP_HOUR_08'),
            'trip8_mi'          : epics.PV('18ID:BLEPS:TRIP_MINUTE_08'),
            'trip8_sec'         : epics.PV('18ID:BLEPS:TRIP_SECOND_08'),
            'trip9_num'         : epics.PV('18ID:BLEPS:TRIP_NUMBER_09'),
            'trip9_year'        : epics.PV('18ID:BLEPS:TRIP_YEAR_09'),
            'trip9_month'       : epics.PV('18ID:BLEPS:TRIP_MONTH_09'),
            'trip9_day'         : epics.PV('18ID:BLEPS:TRIP_DAY_09'),
            'trip9_hour'        : epics.PV('18ID:BLEPS:TRIP_HOUR_09'),
            'trip9_mi'          : epics.PV('18ID:BLEPS:TRIP_MINUTE_09'),
            'trip9_sec'         : epics.PV('18ID:BLEPS:TRIP_SECOND_09'),
            'trip10_num'        : epics.PV('18ID:BLEPS:TRIP_NUMBER_10'),
            'trip10_year'       : epics.PV('18ID:BLEPS:TRIP_YEAR_10'),
            'trip10_month'      : epics.PV('18ID:BLEPS:TRIP_MONTH_10'),
            'trip10_day'        : epics.PV('18ID:BLEPS:TRIP_DAY_10'),
            'trip10_hour'       : epics.PV('18ID:BLEPS:TRIP_HOUR_10'),
            'trip10_mi'         : epics.PV('18ID:BLEPS:TRIP_MINUTE_10'),
            'trip10_sec'        : epics.PV('18ID:BLEPS:TRIP_SECOND_10'),
            'warn1_num'         : epics.PV('18ID:BLEPS:WARN_NUMBER_01'),
            'warn1_year'        : epics.PV('18ID:BLEPS:WARN_YEAR_01'),
            'warn1_month'       : epics.PV('18ID:BLEPS:WARN_MONTH_01'),
            'warn1_day'         : epics.PV('18ID:BLEPS:WARN_DAY_01'),
            'warn1_hour'        : epics.PV('18ID:BLEPS:WARN_HOUR_01'),
            'warn1_mi'          : epics.PV('18ID:BLEPS:WARN_MINUTE_01'),
            'warn1_sec'         : epics.PV('18ID:BLEPS:WARN_SECOND_01'),
            'warn2_num'         : epics.PV('18ID:BLEPS:WARN_NUMBER_02'),
            'warn2_year'        : epics.PV('18ID:BLEPS:WARN_YEAR_02'),
            'warn2_month'       : epics.PV('18ID:BLEPS:WARN_MONTH_02'),
            'warn2_day'         : epics.PV('18ID:BLEPS:WARN_DAY_02'),
            'warn2_hour'        : epics.PV('18ID:BLEPS:WARN_HOUR_02'),
            'warn2_mi'          : epics.PV('18ID:BLEPS:WARN_MINUTE_02'),
            'warn2_sec'         : epics.PV('18ID:BLEPS:WARN_SECOND_02'),
            'warn3_num'         : epics.PV('18ID:BLEPS:WARN_NUMBER_03'),
            'warn3_year'        : epics.PV('18ID:BLEPS:WARN_YEAR_03'),
            'warn3_month'       : epics.PV('18ID:BLEPS:WARN_MONTH_03'),
            'warn3_day'         : epics.PV('18ID:BLEPS:WARN_DAY_03'),
            'warn3_hour'        : epics.PV('18ID:BLEPS:WARN_HOUR_03'),
            'warn3_mi'          : epics.PV('18ID:BLEPS:WARN_MINUTE_03'),
            'warn3_sec'         : epics.PV('18ID:BLEPS:WARN_SECOND_03'),
            'warn4_num'         : epics.PV('18ID:BLEPS:WARN_NUMBER_04'),
            'warn4_year'        : epics.PV('18ID:BLEPS:WARN_YEAR_04'),
            'warn4_month'       : epics.PV('18ID:BLEPS:WARN_MONTH_04'),
            'warn4_day'         : epics.PV('18ID:BLEPS:WARN_DAY_04'),
            'warn4_hour'        : epics.PV('18ID:BLEPS:WARN_HOUR_04'),
            'warn4_mi'          : epics.PV('18ID:BLEPS:WARN_MINUTE_04'),
            'warn4_sec'         : epics.PV('18ID:BLEPS:WARN_SECOND_04'),
            'warn5_num'         : epics.PV('18ID:BLEPS:WARN_NUMBER_05'),
            'warn5_year'        : epics.PV('18ID:BLEPS:WARN_YEAR_05'),
            'warn5_month'       : epics.PV('18ID:BLEPS:WARN_MONTH_05'),
            'warn5_day'         : epics.PV('18ID:BLEPS:WARN_DAY_05'),
            'warn5_hour'        : epics.PV('18ID:BLEPS:WARN_HOUR_05'),
            'warn5_mi'          : epics.PV('18ID:BLEPS:WARN_MINUTE_05'),
            'warn5_sec'         : epics.PV('18ID:BLEPS:WARN_SECOND_05'),
            'warn6_num'         : epics.PV('18ID:BLEPS:WARN_NUMBER_06'),
            'warn6_year'        : epics.PV('18ID:BLEPS:WARN_YEAR_06'),
            'warn6_month'       : epics.PV('18ID:BLEPS:WARN_MONTH_06'),
            'warn6_day'         : epics.PV('18ID:BLEPS:WARN_DAY_06'),
            'warn6_hour'        : epics.PV('18ID:BLEPS:WARN_HOUR_06'),
            'warn6_mi'          : epics.PV('18ID:BLEPS:WARN_MINUTE_06'),
            'warn6_sec'         : epics.PV('18ID:BLEPS:WARN_SECOND_06'),
            'warn7_num'         : epics.PV('18ID:BLEPS:WARN_NUMBER_07'),
            'warn7_year'        : epics.PV('18ID:BLEPS:WARN_YEAR_07'),
            'warn7_month'       : epics.PV('18ID:BLEPS:WARN_MONTH_07'),
            'warn7_day'         : epics.PV('18ID:BLEPS:WARN_DAY_07'),
            'warn7_hour'        : epics.PV('18ID:BLEPS:WARN_HOUR_07'),
            'warn7_mi'          : epics.PV('18ID:BLEPS:WARN_MINUTE_07'),
            'warn7_sec'         : epics.PV('18ID:BLEPS:WARN_SECOND_07'),
            'warn8_num'         : epics.PV('18ID:BLEPS:WARN_NUMBER_08'),
            'warn8_year'        : epics.PV('18ID:BLEPS:WARN_YEAR_08'),
            'warn8_month'       : epics.PV('18ID:BLEPS:WARN_MONTH_08'),
            'warn8_day'         : epics.PV('18ID:BLEPS:WARN_DAY_08'),
            'warn8_hour'        : epics.PV('18ID:BLEPS:WARN_HOUR_08'),
            'warn8_mi'          : epics.PV('18ID:BLEPS:WARN_MINUTE_08'),
            'warn8_sec'         : epics.PV('18ID:BLEPS:WARN_SECOND_08'),
            'warn9_num'         : epics.PV('18ID:BLEPS:WARN_NUMBER_09'),
            'warn9_year'        : epics.PV('18ID:BLEPS:WARN_YEAR_09'),
            'warn9_month'       : epics.PV('18ID:BLEPS:WARN_MONTH_09'),
            'warn9_day'         : epics.PV('18ID:BLEPS:WARN_DAY_09'),
            'warn9_hour'        : epics.PV('18ID:BLEPS:WARN_HOUR_09'),
            'warn9_mi'          : epics.PV('18ID:BLEPS:WARN_MINUTE_09'),
            'warn9_sec'         : epics.PV('18ID:BLEPS:WARN_SECOND_09'),
            'warn10_num'        : epics.PV('18ID:BLEPS:WARN_NUMBER_10'),
            'warn10_year'       : epics.PV('18ID:BLEPS:WARN_YEAR_10'),
            'warn10_month'      : epics.PV('18ID:BLEPS:WARN_MONTH_10'),
            'warn10_day'        : epics.PV('18ID:BLEPS:WARN_DAY_10'),
            'warn10_hour'       : epics.PV('18ID:BLEPS:WARN_HOUR_10'),
            'warn10_mi'         : epics.PV('18ID:BLEPS:WARN_MINUTE_10'),
            'warn10_sec'        : epics.PV('18ID:BLEPS:WARN_SECOND_10'),
            'plc_year'          : epics.PV('18ID:BLEPS:YEAR'),
            'plc_month'         : epics.PV('18ID:BLEPS:MONTH'),
            'plc_day'           : epics.PV('18ID:BLEPS:DAY'),
            'plc_hour'          : epics.PV('18ID:BLEPS:HOUR'),
            'plc_mi'            : epics.PV('18ID:BLEPS:MINUTE'),
            'plc_sec'           : epics.PV('18ID:BLEPS:SECOND'),
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

        stack_box = wx.StaticBox(self, label='Alert Stacks')
        fsize = self.GetFont().Larger().GetPointSize()
        font = wx.Font(fsize, wx.DEFAULT, wx.NORMAL, wx.BOLD)
        stack_box.SetOwnFont(font)
        stack_sizer = wx.StaticBoxSizer(stack_box, wx.VERTICAL)

        stack_layout = wx.FlexGridSizer(cols=2, vgap=5, hgap=5)
        stack_layout.Add(self.make_fault_stack(stack_box, 'fault'))
        stack_layout.Add(self.make_fault_stack(stack_box, 'trip'))
        stack_layout.Add(self.make_fault_stack(stack_box, 'warn'))
        stack_layout.Add(self.make_pv_datetime(stack_box))

        stack_sizer.Add(stack_layout, flag=wx.EXPAND|wx.ALL, border=5)

        sub_sizer1 = wx.BoxSizer(wx.VERTICAL)
        sub_sizer1.Add(bleps_sizer, flag=wx.EXPAND|wx.BOTTOM, border=5)
        sub_sizer1.Add(gate_valve_sizer, flag=wx.EXPAND|wx.BOTTOM, border=5)
        sub_sizer1.Add(stack_sizer, flag=wx.EXPAND)

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

    def make_fault_stack(self, parent, stype):
        if stype.lower() == 'warn':
            box_label = 'Warning Stack'
        else:
            box_label = '{} Stack'.format(stype.capitalize())
        fault_box = wx.StaticBox(parent, label=box_label)
        fsize = self.GetFont().GetPointSize()
        font = wx.Font(fsize, wx.DEFAULT, wx.NORMAL, wx.BOLD)
        fault_box.SetOwnFont(font)

        stack_grid_sizer = wx.FlexGridSizer(cols=3, vgap=5, hgap=10)
        stack_grid_sizer.Add(wx.StaticText(parent, label='{} #'.format(stype.capitalize())),
            flag=wx.ALIGN_CENTER_VERTICAL)
        stack_grid_sizer.Add(wx.StaticText(parent, label='{} Date'.format(stype.capitalize())),
            flag=wx.ALIGN_CENTER_VERTICAL)
        stack_grid_sizer.Add(wx.StaticText(parent, label='{} Time'.format(stype.capitalize())),
            flag=wx.ALIGN_CENTER_VERTICAL)

        for i in range(10, 0, -1):
            num = epics.wx.PVText(parent, self.pvs['{}{}_num'.format(stype.lower(), i)])
            year = epics.wx.PVText(parent, self.pvs['{}{}_year'.format(stype.lower(), i)])
            month = epics.wx.PVText(parent, self.pvs['{}{}_month'.format(stype.lower(), i)])
            day = epics.wx.PVText(parent, self.pvs['{}{}_day'.format(stype.lower(), i)])
            hour = epics.wx.PVText(parent, self.pvs['{}{}_hour'.format(stype.lower(), i)])
            mi = epics.wx.PVText(parent, self.pvs['{}{}_mi'.format(stype.lower(), i)])
            sec = epics.wx.PVText(parent, self.pvs['{}{}_sec'.format(stype.lower(), i)])

            date_sizer = wx.BoxSizer(wx.HORIZONTAL)
            date_sizer.Add(year, flag=wx.ALIGN_CENTER_VERTICAL)
            date_sizer.Add(wx.StaticText(parent, label='/'),
                flag=wx.ALIGN_CENTER_VERTICAL)
            date_sizer.Add(month, flag=wx.ALIGN_CENTER_VERTICAL)
            date_sizer.Add(wx.StaticText(parent, label='/'),
                flag=wx.ALIGN_CENTER_VERTICAL)
            date_sizer.Add(day, flag=wx.ALIGN_CENTER_VERTICAL)

            time_sizer = wx.BoxSizer(wx.HORIZONTAL)
            time_sizer.Add(hour, flag=wx.ALIGN_CENTER_VERTICAL)
            time_sizer.Add(wx.StaticText(parent, label=':'),
                flag=wx.ALIGN_CENTER_VERTICAL)
            time_sizer.Add(mi, flag=wx.ALIGN_CENTER_VERTICAL)
            time_sizer.Add(wx.StaticText(parent, label=':'),
                flag=wx.ALIGN_CENTER_VERTICAL)
            time_sizer.Add(sec, flag=wx.ALIGN_CENTER_VERTICAL)

            stack_grid_sizer.Add(num, flag=wx.ALIGN_CENTER_VERTICAL)
            stack_grid_sizer.Add(date_sizer, flag=wx.ALIGN_CENTER_VERTICAL)
            stack_grid_sizer.Add(time_sizer, flag=wx.ALIGN_CENTER_VERTICAL)

        fault_sizer = wx.StaticBoxSizer(fault_box, wx.VERTICAL)
        fault_sizer.Add(stack_grid_sizer)

        return fault_sizer

    def make_pv_datetime(self, parent):

        year = epics.wx.PVText(parent, self.pvs['plc_year'])
        month = epics.wx.PVText(parent, self.pvs['plc_month'])
        day = epics.wx.PVText(parent, self.pvs['plc_day'])
        hour = epics.wx.PVText(parent, self.pvs['plc_hour'])
        mi = epics.wx.PVText(parent, self.pvs['plc_mi'])
        sec = epics.wx.PVText(parent, self.pvs['plc_sec'])

        date_sizer = wx.BoxSizer(wx.HORIZONTAL)
        date_sizer.Add(year, flag=wx.ALIGN_CENTER_VERTICAL)
        date_sizer.Add(wx.StaticText(parent, label='/'),
            flag=wx.ALIGN_CENTER_VERTICAL)
        date_sizer.Add(month, flag=wx.ALIGN_CENTER_VERTICAL)
        date_sizer.Add(wx.StaticText(parent, label='/'),
            flag=wx.ALIGN_CENTER_VERTICAL)
        date_sizer.Add(day, flag=wx.ALIGN_CENTER_VERTICAL|wx.RIGHT, border=10)

        date_sizer.Add(hour, flag=wx.ALIGN_CENTER_VERTICAL)
        date_sizer.Add(wx.StaticText(parent, label=':'),
            flag=wx.ALIGN_CENTER_VERTICAL)
        date_sizer.Add(mi, flag=wx.ALIGN_CENTER_VERTICAL)
        date_sizer.Add(wx.StaticText(parent, label=':'),
            flag=wx.ALIGN_CENTER_VERTICAL)
        date_sizer.Add(sec, flag=wx.ALIGN_CENTER_VERTICAL)

        top_sizer = wx.BoxSizer(wx.VERTICAL)
        top_sizer.Add(wx.StaticText(parent, label='Current PLC time:'),
            flag=wx.BOTTOM, border=5)
        top_sizer.Add(date_sizer)

        return top_sizer



class APSPanel(wx.Panel):
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

        self._create_layout()

        self._initialize()


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
        aps_expected_status = epics.wx.PVText(aps_box, self.pvs['aps_nominal'])
        beam_current = epics.wx.PVText(aps_box, self.pvs['current'],
            auto_units=True, fg='forest green')
        shutter_permit = epics.wx.PVText(aps_box, self.pvs['aps_shutter_permit'],
            fg='forest green')
        self.aps_msg = wx.StaticText(aps_box)
        self.aps_msg.Wrap(60)
        next_update = epics.wx.PVText(aps_box, self.pvs['aps_update_msg'])

        aps_sub_sizer1 = wx.FlexGridSizer(cols=2, vgap=5, hgap=5)
        aps_sub_sizer1.Add(wx.StaticText(aps_box, label='Beam current:'),
            flag=wx.ALIGN_CENTER_VERTICAL)
        aps_sub_sizer1.Add(beam_current, flag=wx.ALIGN_CENTER_VERTICAL)
        aps_sub_sizer1.Add(wx.StaticText(aps_box, label='Current status:'),
            flag=wx.ALIGN_CENTER_VERTICAL)
        aps_sub_sizer1.Add(aps_status, flag=wx.ALIGN_CENTER_VERTICAL)
        aps_sub_sizer1.Add(wx.StaticText(aps_box, label='APS Mode:'),
            flag=wx.ALIGN_CENTER_VERTICAL)
        aps_sub_sizer1.Add(aps_expected_status, flag=wx.ALIGN_CENTER_VERTICAL)
        aps_sub_sizer1.Add(wx.StaticText(aps_box, label='Shutter permit:'),
            flag=wx.ALIGN_CENTER_VERTICAL)
        aps_sub_sizer1.Add(shutter_permit, flag=wx.ALIGN_CENTER_VERTICAL)
        aps_sub_sizer1.Add(wx.StaticText(aps_box, label='Operator msg.:'),
            flag=wx.ALIGN_CENTER_VERTICAL)
        aps_sub_sizer1.Add(self.aps_msg, flag=wx.ALIGN_CENTER_VERTICAL)
        aps_sub_sizer1.Add(wx.StaticText(aps_box, label='Next update:'))
        aps_sub_sizer1.Add(next_update, flag=wx.ALIGN_CENTER_VERTICAL)

        aps_sub_sizer2 = wx.BoxSizer(wx.VERTICAL)
        aps_sub_sizer2.Add(self._make_beam_current_plot(aps_box),
            proportion=1, flag=wx.EXPAND)

        aps_sizer = wx.StaticBoxSizer(aps_box, wx.HORIZONTAL)
        aps_sizer.Add(aps_sub_sizer1, flag=wx.ALL, border=5)
        aps_sizer.Add(aps_sub_sizer2, proportion=1, flag=wx.ALL|wx.EXPAND,
            border=5)

        top_sizer = wx.BoxSizer(wx.HORIZONTAL)
        top_sizer.Add(aps_sizer, proportion=1, flag=wx.ALL, border=5)
        top_sizer.Add(self._make_bpm_sizer(self), flag=wx.TOP|wx.BOTTOM|wx.RIGHT,
            border=5)

        self.SetSizer(top_sizer)

    def _initialize(self):
        self.msg_pvs = [self.pvs['aps_msg1'], self.pvs['aps_msg2'],
            self.pvs['aps_msg3']]

        self.msg_pvs[0].add_callback(self._aps_msg_callback)

        self.history_pvs = [self.pvs['aps_bc_time'], self.pvs['aps_bc_current']]
        self.history_pvs[1].add_callback(self._beam_current_plot_callback)

        self._aps_msg_callback()

    def _aps_msg_callback(self, **kwargs):
        msg = ' '.join(pv.get() for pv in self.msg_pvs)

        self.aps_msg.SetLabel(msg)
        self.Layout()

    def _make_beam_current_plot(self, parent):
        top_panel = wx.Panel(parent)
        top_panel.SetSizeHints((100, 100), (600, 350))
        self.fig = Figure((5,4), 75)

        self.bc_hist_plot = self.fig.add_subplot(1,1,1)
        self.bc_hist_plot.set_xlabel('Time relative to now [h]')
        self.bc_hist_plot.set_ylabel('Current [mA]')

        y_vals = self.pvs['aps_bc_current'].get()
        # self.bc_hist_line = self.bc_hist_plot.plot(self.pvs['aps_bc_time'].get(),
        #     y_vals)
        self.bc_hist_plot.fill_between(self.pvs['aps_bc_time'].get(), 0,
            y_vals)
        self.bc_hist_plot.set_ylim(min(min(y_vals)*0.98, 95), max(y_vals)*1.002)
        self.bc_hist_plot.set_xlim(-24, 0)

        self.fig.subplots_adjust(left = 0.08, bottom = 0.28, right = 0.99, top = 0.99)
        self.fig.set_facecolor('white')

        self.canvas = FigureCanvasWxAgg(top_panel, wx.ID_ANY, self.fig)
        self.canvas.SetBackgroundColour('white')

        plot_sizer = wx.BoxSizer(wx.VERTICAL)
        plot_sizer.Add(self.canvas, 1, wx.EXPAND)

        top_panel.SetSizer(plot_sizer)

        return top_panel

    def _beam_current_plot_callback(self, **kwargs):
        x_vals = self.history_pvs[0].get()
        y_vals = kwargs['value']
        # self.bc_hist_line.set_xdata(x_vals)
        # self.bc_hist_line.set_ydata(y_vals)
        self.canvas.GetParent().Freeze()
        self.bc_hist_plot.clear()
        self.bc_hist_plot.set_xlabel('Time relative to now [h]')
        self.bc_hist_plot.set_ylabel('Current [mA]')
        self.bc_hist_plot.fill_between(x_vals, 0, y_vals)
        self.bc_hist_plot.set_xlim(-24, 0)
        self.bc_hist_plot.set_ylim(min(min(y_vals)*0.98, 95), max(y_vals)*1.002)
        self.canvas.GetParent().Thaw()

        self.canvas.draw()

    def _make_bpm_sizer(self, parent):
        bpm_box = wx.StaticBox(parent, label='APS BPMS')
        rf_bpm_box = wx.StaticBox(bpm_box, label='RF BPMS')
        x_bpm_box = wx.StaticBox(bpm_box, label='X-ray BPMS')

        rf_bpm_18b_p0_x = epics.wx.PVText(rf_bpm_box, self.pvs['rf_bpm_18b_p0_x'],
            fg='forest green')
        rf_bpm_18b_p0_y = epics.wx.PVText(rf_bpm_box, self.pvs['rf_bpm_18b_p0_y'],
            fg='forest green')
        rf_bpm_18b_p1_x = epics.wx.PVText(rf_bpm_box, self.pvs['rf_bpm_18b_p1_x'],
            fg='forest green')
        rf_bpm_18b_p1_y = epics.wx.PVText(rf_bpm_box, self.pvs['rf_bpm_18b_p1_y'],
            fg='forest green')
        rf_bpm_19a_p0_x = epics.wx.PVText(rf_bpm_box, self.pvs['rf_bpm_19a_p0_x'],
            fg='forest green')
        rf_bpm_19a_p0_y = epics.wx.PVText(rf_bpm_box, self.pvs['rf_bpm_19a_p0_y'],
            fg='forest green')
        rf_bpm_19a_p1_x = epics.wx.PVText(rf_bpm_box, self.pvs['rf_bpm_19a_p1_x'],
            fg='forest green')
        rf_bpm_19a_p1_y = epics.wx.PVText(rf_bpm_box, self.pvs['rf_bpm_19a_p1_y'],
            fg='forest green')

        x_bpm_p1_x = epics.wx.PVText(x_bpm_box, self.pvs['x_bpm_p1_x'],
            fg='forest green')
        x_bpm_p1_y = epics.wx.PVText(x_bpm_box, self.pvs['x_bpm_p1_y'],
            fg='forest green')
        x_bpm_p2_x = epics.wx.PVText(x_bpm_box, self.pvs['x_bpm_p2_x'],
            fg='forest green')
        x_bpm_p2_y = epics.wx.PVText(x_bpm_box, self.pvs['x_bpm_p2_y'],
            fg='forest green')


        rf_layout = wx.FlexGridSizer(cols=4, vgap=5, hgap=5)
        rf_layout.Add(wx.StaticText(rf_bpm_box, label='18B P0 X:'),
            flag=wx.ALIGN_CENTER_VERTICAL)
        rf_layout.Add(rf_bpm_18b_p0_x, flag=wx.ALIGN_CENTER_VERTICAL)
        rf_layout.Add(wx.StaticText(rf_bpm_box, label='18B P0 Y:'),
            flag=wx.ALIGN_CENTER_VERTICAL)
        rf_layout.Add(rf_bpm_18b_p0_y, flag=wx.ALIGN_CENTER_VERTICAL)
        rf_layout.Add(wx.StaticText(rf_bpm_box, label='18B P1 X:'),
            flag=wx.ALIGN_CENTER_VERTICAL)
        rf_layout.Add(rf_bpm_18b_p1_x, flag=wx.ALIGN_CENTER_VERTICAL)
        rf_layout.Add(wx.StaticText(rf_bpm_box, label='18B P1 Y:'),
            flag=wx.ALIGN_CENTER_VERTICAL)
        rf_layout.Add(rf_bpm_18b_p1_y, flag=wx.ALIGN_CENTER_VERTICAL)
        rf_layout.Add(wx.StaticText(rf_bpm_box, label='19A P0 X:'),
            flag=wx.ALIGN_CENTER_VERTICAL)
        rf_layout.Add(rf_bpm_19a_p0_x, flag=wx.ALIGN_CENTER_VERTICAL)
        rf_layout.Add(wx.StaticText(rf_bpm_box, label='19A P0 Y:'),
            flag=wx.ALIGN_CENTER_VERTICAL)
        rf_layout.Add(rf_bpm_19a_p0_y, flag=wx.ALIGN_CENTER_VERTICAL)
        rf_layout.Add(wx.StaticText(rf_bpm_box, label='19A P1 X:'),
            flag=wx.ALIGN_CENTER_VERTICAL)
        rf_layout.Add(rf_bpm_19a_p1_x, flag=wx.ALIGN_CENTER_VERTICAL)
        rf_layout.Add(wx.StaticText(rf_bpm_box, label='19A P1 Y:'),
            flag=wx.ALIGN_CENTER_VERTICAL)
        rf_layout.Add(rf_bpm_19a_p1_y, flag=wx.ALIGN_CENTER_VERTICAL)

        rf_sizer = wx.StaticBoxSizer(rf_bpm_box, wx.VERTICAL)
        rf_sizer.Add(rf_layout, flag=wx.ALL|wx.EXPAND, border=5)

        x_layout = wx.FlexGridSizer(cols=4, vgap=5, hgap=5)
        x_layout.Add(wx.StaticText(x_bpm_box, label='XBPM P1 X:'),
            flag=wx.ALIGN_CENTER_HORIZONTAL)
        x_layout.Add(x_bpm_p1_x, flag=wx.ALIGN_CENTER_VERTICAL)
        x_layout.Add(wx.StaticText(x_bpm_box, label='XBPM P1 Y:'),
            flag=wx.ALIGN_CENTER_HORIZONTAL)
        x_layout.Add(x_bpm_p1_y, flag=wx.ALIGN_CENTER_VERTICAL)
        x_layout.Add(wx.StaticText(x_bpm_box, label='XBPM P2 X:'),
            flag=wx.ALIGN_CENTER_HORIZONTAL)
        x_layout.Add(x_bpm_p2_x, flag=wx.ALIGN_CENTER_VERTICAL)
        x_layout.Add(wx.StaticText(x_bpm_box, label='XBPM P2 Y:'),
            flag=wx.ALIGN_CENTER_HORIZONTAL)
        x_layout.Add(x_bpm_p2_y, flag=wx.ALIGN_CENTER_VERTICAL)

        x_sizer = wx.StaticBoxSizer(x_bpm_box, wx.VERTICAL)
        x_sizer.Add(x_layout, flag=wx.ALL|wx.EXPAND, border=5)

        bpm_layout = wx.StaticBoxSizer(bpm_box, wx.HORIZONTAL)
        bpm_layout.Add(rf_sizer, flag=wx.ALL, border=5)
        bpm_layout.Add(x_sizer, flag=wx.RIGHT|wx.TOP|wx.BOTTOM, border=5)

        return bpm_layout




class StationPanel(wx.ScrolledWindow):
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
        wx.ScrolledWindow.__init__(self, parent,
            style=wx.VSCROLL|wx.HSCROLL)
        self.SetScrollRate(20,20)

        self.pvs = pvs

        self._create_layout()

        self._initialize()


    def _create_layout(self):
        """
        Creates the layout for the panel.

        """
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

        undulator_sizer = self._make_undulator_sizer(self)

        temp_sizer = self._make_temp_sizer(self)


        pss_box = wx.StaticBox(self, label='PSS Status')
        fsize = self.GetFont().Larger().GetPointSize()
        font = wx.Font(fsize, wx.DEFAULT, wx.NORMAL, wx.BOLD)
        pss_box.SetOwnFont(font)

        pss_sizer = wx.StaticBoxSizer(pss_box, wx.HORIZONTAL)
        pss_sizer.Add(self.make_pss_sizer(pss_box, 'D'), flag=wx.ALL, border=5)
        pss_sizer.Add(self.make_pss_sizer(pss_box, 'C'),
            flag=wx.TOP|wx.BOTTOM|wx.RIGHT, border=5)
        pss_sizer.Add(self.make_pss_sizer(pss_box, 'A'),
            flag=wx.TOP|wx.BOTTOM|wx.RIGHT, border=5)

        row1_sizer = wx.BoxSizer(wx.HORIZONTAL)
        row1_sizer.Add(station_sizer, flag=wx.ALL|wx.EXPAND, border=5)
        row1_sizer.Add(undulator_sizer,
            flag=wx.TOP|wx.BOTTOM|wx.RIGHT|wx.EXPAND, border=5)
        row1_sizer.Add(temp_sizer, flag=wx.TOP|wx.BOTTOM|wx.RIGHT, border=5)

        top_sizer = wx.BoxSizer(wx.VERTICAL)
        top_sizer.Add(row1_sizer)
        top_sizer.Add(pss_sizer)

        self.SetSizer(top_sizer)

    def _initialize(self):
        pass

    def _make_undulator_sizer(self, parent):
        u_box = wx.StaticBox(parent, label='Undulator Status')
        fsize = self.GetFont().Larger().GetPointSize()
        font = wx.Font(fsize, wx.DEFAULT, wx.NORMAL, wx.BOLD)
        u_box.SetOwnFont(font)

        gap = custom_epics_widgets.PVTextMonitor(u_box, self.pvs['u_gap'],
            auto_units=True, monitor_pv=self.pvs['u_target_gap'],
            monitor_threshold=0.002, fg='forest green')
        energy = custom_epics_widgets.PVTextMonitor(u_box, self.pvs['u_energy'],
            auto_units=True, monitor_pv=self.pvs['u_target_energy'],
            monitor_threshold=0.002, fg='forest green')
        target_gap = epics.wx.PVText(u_box, self.pvs['u_target_gap'],
            auto_units=True)
        target_energy = epics.wx.PVText(u_box, self.pvs['u_target_energy'],
            auto_units=True)
        start = custom_epics_widgets.PVButton2(u_box, self.pvs['u_start'],
            label='Move to Target')

        u_layout = wx.FlexGridSizer(cols=4, vgap=10, hgap=5)
        u_layout.Add(wx.StaticText(u_box, label='Actual Undulator Energy:'),
            flag=wx.ALIGN_CENTER_VERTICAL)
        u_layout.Add(energy, flag=wx.ALIGN_CENTER_VERTICAL)
        u_layout.Add(wx.StaticText(u_box, label='Target Undulator Energy:'),
            flag=wx.ALIGN_CENTER_VERTICAL)
        u_layout.Add(target_energy, flag=wx.ALIGN_CENTER_VERTICAL)
        u_layout.Add(wx.StaticText(u_box, label='Actual Undulator Gap:'),
            flag=wx.ALIGN_CENTER_VERTICAL)
        u_layout.Add(gap, flag=wx.ALIGN_CENTER_VERTICAL)
        u_layout.Add(wx.StaticText(u_box, label='Target Undulator Gap:'),
            flag=wx.ALIGN_CENTER_VERTICAL)
        u_layout.Add(target_gap, flag=wx.ALIGN_CENTER_VERTICAL)

        u_sizer = wx.StaticBoxSizer(u_box, wx.VERTICAL)
        u_sizer.Add(u_layout, flag=wx.EXPAND|wx.ALL, border=5)
        u_sizer.Add(start,
            flag=wx.ALIGN_CENTER_HORIZONTAL|wx.BOTTOM|wx.LEFT|wx.RIGHT,
            border=5)
        u_sizer.AddStretchSpacer(1)

        return u_sizer

    def _make_temp_sizer(self, parent):
        temp_box = wx.StaticBox(parent, label='Temperatures')
        fsize = self.GetFont().Larger().GetPointSize()
        font = wx.Font(fsize, wx.DEFAULT, wx.NORMAL, wx.BOLD)
        temp_box.SetOwnFont(font)

        mono1_box = wx.StaticBox(temp_box, label='Mono 1')
        fsize = self.GetFont().GetPointSize()
        font = wx.Font(fsize, wx.DEFAULT, wx.NORMAL, wx.BOLD)
        mono1_box.SetOwnFont(font)

        mono1_ib = epics.wx.PVText(mono1_box, self.pvs['T3_temp'],
            auto_units=True)
        mono1_ob = epics.wx.PVText(mono1_box, self.pvs['T4_temp'],
            auto_units=True)
        mono1_bot = epics.wx.PVText(mono1_box, self.pvs['T5_temp'],
            auto_units=True)
        mono1_cb = epics.wx.PVText(mono1_box, self.pvs['T5_temp'],
            auto_units=True)
        mono1_2xtal = epics.wx.PVText(mono1_box, self.pvs['T8_temp'],
            auto_units=True)

        mono1_layout = wx.FlexGridSizer(cols=2, hgap=5, vgap=5)
        mono1_layout.Add(wx.StaticText(mono1_box, label='Compton IB:'),
            flag=wx.ALIGN_CENTER_VERTICAL)
        mono1_layout.Add(mono1_ib, flag=wx.ALIGN_CENTER_VERTICAL)
        mono1_layout.Add(wx.StaticText(mono1_box, label='Compton OB:'),
            flag=wx.ALIGN_CENTER_VERTICAL)
        mono1_layout.Add(mono1_ob, flag=wx.ALIGN_CENTER_VERTICAL)
        mono1_layout.Add(wx.StaticText(mono1_box, label='Compton Bot.:'),
            flag=wx.ALIGN_CENTER_VERTICAL)
        mono1_layout.Add(mono1_bot, flag=wx.ALIGN_CENTER_VERTICAL)
        mono1_layout.Add(wx.StaticText(mono1_box, label='2nd Xtal Shield:'),
            flag=wx.ALIGN_CENTER_VERTICAL)
        mono1_layout.Add(mono1_2xtal, flag=wx.ALIGN_CENTER_VERTICAL)
        mono1_layout.Add(wx.StaticText(mono1_box, label='Copper Block:'),
            flag=wx.ALIGN_CENTER_VERTICAL)
        mono1_layout.Add(mono1_cb, flag=wx.ALIGN_CENTER_VERTICAL)

        mono1_sizer = wx.StaticBoxSizer(mono1_box, wx.VERTICAL)
        mono1_sizer.Add(mono1_layout, flag=wx.EXPAND|wx.ALL, border=5)

        mono2_box = wx.StaticBox(temp_box, label='Mono 2')
        fsize = self.GetFont().GetPointSize()
        font = wx.Font(fsize, wx.DEFAULT, wx.NORMAL, wx.BOLD)
        mono2_box.SetOwnFont(font)

        mono2_ib = epics.wx.PVText(mono2_box, self.pvs['T11_temp'],
            auto_units=True)
        mono2_ob = epics.wx.PVText(mono2_box, self.pvs['T12_temp'],
            auto_units=True)
        mono2_bot = epics.wx.PVText(mono2_box, self.pvs['T13_temp'],
            auto_units=True)
        mono2_cb = epics.wx.PVText(mono2_box, self.pvs['T14_temp'],
            auto_units=True)
        mono2_2xtal = epics.wx.PVText(mono2_box, self.pvs['T16_temp'],
            auto_units=True)

        mono2_layout = wx.FlexGridSizer(cols=2, hgap=5, vgap=5)
        mono2_layout.Add(wx.StaticText(mono2_box, label='Compton IB:'),
            flag=wx.ALIGN_CENTER_VERTICAL)
        mono2_layout.Add(mono2_ib, flag=wx.ALIGN_CENTER_VERTICAL)
        mono2_layout.Add(wx.StaticText(mono2_box, label='Compton OB:'),
            flag=wx.ALIGN_CENTER_VERTICAL)
        mono2_layout.Add(mono2_ob, flag=wx.ALIGN_CENTER_VERTICAL)
        mono2_layout.Add(wx.StaticText(mono2_box, label='Compton Bot.:'),
            flag=wx.ALIGN_CENTER_VERTICAL)
        mono2_layout.Add(mono2_bot, flag=wx.ALIGN_CENTER_VERTICAL)
        mono2_layout.Add(wx.StaticText(mono2_box, label='2nd Xtal Shield:'),
            flag=wx.ALIGN_CENTER_VERTICAL)
        mono2_layout.Add(mono2_2xtal, flag=wx.ALIGN_CENTER_VERTICAL)
        mono2_layout.Add(wx.StaticText(mono2_box, label='Copper Block:'),
            flag=wx.ALIGN_CENTER_VERTICAL)
        mono2_layout.Add(mono2_cb, flag=wx.ALIGN_CENTER_VERTICAL)

        mono2_sizer = wx.StaticBoxSizer(mono2_box, wx.VERTICAL)
        mono2_sizer.Add(mono2_layout, flag=wx.EXPAND|wx.ALL, border=5)

        temp_sizer = wx.StaticBoxSizer(temp_box, wx.HORIZONTAL)
        temp_sizer.Add(mono1_sizer, flag=wx.ALL|wx.EXPAND, border=5)
        temp_sizer.Add(mono2_sizer, flag=wx.TOP|wx.BOTTOM|wx.RIGHT|wx.EXPAND,
            border=5)

        return temp_sizer

    def make_pss_sizer(self, parent, station):
        pss_box = wx.StaticBox(self, label='PSS {} Status'.format(station))
        fsize = self.GetFont().GetPointSize()
        font = wx.Font(fsize, wx.DEFAULT, wx.NORMAL, wx.BOLD)
        pss_box.SetOwnFont(font)

        door_1 = custom_epics_widgets.PVTextLabeled(pss_box,
            self.pvs['{}_door_1'.format(station)], fg='forest green')
        user_key = epics.wx.PVText(pss_box,
            self.pvs['{}_user_key'.format(station)], fg='forest green')
        aps_key_a = epics.wx.PVText(pss_box,
            self.pvs['{}_aps_key_a'.format(station)], fg='forest green')
        searched_a = epics.wx.PVText(pss_box,
            self.pvs['{}_searched_a'.format(station)], fg='forest green')
        beam_ready = epics.wx.PVText(pss_box,
            self.pvs['{}_beam_ready'.format(station)], fg='forest green')
        beam_active = epics.wx.PVText(pss_box,
            self.pvs['{}_beam_active'.format(station)], fg='forest green')
        crash_1 = custom_epics_widgets.PVTextLabeled(pss_box,
            self.pvs['{}_crash_1'.format(station)], fg='forest green')

        door_1.SetTranslations({'ON': 'Closed', 'OFF': 'Open'})
        crash_1.SetTranslations({'OFF': 'Active', 'ON': 'Clear'})

        if station != 'A':
            door_2 = custom_epics_widgets.PVTextLabeled(pss_box,
                self.pvs['{}_door_2'.format(station)], fg='forest green')
            crash_2 = custom_epics_widgets.PVTextLabeled(pss_box,
            self.pvs['{}_crash_2'.format(station)], fg='forest green')

            door_2.SetTranslations({'ON': 'Closed', 'OFF': 'Open'})
            crash_2.SetTranslations({'OFF': 'Active', 'ON': 'Clear'})

        if station == 'D':
            door_3 = custom_epics_widgets.PVTextLabeled(pss_box,
                self.pvs['{}_door_3'.format(station)], fg='forest green')
            door_4 = custom_epics_widgets.PVTextLabeled(pss_box,
                self.pvs['{}_door_4'.format(station)], fg='forest green')
            crash_3 = custom_epics_widgets.PVTextLabeled(pss_box,
                self.pvs['{}_crash_3'.format(station)], fg='forest green')

            door_3.SetTranslations({'ON': 'Closed', 'OFF': 'Open'})
            door_4.SetTranslations({'ON': 'Closed', 'OFF': 'Open'})
            crash_3.SetTranslations({'OFF': 'Active', 'ON': 'Clear'})

        pss_layout = wx.FlexGridSizer(cols=2, hgap=5, vgap=5)
        pss_layout.Add(wx.StaticText(pss_box, label='Door 1:'.format(station)),
            flag=wx.ALIGN_CENTER_VERTICAL)
        pss_layout.Add(door_1)

        if station != 'A':
            pss_layout.Add(wx.StaticText(pss_box, label='Door 2:'.format(station)),
                flag=wx.ALIGN_CENTER_VERTICAL)
            pss_layout.Add(door_2)

        if station == 'D':
            pss_layout.Add(wx.StaticText(pss_box, label='Door 3:'.format(station)),
                flag=wx.ALIGN_CENTER_VERTICAL)
            pss_layout.Add(door_3)
            pss_layout.Add(wx.StaticText(pss_box, label='Door 4:'.format(station)),
                flag=wx.ALIGN_CENTER_VERTICAL)
            pss_layout.Add(door_4)

        pss_layout.Add(wx.StaticText(pss_box, label='User Key:'.format(station)),
            flag=wx.ALIGN_CENTER_VERTICAL)
        pss_layout.Add(user_key)
        pss_layout.Add(wx.StaticText(pss_box, label='APS Key:'.format(station)),
            flag=wx.ALIGN_CENTER_VERTICAL)
        pss_layout.Add(aps_key_a)
        pss_layout.Add(wx.StaticText(pss_box, label='Searched:'.format(station)),
            flag=wx.ALIGN_CENTER_VERTICAL)
        pss_layout.Add(searched_a)
        pss_layout.Add(wx.StaticText(pss_box, label='Beam Ready:'.format(station)),
            flag=wx.ALIGN_CENTER_VERTICAL)
        pss_layout.Add(beam_ready)
        pss_layout.Add(wx.StaticText(pss_box, label='Beam Active:'.format(station)),
            flag=wx.ALIGN_CENTER_VERTICAL)
        pss_layout.Add(beam_active)
        pss_layout.Add(wx.StaticText(pss_box, label='Crash Btn. 1:'.format(station)),
            flag=wx.ALIGN_CENTER_VERTICAL)
        pss_layout.Add(crash_1)

        if station != 'A':
            pss_layout.Add(wx.StaticText(pss_box, label='Crash Btn. 2:'.format(station)),
                flag=wx.ALIGN_CENTER_VERTICAL)
            pss_layout.Add(crash_2)

        if station == 'D':
            pss_layout.Add(wx.StaticText(pss_box, label='Crash Btn. 3:'.format(station)),
                flag=wx.ALIGN_CENTER_VERTICAL)
            pss_layout.Add(crash_3)

        pss_sizer = wx.StaticBoxSizer(pss_box, wx.VERTICAL)
        pss_sizer.Add(pss_layout, flag=wx.EXPAND|wx.ALL, border=5)

        return pss_sizer

class ExpPanel(wx.Panel):
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

        self._create_layout()

        self._initialize()


    def _create_layout(self):
        """
        Creates the layout for the panel.

        """

        vac_sizer = self._make_vacuum_sizer(self)
        shutter_sizer = self._make_shutter_sizer(self)
        atten_sizer = self._make_attenuator_sizer(self)

        top_sizer = wx.BoxSizer(wx.HORIZONTAL)
        top_sizer.Add(vac_sizer, flag=wx.ALL, border=5)
        top_sizer.Add(shutter_sizer, flag=wx.TOP|wx.RIGHT|wx.BOTTOM, border=5)
        top_sizer.Add(atten_sizer, flag=wx.TOP|wx.RIGHT|wx.BOTTOM, border=5)

        self.SetSizer(top_sizer)

    def _initialize(self):
        self.pvs['atten_1'].add_callback(self._atten_calc)
        self.pvs['atten_2'].add_callback(self._atten_calc)
        self.pvs['atten_4'].add_callback(self._atten_calc)
        self.pvs['atten_8'].add_callback(self._atten_calc)
        self.pvs['atten_16'].add_callback(self._atten_calc)
        self.pvs['atten_32'].add_callback(self._atten_calc)

        self._atten_calc()

    def _make_vacuum_sizer(self, parent):
        vac_box = wx.StaticBox(parent, label='Vacuum')
        fsize = self.GetFont().Larger().GetPointSize()
        font = wx.Font(fsize, wx.DEFAULT, wx.NORMAL, wx.BOLD)
        vac_box.SetOwnFont(font)

        col_vac = custom_epics_widgets.PVTextLabeled(vac_box,
            self.pvs['col_vac'], scale=1000, do_round=True)
        guard_vac = custom_epics_widgets.PVTextLabeled(vac_box,
            self.pvs['guard_vac'], scale=1000, do_round=True)
        scatter_vac = custom_epics_widgets.PVTextLabeled(vac_box,
            self.pvs['scatter_vac'], scale=1000, do_round=True)
        sample_vac = custom_epics_widgets.PVTextLabeled(vac_box,
            self.pvs['sample_vac'], scale=1000, do_round=True)
        vs1_vac = custom_epics_widgets.PVTextLabeled(vac_box,
            self.pvs['vs1_vac'], scale=1000, do_round=True)
        vs2_vac = custom_epics_widgets.PVTextLabeled(vac_box,
            self.pvs['vs2_vac'], scale=1000, do_round=True)

        vac_layout = wx.FlexGridSizer(cols=2, hgap=5, vgap=5)
        vac_layout.Add(wx.StaticText(vac_box, label='Col. Vac. [mTorr]:'),
            flag=wx.ALIGN_CENTER_VERTICAL)
        vac_layout.Add(col_vac, flag=wx.ALIGN_CENTER_VERTICAL)
        vac_layout.Add(wx.StaticText(vac_box, label='Guard Vac. [mTorr]:'),
            flag=wx.ALIGN_CENTER_VERTICAL)
        vac_layout.Add(guard_vac, flag=wx.ALIGN_CENTER_VERTICAL)
        vac_layout.Add(wx.StaticText(vac_box, label='Sample Vac. [mTorr]:'),
            flag=wx.ALIGN_CENTER_VERTICAL)
        vac_layout.Add(sample_vac, flag=wx.ALIGN_CENTER_VERTICAL)
        vac_layout.Add(wx.StaticText(vac_box, label='S.C. Vac. [mTorr]:'),
            flag=wx.ALIGN_CENTER_VERTICAL)
        vac_layout.Add(scatter_vac, flag=wx.ALIGN_CENTER_VERTICAL)
        vac_layout.Add(wx.StaticText(vac_box, label='Vac Sec. 1 [mTorr]:'),
            flag=wx.ALIGN_CENTER_VERTICAL)
        vac_layout.Add(vs1_vac, flag=wx.ALIGN_CENTER_VERTICAL)
        vac_layout.Add(wx.StaticText(vac_box, label='Vac Sec. 2 [mTorr]:'),
            flag=wx.ALIGN_CENTER_VERTICAL)
        vac_layout.Add(vs2_vac, flag=wx.ALIGN_CENTER_VERTICAL)

        vac_sizer = wx.StaticBoxSizer(vac_box, wx.VERTICAL)
        vac_sizer.Add(vac_layout, flag=wx.ALL|wx.EXPAND, border=5)

        return vac_sizer

    def _make_shutter_sizer(self, parent):
        shutter_box = wx.StaticBox(parent, label='Shutters and Intensity')
        fsize = self.GetFont().Larger().GetPointSize()
        font = wx.Font(fsize, wx.DEFAULT, wx.NORMAL, wx.BOLD)
        shutter_box.SetOwnFont(font)

        slow_shtr1 = custom_epics_widgets.PVTextLabeled(shutter_box,
            self.pvs['exp_slow_shtr1'], fg='forest green')
        slow_shtr2 = custom_epics_widgets.PVTextLabeled(shutter_box,
            self.pvs['exp_slow_shtr2'], fg='forest green')
        fast_shtr = custom_epics_widgets.PVTextLabeled(shutter_box,
            self.pvs['exp_fast_shtr'], fg='forest green')

        slow_shtr1.SetTranslations({'On': 'Open', 'Off': 'Closed'})
        slow_shtr2.SetTranslations({'Off': 'Open', 'On': 'Closed'})
        fast_shtr.SetTranslations({'On': 'Open', 'Off': 'Closed'})

        slow_shtr1.SetForegroundColourTranslations({'Open': 'forest green', 'Closed': 'red'})
        slow_shtr2.SetForegroundColourTranslations({'Open': 'forest green', 'Closed': 'red'})
        fast_shtr.SetForegroundColourTranslations({'Open': 'forest green', 'Closed': 'red'})

        i0 = custom_epics_widgets.PVTextLabeled(shutter_box,
            self.pvs['i0'], do_round=True, sig_fig=2)
        i1 = custom_epics_widgets.PVTextLabeled(shutter_box,
            self.pvs['i1'], do_round=True, sig_fig=2)

        shutter_layout = wx.FlexGridSizer(cols=2, hgap=5, vgap=5)
        shutter_layout.Add(wx.StaticText(shutter_box, label='Slow shutter 1:'),
            flag=wx.ALIGN_CENTER_VERTICAL)
        shutter_layout.Add(slow_shtr1, flag=wx.ALIGN_CENTER_VERTICAL)
        shutter_layout.Add(wx.StaticText(shutter_box, label='Slow shutter 2:'),
            flag=wx.ALIGN_CENTER_VERTICAL)
        shutter_layout.Add(slow_shtr2, flag=wx.ALIGN_CENTER_VERTICAL)
        shutter_layout.Add(wx.StaticText(shutter_box, label='Fast shutter:'),
            flag=wx.ALIGN_CENTER_VERTICAL)
        shutter_layout.Add(fast_shtr, flag=wx.ALIGN_CENTER_VERTICAL)
        shutter_layout.Add(wx.StaticText(shutter_box, label='I0 [V]:'),
            flag=wx.ALIGN_CENTER_VERTICAL)
        shutter_layout.Add(i0, flag=wx.ALIGN_CENTER_VERTICAL)
        shutter_layout.Add(wx.StaticText(shutter_box, label='I1 [V]:'),
            flag=wx.ALIGN_CENTER_VERTICAL)
        shutter_layout.Add(i1, flag=wx.ALIGN_CENTER_VERTICAL)

        shutter_sizer = wx.StaticBoxSizer(shutter_box, wx.VERTICAL)
        shutter_sizer.Add(shutter_layout, flag=wx.ALL|wx.EXPAND, border=5)

        return shutter_sizer

    def _make_attenuator_sizer(self, parent):
        atten_box = wx.StaticBox(parent, label='Attenuators')
        fsize = self.GetFont().Larger().GetPointSize()
        font = wx.Font(fsize, wx.DEFAULT, wx.NORMAL, wx.BOLD)
        atten_box.SetOwnFont(font)

        atten_1 = custom_epics_widgets.PVTextLabeled(atten_box,
            self.pvs['atten_1'], fg='forest green')
        atten_2 = custom_epics_widgets.PVTextLabeled(atten_box,
            self.pvs['atten_2'], fg='forest green')
        atten_4 = custom_epics_widgets.PVTextLabeled(atten_box,
            self.pvs['atten_4'], fg='forest green')
        atten_8 = custom_epics_widgets.PVTextLabeled(atten_box,
            self.pvs['atten_8'], fg='forest green')
        atten_16 = custom_epics_widgets.PVTextLabeled(atten_box,
            self.pvs['atten_16'], fg='forest green')
        atten_32 = custom_epics_widgets.PVTextLabeled(atten_box,
            self.pvs['atten_32'], fg='forest green')

        atten_1.SetTranslations({'On': 'Out', 'Off': 'In'})
        atten_2.SetTranslations({'On': 'Out', 'Off': 'In'})
        atten_4.SetTranslations({'On': 'Out', 'Off': 'In'})
        atten_8.SetTranslations({'On': 'Out', 'Off': 'In'})
        atten_16.SetTranslations({'On': 'Out', 'Off': 'In'})
        atten_32.SetTranslations({'On': 'Out', 'Off': 'In'})

        atten_1.SetForegroundColourTranslations({'Out': 'forest green',
            'In': 'red'})
        atten_2.SetForegroundColourTranslations({'Out': 'forest green',
            'In': 'red'})
        atten_4.SetForegroundColourTranslations({'Out': 'forest green',
            'In': 'red'})
        atten_8.SetForegroundColourTranslations({'Out': 'forest green',
            'In': 'red'})
        atten_16.SetForegroundColourTranslations({'Out': 'forest green',
            'In': 'red'})
        atten_32.SetForegroundColourTranslations({'Out': 'forest green',
            'In': 'red'})

        atten_layout = wx.FlexGridSizer(cols=6, hgap=5, vgap=5)
        atten_layout.Add(wx.StaticText(atten_box, label='1 foil:'),
            flag=wx.ALIGN_CENTER_VERTICAL)
        atten_layout.Add(atten_1, flag=wx.ALIGN_CENTER_VERTICAL)
        atten_layout.Add(wx.StaticText(atten_box, label='2 foil:'),
            flag=wx.ALIGN_CENTER_VERTICAL)
        atten_layout.Add(atten_2, flag=wx.ALIGN_CENTER_VERTICAL)
        atten_layout.Add(wx.StaticText(atten_box, label='4 foil:'),
            flag=wx.ALIGN_CENTER_VERTICAL)
        atten_layout.Add(atten_4, flag=wx.ALIGN_CENTER_VERTICAL)
        atten_layout.Add(wx.StaticText(atten_box, label='8 foil:'),
            flag=wx.ALIGN_CENTER_VERTICAL)
        atten_layout.Add(atten_8, flag=wx.ALIGN_CENTER_VERTICAL)
        atten_layout.Add(wx.StaticText(atten_box, label='16 foil:'),
            flag=wx.ALIGN_CENTER_VERTICAL)
        atten_layout.Add(atten_16, flag=wx.ALIGN_CENTER_VERTICAL)
        atten_layout.Add(wx.StaticText(atten_box, label='32 foil:'),
            flag=wx.ALIGN_CENTER_VERTICAL)
        atten_layout.Add(atten_32, flag=wx.ALIGN_CENTER_VERTICAL)


        self.transmission = wx.StaticText(atten_box, label='')

        trans_sizer = wx.BoxSizer(wx.HORIZONTAL)
        trans_sizer.Add(wx.StaticText(atten_box, label='Nominal Trans. (12 keV):'))
        trans_sizer.Add(self.transmission)

        atten_sizer = wx.StaticBoxSizer(atten_box, wx.VERTICAL)
        atten_sizer.Add(atten_layout, flag=wx.ALL|wx.EXPAND, border=5)
        atten_sizer.Add(trans_sizer, flag=wx.LEFT|wx.RIGHT|wx.BOTTOM,
            border=5)

        return atten_sizer

    def _atten_calc(self, **kwargs):
        length = 0

        for i in [1, 2, 4, 8, 16, 32]:
            atten_on = self.pvs['atten_{}'.format(i)].get(as_string=False)

            if atten_on == 0:
                length = length+i

        length = 20*length
        atten = math.exp(-length/256.568) #256.568 is Al attenuation length at 12 keV

        if atten > 0.1:
            atten = '{}'.format(round(atten, 3))
        elif atten > 0.01:
            atten = '{}'.format(round(atten, 4))
        else:
            atten = '{}'.format(round(atten, 5))

        self.transmission.SetLabel(atten)


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

        screen_two = wx.Display(1)
        w_edge, h_edge_, screen_two_w, screen_two_h = screen_two.GetGeometry()

        self.SetPosition((int(w_edge + (screen_two_w / 8)),
                                   int(screen_two_h / 8)))

        self.SetSizer(top_sizer)
        self.Layout()
        self.Fit()
        # self.Raise()
        if platform.system() == 'Darwin':
            self.PostSizeEvent()
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
