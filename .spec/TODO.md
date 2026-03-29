现有bug：

1. 目录不支持子域名
2. 新增了页面，图谱没有重绘。

### 后端效果参考：

构建命令：
```
npx quartz build -d E:\ProgramProjects\VScode_projects\quartz-fullstack\input\xm -o E:\ProgramProjects\VScode_projects\quartz-fullstack\output\xm
```

nginx配置：

```
worker_processes 1;

events {
    worker_connections 1024;
}

http {
    include mime.types;
    default_type application/octet-stream;
    sendfile on;
    keepalive_timeout 65;

    # 这里才是放 server 的地方
    server {
        listen 8767;
        server_name localhost;

        # 注意 Windows 路径建议用正斜杠 /，且用引号包裹
        root "E:/ProgramProjects/VScode_projects/quartz-fullstack/output";

        index index.html;

        location /xm/ {
            try_files $uri $uri/ $uri.html =404;
        }

        error_page 404 /404.html;
    }

} # 确保这个是 http 块的右花括号
```