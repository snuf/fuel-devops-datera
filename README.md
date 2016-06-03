# Fuel Devops Datera
The module that is used for Datera Fuel testing.

## Description
The module can be used standalone, although needs to be copied in then,
or daisy changed with [fuel-devops-simple](https://github.com/snuf/fuel-devops-simple), 
which prepares the environment and sets up fuel-devops.

## Requirements
* A working fuel-devops environment, rolled out with fuel-devops-simple for example.
* ~/.devops/snap needs to be able to hold at least 70G (for 7.0).
* the default pool should be able to hold at least 80G (for both 7.0 and 8.0).
* failure will require more space.
* Minimum requirement is 4 cores and 20GB ram.
* Patience... the full run takes a while.
* The Datera cluster or training VM lives outside the network and is routed to on 192.168.123.10

## Notes
Networks are destroyed when the process starts over, anything that lives in these networks
will not have connectivity. The assumption that a machine will have connectivity if it is
left on, in a network that is removed, is incorrect.
If storage or something else lives in a network it means the respective VM will have to
be stopped, and started after the admin and slave nodes have been "created". They do not
require to have been started, just created. So running all dependencies outside this
is recommended and making sure things are routed.

If something goes wrong during a step in the runs it's best to chuck everything out and
start over after fixing the issue. Restarts are an issue, exporting the KEEP_BEFORE env 
variable before running is helpfull in this case. The files in helpers are just simply
to cleanup.

