#!/bin/bash

#$1 is model filename, $2 is test sentences filename, $3 is language (en|es|syn), $4 is output filename, $5 is vocab filename

if [ "$3" = "en" ] ; then
    vocab='./models/en_models/en-vocab.txt'
fi

if [ "$3" = "es" ] ; then
    vocab='./models/es_models/es-vocab.txt'
fi

#if [ "$3" = "syn" ]; then
#    PRCS="8e-05"
#    P="synthetic/distro/zero_008/data/"
#    vocab=$P$PRCS'_syn-vocab.txt' 
#fi

#time python main.py --model_file "$1" --vocab_file "$vocab" --data_dir './' --testfname "$2" --test --cuda --words --nopp > $4
time python main.py --model_file "$1" --vocab_file "$vocab" --data_dir './' --testfname "$2" --test --words --nopp > $4

