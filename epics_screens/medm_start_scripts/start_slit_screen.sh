#!/bin/bash

source source_medm.sh

#Check provided arguments for record prefix
if [ -z "$1" ]
then
      # No args provided, default
      export RECPREFIX=Xenocs_US
else
      # Record prefix provided as argument 1
      export RECPREFIX=$1
fi

if [[ "$RECPREFIX" == "Xenocs_US" ]]; then
    medm -x -macro "P=18ID_DMC_E04:,SLIT=XenocsUS,V=XenocsUS_V:,H=XenocsUS_H:" 4slitGraphic_soft.adl &
elif [[ "$RECPREFIX" == "Xenocs_DS" ]]; then
    medm -x -macro "P=18ID_DMC_E04:,SLIT=XenocsDS,V=XenocsDS_V:,H=XenocsDS_H:" 4slitGraphic_soft.adl &
elif [[ "$RECPREFIX" == "Xenocs_US_V" ]]; then
    medm -x -macro "P=18ID_DMC_E04:,SLIT=XenocsUS_V:,mXp=25,mXn=26" 2slit_soft.adl &
elif [[ "$RECPREFIX" == "Xenocs_US_H" ]]; then
    medm -x -macro "P=18ID_DMC_E04:,SLIT=XenocsUS_H:,mXp=28,mXn=27" 2slit_soft.adl &
elif [[ "$RECPREFIX" == "Xenocs_DS_V" ]]; then
    medm -x -macro "P=18ID_DMC_E04:,SLIT=XenocsDS_V:,mXp=29,mXn=30" 2slit_soft.adl &
elif [[ "$RECPREFIX" == "Xenocs_DS_H" ]]; then
    medm -x -macro "P=18ID_DMC_E04:,SLIT=XenocsDS_H:,mXp=32,mXn=31" 2slit_soft.adl &
fi
