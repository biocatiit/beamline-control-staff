#!/bin/bash

#From: /APSshare/adlsys/screens/adl/iocs/xsrcpt/

source source_medm.sh

medm -x -macro "sec=18,ds=19,us=18" IDbpmSingle.adl &
