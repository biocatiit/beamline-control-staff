#!/bin/bash

source source_caqtdm.sh

# Check provided arguments for record prefix
if [ -z "$1" ]
then
      # No args provided, default
      export PREFIX="ETC"
else
      # Record prefix provided as argument 1
      export PREFIX=$1
fi

if [[ "$PREFIX" == "ETC" ]]; then
    caQtDM -attach -noMsg -macro "P=18ID:ETC:,Ti=Ti,Ct=Counter,Bo=Bo,Bi=Bi,Bd=Bd,Li=Li,Lo=Lo" ETC_module.ui &
elif [[ "$PREFIX" == "E1608" ]]; then
    caQtDM -attach -noMsg -macro "P=18ID:E1608:,Ai=Ai,Ao=Ao,Ct=Counter,Bo=Bo,Bi=Bi,Bd=Bd,Li=Li,Lo=Lo,Tg=Trig,Wd=WaveDig" E1608_module.ui &
elif [[ "$PREFIX" == "USB1608G_1" ]]; then
    caQtDM -attach -noMsg -macro "P=18ID:USB1608G_1:,Ai=Ai,Ao=Ao,Ct=Counter,Bo=Bo,Bi=Bi,Bd=Bd,Li=Li,Lo=Lo,Tg=Trig,Wd=WaveDig,Pg=PulseGen" 1608G_module.ui &
elif [[ "$PREFIX" == "USB1608G_2" ]]; then
    caQtDM -attach -noMsg -macro "P=18ID:USB1608G_2:,Ai=Ai,Ao=Ao,Ct=Counter,Bo=Bo,Bi=Bi,Bd=Bd,Li=Li,Lo=Lo,Tg=Trig,Wd=WaveDig,Pg=PulseGen" 1608G_module.ui &
elif [[ "$PREFIX" == "USB1608G_2AO_1" ]]; then
    caQtDM -attach -noMsg -macro "P=18ID:USB1608G_2AO_1:,Ai=Ai,Ao=Ao,Ct=Counter,Bo=Bo,Bi=Bi,Bd=Bd,Li=Li,Lo=Lo,Tg=Trig,Wd=WaveDig,Wg=WaveGen,Pg=PulseGen" USB1608G_2AO_module.ui &
fi
