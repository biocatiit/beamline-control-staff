#!/bin/bash
conda init
conda activate medm

base_display_path="/usr/local/beamline-control-staff/epics_screens/displays"
#From module top, add offset path to medm screens
export motorpath=$base_display_path/motorApp/op/adl
export sscanpath=$base_display_path/sscanApp/op/adl
export galilpath=$base_display_path/GalilSup/op/adl
export mcapath=$base_display_path/mcaApp/op/adl
export scalerpath=$base_display_path/scalerApp/op/adl

export EPICS_DISPLAY_PATH=$motorpath:$galilpath:$sscanpath:$mcapath:$scalerpath

medm -x -macro "P=18ID:, S=scaler2" scaler16_full.adl &
