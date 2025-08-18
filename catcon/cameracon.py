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

from builtins import object, range, map
from io import open

if __name__ == "__main__" and __package__ is None:
    __package__ = "catcon"

import wx
import epics, epics.wx, epics.devices

import utils
import custom_epics_widgets

class EpicsCamera(epics.devices.ad_base.AD_Camera):
    attrs = ("Acquire", "AcquirePeriod", "AcquirePeriod_RBV",
             "AcquireTime", "AcquireTime_RBV",
             "ArrayCallbacks", "ArrayCallbacks_RBV",
             "ArrayCounter", "ArrayCounter_RBV", "ArrayRate_RBV",
             "ArraySizeX_RBV", "ArraySizeY_RBV", "ArraySize_RBV",
             "BinX", "BinX_RBV", "BinY", "BinY_RBV",
             "ColorMode", "ColorMode_RBV",
             "DataType", "DataType_RBV", "DetectorState_RBV",
             "Gain", "Gain_RBV", "ImageMode", "ImageMode_RBV",
             "MaxSizeX_RBV", "MaxSizeY_RBV",
             "MinX", "MinX_RBV", "MinY", "MinY_RBV",
             "NumImages", "NumImagesCounter_RBV", "NumImages_RBV",
             "SizeX", "SizeX_RBV", "SizeY", "SizeY_RBV",
             "TimeRemaining_RBV",
             "TriggerMode", "TriggerMode_RBV", "TriggerSoftware",
             "ExposureAuto", "ExposureAuto_RBV",
             "GainAuto", "GainAuto_RBV",
             "FrameRate", "FrameRate_RBV")

    def __init__(self, prefix):
        epics.devices.ad_base.AD_Camera.__init__(self, prefix)

class EpicsCameraOverlay(epics.devices.ad_overlay.AD_OverlayPlugin):
    ttrs = ('Name', 'Name_RBV',
             'Use', 'Use_RBV',
             'PositionX', 'PositionX_RBV',
             'PositionY', 'PositionY_RBV',
             'PositionXLink', 'PositionYLink',
             'SizeXLink', 'SizeYLink',
             'SizeX', 'SizeX_RBV',
             'SizeY', 'SizeY_RBV',
             'Shape', 'Shape_RBV',
             'DrawMode', 'DrawMode_RBV',
             'Red',    'Red_RBV',
             'Green', 'Green_RBV',
             'Blue', 'Blue_RBV',
             'CenterX', 'CenterX_RBV',
             'CenterY', 'CenterY_RBV',
             'WidthX', 'WidthX_RBV',
             'WidthY', 'WidthY_RBV',)

    def __init__(self, prefix):
        epics.devices.ad_base.AD_Camera.__init__(self, prefix)

class CameraControlPanel(wx.Panel):
    def __init__(self, name, mx_database, *args, **kwargs):
        wx.Panel.__init__(self, *args, **kwargs)

        self._known_cameras = {
            'inline_viewer' : '18ID:FLIR:D:Inline:',
            'tripod'        : '18ID:FLIR:D:Tripod:',
            'screen'        : '18ID:FLIR:C:Screen:',
            'mono1'         : '18ID:FLIR:C:Mono1:',
            'mono2'         : '18ID:FLIR:C:Mono2:',
        }

        self._camera_names = {
            'Inline Viewer'         : 'inline_viewer',
            'Tripod'                : 'tripod',
            'Fluorescent Screen'    : 'screen',
            'Mono 1'                : 'mono1',
            'Mono 2'                : 'mono2',
        }

        self._ctrl_sizers = {}

        self._current_camera = None
        self._current_overlay = None

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

    def on_close(self):
        pass

    def _create_layout(self):
        parent = self

        self.camera_choice = wx.Choice(parent, choices=list(self._camera_names.keys()))
        self.camera_choice.SetStringSelection('Inline Viewer')
        self.camera_choice.Bind(wx.EVT_CHOICE, self._on_camera_choice)

        choice_sizer = wx.BoxSizer(wx.HORIZONTAL)
        choice_sizer.Add(wx.StaticText(parent, label='Camera:'),
            flag=wx.ALIGN_CENTER_VERTICAL)
        choice_sizer.Add(self.camera_choice, flag=wx.LEFT|wx.ALIGN_CENTER_VERTICAL,
            border=self._FromDIP(5))

        self.current_ctrl_sizer = self._create_control_sizer()

        self._ctrl_sizers['inline'] = self.current_ctrl_sizer

        self.top_sizer = wx.BoxSizer(wx.VERTICAL)
        self.top_sizer.Add(choice_sizer, flag=wx.ALL, border=self._FromDIP(5))
        self.top_sizer.Add(self.current_ctrl_sizer, flag=wx.LEFT|wx.RIGHT|wx.BOTTOM,
            border=self._FromDIP(5))

        self.SetSizer(self.top_sizer)

    def _create_control_sizer(self):
        camera = self._camera_names[self.camera_choice.GetStringSelection()]
        pv = self._known_cameras[camera]

        self._current_camera = EpicsCamera('{}cam1:'.format(pv))
        self._current_overlay = EpicsCameraOverlay('{}Over1:1:'.format(pv))

        parent = self

        ctrl_box = wx.StaticBox(parent, label='Controls')

        exp_box = wx.StaticBox(ctrl_box, label='Exposure')

        exp_auto = custom_epics_widgets.PVEnumChoice2(exp_box,
            self._current_camera.PV('ExposureAuto'), self._on_exp_auto_change)
        self.exp_time = custom_epics_widgets.PVTextCtrl2(exp_box,
            self._current_camera.PV('AcquireTime'), size=self._FromDIP((75, -1)),
            validator=utils.CharValidator('float_te'))
        exp_time_rbv = epics.wx.PVText(exp_box,
            self._current_camera.PV('AcquireTime_RBV'), size=self._FromDIP((50, -1)),
            style=wx.ST_NO_AUTORESIZE)
        acq_period = custom_epics_widgets.PVTextCtrl2(exp_box,
            self._current_camera.PV('AcquirePeriod'), size=self._FromDIP((75, -1)),
            validator=utils.CharValidator('float_te'))
        acq_period_rbv = epics.wx.PVText(exp_box,
            self._current_camera.PV('AcquirePeriod_RBV'), size=self._FromDIP((50, -1)),
            style=wx.ST_NO_AUTORESIZE)
        frame_rate = custom_epics_widgets.PVTextCtrl2(exp_box,
            self._current_camera.PV('FrameRate'), size=self._FromDIP((75, -1)),
            validator=utils.CharValidator('float_te'))
        frame_rate_rbv = epics.wx.PVText(exp_box,
            self._current_camera.PV('FrameRate_RBV'), size=self._FromDIP((50, -1)),
            style=wx.ST_NO_AUTORESIZE)
        gain_auto = custom_epics_widgets.PVEnumChoice2(exp_box,
            self._current_camera.PV('GainAuto'), self._on_gain_auto_change)
        self.gain = custom_epics_widgets.PVTextCtrl2(exp_box,
            self._current_camera.PV('Gain'), size=self._FromDIP((75, -1)),
            validator=utils.CharValidator('float_te'))
        gain_rbv = epics.wx.PVText(exp_box,
            self._current_camera.PV('Gain_RBV'), size=self._FromDIP((50, -1)),
            style=wx.ST_NO_AUTORESIZE)


        exp_sub_sizer = wx.GridBagSizer(hgap=self._FromDIP(5),
            vgap=self._FromDIP(5))
        exp_sub_sizer.Add(wx.StaticText(exp_box, label='Exp. auto:'),
            (0,0), flag=wx.ALIGN_CENTER_VERTICAL)
        exp_sub_sizer.Add(exp_auto, (0, 1), (1, 2), flag=wx.ALIGN_CENTER_VERTICAL)
        exp_sub_sizer.Add(wx.StaticText(exp_box, label='Exp. time [s]:'),
            (1,0), flag=wx.ALIGN_CENTER_VERTICAL)
        exp_sub_sizer.Add(self.exp_time, (1,1), flag=wx.ALIGN_CENTER_VERTICAL)
        exp_sub_sizer.Add(exp_time_rbv, (1,2), flag=wx.ALIGN_CENTER_VERTICAL)
        exp_sub_sizer.Add(wx.StaticText(exp_box, label='Period [s]:'), (2,0),
            flag=wx.ALIGN_CENTER_VERTICAL)
        exp_sub_sizer.Add(acq_period, (2,1), flag=wx.ALIGN_CENTER_VERTICAL)
        exp_sub_sizer.Add(acq_period_rbv, (2,2), flag=wx.ALIGN_CENTER_VERTICAL)
        exp_sub_sizer.Add(wx.StaticText(exp_box, label='Frame rate [Hz]:'), (3,0),
            flag=wx.ALIGN_CENTER_VERTICAL)
        exp_sub_sizer.Add(frame_rate, (3,1), flag=wx.ALIGN_CENTER_VERTICAL)
        exp_sub_sizer.Add(frame_rate_rbv, (3,2), flag=wx.ALIGN_CENTER_VERTICAL)
        exp_sub_sizer.Add(wx.StaticText(exp_box, label='Gain auto:'),
            (4,0), flag=wx.ALIGN_CENTER_VERTICAL)
        exp_sub_sizer.Add(gain_auto, (4, 1), (1, 2), flag=wx.ALIGN_CENTER_VERTICAL)
        exp_sub_sizer.Add(wx.StaticText(exp_box, label='Gain:'), (5,0),
            flag=wx.ALIGN_CENTER_VERTICAL)
        exp_sub_sizer.Add(self.gain, (5,1), flag=wx.ALIGN_CENTER_VERTICAL)
        exp_sub_sizer.Add(gain_rbv, (5,2), flag=wx.ALIGN_CENTER_VERTICAL)


        state = epics.wx.PVText(exp_box,
            self._current_camera.PV('Acquire'), size=self._FromDIP((75, -1)),
            style=wx.ST_NO_AUTORESIZE)

        start_button = epics.wx.PVButton(exp_box,
            self._current_camera.PV('Acquire'), 1, label='Start')
        stop_button = epics.wx.PVButton(exp_box,
            self._current_camera.PV('Acquire'), 0, label='Stop')

        exp_sub_sizer2 = wx.BoxSizer(wx.HORIZONTAL)
        exp_sub_sizer2.Add(wx.StaticText(exp_box, label='Status:'),
            flag=wx.ALIGN_CENTER_VERTICAL)
        exp_sub_sizer2.Add(state, flag=wx.LEFT|wx.ALIGN_CENTER_VERTICAL,
            border=self._FromDIP(5))

        exp_sub_sizer3 = wx.BoxSizer(wx.HORIZONTAL)
        exp_sub_sizer3.Add(start_button, flag=wx.ALIGN_CENTER_VERTICAL)
        exp_sub_sizer3.Add(stop_button, flag=wx.LEFT|wx.ALIGN_CENTER_VERTICAL,
            border=self._FromDIP(15))


        exp_sizer = wx.StaticBoxSizer(exp_box, wx.VERTICAL)
        exp_sizer.Add(exp_sub_sizer, flag=wx.EXPAND|wx.ALL,
            border=self._FromDIP(5))
        exp_sizer.AddSpacer(10)
        exp_sizer.Add(exp_sub_sizer2, flag=wx.ALL, border=self._FromDIP(5))
        exp_sizer.Add(exp_sub_sizer3, flag=wx.LEFT|wx.RIGHT|wx.BOTTOM
            |wx.ALIGN_CENTER_HORIZONTAL, border=self._FromDIP(5))


        over_box = wx.StaticBox(ctrl_box, label='Overlay')

        use_over = epics.wx.PVEnumChoice(over_box, self._current_overlay.PV('Use'))

        over_sub_sizer1 = wx.BoxSizer(wx.HORIZONTAL)
        over_sub_sizer1.Add(wx.StaticText(over_box, label='Use:'),
            flag=wx.ALIGN_CENTER_VERTICAL)
        over_sub_sizer1.Add(use_over, flag=wx.ALIGN_CENTER_VERTICAL|wx.LEFT,
            border=self._FromDIP(5))

        centerx = custom_epics_widgets.PVFloatSpin2(over_box, self._current_overlay.PV('CenterX'),
            digits=0, size=self._FromDIP((80, -1)))
        centerx_rbv = epics.wx.PVText(over_box,
            self._current_overlay.PV('CenterX'), size=self._FromDIP((50, -1)),
            style=wx.ST_NO_AUTORESIZE)
        centery = custom_epics_widgets.PVFloatSpin2(over_box, self._current_overlay.PV('CenterY'),
            digits=0, size=self._FromDIP((80, -1)))
        centery_rbv = epics.wx.PVText(over_box,
            self._current_overlay.PV('CenterY'), size=self._FromDIP((50, -1)),
            style=wx.ST_NO_AUTORESIZE)
        sizex = custom_epics_widgets.PVFloatSpin2(over_box, self._current_overlay.PV('SizeX'),
            digits=0, size=self._FromDIP((80, -1)))
        sizex_rbv = epics.wx.PVText(over_box,
            self._current_overlay.PV('SizeX'), size=self._FromDIP((50, -1)),
            style=wx.ST_NO_AUTORESIZE)
        sizey = custom_epics_widgets.PVFloatSpin2(over_box, self._current_overlay.PV('SizeY'),
            digits=0, size=self._FromDIP((80, -1)))
        sizey_rbv = epics.wx.PVText(over_box,
            self._current_overlay.PV('SizeY'), size=self._FromDIP((50, -1)),
            style=wx.ST_NO_AUTORESIZE)
        widthx = custom_epics_widgets.PVFloatSpin2(over_box, self._current_overlay.PV('WidthX'),
            digits=0, size=self._FromDIP((80, -1)))
        widthx_rbv = epics.wx.PVText(over_box,
            self._current_overlay.PV('WidthX'), size=self._FromDIP((50, -1)),
            style=wx.ST_NO_AUTORESIZE)
        widthy = custom_epics_widgets.PVFloatSpin2(over_box, self._current_overlay.PV('WidthY'),
            digits=0, size=self._FromDIP((80, -1)))
        widthy_rbv = epics.wx.PVText(over_box,
            self._current_overlay.PV('WidthY'), size=self._FromDIP((50, -1)),
            style=wx.ST_NO_AUTORESIZE)

        over_sub_sizer2 = wx.GridBagSizer(hgap=self._FromDIP(5), vgap=self._FromDIP(5))
        over_sub_sizer2.Add(wx.StaticText(over_box, label='X'), (0,1), (1,2),
            flag=wx.ALIGN_CENTER_HORIZONTAL|wx.ALIGN_CENTER_VERTICAL)
        over_sub_sizer2.Add(wx.StaticText(over_box, label='Y'), (0,3), (1,2),
            flag=wx.ALIGN_CENTER_HORIZONTAL|wx.ALIGN_CENTER_VERTICAL)
        over_sub_sizer2.Add(wx.StaticText(over_box, label='Center:'), (1,0),
            flag=wx.ALIGN_CENTER_VERTICAL)
        over_sub_sizer2.Add(centerx, (1,1), flag=wx.ALIGN_CENTER_VERTICAL)
        over_sub_sizer2.Add(centerx_rbv, (1,2), flag=wx.ALIGN_CENTER_VERTICAL)
        over_sub_sizer2.Add(centery, (1,3), flag=wx.ALIGN_CENTER_VERTICAL)
        over_sub_sizer2.Add(centery_rbv, (1,4), flag=wx.ALIGN_CENTER_VERTICAL)
        over_sub_sizer2.Add(wx.StaticText(over_box, label='Extent:'), (2,0),
            flag=wx.ALIGN_CENTER_VERTICAL)
        over_sub_sizer2.Add(sizex, (2,1), flag=wx.ALIGN_CENTER_VERTICAL)
        over_sub_sizer2.Add(sizex_rbv, (2,2), flag=wx.ALIGN_CENTER_VERTICAL)
        over_sub_sizer2.Add(sizey, (2,3), flag=wx.ALIGN_CENTER_VERTICAL)
        over_sub_sizer2.Add(sizey_rbv, (2,4), flag=wx.ALIGN_CENTER_VERTICAL)
        over_sub_sizer2.Add(wx.StaticText(over_box, label='Width:'), (3,0),
            flag=wx.ALIGN_CENTER_VERTICAL)
        over_sub_sizer2.Add(widthx, (3,1), flag=wx.ALIGN_CENTER_VERTICAL)
        over_sub_sizer2.Add(widthx_rbv, (3,2), flag=wx.ALIGN_CENTER_VERTICAL)
        over_sub_sizer2.Add(widthy, (3,3), flag=wx.ALIGN_CENTER_VERTICAL)
        over_sub_sizer2.Add(widthy_rbv, (3,4), flag=wx.ALIGN_CENTER_VERTICAL)

        color_box = wx.StaticBox(over_box, label='Color')

        red = custom_epics_widgets.PVTextCtrl2(color_box,
            self._current_overlay.PV('Red'), size=self._FromDIP((75, -1)),
            validator=utils.CharValidator('int_te'), val_type='int')
        red_rbv = epics.wx.PVText(color_box,
            self._current_overlay.PV('Red_RBV'), size=self._FromDIP((50, -1)),
            style=wx.ST_NO_AUTORESIZE)
        green = custom_epics_widgets.PVTextCtrl2(color_box,
            self._current_overlay.PV('Green'), size=self._FromDIP((75, -1)),
            validator=utils.CharValidator('int_te'), val_type='int')
        green_rbv = epics.wx.PVText(color_box,
            self._current_overlay.PV('Green_RBV'), size=self._FromDIP((50, -1)),
            style=wx.ST_NO_AUTORESIZE)
        blue = custom_epics_widgets.PVTextCtrl2(color_box,
            self._current_overlay.PV('Blue'), size=self._FromDIP((75, -1)),
            validator=utils.CharValidator('int_te'), val_type='int')
        blue_rbv = epics.wx.PVText(color_box,
            self._current_overlay.PV('Blue_RBV'), size=self._FromDIP((50, -1)),
            style=wx.ST_NO_AUTORESIZE)

        color_sub_sizer = wx.FlexGridSizer(cols=3, vgap=self._FromDIP(5),
            hgap=self._FromDIP(5))
        color_sub_sizer.Add(wx.StaticText(color_box, label='Red:'),
            flag=wx.ALIGN_CENTER_VERTICAL)
        color_sub_sizer.Add(red, flag=wx.ALIGN_CENTER_VERTICAL)
        color_sub_sizer.Add(red_rbv, flag=wx.ALIGN_CENTER_VERTICAL)
        color_sub_sizer.Add(wx.StaticText(color_box, label='Green (mono):'),
            flag=wx.ALIGN_CENTER_VERTICAL)
        color_sub_sizer.Add(green, flag=wx.ALIGN_CENTER_VERTICAL)
        color_sub_sizer.Add(green_rbv, flag=wx.ALIGN_CENTER_VERTICAL)
        color_sub_sizer.Add(wx.StaticText(color_box, label='Blue:'),
            flag=wx.ALIGN_CENTER_VERTICAL)
        color_sub_sizer.Add(blue, flag=wx.ALIGN_CENTER_VERTICAL)
        color_sub_sizer.Add(blue_rbv, flag=wx.ALIGN_CENTER_VERTICAL)

        color_sizer = wx.StaticBoxSizer(color_box, wx.HORIZONTAL)
        color_sizer.Add(color_sub_sizer, flag=wx.ALL, border=self._FromDIP(5))
        color_sizer.AddStretchSpacer(1)

        overlay_sizer = wx.StaticBoxSizer(over_box, wx.VERTICAL)
        overlay_sizer.Add(over_sub_sizer1, flag=wx.ALL, border=self._FromDIP(5))
        overlay_sizer.Add(over_sub_sizer2, flag=wx.LEFT|wx.RIGHT|wx.BOTTOM,
            border=self._FromDIP(5))
        overlay_sizer.Add(color_sizer, flag=wx.EXPAND|wx.LEFT|wx.RIGHT|wx.BOTTOM,
            border=self._FromDIP(5))

        ctrl_sizer = wx.StaticBoxSizer(ctrl_box, wx.VERTICAL)
        ctrl_sizer.Add(exp_sizer, flag=wx.EXPAND|wx.ALL,
            border=self._FromDIP(5))
        ctrl_sizer.Add(overlay_sizer, flag=wx.EXPAND|wx.LEFT|wx.RIGHT|wx.BOTTOM,
            border=self._FromDIP(5))

        return ctrl_sizer

    def _on_camera_choice(self, evt):

        camera = self._camera_names[self.camera_choice.GetStringSelection()]

        self.top_sizer.Hide(self.current_ctrl_sizer)

        if camera in self._ctrl_sizers:
            self.current_ctrl_sizer = self._ctrl_sizers[camera]
            self.top_sizer.Show(self.current_ctrl_sizer)
        else:
            self.current_ctrl_sizer = self._create_control_sizer()
            self._ctrl_sizers[camera] = self.current_ctrl_sizer
            self.top_sizer.Add(self.current_ctrl_sizer, flag=wx.LEFT|wx.RIGHT|wx.BOTTOM,
                border=self._FromDIP(5))

        self.Layout()

    def _destroy_ctrl(self, widget):
        try:
            children = widget.GetChildren()
            for child in children:
                widget.Detach(child)
                self._destroy_ctrl(child)
            widget.Destroy()
        except Exception:
            widget.Destroy()

    def _on_exp_auto_change(self, value):
        if value.lower() == 'continuous':
            self.exp_time.Disable()
        else:
            self.exp_time.Enable()

    def _on_gain_auto_change(self, value):
        if value.lower() == 'continuous':
            self.gain.Disable()
        else:
            self.gain.Enable()

class CameraFrame(wx.Frame):
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

        camera_con_panel = CameraControlPanel('CameraControl', None, self)

        top_sizer.Add(camera_con_panel, flag=wx.EXPAND, proportion=1)

        self.SetSizer(top_sizer)


if __name__ == '__main__':

    app = wx.App()
    frame = CameraFrame(parent=None, title='Camera Control')
    frame.Show()
    app.MainLoop()
