#!/bin/bash

source source_caqtdm.sh

caQtDM -attach -noMsg -macro "P=$1, M=$2" motorx_more.ui &
