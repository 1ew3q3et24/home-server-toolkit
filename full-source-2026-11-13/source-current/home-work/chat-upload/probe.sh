php -v | head -1
php -r 'echo ini_get("upload_max_filesize")." / ".ini_get("post_max_size")." / user_ini=".ini_get("user_ini.filename")." / cache=".ini_get("user_ini.cache_ttl").PHP_EOL;'
php -m | grep -iE '^(fileinfo|gd|exif)$'
php -i | grep -E 'Loaded Configuration File|Scan this dir|user_ini.filename'
ls -ld /var/lib/chat-uploads 2>/dev/null || echo NO_UPLOAD_DIR
grep -n client_max_body_size /etc/nginx/nginx.conf /etc/nginx/sites-enabled/chat 2>/dev/null || echo NO_CMB
id www-data
php -r 'var_dump(class_exists("finfo"), function_exists("getimagesize"));'