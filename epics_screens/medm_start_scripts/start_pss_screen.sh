#!/bin/bash

#From: /APSshare/adlsys/sr/pss/adl/

source source_medm.sh

medm -x -macro "xx=18,yy=ID" sr/pss/adl/Main_18ID.adl &
