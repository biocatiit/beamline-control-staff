#!/bin/bash

#From: /APSshare/adlsys/screens/adl/iocs/sioc2id

source source_caqtdm.sh

caQtDM -attach -noMsg -macro "P=S18ID:DSID" iocs/sioc2id/IDControl_Planar.adl &
