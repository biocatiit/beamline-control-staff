#!/bin/bash -i

source /usr/local/source_epics.sh

# Deactivate conda so that it doens't interfer with things
for i in $(seq ${CONDA_SHLVL}); do
    eval "conda deactivate"
done

base_display_path="/usr/local/beamline-control-staff/epics_screens/displays"
export ADLDIR=/APSshare/adlsys

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
# apspath=$base_display_path/aps
apspath=$ADLDIR/screens:$ADLDIR/adlsys:$ADLDIR/screens/adl
apspath=$apspath:$ADLDIR/sr/fe:$ADLDIR/sr/facilitiesApp
#apspath=$apspath:$ADLDIR/sr/psApp:$ADLDIR/screens/adl/systems/sr
#apspath=$apspath:$ADLDIR/screens/adl/iocs/idctl/adl_Global
#apspath=$apspath:$ADLDIR/screens/adl/iocs/xsrcpt/:$ADLDIR/sr/pss/adl/
#apspath=$apspath:$ADLDIR/screens/adl/iocs/sioc2id:$ADLDIR/xfd-display
meascomppath=$base_display_path/measCompApp/op/ui:$base_display_path/measCompApp/op/ui/autoconvert
opticspath=$base_display_path/opticsApp/op/ui:$base_display_path/opticsApp/op/ui/autoconvert
newportpath=$base_display_path/newportApp/op/ui:$base_display_path/newportApp/op/ui/autoconvert
quadempath=$base_display_path/quadEMApp/op/ui:$base_display_path/quadEMApp/op/ui/autoconvert
genicampath=$base_display_path/GenICamApp/op/ui:$base_display_path/GenICamApp/op/ui/autoconvert
ffmpegpath=$base_display_path/ffmpegServerApp/op/ui:$base_display_path/ffmpegServerApp/op/ui/autoconvert
spinnakerpath=$base_display_path/spinnakerApp/op/ui:$base_display_path/spinnakerApp/op/ui/autoconvert
ippath=$base_display_path/ipApp/op/ui:$base_display_path/ipApp/op/ui/autoconvert:$base_display_path/ipApp/op/ui/Synaccess_netbooster
asynpath=$base_display_path/asynApp/op/ui:$base_display_path/asynApp/op/ui/autoconvert:$base_display_path/ipApp/op/ui/Synaccess_netbooster


CAQTDM_DISPLAY_PATH=$motorpath:$galilpath:$sscanpath:$mcapath:$scalerpath
CAQTDM_DISPLAY_PATH=$CAQTDM_DISPLAY_PATH:$adcorepath:$eigerpath:$marpath
CAQTDM_DISPLAY_PATH=$CAQTDM_DISPLAY_PATH:$pilatuspath:$labjackpath:$apspath
CAQTDM_DISPLAY_PATH=$CAQTDM_DISPLAY_PATH:$meascomppath:$opticspath:$newportpath
CAQTDM_DISPLAY_PATH=$CAQTDM_DISPLAY_PATH:$quadempath:$genicampath:$ffmpegpath
CAQTDM_DISPLAY_PATH=$CAQTDM_DISPLAY_PATH:$spinnakerpath:$ippath:$asynpath

export CAQTDM_DISPLAY_PATH
# echo $CAQTDM_DISPLAY_PATH
