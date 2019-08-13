# yangtovnfinfo

1. Set path for Yang which covers both runtime and ncs 

export YANG_MODPATH="/Users/username/Documents/Projects/NSO/NSO5/NSOCFS/nso5101/src/ncs/yang/:/Users/username/Documents/Projects/NSO/NSO5/NSOCFS/ncsrun/packages/rmno-common/src/yang/"

2. Execute python file 

 python3 yangtovnfinfo.py -sf sol001.yaml -yf <Yang file name> -tf sampleVnfInfo.xml -g <grouping name> -o vnf-info.xml
 
 
To see more details use

 python3 yangtovnfinfo.py --help