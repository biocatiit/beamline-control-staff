#!/bin/bash

source source_caqtdm.sh

# Motors (could be done through standard motor start script)
#caQtDM -attach -noMsg -macro "P=18ID_Newport_D:, M=m1" motorx_more.ui &
#caQtDM -attach -noMsg -macro "P=18ID_Newport_D:, M=m2" motorx_more.ui &
#caQtDM -attach -noMsg -macro "P=18ID_Newport_D:, M=m3" motorx_more.ui &

# Motor extras
#caQtDM -attach -noMsg -macro "P=18ID_Newport_D:, M=m1" XPSExtra.ui &
#caQtDM -attach -noMsg -macro "P=18ID_Newport_D:, M=m2" XPSExtra.ui &
#caQtDM -attach -noMsg -macro "P=18ID_Newport_D:, M=m3" XPSExtra.ui &

# Top menu
caQtDM -attach -noMsg -macro "P=18ID_Newport_D:, R=Prof1:, A=XPSAux, M1=m1, M2=m2, M3=m3, M4=m4, M5=m5, M6=m6, M7=m7, M8=m8" XPSTop.ui &

# Profile move
#caQtDM -attach -noMsg -macro "TITLE=XPS D Hutch, P=18ID_Newport_D:, R=Prof1:, M1=m1, M2=m2, M3=m3, M4=m4, M5=m5, M6=m6, M7=m7, M8=m8" profileMoveXPS.ui &

# Aux doesn't currently work for D8s
#caQtDM -attach -noMsg -macro "P=18ID_Newport_D:, R=XPSAux" XPSAux.ui &

# PCO doesn't currently work for D8s
#caQtDM -attach -noMsg -macro "P=18ID_Newport_D:,M1=m1,M2=m2,M3=m3,M4=m4,M5=m5,M6=m6,M7=m7,M8=m8" XPSPositionCompare8.ui &

# Hexapod stuff
# caQtDM -attach -noMsg -macro "P=18ID_CRL_Newport:hxp:,R=c0:,M1=c0:m1,M2=c0:m2,M3=c0:m3,M4=c0:m4,M5=c0:m5,M6=c0:m6,M7=c0:m7,M8=c0:m8" HXP.ui &


