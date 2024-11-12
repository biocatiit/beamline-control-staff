#!/bin/bash

source source_medm.sh

medm -x -macro "P=18ID_D_Newport:,R=Prof1:,M1=m1,M2=m2,M3=m3,M4=m4,M5=m5,M6=m6,M7=m7,M8=m8" profileMoveXPS.adl &
#medm -x -macro "P=18ID_D_Newport:, M=m8" XPSExtra.adl &
#medm -x -macro "P=18ID_D_Newport:, M=m8" motorx_more.adl &
