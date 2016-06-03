for i in `virsh net-list | grep fuel | awk '{ print $1 }'`; do 
    virsh net-destroy $i
    virsh net-undefine $i
done
