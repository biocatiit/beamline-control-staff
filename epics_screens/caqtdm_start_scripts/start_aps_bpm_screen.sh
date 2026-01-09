#!/bin/bash

#From: /APSshare/adlsys/screens/adl/iocs/xsrcpt/

source source_caqtdm.sh

caQtDM -attach -noMsg -macro "sec=18,ds=19,us=18" IDbpmSingle.ui &
