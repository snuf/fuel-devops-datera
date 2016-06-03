#!/bin/bash
#
# Simple run examle
#
fuelVersion="$1"
if [ -z "$fuelVersion" ]; then
    echo "We meed a fuel version, 7.0 or 8.0."
    exit 1
fi
# do not blow away our old env, saves some time if we've had a failure...
export KEEP_BEFORE="yes"
export KEEP_AFTER="yes"
plugin=`readlink -f fuel-plugin-datera-cinder-0.1-0.1.51-1.noarch.rpm`
bash -x ../fuel-devops-simple/fuel-devops-simple.sh -v $fuelVersion \
    -S "bash -x fuel-devops-datera.sh \
        -v $fuelVersion \
        -s settings-${fuelVersion}.py \
        -p $plugin \
        -D 192.168.123.10,admin,password,2"

# DATE=`date +%Y%d%M_%H%M%S`
# cd $workDir
# tar -zcvf fuel-qa-$fuelVersion-$DATE.logs.gz fuel-qa/logs
# rm -rf fuel-qa/logs/
