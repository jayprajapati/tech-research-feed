#!/bin/sh
cd /home/site/wwwroot
if [ -L node_modules ]; then rm node_modules; fi
if [ ! -d node_modules ] && [ -d _del_node_modules ]; then mv _del_node_modules node_modules; fi
exec node server.mjs
