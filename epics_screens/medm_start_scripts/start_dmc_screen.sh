#!/bin/bash

source source_medm.sh

#Check provided arguments for record prefix
if [ -z "$1" ]
then
      # No args provided, default
      export RECPREFIX=DMC01:
else
      # Record prefix provided as argument 1
      export RECPREFIX=$1
fi

# R = Record name for digital IO not including byte/word, and bit number
# Digital IO naming
# $(DMC)$(R)<Byte or word num><Type Bo or Bi><Bit>

if [[ "$RECPREFIX" == "18ID_DMC_E03" ]]; then
medm -x -macro "R=Galil,DMC=$RECPREFIX:,IOC=IOC_18ID_DMC_E03:,M1=17,M2=18,M3=19,M4=20,M5=21,M6=22,M7=23,M8=24,M9=I,M10=J,M11=K,M12=L,M13=M,M14=N,M15=O,M16=P" galil_dmc_ctrl.adl &
elif [[ "$RECPREFIX" == "18ID_DMC_E04" ]]; then
medm -x -macro "R=Galil,DMC=$RECPREFIX:,IOC=IOC_18ID_DMC_E04:,M1=25,M2=26,M3=27,M4=28,M5=29,M6=30,M7=31,M8=32,M9=I,M10=J,M11=K,M12=L,M13=M,M14=N,M15=O,M16=P" galil_dmc_ctrl.adl &
elif [[ "$RECPREFIX" == "18ID_DMC_E05" ]]; then
medm -x -macro "R=Galil,DMC=$RECPREFIX:,IOC=IOC_18ID_DMC_E05:,M1=33,M2=34,M3=35,M4=36,M5=37,M6=38,M7=39,M8=40,M9=I,M10=J,M11=K,M12=L,M13=M,M14=N,M15=O,M16=P" galil_dmc_ctrl.adl &
fi
