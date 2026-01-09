#!/bin/bash

source source_caqtdm.sh

caQtDM -attach -noMsg -macro "P=18ID:, S=scaler2" scaler16_full.ui &
