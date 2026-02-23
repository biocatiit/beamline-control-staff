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

import os
import time
import sys
import string
import platform

import wx
from matplotlib.backends.backend_wxagg import NavigationToolbar2WxAgg

def get_mxdir():
    """Gets the top level install directory for MX."""
    try:
        mxdir = os.environ["MXDIR"]
    except:
        mxdir = "/opt/mx"   # This is the default location.

    return mxdir

def get_mpdir():
    """Construct the name of the Mp modules directory."""
    mxdir = get_mxdir()

    mp_modules_dir = os.path.join(mxdir, "lib", "mp")
    mp_modules_dir = os.path.normpath(mp_modules_dir)

    return mp_modules_dir

def set_mppath():
    """Puts the mp directory in the system path, if it isn't already."""
    os.environ['PATH']

    mp_dir = get_mpdir()

    if mp_dir not in os.environ['PATH']:
        os.environ["PATH"] = mp_dir+os.pathsep+os.environ["PATH"]
    if mp_dir not in sys.path:
        sys.path.append(mp_dir)


def file_follow(the_file, stop_event):
    """
    This function follows a file that is continuously being written to and
    provides a generator that gives each new line written into the file.

    Modified from: http://www.dabeaz.com/generators/follow.py

    :param file the_file: The file object to read lines from.
    :param threading.Event stop_event: A stop event that will end the generator,
        allowing any loops iterating on the generator to exit.
    """
    while True:
        if stop_event.is_set():
            break
        line = the_file.readline()
        if not line:
            time.sleep(0.001)
            continue
        yield line

class CharValidator(wx.Validator):
    ''' Validates data as it is entered into the text controls. '''

    def __init__(self, flag):
        wx.Validator.__init__(self)
        self.flag = flag
        self.Bind(wx.EVT_CHAR, self.OnChar)

        self.fname_chars = string.ascii_letters+string.digits+'_-'

        self.special_keys = [wx.WXK_BACK, wx.WXK_DELETE,
            wx.WXK_TAB, wx.WXK_NUMPAD_TAB, wx.WXK_NUMPAD_ENTER]

    def Clone(self):
        '''Required Validator method'''
        return CharValidator(self.flag)

    def Validate(self, win):
        return True

    def TransferToWindow(self):
        return True

    def TransferFromWindow(self):
        return True

    def OnChar(self, event):
        keycode = int(event.GetKeyCode())
        if keycode < 256 and keycode not in self.special_keys:
            #print keycode
            key = chr(keycode)
            #print key
            if self.flag == 'int' and key not in string.digits:
                return
            elif self.flag == 'int_te' and key not in string.digits+'\n\r':
                return
            elif self.flag == 'float' and key not in string.digits+'.':
                return
            elif self.flag == 'fname' and key not in self.fname_chars:
                return
            elif self.flag == 'float_te' and key not in string.digits+'.\n\r':
                return
            elif self.flag == 'float_neg' and key not in string.digits+'.-':
                return
            elif self.flag == 'float_neg_te' and key not in string.digits+'.-\n\r':
                return
        event.Skip()

class CustomPlotToolbar(NavigationToolbar2WxAgg):
    """
    A custom plot toolbar that displays the cursor position (or other text)
    in addition to the usual controls.
    """
    def __init__(self, canvas):
        """
        Initializes the toolbar.

        :param wx.Window parent: The parent window
        :param matplotlib.Canvas: The canvas associated with the toolbar.
        """
        NavigationToolbar2WxAgg.__init__(self, canvas)

        self.status = wx.StaticText(self, label='')

        self.AddControl(self.status)

    def set_status(self, status):
        """
        Called to set the status text in the toolbar, i.e. the cursor position
        on the plot.
        """
        self.status.SetLabel(status)

def set_best_size(window, shrink=False):

    best_size = window.GetBestSize()
    current_size = window.GetSize()

    client_display = wx.GetClientDisplayRect()

    best_width = min(best_size.GetWidth(), client_display.Width)
    best_height = min(best_size.GetHeight(), client_display.Height)

    if best_size.GetWidth() > current_size.GetWidth():
        best_size.SetWidth(best_width)
    else:
        if not shrink:
            best_size.SetWidth(current_size.GetWidth())
        else:
            best_size.SetWidth(best_width)

    if best_size.GetHeight() > current_size.GetHeight():
        best_size.SetHeight(best_height)
    else:
        if not shrink:
            best_size.SetHeight(current_size.GetHeight())
        else:
            best_size.SetHeight(best_height)

    window.SetSize(best_size)

class FloatSpinEvent(wx.PyCommandEvent):

    def __init__(self, evtType, id, obj):

        wx.PyCommandEvent.__init__(self, evtType, id)
        self.value = 0
        self.obj = obj

    def GetValue(self):
        return self.value

    def SetValue(self, value):
        self.value = value

    def GetEventObject(self):
        return self.obj

myEVT_MY_SPIN = wx.NewEventType()
EVT_MY_SPIN = wx.PyEventBinder(myEVT_MY_SPIN, 1)

class IntSpinCtrl(wx.Panel):

    def __init__(self, parent, my_id=wx.ID_ANY, my_min=None, my_max=None,
        TextLength=40, **kwargs):

        wx.Panel.__init__(self, parent, my_id, **kwargs)

        if platform.system() != 'Windows':
            self.ScalerButton = wx.SpinButton(self, style=wx.SP_VERTICAL)
        else:
            self.ScalerButton = wx.SpinButton(self, size=self._FromDIP((-1,22)),
                style=wx.SP_VERTICAL)

        self.ScalerButton.Bind(wx.EVT_SET_FOCUS, self.OnScaleChange)
        self.ScalerButton.Bind(wx.EVT_SPIN_UP, self.OnSpinUpScale)
        self.ScalerButton.Bind(wx.EVT_SPIN_DOWN, self.OnSpinDownScale)
        self.ScalerButton.SetRange(-99999, 99999)
        self.max = my_max
        self.min = my_min

        if platform.system() != 'Windows':
            self.Scale = wx.TextCtrl(self, value=str(my_min),
                size=self._FromDIP((TextLength,-1)), style=wx.TE_PROCESS_ENTER,
                validator=CharValidator('int_te'))
        else:
            self.Scale = wx.TextCtrl(self, value=str(my_min),
                size=self._FromDIP((TextLength,22)), style=wx.TE_PROCESS_ENTER,
                validator=CharValidator('int_te'))

        self.Scale.Bind(wx.EVT_KILL_FOCUS, self.OnScaleChange)
        self.Scale.Bind(wx.EVT_TEXT_ENTER, self.OnScaleChange)
        self.Scale.Bind(wx.EVT_TEXT, self.OnText)

        sizer = wx.BoxSizer()

        sizer.Add(self.Scale, 0, wx.RIGHT, 1)
        sizer.Add(self.ScalerButton, 0)

        self.oldValue = 0

        self.SetSizer(sizer)

        self.ScalerButton.SetValue(0)

        self.Scale.SetBackgroundColour(wx.NullColour)
        self.Scale.SetModified(False)

    def _FromDIP(self, size):
        # This is a hack to provide easy back compatibility with wxpython < 4.1
        try:
            return self.FromDIP(size)
        except Exception:
            return size

    def CastFloatSpinEvent(self):
        event = FloatSpinEvent(myEVT_MY_SPIN, self.GetId(), self)
        event.SetValue(self.Scale.GetValue())
        self.GetEventHandler().ProcessEvent(event)

    def OnText(self, event):
        """
        Called when text is changed in the box. Changes the background
        color of the text box to indicate there are unset changes.
        """
        self.Scale.SetBackgroundColour("yellow")
        self.Scale.SetModified(True)

    def OnScaleChange(self, event):
        self.ScalerButton.SetValue(0) # Resit spinbutton position for button to work in linux

        val = self.Scale.GetValue()

        try:
            float(val)
        except ValueError:
            return

        if self.max is not None:
            if float(val) > self.max:
                self.Scale.ChangeValue(str(self.max))
        if self.min is not None:
            if float(val) < self.min:
                self.Scale.ChangeValue(str(self.min))

        #if val != self.oldValue:
        self.oldValue = val
        self.CastFloatSpinEvent()

        event.Skip()

        self.Scale.SetBackgroundColour(wx.NullColour)
        self.Scale.SetModified(False)

    def OnSpinUpScale(self, event):
        self.ScalerButton.SetFocus()    # Just to remove focus from the bgscaler to throw kill_focus event and update

        val = self.Scale.GetValue()
        try:
            float(val)
        except ValueError:
            if self.min is not None:
                val = self.min -1
            elif self.max is not None:
                val = self.max -1
            else:
                return

        newval = int(val) + 1

        # Reset spinbutton counter. Fixes bug on MAC
        if self.ScalerButton.GetValue() > 90000:
            self.ScalerButton.SetValue(0)

        if self.max is not None:
            if newval > self.max:
                self.Scale.ChangeValue(str(self.max))
            else:
                self.Scale.ChangeValue(str(newval))
        else:
            self.Scale.ChangeValue(str(newval))

        self.oldValue = newval
        wx.CallAfter(self.CastFloatSpinEvent)

        self.Scale.SetBackgroundColour(wx.NullColour)
        self.Scale.SetModified(False)

    def OnSpinDownScale(self, event):
        #self.ScalerButton.SetValue(80)   # This breaks the spinbutton on Linux
        self.ScalerButton.SetFocus()    # Just to remove focus from the bgscaler to throw kill_focus event and update

        val = self.Scale.GetValue()

        try:
            float(val)
        except ValueError:
            if self.max is not None:
                val = self.max +1
            elif self.min is not None:
                val = self.min +1
            else:
                return

        newval = int(val) - 1

        # Reset spinbutton counter. Fixes bug on MAC
        if self.ScalerButton.GetValue() < -90000:
            self.ScalerButton.SetValue(0)

        if self.min is not None:
            if newval < self.min:
                self.Scale.ChangeValue(str(self.min))
            else:
                self.Scale.ChangeValue(str(newval))
        else:
            self.Scale.ChangeValue(str(newval))

        self.oldValue = newval
        wx.CallAfter(self.CastFloatSpinEvent)

        self.Scale.SetBackgroundColour(wx.NullColour)
        self.Scale.SetModified(False)

    def GetValue(self):
        value = self.Scale.GetValue()

        try:
            return int(value)
        except ValueError:
            return value

    def SetValue(self, value):
        self.Scale.SetValue(str(value))

    def ChangeValue(self, value):
        self.Scale.ChangeValue(str(value))

    def SetRange(self, minmax):
        self.max = minmax[1]
        self.min = minmax[0]

    def GetRange(self):
        return (self.min, self.max)

    def SetMin(self, value):
        self.min = int(value)

    def SetMax(self, value):
        self.max = int(value)

    def SafeSetValue(self, val):
        if not self.Scale.IsModified():
            self.SetValue(val)

    def SafeChangeValue(self, val):
        if not self.Scale.IsModified():
            self.ChangeValue(val)

class FloatSpinCtrl(wx.Panel):

    def __init__(self, parent, my_id=-1, initValue=None, min_val=None, max_val=None,
        button_style = wx.SP_VERTICAL, TextLength=45, never_negative=False,
        **kwargs):

        wx.Panel.__init__(self, parent, my_id, **kwargs)

        if initValue is None:
            initValue = '1.00'

        self.defaultScaleDivider = 100
        self.ScaleDivider = 100

        if platform.system() != 'Windows':
            self.ScalerButton = wx.SpinButton(self, -1, style = button_style)
        else:
            self.ScalerButton = wx.SpinButton(self, -1,
                size=self._FromDIP((-1, 22)), style=button_style)
        self.ScalerButton.Bind(wx.EVT_SET_FOCUS, self.OnFocusChange)
        self.ScalerButton.Bind(wx.EVT_SPIN_UP, self.OnSpinUpScale)
        self.ScalerButton.Bind(wx.EVT_SPIN_DOWN, self.OnSpinDownScale)
        self.ScalerButton.SetRange(-99999, 99999)   #Needed for proper function of button on Linux

        self.max = max_val
        self.min = min_val

        if never_negative:
            if self.min is None:
                self.min = 0.0
            else:
                self.min = max(self.min, 0.0)

        self._never_negative = never_negative

        if platform.system() != 'Windows':
            self.Scale = wx.TextCtrl(self, -1, initValue,
                size=self._FromDIP((TextLength,-1)), style=wx.TE_PROCESS_ENTER,
                validator=CharValidator('float_te'))
        else:
            self.Scale = wx.TextCtrl(self, -1, initValue,
                size=self._FromDIP((TextLength,22)), style=wx.TE_PROCESS_ENTER,
                validator=CharValidator('float_te'))

        self.Scale.Bind(wx.EVT_KILL_FOCUS, self.OnFocusChange)
        self.Scale.Bind(wx.EVT_TEXT_ENTER, self.OnEnter)

        sizer = wx.BoxSizer()

        sizer.Add(self.Scale, 1, wx.RIGHT, border=self._FromDIP(1))
        sizer.Add(self.ScalerButton, 0)

        self.oldValue = float(initValue)

        self.SetSizer(sizer)

        self.ScalerButton.SetValue(0)

    def _FromDIP(self, size):
        # This is a hack to provide easy back compatibility with wxpython < 4.1
        try:
            return self.FromDIP(size)
        except Exception:
            return size

    def CastFloatSpinEvent(self):
        event = FloatSpinEvent(myEVT_MY_SPIN, self.GetId(), self)
        event.SetValue( self.Scale.GetValue() )
        self.GetEventHandler().ProcessEvent(event)

    def OnFocusChange(self, event):

        val = self.Scale.GetValue()

        try:
             float(val)
        except ValueError:
            return

        self.Scale.SetModified(False)

        self.CastFloatSpinEvent()

        event.Skip()

    def OnEnter(self, event):
        self.OnScaleChange(None)
        # self.Scale.SelectAll()

        self.Scale.SetModified(False)
        self.CastFloatSpinEvent()
        event.Skip()

    def OnScaleChange(self, event):

        val = self.Scale.GetValue()
        val = val.replace(',', '.')

        if self.max is not None:
            if float(val) > self.max:
                self.Scale.SetValue(str(self.max ))
        if self.min is not None:
            if float(val) < self.min:
                self.Scale.SetValue(str(self.min))

        try:
            self.num_of_digits = len(val.split('.')[1])

            if self.num_of_digits == 0:
                self.ScaleDivider = self.defaultScaleDivider
            else:
                self.ScaleDivider = math.pow(10, self.num_of_digits)

        except IndexError:
            self.ScaleDivider = 1.0
            self.num_of_digits = 0

    def OnSpinUpScale(self, event):

        self.OnScaleChange(None)

        val = self.Scale.GetValue()
        val = float(val.replace(',', '.'))

        # Reset spinbutton counter. Fixes bug on MAC
        if self.ScalerButton.GetValue() > 90000:
            self.ScalerButton.SetValue(0)

        try:
            newval = self.find_new_val_up(val)

        except ValueError:
            self.CastFloatSpinEvent()
            return

        if self.num_of_digits > 0:
            newval_str = ("%." + str(self.num_of_digits) + "f") %  newval
        else:
            newval_str = ("%d") %  newval

        self.Scale.SetValue(newval_str)
        self.Scale.SetModified(False)
        self.CastFloatSpinEvent()

    def find_new_val_up(self, val):

        if self.max is not None and val > self.max:
            newval = self.max

        elif self.max is not None and val == self.max:
            newval = val

        else:
            newval = val + (1./self.ScaleDivider)

            if self.max is not None and newval > self.max:
                self.num_of_digits = self.num_of_digits + 1
                self.ScaleDivider = math.pow(10, self.num_of_digits)

                newval = self.find_new_val_up(val)

        return newval


    def find_new_val_down(self, val):
        if self.min is not None and val < self.min and not self._never_negative:
            newval = self.min

        elif self.min is not None and val == self.min and not self._never_negative:
            newval = val

        else:
            newval = val - (1./self.ScaleDivider)

            if self.min is not None and newval < self.min:
                self.num_of_digits = self.num_of_digits + 1
                self.ScaleDivider = math.pow(10, self.num_of_digits)

                newval = self.find_new_val_down(val)

            elif self._never_negative and newval == 0.0:
                self.num_of_digits = self.num_of_digits + 1
                self.ScaleDivider = math.pow(10, self.num_of_digits)

                newval = float(val) - (1./self.ScaleDivider)

        return newval


    def _showInvalidNumberError(self):
        wx.CallAfter(wx.MessageBox, 'The entered value is invalid. Please remove non-numeric characters.', 'Invalid Value Error', style = wx.ICON_ERROR)

    def OnSpinDownScale(self, event):

        self.OnScaleChange(None)

        val = self.Scale.GetValue()
        val = float(val.replace(',', '.'))

        # Reset spinbutton counter. Fixes bug on MAC
        if self.ScalerButton.GetValue() < -90000:
            self.ScalerButton.SetValue(0)

        try:
            newval = self.find_new_val_down(val)

        except ValueError:
            self.CastFloatSpinEvent()
            return

        if self.num_of_digits > 0:
            newval_str = ("%." + str(self.num_of_digits) + "f") %  newval
        else:
            newval_str = ("%d") %  newval

        self.Scale.SetValue(str(newval_str))
        self.Scale.SetModified(False)
        self.CastFloatSpinEvent()

    def GetValue(self):
        value = self.Scale.GetValue()
        return value

    def SetValue(self, value):
        self.Scale.SetValue(str(value))
        self.Scale.SetModified(False)

    def SetRange(self, minmax):
        self.max = float(minmax[1])
        self.min = float(minmax[0])

    def GetRange(self):
        return (self.min, self.max)

    def SafeSetValue(self, val):
        if not self.Scale.IsModified():
            self.SetValue(val)

    def SafeChangeValue(self, val):
        if not self.Scale.IsModified():
            self.ChangeValue(val)

class FloatSliderEvent(wx.PyCommandEvent):

    def __init__(self, evtType, id, obj):

        wx.PyCommandEvent.__init__(self, evtType, id)
        self.value = 0
        self.obj = obj

    def GetValue(self):
        return self.value

    def SetValue(self, value):
        self.value = value

    def GetEventObject(self):
        return self.obj

myEVT_MY_SCROLL = wx.NewEventType()
EVT_MY_SCROLL = wx.PyEventBinder(myEVT_MY_SCROLL, 1)

class FloatSlider(wx.Slider):

    def __init__(self, parent, id, value, minval, maxval, res,
                 size=wx.DefaultSize, style=wx.SL_HORIZONTAL,
                 name='floatslider'):
        self._value = value
        self._min = minval
        self._max = maxval
        self._res = res
        ival, imin, imax = [round(v/res) for v in (value, minval, maxval)]
        self._islider = super(FloatSlider, self)
        self._islider.__init__(
            parent, id, ival, imin, imax, size=size, style=style, name=name
        )
        self.Bind(wx.EVT_SCROLL, self._OnScroll)

    def _OnScroll(self, event):
        ival = self._islider.GetValue()
        imin = self._islider.GetMin()
        imax = self._islider.GetMax()
        if ival == imin:
            self._value = self._min
        elif ival == imax:
            self._value = self._max
        else:
            self._value = ival * self._res
        # event.Skip()
        # print('OnScroll: value=%f, ival=%d' % (self._value, ival))
        event = FloatSliderEvent(myEVT_MY_SCROLL, self.GetId(), self)
        event.SetValue(self._value)
        self.GetEventHandler().ProcessEvent(event)

    def GetValue(self):
        return self._value

    def GetMin(self):
        return self._min

    def GetMax(self):
        return self._max

    def GetRes(self):
        return self._res

    def SetValue(self, value):
        self._islider.SetValue(round(value/self._res))
        self._value = value

    def SetMin(self, minval):
        self._islider.SetMin(round(minval/self._res))
        self._min = minval

    def SetMax(self, maxval):
        self._islider.SetMax(round(maxval/self._res))
        self._max = maxval

    def SetRes(self, res):
        self._islider.SetRange(round(self._min/res), round(self._max/res))
        self._islider.SetValue(round(self._value/res))
        self._res = res

    def SetRange(self, minval, maxval):
        self._islider.SetRange(round(minval/self._res), round(maxval/self._res))
        self._min = minval
        self._max = maxval
