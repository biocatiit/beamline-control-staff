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
import subprocess
import pathlib

import wx
import epics, epics.wx

import utils

class EPICSLauncherPanel(wx.Panel):
    """
    """
    def __init__(self, name, mx_database, *args, **kwargs):
        """
        """
        wx.Panel.__init__(self, *args, name=name, **kwargs)

        self._base_path = pathlib.Path(__file__).parent.resolve()
        self._epics_path = self._base_path  / '..' / 'epics_screens' / 'medm_start_scripts'
        self._epics_path = self._epics_path.resolve()

        self._create_layout()

        self._initialize()

        self.SendSizeEvent()

    def _FromDIP(self, size):
        # This is a hack to provide easy back compatibility with wxpython < 4.1
        try:
            return self.FromDIP(size)
        except Exception:
            return size

    def on_close(self):
        pass

    def _create_layout(self):
        """
        Creates the layout for the panel.
        """
        parent = self

        io_box = wx.StaticBox(parent, label='I/Os')
        labjack1_button = wx.Button(io_box, label='LabJack 1')
        labjack2_button = wx.Button(io_box, label='LabJack 2')
        labjack3_button = wx.Button(io_box, label='LabJack 3')
        mc_1608G_1_button = wx.Button(io_box, label='MC 1608G 1')
        mc_1608G_2_button = wx.Button(io_box, label='MC 1608G 2')
        mc_1608G_2ao_1_button = wx.Button(io_box, label='MC 1608G 2AO 1')
        mc_e1608_button = wx.Button(io_box, label='MC E-1608')
        mc_etc_1_button = wx.Button(io_box, label='MC E-TC')

        labjack1_button.Bind(wx.EVT_BUTTON, self._on_labjack1_button)
        labjack2_button.Bind(wx.EVT_BUTTON, self._on_labjack2_button)
        labjack3_button.Bind(wx.EVT_BUTTON, self._on_labjack3_button)

        mc_1608G_1_button.Bind(wx.EVT_BUTTON, self._on_mc_1608g_1_button)
        mc_1608G_2_button.Bind(wx.EVT_BUTTON, self._on_mc_1608g_2_button)
        mc_1608G_2ao_1_button.Bind(wx.EVT_BUTTON, self._on_mc_1608g_2ao_1_button)
        mc_e1608_button.Bind(wx.EVT_BUTTON, self._on_mc_e1608_button)
        mc_etc_1_button.Bind(wx.EVT_BUTTON, self._on_mc_etc_button)

        io_sizer = wx.StaticBoxSizer(io_box, wx.VERTICAL)
        io_sizer.Add(labjack1_button, flag=wx.TOP|wx.LEFT|wx.RIGHT,
            border=self._FromDIP(5))
        io_sizer.Add(labjack2_button, flag=wx.TOP|wx.LEFT|wx.RIGHT,
            border=self._FromDIP(5))
        io_sizer.Add(labjack3_button, flag=wx.TOP|wx.LEFT|wx.RIGHT,
            border=self._FromDIP(5))
        io_sizer.Add(mc_1608G_1_button, flag=wx.TOP|wx.LEFT|wx.RIGHT,
            border=self._FromDIP(5))
        io_sizer.Add(mc_1608G_2_button, flag=wx.TOP|wx.LEFT|wx.RIGHT,
            border=self._FromDIP(5))
        io_sizer.Add(mc_1608G_2ao_1_button, flag=wx.TOP|wx.LEFT|wx.RIGHT,
            border=self._FromDIP(5))
        io_sizer.Add(mc_e1608_button, flag=wx.TOP|wx.LEFT|wx.RIGHT,
            border=self._FromDIP(5))
        io_sizer.Add(mc_etc_1_button, flag=wx.ALL,
            border=self._FromDIP(5))


        scaler_box = wx.StaticBox(parent, label='Scalers')
        struck_button = wx.Button(scaler_box, label='Struck SIS3820')
        joerger_button = wx.Button(scaler_box, label='Joerger')

        struck_button.Bind(wx.EVT_BUTTON, self._on_struck_button)
        joerger_button.Bind(wx.EVT_BUTTON, self._on_joerger_button)

        scaler_sizer = wx.StaticBoxSizer(scaler_box, wx.VERTICAL)
        scaler_sizer.Add(struck_button, flag=wx.TOP|wx.LEFT|wx.RIGHT,
            border=self._FromDIP(5))
        scaler_sizer.Add(joerger_button, flag=wx.ALL,
            border=self._FromDIP(5))


        ad_box = wx.StaticBox(parent, label='Area Detectors')
        eiger_button = wx.Button(ad_box, label='Eiger2 XE 9M')
        pilatus_button = wx.Button(ad_box, label='Pilatus3 X 1M')
        mar_button = wx.Button(ad_box, label='Mar165')

        eiger_button.Bind(wx.EVT_BUTTON, self._on_eiger_button)
        pilatus_button.Bind(wx.EVT_BUTTON, self._on_pilatus_button)
        mar_button.Bind(wx.EVT_BUTTON, self._on_mar_button)

        ad_sizer = wx.StaticBoxSizer(ad_box, wx.VERTICAL)
        ad_sizer.Add(eiger_button, flag=wx.TOP|wx.LEFT|wx.RIGHT,
            border=self._FromDIP(5))
        ad_sizer.Add(pilatus_button, flag=wx.TOP|wx.LEFT|wx.RIGHT,
            border=self._FromDIP(5))
        ad_sizer.Add(mar_button, flag=wx.ALL,
            border=self._FromDIP(5))


        motor_box = wx.StaticBox(parent, label='Motors')
        motor_channel_button = wx.Button(motor_box, label='Motor Channels')
        dmc_e01_button = wx.Button(motor_box, label='DMC E01')
        dmc_e02_button = wx.Button(motor_box, label='DMC E02')
        dmc_e03_button = wx.Button(motor_box, label='DMC E03')
        dmc_e04_button = wx.Button(motor_box, label='DMC E04')
        dmc_e05_button = wx.Button(motor_box, label='DMC E05')
        dmc_a01_button = wx.Button(motor_box, label='DMC A01')

        motor_channel_button.Bind(wx.EVT_BUTTON, self._on_motor_channel_button)
        dmc_e01_button.Bind(wx.EVT_BUTTON, self._on_dmc_e01_button)
        dmc_e02_button.Bind(wx.EVT_BUTTON, self._on_dmc_e02_button)
        dmc_e03_button.Bind(wx.EVT_BUTTON, self._on_dmc_e03_button)
        dmc_e04_button.Bind(wx.EVT_BUTTON, self._on_dmc_e04_button)
        dmc_e05_button.Bind(wx.EVT_BUTTON, self._on_dmc_e05_button)
        dmc_a01_button.Bind(wx.EVT_BUTTON, self._on_dmc_a01_button)

        motor_sizer = wx.StaticBoxSizer(motor_box, wx.VERTICAL)
        motor_sizer.Add(motor_channel_button, flag=wx.TOP|wx.LEFT|wx.RIGHT,
            border=self._FromDIP(5))
        motor_sizer.Add(dmc_e01_button, flag=wx.TOP|wx.LEFT|wx.RIGHT,
            border=self._FromDIP(5))
        motor_sizer.Add(dmc_e02_button, flag=wx.TOP|wx.LEFT|wx.RIGHT,
            border=self._FromDIP(5))
        motor_sizer.Add(dmc_e03_button, flag=wx.TOP|wx.LEFT|wx.RIGHT,
            border=self._FromDIP(5))
        motor_sizer.Add(dmc_e04_button, flag=wx.TOP|wx.LEFT|wx.RIGHT,
            border=self._FromDIP(5))
        motor_sizer.Add(dmc_e05_button, flag=wx.ALL,
            border=self._FromDIP(5))
        motor_sizer.Add(dmc_a01_button, flag=wx.ALL,
            border=self._FromDIP(5))


        aps_box = wx.StaticBox(parent, label='APS')
        id_button = wx.Button(aps_box, label='Undulator')
        aps_bpm_button = wx.Button(aps_box, label='APS BPMs')
        pss_button = wx.Button(aps_box, label='PSS')

        id_button.Bind(wx.EVT_BUTTON, self._on_id_button)
        aps_bpm_button.Bind(wx.EVT_BUTTON, self._on_aps_bpm_button)
        pss_button.Bind(wx.EVT_BUTTON, self._on_pss_button)

        aps_sizer = wx.StaticBoxSizer(aps_box, wx.VERTICAL)
        aps_sizer.Add(id_button, flag=wx.TOP|wx.LEFT|wx.RIGHT,
            border=self._FromDIP(5))
        aps_sizer.Add(aps_bpm_button, flag=wx.TOP|wx.LEFT|wx.RIGHT,
            border=self._FromDIP(5))
        aps_sizer.Add(pss_button, flag=wx.ALL,
            border=self._FromDIP(5))


        top_sizer = wx.FlexGridSizer(cols=2, hgap=self._FromDIP(5),
            vgap=self._FromDIP(5))
        top_sizer.Add(motor_sizer, flag=wx.EXPAND|wx.ALL, border=self._FromDIP(5))
        top_sizer.Add(io_sizer, flag=wx.EXPAND|wx.LEFT|wx.RIGHT|wx.BOTTOM,
            border=self._FromDIP(5))
        top_sizer.Add(ad_sizer, flag=wx.EXPAND|wx.LEFT|wx.RIGHT|wx.BOTTOM,
            border=self._FromDIP(5))
        top_sizer.Add(aps_sizer, flag=wx.EXPAND|wx.LEFT|wx.RIGHT|wx.BOTTOM,
            border=self._FromDIP(5))
        top_sizer.Add(scaler_sizer, flag=wx.EXPAND|wx.LEFT|wx.RIGHT|wx.BOTTOM,
            border=self._FromDIP(5))


        self.SetSizer(top_sizer)

    def _initialize(self):
        pass

    def _on_labjack1_button(self, evt):
        self._start_labjack(1)

    def _on_labjack2_button(self, evt):
        self._start_labjack(2)

    def _on_labjack3_button(self, evt):
        self._start_labjack(3)

    def _start_labjack(self, num):
        script = self._epics_path / 'start_labjack_screen.sh'
        cmd = '{} {}'.format(script, num)
        self._start_epics(cmd)

    def _on_mc_1608g_1_button(self, evt):
        self._start_mc('USB1608G_1')

    def _on_mc_1608g_2_button(self, evt):
        self._start_mc('USB1608G_2')

    def _on_mc_1608g_2ao_1_button(self, evt):
        self._start_mc('USB1608G_2AO_1')

    def _on_mc_e1608_button(self, evt):
        self._start_mc('E1608')

    def _on_mc_etc_button(self, evt):
        self._start_mc('ETC')

    def _start_mc(self, prefix):
        script = self._epics_path / 'start_meascomp_screen.sh'
        cmd = '{} {}'.format(script, prefix)
        self._start_epics(cmd)

    def _on_struck_button(self, evt):
        script = self._epics_path / 'start_sis3820_screen.sh'
        cmd = '{}'.format(script)
        self._start_epics(cmd)

    def _on_joerger_button(self, evt):
        script = self._epics_path / 'start_joerger_screen.sh'
        cmd = '{}'.format(script)
        self._start_epics(cmd)

    def _on_eiger_button(self, evt):
        script = self._epics_path / 'start_eiger_screen.sh'
        cmd = '{}'.format(script)
        self._start_epics(cmd)

    def _on_pilatus_button(self, evt):
        script = self._epics_path / 'start_pilatus_screen.sh'
        cmd = '{}'.format(script)
        self._start_epics(cmd)

    def _on_mar_button(self, evt):
        script = self._epics_path / 'start_mar_screen.sh'
        cmd = '{}'.format(script)
        self._start_epics(cmd)

    def _on_id_button(self, evt):
        script = self._epics_path / 'start_undulator_screen.sh'
        cmd = '{}'.format(script)
        self._start_epics(cmd)

    def _on_aps_bpm_button(self, evt):
        script = self._epics_path / 'start_aps_bpm_screen.sh'
        cmd = '{}'.format(script)
        self._start_epics(cmd)

    def _on_pss_button(self, evt):
        script = self._epics_path / 'start_pss_screen.sh'
        cmd = '{}'.format(script)
        self._start_epics(cmd)

    def _on_motor_channel_button(self, evt):
        motor_channel_frame = MotorChannelFrame(self,
            title='Motor Channels')
        motor_channel_frame.Show()

    def _on_dmc_e01_button(self, evt):
        self._start_dmc('E01')

    def _on_dmc_e02_button(self, evt):
        self._start_dmc('E02')

    def _on_dmc_e03_button(self, evt):
        self._start_dmc('E03')

    def _on_dmc_e04_button(self, evt):
        self._start_dmc('E04')

    def _on_dmc_e05_button(self, evt):
        self._start_dmc('E05')

    def _on_dmc_a01_button(self, evt):
        self._start_dmc('A01')

    def _start_dmc(self, num):
        script = self._epics_path / 'start_dmc_screen.sh'
        cmd = '{} 18ID_DMC_{}'.format(script, num)
        self._start_epics(cmd)

    def _start_epics(self, cmd):
        process = subprocess.Popen(cmd, shell=True, cwd=self._epics_path)
        output, error = process.communicate()

class MotorChannelPanel(wx.Panel):
    def __init__(self, name, mx_database, *args, **kwargs):
        wx.Panel.__init__(self, *args, **kwargs)

        self._base_path = pathlib.Path(__file__).parent.resolve()
        self._epics_path = self._base_path  / '..' / 'epics_screens' / 'medm_start_scripts'
        self._epics_path = self._epics_path.resolve()

        self._channels = [
            ('18ID_DMC_E01:', 1, 8, ''),
            ('18ID_DMC_E02:', 9, 16, ''),
            ('18ID_DMC_E03:', 17, 24, ''),
            ('18ID_DMC_E04:', 25, 32, ''),
            ('18ID_DMC_E05:', 33, 40, ''),
            ('18ID_DMC_A01:', 1, 8, 'A'),
            ]

        self._channel_show = {}

        self._create_layout()

        # self.SetMinSize(self._FromDIP((600, -1)))

        self.Layout()
        self.Fit()
        self.Raise()

    def _FromDIP(self, size):
        # This is a hack to provide easy back compatibility with wxpython < 4.1
        try:
            return self.FromDIP(size)
        except Exception:
            return size

    def on_close(self):
        pass

    def _create_layout(self):
        # top_sizer = wx.BoxSizer(wx.VERTICAL)

        motor_panel = self

        motor_grid_sizer = wx.FlexGridSizer(cols=3, vgap=self._FromDIP(5),
            hgap=self._FromDIP(5))

        for channel in self._channels:
            channel_sizer = self._create_channels_sizer(channel, motor_panel)

            motor_grid_sizer.Add(channel_sizer, flag=wx.EXPAND)

        motor_grid_sizer.AddGrowableCol(0)
        motor_grid_sizer.AddGrowableCol(1)


        slit_box = wx.StaticBox(motor_panel, label='Slit Center and Gap')

        wb = wx.Button(slit_box, label='WB')
        wb.Bind(wx.EVT_BUTTON, self._on_show_slit)
        wb_v = wx.Button(slit_box, label='WB V')
        wb_v.Bind(wx.EVT_BUTTON, self._on_show_slit)
        wb_h = wx.Button(slit_box, label='WB H')
        wb_h.Bind(wx.EVT_BUTTON, self._on_show_slit)
        jj_c = wx.Button(slit_box, label='JJ C')
        jj_c.Bind(wx.EVT_BUTTON, self._on_show_slit)
        jj_c_v = wx.Button(slit_box, label='JJ C V')
        jj_c_v.Bind(wx.EVT_BUTTON, self._on_show_slit)
        jj_c_h = wx.Button(slit_box, label='JJ C H')
        jj_c_h.Bind(wx.EVT_BUTTON, self._on_show_slit)
        jj_d = wx.Button(slit_box, label='JJ D')
        jj_d.Bind(wx.EVT_BUTTON, self._on_show_slit)
        jj_d_v = wx.Button(slit_box, label='JJ D V')
        jj_d_v.Bind(wx.EVT_BUTTON, self._on_show_slit)
        jj_d_h = wx.Button(slit_box, label='JJ D H')
        jj_d_h.Bind(wx.EVT_BUTTON, self._on_show_slit)
        xenocs_us = wx.Button(slit_box, label='Xenocs US')
        xenocs_us.Bind(wx.EVT_BUTTON, self._on_show_slit)
        xenocs_us_v = wx.Button(slit_box, label='Xenocs US V')
        xenocs_us_v.Bind(wx.EVT_BUTTON, self._on_show_slit)
        xenocs_us_h = wx.Button(slit_box, label='Xenocs US H')
        xenocs_us_h.Bind(wx.EVT_BUTTON, self._on_show_slit)
        xenocs_ds = wx.Button(slit_box, label='Xenocs DS')
        xenocs_ds.Bind(wx.EVT_BUTTON, self._on_show_slit)
        xenocs_ds_v = wx.Button(slit_box, label='Xenocs DS V')
        xenocs_ds_v.Bind(wx.EVT_BUTTON, self._on_show_slit)
        xenocs_ds_h = wx.Button(slit_box, label='Xenocs DS H')
        xenocs_ds_h.Bind(wx.EVT_BUTTON, self._on_show_slit)

        slit_grid_sizer = wx.FlexGridSizer(cols=6, vgap=self._FromDIP(5),
            hgap=self._FromDIP(5))
        slit_grid_sizer.Add(wb)
        slit_grid_sizer.Add(wb_v)
        slit_grid_sizer.Add(wb_h)
        slit_grid_sizer.Add(jj_c)
        slit_grid_sizer.Add(jj_c_v)
        slit_grid_sizer.Add(jj_c_h)
        slit_grid_sizer.Add(jj_d)
        slit_grid_sizer.Add(jj_d_v)
        slit_grid_sizer.Add(jj_d_h)
        slit_grid_sizer.Add(xenocs_us)
        slit_grid_sizer.Add(xenocs_us_v)
        slit_grid_sizer.Add(xenocs_us_h)
        slit_grid_sizer.Add(xenocs_ds)
        slit_grid_sizer.Add(xenocs_ds_v)
        slit_grid_sizer.Add(xenocs_ds_h)

        slit_sizer = wx.StaticBoxSizer(slit_box, wx.VERTICAL)
        slit_sizer.Add(slit_grid_sizer, flag=wx.ALL, border=self._FromDIP(5))

        motor_sizer = wx.BoxSizer(wx.VERTICAL)
        motor_sizer.Add(motor_grid_sizer, proportion=1,flag=wx.EXPAND|wx.ALL,
            border=self._FromDIP(5))
        motor_sizer.Add(slit_sizer, flag=wx.LEFT|wx.RIGHT|wx.BOTTOM,
            border=self._FromDIP(5))

        motor_panel.SetSizer(motor_sizer)

        # top_sizer.Add(motor_panel, flag=wx.EXPAND, proportion=1)

        # self.SetSizer(top_sizer)

    def _create_channels_sizer(self, channel, parent):
        prefix, start, end, extra = channel
        channel_box = wx.StaticBox(parent, label=prefix)

        channel_sizer = wx.FlexGridSizer(cols=3, vgap=self._FromDIP(5),
            hgap=self._FromDIP(5))

        for mnum in range(start, end+1):
            pv = '{}{}{}'.format(prefix, extra, mnum)
            descrip = epics.wx.PVText(channel_box, '{}.DESC'.format(pv),
                minor_alarm=None, major_alarm=None, invalid_alarm=None,
                size=self._FromDIP((150,-1)), bg='white')

            show = wx.Button(channel_box, label='Show')
            show.Bind(wx.EVT_BUTTON, self._on_show_button)

            self._channel_show[show] = (prefix, mnum, extra)

            channel_sizer.Add(wx.StaticText(channel_box, label='{}{}:'.format(extra, mnum)),
                flag=wx.ALIGN_CENTER_VERTICAL)
            channel_sizer.Add(descrip, flag=wx.ALIGN_CENTER_VERTICAL|wx.EXPAND)
            channel_sizer.Add(show, flag=wx.ALIGN_CENTER_VERTICAL)

        channel_sizer.AddGrowableCol(1)

        top_sizer = wx.StaticBoxSizer(channel_box, wx.VERTICAL)
        top_sizer.Add(channel_sizer, flag=wx.ALL|wx.EXPAND, border=self._FromDIP(5))

        return top_sizer

    def _on_show_button(self, evt):
        button = evt.GetEventObject()

        prefix, mnum, extra = self._channel_show[button]

        script = self._epics_path / 'start_motor_screen.sh'
        cmd = '{} {} {}{}'.format(script, prefix, extra, mnum)

        process = subprocess.Popen(cmd, shell=True, cwd=self._epics_path)
        output, error = process.communicate()

    def _on_show_slit(self, evt):
        button = evt.GetEventObject()

        label = button.GetLabel()
        param = label.replace(' ', '_')

        script = self._epics_path / 'start_slit_screen.sh'
        cmd = '{} {}'.format(script, param)

        process = subprocess.Popen(cmd, shell=True, cwd=self._epics_path)
        output, error = process.communicate()

class MotorChannelFrame(wx.Frame):
    """
    A lightweight amplifier frame designed to hold the EPICS launcher panel.
    """
    def __init__(self, *args, **kwargs):
        """
        """
        wx.Frame.__init__(self, *args, **kwargs)


        self._create_layout()

        self.Layout()
        self.Fit()
        self.Raise()

    def _FromDIP(self, size):
        # This is a hack to provide easy back compatibility with wxpython < 4.1
        try:
            return self.FromDIP(size)
        except Exception:
            return size

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
        top_sizer = wx.BoxSizer(wx.VERTICAL)

        epics_panel = MotorChannelPanel('EpicsLauncher', None, self)

        top_sizer.Add(epics_panel, flag=wx.EXPAND, proportion=1)

        self.SetSizer(top_sizer)


class EPICSLauncherFrame(wx.Frame):
    """
    A lightweight amplifier frame designed to hold the EPICS launcher panel.
    """
    def __init__(self, *args, **kwargs):
        """
        """
        wx.Frame.__init__(self, *args, **kwargs)


        self._create_layout()

        self.Layout()
        self.Fit()
        self.Raise()

    def _FromDIP(self, size):
        # This is a hack to provide easy back compatibility with wxpython < 4.1
        try:
            return self.FromDIP(size)
        except Exception:
            return size

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
        top_sizer = wx.BoxSizer(wx.VERTICAL)

        epics_panel = EPICSLauncherPanel('EpicsLauncher', None, self)

        top_sizer.Add(epics_panel, flag=wx.EXPAND, proportion=1)

        self.SetSizer(top_sizer)

if __name__ == '__main__':

    app = wx.App()
    frame = EPICSLauncherFrame(parent=None, title='Test EPICS Launcher')
    frame.Show()
    app.MainLoop()
