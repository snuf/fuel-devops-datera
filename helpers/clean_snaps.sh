for i in `virsh list --all | grep fuel | awk '{ print $2 }'`; do 
    for x in `virsh snapshot-list $i | awk '{ print $1 }'`; do 
        virsh snapshot-delete $i $x; 
    done; virsh undefine $i ; 
done
