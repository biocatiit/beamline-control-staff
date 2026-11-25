#!/bin/bash

source source_caqtdm.sh

caQtDM -attach -noMsg -macro "P=18ID:,MN=Mono,ENERGY=Energy,LAMBDA=Lambda,BRAGG=Bragg,GAP=Gap,OFFSET=Offset,BRAGG_HM=18ID_Aerotech_C:m1,GAP_HM=18ID_DMC_E08:C24" bragg_gap_mono_main.ui &
