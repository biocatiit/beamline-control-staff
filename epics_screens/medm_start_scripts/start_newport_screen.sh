#!/bin/bash

source source_medm.sh

# medm -x -macro "P=18ID_D_Newport:,R=Prof1:,M1=m1,M2=m2,M3=m3,M4=m4,M5=m5,M6=m6,M7=m7,M8=m8" profileMoveXPS.adl &
#medm -x -macro "P=18ID_D_Newport:, M=m8" XPSExtra.adl &
#medm -x -macro "P=18ID_D_Newport:, M=m8" motorx_more.adl &
# medm -x -macro "P=18ID_CRL_Newport:hxp:c0:, M=m1" motorx_more.adl &
# medm -x -macro "P=18ID_CRL_Newport:hxp:,R=c0:,M1=c0:m1,M2=c0:m2,M3=c0:m3,M4=c0:m4,M5=c0:m5,M6=c0:m6,M7=c0:m7,M8=c0:m8" HXP.adl &
# medm -x -macro "P=18ID_D_Newport:,M1=m1,M2=m2,M3=m3,M4=m4,M5=m5,M6=m6,M7=m7,M8=m8" XPSPositionCompare8.adl &
medm -x -macro "P=18ID_Newport_TR:, M=m1" motorx_more.adl &
medm -x -macro "P=18ID_Newport_TR:, M=m2" motorx_more.adl &
# medm -x -macro "P=18ID_Newport_TR:,M1=m1,M2=m2,M3=m3,M4=m4,M5=m5,M6=m6,M7=m7,M8=m8" XPSPositionCompare8.adl &
# medm -x -macro "P=18ID_Newport_D:, M=m6" motorx_more.adl &
# medm -x -macro "P=18ID_Newport_D:, M=m7" motorx_more.adl &
# medm -x -macro "P=18ID_Newport_D:, M=m8" motorx_more.adl &
