dist_client:
	cat src/client/plugins.py > dist/client.py
	tail +2 src/client/main.py >> dist/client.py
	# chmod u+x dist/client.py

dist_server:
	tar czf dist/server.tgz -C src/server src/server/template src/server/main.py

dist: dist_client dist_server

