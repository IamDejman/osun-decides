FROM nginx:alpine
COPY nginx.conf /etc/nginx/templates/default.conf.template
COPY index.html app.js styles.css /usr/share/nginx/html/
COPY data /usr/share/nginx/html/data
COPY assets /usr/share/nginx/html/assets
