#!/bin/bash

#From: /APSshare/adlsys/screens/adl/iocs/sr-steering

source source_caqtdm.sh

# For some reason I can't figure out these won't open in attach mode like everything else

caQtDM -noMsg -macro "sector=S18ID" SteeringSectorDetailsID.adl &
caQtDM -noMsg -macro "sector=S18ID" UserSteeringID.adl &
