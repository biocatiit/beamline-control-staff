#!/bin/bash

source source_caqtdm.sh

caQtDM -attach -noMsg -macro "P=,Q=18ID:ADCTable,T=18ID:ADCTable,M0X=18ID_DMC_E05:36,M0Y=18ID_DMC_E05:34,M1Y=18ID_DMC_E05:37,M2X=18ID_DMC_E05:35,M2Y=18ID_DMC_E05:33,M2Z=m6" table_full_soft.ui &
