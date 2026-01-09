#!/bin/bash

source source_caqtdm.sh

caQtDM -attach -noMsg -macro "P=Mar165:, R=cam1:" marCCD.ui &
# caQtDM  -macro "P=Mar165:, R=cam1:" marCCDAncillary.ui &
