for i in `virsh list | grep fuel | awk '{ print $2 }'`; do virsh destroy $i; done
