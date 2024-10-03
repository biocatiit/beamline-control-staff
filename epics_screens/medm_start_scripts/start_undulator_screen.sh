#!/bin/bash

#From: /APSshare/adlsys/screens/adl/iocs/sioc2id

source source_medm.sh

medm -x -macro "P=S18ID:DSID" IDControl_Planar.adl &
