#!/bin/bash

eval "$(conda shell.bash hook)"
conda activate medm

base_display_path="/usr/local/beamline-control-staff/epics_screens/displays"
export ADLDIR=/APSshare/adlsys

#From module top, add offset path to medm screens
motorpath=$base_display_path/motorApp/op/adl
sscanpath=$base_display_path/sscanApp/op/adl
galilpath=$base_display_path/GalilSup/op/adl
mcapath=$base_display_path/mcaApp/op/adl
scalerpath=$base_display_path/scalerApp/op/adl
adcorepath=$base_display_path/ADApp/op/adl
eigerpath=$base_display_path/eigerApp/op/adl
marpath=$base_display_path/marCCDApp/op/adl
pilatuspath=$base_display_path/pilatusApp/op/adl
labjackpath=$base_display_path/LabJackApp/op/adl
# apspath=$base_display_path/aps
apspath=$ADLDIR/screens:$ADLDIR/adlsys:$ADLDIR/screens/adl
apspath=$apspath:$ADLDIR/sr/fe:$ADLDIR/sr/facilitiesApp
#apspath=$apspath:$ADLDIR/sr/psApp:$ADLDIR/screens/adl/systems/sr
#apspath=$apspath:$ADLDIR/screens/adl/iocs/idctl/adl_Global
#apspath=$apspath:$ADLDIR/screens/adl/iocs/xsrcpt/:$ADLDIR/sr/pss/adl/
#apspath=$apspath:$ADLDIR/screens/adl/iocs/sioc2id:$ADLDIR/xfd-display
meascomppath=$base_display_path/measCompApp/op/adl
opticspath=$base_display_path/opticsApp/op/adl
newportpath=$base_display_path/newportApp/op/adl
quadempath=$base_display_path/quadEMApp/op/adl
genicampath=$base_display_path/GenICamApp/op/adl
ffmpegpath=$base_display_path/ffmpegServerApp/op/adl
spinnakerpath=$base_display_path/spinnakerApp/op/adl
ippath=$base_display_path/ipApp/op/adl
asynpath=$base_display_path/asynApp/op/adl


EPICS_DISPLAY_PATH=$motorpath:$galilpath:$sscanpath:$mcapath:$scalerpath
EPICS_DISPLAY_PATH=$EPICS_DISPLAY_PATH:$adcorepath:$eigerpath:$marpath
EPICS_DISPLAY_PATH=$EPICS_DISPLAY_PATH:$pilatuspath:$labjackpath:$apspath
EPICS_DISPLAY_PATH=$EPICS_DISPLAY_PATH:$meascomppath:$opticspath:$newportpath
EPICS_DISPLAY_PATH=$EPICS_DISPLAY_PATH:$quadempath:$genicampath:$ffmpegpath
EPICS_DISPLAY_PATH=$EPICS_DISPLAY_PATH:$spinnakerpath:$ippath:$asynpath

export EPICS_DISPLAY_PATH

