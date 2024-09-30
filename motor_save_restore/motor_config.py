from builtins import object, range, map
from io import open

import logging
import logging.handlers as handlers
import sys
import os
import pathlib


if __name__ != '__main__':
    logger = logging.getLogger(__name__)

import wx
import wx.lib.agw.ultimatelistctrl as ULC
import epics, epics.wx, epics.autosave

class MotorConfigFrame(wx.Frame):
    def __init__(self, settings, *args, **kwargs):
        super(MotorConfigFrame, self).__init__(*args, **kwargs)
        logger.debug('Setting up the MotorConfigFrame')

        self.settings = settings
        self._base_path = pathlib.Path(__file__).parent.resolve()
        self._last_path = os.path.join(self._base_path, 'motor_configs')

        self.Bind(wx.EVT_CLOSE, self._on_exit)

        self._create_layout()

        self.SetMinSize(self._FromDIP((400, 500)))
        self.Fit()
        self.Raise()

    def _FromDIP(self, size):
        # This is a hack to provide easy back compatibility with wxpython < 4.1
        try:
            return self.FromDIP(size)
        except Exception:
            return size

    def _create_layout(self):
        """Creates the layout"""
        top_panel = wx.Panel(self)

        panel_sizer = wx.BoxSizer(wx.VERTICAL)

        motor_box = wx.StaticBox(top_panel, label='Motors')

        self._create_pv_list(motor_box)

        motor_sizer = wx.StaticBoxSizer(motor_box, wx.VERTICAL)
        motor_sizer.Add(self.pv_list, flag=wx.EXPAND|wx.ALL, proportion=1,
            border=self._FromDIP(2))

        save_config = wx.Button(top_panel, label='Save Config.')
        save_config.Bind(wx.EVT_BUTTON, self._on_save_config)

        load_config = wx.Button(top_panel, label='Load Config.')
        load_config.Bind(wx.EVT_BUTTON, self._on_load_config)

        view_config = wx.Button(top_panel, label='View Config.')
        view_config.Bind(wx.EVT_BUTTON, self._on_view_config)

        button_sizer = wx.BoxSizer(wx.HORIZONTAL)
        button_sizer.Add(save_config, flag=wx.RIGHT, border=self._FromDIP(5))
        button_sizer.Add(load_config, flag=wx.RIGHT, border=self._FromDIP(5))
        button_sizer.Add(view_config)


        panel_sizer.Add(motor_sizer, flag=wx.EXPAND, proportion=1)
        panel_sizer.Add(button_sizer, flag=wx.TOP|wx.ALIGN_CENTER_HORIZONTAL,
            border=self._FromDIP(5))

        top_panel.SetSizer(panel_sizer)

        top_sizer = wx.BoxSizer(wx.VERTICAL)
        top_sizer.Add(top_panel, flag=wx.EXPAND|wx.ALL, proportion=1,
            border=self._FromDIP(5))

        self.SetSizer(top_sizer)

    def _create_pv_list(self, parent):
        self.pv_list = ULC.UltimateListCtrl(parent, agwStyle=ULC.ULC_SINGLE_SEL|
            ULC.ULC_NO_ITEM_DRAG|ULC.ULC_REPORT|ULC.ULC_HAS_VARIABLE_ROW_HEIGHT)

        self.pv_list.InsertColumn(0, "PV")
        self.pv_list.InsertColumn(1, "Description", width=200)

        for item in self.settings['motors']:
            prefix, start, end = item

            for mnum in range(start, end+1):
                index = self.pv_list.GetItemCount()
                pv = '{}{}'.format(prefix, mnum)
                self.pv_list.InsertStringItem(index, '')
                self.pv_list.SetStringItem(index, 0, pv)

                descrip = epics.wx.PVText(self.pv_list, '{}.DESC'.format(pv),
                    minor_alarm=None, major_alarm=None, invalid_alarm=None)

                self.pv_list.SetItemWindow(index, 1, descrip, expand=True)

        self.pv_list.SetColumnWidth(0, -1)
        c0_width = self.pv_list.GetColumnWidth(0)
        self.pv_list.SetColumnWidth(0, c0_width+20)
        self.pv_list.SetColumnWidth(1, -3)

    def _on_save_config(self, evt):
        pv, desc = self._get_selected_pv()
        fname = self._create_file_dialog(wx.FD_SAVE, desc)

        if fname is not None:
            if os.path.splitext(fname)[1] != '.sav':
                fname = fname + '.sav'

            self._last_path = str(pathlib.Path(fname).parent.resolve())

            wx.CallAfter(self._save_settings, pv, fname)

    def _on_load_config(self, evt):
        pv, desc = self._get_selected_pv()
        fname = self._create_file_dialog(wx.FD_OPEN, desc)

        if fname is not None:
            self._last_path = str(pathlib.Path(fname).parent.resolve())

            wx.CallAfter(self._load_settings, pv, fname)

    def _get_selected_pv(self):
        index = self.pv_list.GetFirstSelected()

        if index != -1:
            pv_item = self.pv_list.GetItem(index,0)
            pv = pv_item.GetText()
            desc_item = self.pv_list.GetItem(index, 1).GetWindow()
            desc = desc_item.GetLabel()
        else:
            pv = None
            desc = None

        return pv, desc

    def _create_file_dialog(self, mode, desc, name='Motor Config files',
        ext='*.sav'):

        f = None

        if mode == wx.FD_OPEN:
            filters = name + ' (' + ext + ')|' + ext + '|All files (*.*)|*.*'
            dialog = wx.FileDialog( None, style = mode, wildcard = filters,
                defaultDir = self._last_path)

        elif mode == wx.FD_SAVE:
            filters = name + ' ('+ext+')|'+ext
            dialog = wx.FileDialog(None, style=mode|wx.FD_OVERWRITE_PROMPT,
                wildcard=filters, defaultDir=self._last_path,
                defaultFile=desc+'.sav')

        # Show the dialog and get user input
        if dialog.ShowModal() == wx.ID_OK:
            f = dialog.GetPath()

        # Destroy the dialog
        dialog.Destroy()

        return f

    def _save_settings(self, pv, fname):
        base_save = os.path.join(self._base_path, 'base_save.req')
        current_save = os.path.join(self._base_path, 'current_save.req')

        with open(base_save, 'r') as f:
            lines = f.readlines()

        prefix = ':'.join(pv.split(':')[:-1])
        if ':' in pv:
            prefix += ':'

        mnum = pv.split(':')[-1]

        for i in range(len(lines)):
            line = lines[i]
            line = line.replace('$(P)', prefix)
            line = line.replace('$(M)', mnum)
            lines[i] = line

        with open(current_save, 'w') as f:
            f.writelines(lines)

        epics.autosave.save_pvs(current_save, fname)

    def _load_settings(self, pv, fname):
        load_pref = self.settings['load_pref']

        current_load = os.path.join(self._base_path, 'current_load.sav')

        with open(fname, 'r') as f:
            lines = f.readlines()

        old_pv = None
        for i, line in enumerate(lines):
            if line.startswith(load_pref):
                full_pv = line.split()[0]
                old_pv = '.'.join(full_pv.split('.')[:-1])

                if os.path.splitext(fname)[1] == '.usnap':
                    start = i
                break

        if os.path.splitext(fname)[1] == '.usnap':
            lines = lines[start:]

        if old_pv != None:
            for i in range(len(lines)):
                line = lines[i]
                if old_pv in line:
                    line = line.replace(old_pv, pv)

                if os.path.splitext(fname)[1] == '.usnap':
                    temp_line = line.split(' ')
                    pv_temp = temp_line[0]
                    val_temp = ' '.join(temp_line[2:])
                    val_temp = val_temp.replace('"', '')
                    line = '{} {}'.format(pv_temp, val_temp)

                lines[i] = line

            with open(current_load, 'w') as f:
                f.writelines(lines)

            epics.autosave.restore_pvs(current_load)

        else:
            wx.CallAfter(wx.MessageBox, 'Failed to load settings', 'Error')

    def _on_view_config(self, evt):
        fname = self._create_file_dialog(wx.FD_OPEN, '')

        if fname is not None:
            wx.CallAfter(self._view_config, fname)

    def _view_config(self, fname):

        view_dlg = ConfigDialog(self, fname)
        view_dlg.Show()

    def _on_exit(self, evt):
        logger.debug('Closing the MotorConfigFrame')

        self.Destroy()

class ConfigDialog(wx.Dialog):

    def __init__(self, parent, fname, *args, **kwargs):

        wx.Dialog.__init__(self, parent, -1, 'Motor Config. Display',
            *args, style=wx.RESIZE_BORDER|wx.CAPTION|wx.CLOSE_BOX, **kwargs)

        self.CenterOnParent()

        self.SetSize(self._FromDIP((500,600)))

        self.sizer = wx.BoxSizer(wx.VERTICAL)

        self.fname = fname

        with open(fname, 'r') as f:
            fdata = f.readlines()

        self.text = wx.TextCtrl(self, -1, style = wx.TE_MULTILINE | wx.TE_READONLY)
        self.text.AppendText('#############################################\n')
        self.text.AppendText('Config from: %s\n' %(fname))
        self.text.AppendText('#############################################\n\n')

        self.text.AppendText(''.join(fdata))
        self.text.ShowPosition(0)

        self.sizer.Add(self.text, 1, wx.ALL | wx.EXPAND, border=self._FromDIP(10))

        self.sizer.Add(self.CreateButtonSizer(wx.OK), 0, wx.ALIGN_RIGHT|wx.RIGHT
            |wx.BOTTOM, border=self._FromDIP(10))

        self.Bind(wx.EVT_BUTTON, self._onOk, id=wx.ID_OK)

        self.SetSizer(self.sizer)

        self.CenterOnParent()

    def _FromDIP(self, size):
        # This is a hack to provide easy back compatibility with wxpython < 4.1
        try:
            return self.FromDIP(size)
        except Exception:
            return size

    def _onOk(self, event):

        self.Destroy()

if __name__ == '__main__':
    logger = logging.getLogger()
    logger.setLevel(logging.DEBUG)

    h1 = logging.StreamHandler(sys.stdout)
    h1.setLevel(logging.INFO)
    # h1.setLevel(logging.DEBUG)
    formatter = logging.Formatter('%(asctime)s - %(message)s')
    h1.setFormatter(formatter)

    logger.addHandler(h1)

    app = wx.App()

    # standard_paths = wx.StandardPaths.Get() #Can't do this until you start the wx app
    # info_dir = standard_paths.GetUserLocalDataDir()

    # if not os.path.exists(info_dir):
    #     os.mkdir(info_dir)

    # h2 = handlers.RotatingFileHandler(os.path.join(info_dir, 'biocon.log'), maxBytes=10e6, backupCount=5, delay=True)
    # h2.setLevel(logging.INFO)
    # h2.setLevel(logging.DEBUG)
    # formatter2 = logging.Formatter('%(asctime)s - %(name)s - %(threadName)s - %(levelname)s - %(message)s')
    # h2.setFormatter(formatter2)

    # logger.addHandler(h2)

    settings = {
        'motors'    : [
                        ['18ID_DMC_E03:', 17, 24],
                        ['18ID_DMC_E04:', 25, 32],
                        ['18ID_DMC_E05:', 33, 40],
                        ],
        'load_pref' : '18ID' #string key all PVs in the config files are expected to start with
        }

    logger.debug('Setting up wx app')
    frame = MotorConfigFrame(settings, None, title='Motor Config Save/Restore',
        name='motorconfig')
    frame.Show()
    app.MainLoop()
