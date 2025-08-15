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

import wx
import wx.lib.agw.floatspin as floatspin
import six

import epics, epics.wx, epics.wx.wxlib, epics.wx.wxlib

import utils


class PVTextLabeled(epics.wx.PVText):
    """ Static text for displaying a PV value,
        with callback for automatic updates
        By default the text colour will change on alarm states.
        This can be overriden or disabled as constructor
        parameters
        """

    def __init__(self, parent, pv=None, as_string=True,
                 font=None, fg=None, bg=None, style=None,
                 minor_alarm="DARKRED", major_alarm="RED",
                 invalid_alarm="ORANGERED", auto_units=False, units="",
                 scale=1., sig_fig=0, do_round=False, offset=0., **kw):

        """
        Create a new pvText
        minor_alarm, major_alarm & invalid_alarm are all text colours
        that will be set depending no the alarm state of the target
        PV. Set to None if you want no highlighting in that alarm state.
        auto_units means the PV value will be displayed with the EGU
        "engineering units" as a suffix. Alternately, you can specify
        an explicit unit string.
        """

        epics.wx.PVText.__init__(self, parent, pv, as_string, font, fg, bg, style,
            minor_alarm, major_alarm, invalid_alarm, auto_units, units, **kw)

        self.scale = scale
        self.offset = offset
        self.sig_fig = sig_fig
        self.do_round = do_round

    def SetTranslations(self, translations):
        """
        Pass a dictionary of value->value translations here if you want some P
        PV values to automatically appear in the event callback as a different
        value.
        ie, to override PV value 0.0 to say "Disabled", call this method as
        control.SetTranslations({ 0.0 : "Disabled" })
        It is recommended that you use this function only when it is not
        possible to change the PV value in the database, or set a string
        value in the database.
        """
        self._translations = translations

    def SetForegroundColourTranslations(self, translations):
        """
        Pass a dictionary of value->colour translations here if you want the
        control to automatically set foreground colour based on PV value.
        Values used to lookup colours will be string values if available,
        but will otherwise be the raw PV value.
        Colour values in the dictionary may be strings or wx.Colour objects.
        """
        self._fg_colour_translations = translations

    def _SetValue(self, value):
        "set widget label"
        if self.auto_units and self.pv.units:
            self.units = " " + self.pv.units

        if value is not None:
            if value in self._translations:
                value = self._translations[value]

            if self.scale != 1:
                value = float(value)*self.scale

            if self.offset != 0:
                value = float(value) + self.offset

            if self.do_round:
                value = round(float(value), self.sig_fig)

                if self.sig_fig == 0:
                    value = int(value)

            new_label = "%s%s" % (value, self.units)

            if self.GetLabel() != new_label:
                self.SetLabel(new_label)

                colour = None
                if (self._fg_colour_translations is not None and
                    value in self._fg_colour_translations):
                    colour = self._fg_colour_translations[value]
                    self.OverrideForegroundColour(colour)
                elif (self._fg_colour_translations is not None and
                    value not in self._fg_colour_translations):
                    self.OverrideForegroundColour(colour)


class PVButton2(wx.Button, epics.wx.wxlib.PVCtrlMixin):
    """ A Button linked to a PV. When the button is pressed, a certain value
        is written to the PV (useful for momentary PVs with HIGH= set.)
    """
    def __init__(self, parent, pv=None, pushValue=1,
                 disablePV=None, disableValue=1, disableOnPushVal=False, **kw):
        """
        pv = pv to write back to
        pushValue = value to write when button is pressed
        disablePV = read this PV in order to disable the button
        disableValue = disable the button if/when the disablePV has this value
        """
        wx.Button.__init__(self, parent, **kw)
        epics.wx.wxlib.PVCtrlMixin.__init__(self, pv=pv, font="", fg=None, bg=None)
        self.pushValue = pushValue
        self.Bind(wx.EVT_BUTTON, self.OnPress)
        if isinstance(disablePV, six.string_types):
            disablePV = epics.get_pv(disablePV)
            disablePV.connect()
        self.disablePV = disablePV
        self.disableValue = disableValue
        if disablePV is not None:
            ncback = len(self.disablePV.callbacks) + 1
            self.disablePV.add_callback(self._disableEvent, wid=self.GetId(),
                                        cb_info=ncback)
        self.maskedEnabled = True
        self.disableOnPushVal = disableOnPushVal

    def Enable(self, value=None):
        "enable button"
        if value is not None:
            self.maskedEnabled = value
        self._UpdateEnabled()

    @epics.wx.EpicsFunction
    def _UpdateEnabled(self):
        "epics function, called by event handler"
        enableValue = self.maskedEnabled
        if self.disablePV is not None and \
           (self.disablePV.get() == self.disableValue):
            enableValue = False
        if (self.pv is not None and (self.pv.get() == self.pushValue)
            and self.disableOnPushVal):
            enableValue = False
        wx.Button.Enable(self, enableValue)

    @epics.wx.DelayedEpicsCallback
    def _disableEvent(self, **kw):
        "disable event handler"
        self._UpdateEnabled()

    def _SetValue(self, event):
        "set value"
        self._UpdateEnabled()

    @epics.wx.EpicsFunction
    def OnPress(self, event):
        "button press event handler"
        self.pv.put(self.pushValue)


class PVTextMonitor(epics.wx.PVText):
    """ Static text for displaying a PV value,
        with callback for automatic updates
        By default the text colour will change on alarm states.
        This can be overriden or disabled as constructor
        parameters
        """

    def __init__(self, parent, pv=None, as_string=True,
                 font=None, fg=None, bg=None, style=None,
                 minor_alarm="DARKRED", major_alarm="RED",
                 invalid_alarm="ORANGERED", auto_units=False, units="",
                 scale=1., sig_fig=0, do_round=False, monitor_pv=None,
                 monitor_threshold=None, **kw):

        """
        Create a new pvText
        minor_alarm, major_alarm & invalid_alarm are all text colours
        that will be set depending no the alarm state of the target
        PV. Set to None if you want no highlighting in that alarm state.
        auto_units means the PV value will be displayed with the EGU
        "engineering units" as a suffix. Alternately, you can specify
        an explicit unit string.
        """

        epics.wx.PVText.__init__(self, parent, pv, as_string, font, fg, bg, style,
            minor_alarm, major_alarm, invalid_alarm, auto_units, units, **kw)

        self.scale = scale
        self.sig_fig = sig_fig
        self.do_round = do_round

        self.monitor_value = None
        self.monitor_pv = monitor_pv
        self.monitor_pv.add_callback(self._on_monitor_pv)
        self.monitor_pv.connection_callbacks.append(self._on_monitor_pv_connect)

        if self.monitor_pv.connected:
            self._on_monitor_pv_connect(value=self.monitor_pv.get())
        self.monitor_threshold = monitor_threshold

    def SetTranslations(self, translations):
        """
        Pass a dictionary of value->value translations here if you want some
        PV values to automatically appear in the event callback as a different
        value.
        ie, to override PV value 0.0 to say "Disabled", call this method as
        control.SetTranslations({ 0.0 : "Disabled" })
        It is recommended that you use this function only when it is not
        possible to change the PV value in the database, or set a string
        value in the database.
        """
        self._translations = translations

    def SetForegroundColourTranslations(self, translations):
        """
        Pass a dictionary of value->colour translations here if you want the
        control to automatically set foreground colour based on PV value.
        Values used to lookup colours will be string values if available,
        but will otherwise be the raw PV value.
        Colour values in the dictionary may be strings or wx.Colour objects.
        """
        self._fg_colour_translations = translations

    def _SetValue(self, value):
        "set widget label"
        if self.auto_units and self.pv.units:
            self.units = " " + self.pv.units

        if value is not None:
            if value in self._translations:
                value = self._translations[value]

            if self.scale != 1:
                value = float(value)*self.scale

            if self.do_round:
                value = round(float(value), self.sig_fig)

                if self.sig_fig == 0:
                    value = int(value)

            new_label = "%s%s" % (value, self.units)

            if self.GetLabel() != new_label:
                self.SetLabel(new_label)

                colour = None
                if (self._fg_colour_translations is not None and
                    value in self._fg_colour_translations):
                    colour = self._fg_colour_translations[value]
                    self.OverrideForegroundColour(colour)
                elif (self._fg_colour_translations is not None and
                    value not in self._fg_colour_translations):
                    self.OverrideForegroundColour(colour)

            if self.monitor_value is not None:
                try:
                    if (abs(float(value) - float(self.monitor_value))
                        > self.monitor_threshold):
                        self.OverrideForegroundColour('red')
                    else:
                        self.OverrideForegroundColour(None)
                except Exception:
                    pass

    @epics.wx.EpicsFunction
    def _on_monitor_pv(self, **kwargs):
        self.monitor_value = kwargs['value']

        try:
            if (abs(float(self.GetLabel()) - float(self.monitor_value))
                > self.monitor_threshold):
                self.OverrideForegroundColour('red')
            else:
                self.OverrideForegroundColour(None)
        except Exception:
            pass


    def _on_monitor_pv_connect(self, **kwargs):
        self.monitor_value = kwargs['value']

        try:
            if (abs(float(self.GetLabel()) - float(self.monitor_value))
                > self.monitor_threshold):
                self.OverrideForegroundColour('red')
            else:
                self.OverrideForegroundColour(None)
        except Exception:
            pass


class PVTextCtrl2(epics.wx.PVTextCtrl):
    """ Static text for displaying a PV value,
        with callback for automatic updates
        By default the text colour will change on alarm states.
        This can be overriden or disabled as constructor
        parameters
        """

    def __init__(self, parent, pv=None, font=None, fg=None, bg=None,
            dirty_timeout=2500, scale=1., offset=0., val_type='float', **kw):

        """
        Create a new pvText
        minor_alarm, major_alarm & invalid_alarm are all text colours
        that will be set depending no the alarm state of the target
        PV. Set to None if you want no highlighting in that alarm state.
        auto_units means the PV value will be displayed with the EGU
        "engineering units" as a suffix. Alternately, you can specify
        an explicit unit string.
        """

        epics.wx.PVTextCtrl.__init__(self, parent, pv, font, fg, bg, dirty_timeout,
            **kw)

        self.scale = scale
        self.offset = offset
        self.val_type = val_type

    @epics.wx.DelayedEpicsCallback
    def OnEpicsConnect(self, pvname=None, conn=None, pv=None):
        """Connect Callback:
             Enable/Disable widget on change in connection status
        """
        PVMixin.OnEpicsConnect(self, pvname, conn, pv)

        if self.IsEnabled():
            action = getattr(self, 'Enable', None)
        else:
            action = getattr(self, 'Disable', None)
        bgcol = self._connect_bgcol
        fgcol = self._connect_fgcol
        if not conn:
            action = getattr(self, 'Disable', None)
            self._connect_bgcol = self.GetBackgroundColour()
            self._connect_fgcol = self.GetForegroundColour()
            bgcol = wx.Colour(240, 240, 210)
            fgcol = wx.Colour(200, 100, 100)
        if action is not None:
            self.SetBackgroundColour(bgcol)
            self.SetForegroundColour(fgcol)
            action()

    def SetValue(self, value):
        value = (float(value)- self.offset)/self.scale
        if self.val_type == 'int':
            value = str(int(value))
        else:
            value = str(value)
        self._caput(value)

    def _SetValue(self, value):
        "set widget label"
        value = float(value)*self.scale + self.offset
        if self.val_type == 'int':
            value = str(int(value))
        else:
            value = str(value)
        wx.TextCtrl.SetValue(self, value)

    def OnChar(self, event):
        "char event handler"
        try:
            key_code = event.KeyCode
        except Exception:
            key_code = None
        if key_code == wx.WXK_RETURN:
            self.OnWriteback()
        else:
            self.SetBackgroundColour("yellow")
            if self.dirty_timeout is not None:
                self.dirty_writeback_timer.Start(self.dirty_timeout)
            event.Skip()

    def OnWriteback(self, event=None):
        """ writeback the currently displayed value to the PV """
        self.dirty_writeback_timer.Stop()
        entry = str(self.GetValue().strip())
        self.SetValue(entry)
        self.SetBackgroundColour(wx.NullColour)

class PVEnumChoice2(epics.wx.PVEnumChoice):
    """ a dropdown choice for Epics ENUM controls """

    def __init__(self, parent, pv=None, on_change=None, **kw):
        epics.wx.PVEnumChoice.__init__(self, parent, pv, **kw)

        self.on_change = on_change

    @epics.wx.EpicsFunction
    def SetPV(self, pv=None):
        "set pv, either an epics.PV object or a pvname"
        if pv is None:
            return
        if isinstance(pv, epics.PV):
            self.pv = pv
        elif isinstance(pv, str):
            self.pv = epics.get_pv(pv)
            self.pv.connect()

        epics.poll()
        self.pv.connection_callbacks.append(self.OnEpicsConnect)

        self.pv.get_ctrlvars()

        self.OnPVChange(self.pv.get(as_string=True))
        ncback = len(self.pv.callbacks) + 1
        self.pv.add_callback(self._pvEvent, wid=self.GetId(), cb_info=ncback)

        self.Bind(wx.EVT_CHOICE, self._onChoice)

        pv_value = self.pv.get(as_string=True)
        enum_strings = self.pv.enum_strs

        self.Clear()
        self.AppendItems(enum_strings)
        self.SetStringSelection(pv_value)

        self.on_change(pv_value)


    @epics.wx.DelayedEpicsCallback
    def _pvEvent(self, pvname=None, value=None, **kw):
        "pv event handler"
        if value is not None:
            self.SetSelection(value)
            self.on_change(self.pv.enum_strs[value])


class PVFloatSpin2(epics.wx.PVFloatSpin):
    """
    A FloatSpin (floating-point-aware SpinCtrl) linked to a PV,
    both reads and writes the PV on changes.

    """
    def __init__(self, parent, pv=None, deadTime=2500,
                 min_val=None, max_val=None, increment=1.0, digits=-1, **kw):
        """
        Most arguments are common with FloatSpin.

        Additional Arguments:
        pv = pv to set
        deadTime = delay (ms) between user typing a value into the field,
        and it being set to the PV

        """
        floatspin.FloatSpin.__init__(self, parent, increment=increment,
                                     min_val=min_val, max_val=max_val,
                                     digits=digits, **kw)
        epics.wx.wxlib.PVCtrlMixin.__init__(self, pv=pv, font="", fg=None, bg=None)
        # floatspin.EVT_FLOATSPIN(parent, self.GetId(), self.OnSpin)
        self.Bind(floatspin.EVT_FLOATSPIN, self.OnSpin)

        self.deadTimer = wx.Timer(self)
        self.deadTime = deadTime
        self.deadTimer.Bind(wx.EVT_TIMER, self.OnTimeout)
