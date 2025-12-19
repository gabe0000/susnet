#flash 1.3
# start
while true; do
	if lsusb | grep -q -i All-In-One-Cable; then
		dfu-util -d 1209:7388 -a 0 -s 0x08000000:leave -D aioc-fw-1.3.0.bin
	else
		dfu-util -a 0 -s 0x08000000 -D aioc-fw-1.3.0.bin
	fi
	result=$?
	echo
	if [ ${result} -eq 0 ]; then
		echo "Done programming URC.  Pull from USB Cable..."
		echo "Sleeping 10 seconds..."
		sleep 7
	else
		echo "Failed."
	fi
	echo -n "Trying again in 3 seconds..."
	sleep 1
	echo -n " 2..."
	sleep 1
	echo -n " 1..."
	sleep 1
	echo " Go"
done
