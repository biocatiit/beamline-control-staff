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
    def __init__(self, parent, panel_id=wx.ID_ANY, panel_name=''):
        wx.Panel.__init__(self, parent, panel_id, name=panel_name)

        self._initialize()

        self._create_layout()

        self.SetMinSize((600, -1))

    def _create_layout(self):
        """
        Creates the layout for the panel.
        """

        notebook = wx.Notebook(self)

        overview_page = OverviewPanel(self.pvs, notebook)

        notebook.AddPage(overview_page, 'Overview')

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

        aps_status = epics.wx.PVText(aps_box, self.pvs['aps_status'],
            fg='forest green')
        beam_current = epics.wx.PVText(aps_box, self.pvs['current'],
            auto_units=True, fg='forest green')

        aps_sizer = wx.StaticBoxSizer(aps_box, wx.HORIZONTAL)
        aps_sizer.Add(wx.StaticText(aps_box, label='Beam current:'), border=5,
            flag=wx.ALL|wx.ALIGN_CENTER_VERTICAL)
        aps_sizer.Add(beam_current, border=5,
            flag=wx.RIGHT|wx.TOP|wx.BOTTOM|wx.ALIGN_CENTER_VERTICAL)
        aps_sizer.Add(wx.StaticText(aps_box, label='APS beam status:'),
            border=5, flag=wx.RIGHT|wx.TOP|wx.BOTTOM|wx.ALIGN_CENTER_VERTICAL)
        aps_sizer.Add(aps_status, border=5,
            flag=wx.RIGHT|wx.TOP|wx.BOTTOM|wx.ALIGN_CENTER_VERTICAL)


        bleps_box = wx.StaticBox(self, label='BLEPS Status')

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
        bleps_grid_sizer.Add(wx.StaticText(bleps_box, label='BLEPS trip:'),
            pos=(0,2), flag=wx.ALIGN_CENTER_VERTICAL)
        bleps_grid_sizer.Add(bleps_trip, pos=(0,3),
            flag=wx.ALIGN_CENTER_VERTICAL)
        bleps_grid_sizer.Add(wx.StaticText(bleps_box, label='BLEPS warning:'),
            pos=(0,4), flag=wx.ALIGN_CENTER_VERTICAL)
        bleps_grid_sizer.Add(bleps_warning, pos=(0,5),
            flag=wx.ALIGN_CENTER_VERTICAL)
        bleps_grid_sizer.Add(bleps_fault_reset, pos=(1,0), span=(0, 2),
            flag=wx.ALIGN_CENTER_VERTICAL|wx.ALIGN_CENTER_HORIZONTAL)
        bleps_grid_sizer.Add(bleps_trip_reset, pos=(1,2), span=(0, 2),
            flag=wx.ALIGN_CENTER_VERTICAL|wx.ALIGN_CENTER_HORIZONTAL)

        bleps_sizer = wx.StaticBoxSizer(bleps_box, wx.HORIZONTAL)
        bleps_sizer.Add(bleps_grid_sizer, proportion=1, flag=wx.ALL|wx.EXPAND,
            border=5)

        station_box = wx.StaticBox(self, label='Station Status')

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
        station_sizer.Add(station_grid_sizer, proportion=1, flag=wx.EXPAND)


        exp_box = wx.StaticBox(self, label='Experiment Status')

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

        exp_grid_sizer = wx.FlexGridSizer(cols=6, hgap=5, vgap=5)
        exp_grid_sizer.Add(wx.StaticText(exp_box, label='Slow shutter 1:'),
            flag=wx.ALIGN_CENTER_VERTICAL)
        exp_grid_sizer.Add(exp_slow_shtr1, flag=wx.ALIGN_CENTER_VERTICAL)
        exp_grid_sizer.Add(wx.StaticText(exp_box, label='Slow shutter 2:'),
            flag=wx.ALIGN_CENTER_VERTICAL)
        exp_grid_sizer.Add(exp_slow_shtr2, flag=wx.ALIGN_CENTER_VERTICAL)
        exp_grid_sizer.Add(wx.StaticText(exp_box, label='Fast shutter:'),
            flag=wx.ALIGN_CENTER_VERTICAL)
        exp_grid_sizer.Add(exp_fast_shtr, flag=wx.ALIGN_CENTER_VERTICAL)
        exp_grid_sizer.Add(wx.StaticText(exp_box, label='Col. Vac. [mTorr]:'),
            flag=wx.ALIGN_CENTER_VERTICAL)
        exp_grid_sizer.Add(exp_col_vac, flag=wx.ALIGN_CENTER_VERTICAL)
        exp_grid_sizer.Add(wx.StaticText(exp_box, label='Guard Vac. [mTorr]:'),
            flag=wx.ALIGN_CENTER_VERTICAL)
        exp_grid_sizer.Add(exp_guard_vac, flag=wx.ALIGN_CENTER_VERTICAL)
        exp_grid_sizer.Add(wx.StaticText(exp_box, label='Sample Vac.[mTorr]:'),
            flag=wx.ALIGN_CENTER_VERTICAL)
        exp_grid_sizer.Add(exp_sample_vac, flag=wx.ALIGN_CENTER_VERTICAL)
        exp_grid_sizer.Add(wx.StaticText(exp_box, label='S.C. Vac.[mTorr]:'),
            flag=wx.ALIGN_CENTER_VERTICAL)
        exp_grid_sizer.Add(exp_scatter_vac, flag=wx.ALIGN_CENTER_VERTICAL)
        exp_grid_sizer.Add(wx.StaticText(exp_box, label='I0 [V]:'),
            flag=wx.ALIGN_CENTER_VERTICAL)
        exp_grid_sizer.Add(exp_i0, flag=wx.ALIGN_CENTER_VERTICAL)
        exp_grid_sizer.Add(wx.StaticText(exp_box, label='I1 [V]:'),
            flag=wx.ALIGN_CENTER_VERTICAL)
        exp_grid_sizer.Add(exp_i1, flag=wx.ALIGN_CENTER_VERTICAL)

        exp_sizer = wx.StaticBoxSizer(exp_box, wx.VERTICAL)
        exp_sizer.Add(exp_grid_sizer, proportion=1, flag=wx.EXPAND|wx.ALL,
            border=5)


        top_sizer = wx.BoxSizer(wx.VERTICAL)
        top_sizer.Add(aps_sizer, border=5, flag=wx.ALL)
        top_sizer.Add(bleps_sizer, border=5, flag=wx.LEFT|wx.RIGHT|wx.BOTTOM)
        top_sizer.Add(station_sizer, border=5, flag=wx.LEFT|wx.RIGHT|wx.BOTTOM)
        top_sizer.Add(exp_sizer, border=5, flag=wx.LEFT|wx.RIGHT|wx.BOTTOM)

        self.SetSizer(top_sizer)

        # return top_sizer

    def _initialize(self):
        pass



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

        self.SetPosition((int(w_edge + (screen_two_w / 2)),
                                   int(screen_two_h / 2)))

        self.SetSizer(top_sizer)
        self.Layout()
        self.Fit()
        self.Raise()
        self.PostSizeEvent()


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
        main_panel = MainStatusPanel(self)

        top_sizer = wx.BoxSizer(wx.VERTICAL)
        top_sizer.Add(main_panel, proportion=1, flag=wx.EXPAND)

        return top_sizer


if __name__ == '__main__':

    app = wx.App()
    frame = BeamlineStatusFrame(parent=None, title='Test Status Page')
    frame.Show()
    app.MainLoop()
