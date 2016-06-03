#!/bin/bash
#
# Wrapper script specific for Datera testing, can be used as an example
# for other testing
#
#
fuelVersion=""
workDir="$HOME/working_dir"
settingsFile=""

usage() {
  echo "$0:
    -h|--help           this!
    -v|--fuel-version   Version of the Fuel image, 7.0 or 8.0
    -s|--settings       Settings file to copy in
    -p|--plugin         Path to example plugin
    -D|--datera         ip,username,password,replicas,rpm
    -w|--workdir        Directory to work from ($workDir)"
}

# can condense this and make it more elegent later
dateraPrep() {
  IFS=',' read -a datOpts <<< "$1"
  # ip,username,password,replicas,rpm"
  if test "${datOpts[4]+isset}"; then
    export DATERA_PLUGIN_PATH=${datOpts[4]}
  else
    export DATERA_PLUGIN_PATH=$pluginFile
  fi
  if test "${datOpts[3]+isset}"; then
    export DATERA_NUM_REPLICAS=${datOpts[3]}
  else
    export DATERA_NUM_REPLICAS='2'
  fi
  if test "${datOpts[2]+isset}"; then
    export DATERA_PASSWORD=${datOpts[2]}
  else
    export DATERA_PASSWORD='password'
  fi
  if test "${datOpts[1]+isset}"; then
    export DATERA_USERNAME=${datOpts[1]}
  else
    export DATERA_USERNAME='admin'
  fi
  if test "${datOpts[0]+isset}"; then
    export DATERA_MVIP=${datOpts[0]}
  else
    export DATERA_MVIP='10.10.10.10'
  fi
  export EXAMPLE_PLUGIN_V3_PATH=$pluginFile

  cp -pr $origPwd/plugin_datera $workDir/fuel-qa/fuelweb_test/tests/plugins/
  perl -pi.org -e 's/plugin_emc/plugin_datera/g' \
    $workDir/fuel-qa/fuelweb_test/run_tests.py
}

set -- `getopt -u -o "lhv:d:i:l:w:p:s:D:" \
  --longoptions="fuel-version settings plugin datera"  "h" "$@"` || usage

while [ $# -gt 0 ]
do
    case "$1" in
    --fuel-version|-v)
      fuelVersion=$2
      shift
    ;;
    --workdir|-w)
      workDir=$2
      shift
    ;;
    --settings|-s)
      settingsFile=$2
      shift
    ;;
    --plugin|-p)
      pluginFile=$2
      shift
    ;;
    --datera|-D)
      dateraOpts=$2
      shift
    ;;
    esac
    shift
done

if [ "$fuelVersion" == "" ]; then
    usage
    echo "You must give a fuel version!!. (-v)"
    exit 1
fi

if [ "$settingsFile" == "" ]; then
    settingsFile="settings-${fuelVersion}.py"
fi
if [ ! -e "$settingsFile" ]; then
    echo "Settings File: $settingsFile not found."
    exit 1
fi

origPwd=$PWD
dateraPrep $dateraOpts 
cd $workDir/fuel-qa
export PROMPT_COMMAND="echo -n '(fuel_qa_venv:$fuelVersion) '"
output="Test: ./utils/jenkins/system_tests.sh -t test -w $workDir/fuel-qa "
output+="-j fuelweb_test -i $workDir/MirantisOpenStack-$fuelVersion.iso "
output+="-o --group=fuel_plugin_datera"
echo $output
exec bash
