# Quartz全栈项目

包含客户端与服务端。

考虑前后端分离，必须在项目根目录把input文件夹和output文件夹分开，各自在里面区分**域文件夹**（一级目录）。

## 客户端

进入`client`文件夹，
执行`npm install`安装依赖包。

## 服务端

进入`server`文件夹，

执行构建：

```bash
go build -ldflags="-s -w" -o quartz-service.exe .
```

首次访问：
http://127.0.0.1:8766/xm?user=admin&pwd=password123

http://127.0.0.1:8766/testwork0?user=admin&pwd=password123