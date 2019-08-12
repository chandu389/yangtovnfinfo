# yangtovnfinfo

1. Set path for Yang which covers both runtime and ncs 

export YANG_MODPATH="/Users/username/Documents/Projects/NSO/NSO5/NSOCFS/nso5101/src/ncs/yang/:/Users/username/Documents/Projects/NSO/NSO5/NSOCFS/ncsrun/packages/rmno-common/src/yang/"

2. Execute python file 

 python3 yangtovnfinfo.py -yf rmno-common.yang -tf sampleVnfInfo.xml -g mavenir-rcs-wsg-extensions -o vnf-info.xml
 
 
To see more details use

 python3 yangtovnfinfo.py --help