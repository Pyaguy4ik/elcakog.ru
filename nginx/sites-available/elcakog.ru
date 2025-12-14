server {
    listen 80;
    listen [::]:80;

    server_name elcakog.ru www.elcakog.ru;
    root /var/www/elcakog.ru/html;
    index index.html;

    location / {
        try_files $uri $uri/ =404;
    }

    location /api/ {
        include proxy_params;
        proxy_pass http://127.0.0.1:5001;
    }
}
