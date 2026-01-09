#!/bin/bash -i

source /usr/local/source_epics.sh

# Deactivate conda so that it doens't interfer with things
for i in $(seq ${CONDA_SHLVL}); do
    eval "conda deactivate"
done

base_display_path="/usr/local/beamline-control-staff/epics_screens/displays"

#From module top, add offset path to medm screens
motorpath=$base_display_path/motorApp/op/ui:$base_display_path/motorApp/op/ui/autoconvert
sscanpath=$base_display_path/sscanApp/op/ui:$base_display_path/sscanApp/op/ui/autoconvert
galilpath=$base_display_path/GalilSup/op/ui:$base_display_path/GalilSup/op/ui/autoconvert
mcapath=$base_display_path/mcaApp/op/ui:$base_display_path/mcaApp/op/ui/autoconvert
scalerpath=$base_display_path/scalerApp/op/ui:$base_display_path/scalerApp/op/ui/autoconvert
adcorepath=$base_display_path/ADApp/op/ui:$base_display_path/ADApp/op/ui/autoconvert
eigerpath=$base_display_path/eigerApp/op/ui:$base_display_path/eigerApp/op/ui/autoconvert
marpath=$base_display_path/marCCDApp/op/ui:$base_display_path/marCCDApp/op/ui/autoconvert
pilatuspath=$base_display_path/pilatusApp/op/ui:$base_display_path/pilatusApp/op/ui/autoconvert
labjackpath=$base_display_path/LabJackApp/op/ui:$base_display_path/LabJackApp/op/ui/autoconvert
apspath=$base_display_path/aps
meascomppath=$base_display_path/measCompApp/op/ui:$base_display_path/measCompApp/op/ui/autoconvert
opticspath=$base_display_path/opticsApp/op/ui:$base_display_path/opticsApp/op/ui/autoconvert
newportpath=$base_display_path/newportApp/op/ui:$base_display_path/newportApp/op/ui/autoconvert
quadempath=$base_display_path/quadEMApp/op/ui:$base_display_path/quadEMApp/op/ui/autoconvert
genicampath=$base_display_path/GenICamApp/op/ui:$base_display_path/GenICamApp/op/ui/autoconvert
ffmpegpath=$base_display_path/ffmpegServerApp/op/ui:$base_display_path/ffmpegServerApp/op/ui/autoconvert
spinnakerpath=$base_display_path/spinnakerApp/op/ui:$base_display_path/spinnakerApp/op/ui/autoconvert

CAQTDM_DISPLAY_PATH=$motorpath:$galilpath:$sscanpath:$mcapath:$scalerpath
CAQTDM_DISPLAY_PATH=$CAQTDM_DISPLAY_PATH:$adcorepath:$eigerpath:$marpath
CAQTDM_DISPLAY_PATH=$CAQTDM_DISPLAY_PATH:$pilatuspath:$labjackpath:$apspath
CAQTDM_DISPLAY_PATH=$CAQTDM_DISPLAY_PATH:$meascomppath:$opticspath:$newportpath
CAQTDM_DISPLAY_PATH=$CAQTDM_DISPLAY_PATH:$quadempath:$genicampath:$ffmpegpath
CAQTDM_DISPLAY_PATH=$CAQTDM_DISPLAY_PATH:$spinnakerpath

export CAQTDM_DISPLAY_PATH
# echo $CAQTDM_DISPLAY_PATH