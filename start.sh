dts devel build -f
dts devel run -R wayne2 --  -e DISPLAY=$DISPLAY   -e WAYLAND_DISPLAY=$WAYLAND_DISPLAY   -e XDG_RUNTIME_DIR=$XDG_RUNTIME_DIR   -v /tmp/.X11-unix:/tmp/.X11-unix   -v /mnt/wslg:/mnt/wslg
