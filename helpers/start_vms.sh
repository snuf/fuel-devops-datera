for i in `virsh list --all | grep fuel | awk '{ print $2 }'`; do virsh start $i; done
