#!/bin/bash

source source_caqtdm.sh

# Check provided arguments for record prefix
if [ -z "$1" ]
then
      # No args provided, default
      export PREFIX="18ID_Newport_D:"
else
      # Record prefix provided as argument 1
      export PREFIX=$1
fi

caQtDM -attach -noMsg -macro "P=${PREFIX}, R=Prof1:, A=XPSAux, M1=m1, M2=m2, M3=m3, M4=m4, M5=m5, M6=m6, M7=m7, M8=m8" XPSTop.ui &

# Hexapod stuff
# caQtDM -attach -noMsg -macro "P=18ID_CRL_Newport:hxp:,R=c0:,M1=c0:m1,M2=c0:m2,M3=c0:m3,M4=c0:m4,M5=c0:m5,M6=c0:m6,M7=c0:m7,M8=c0:m8" HXP.ui &


