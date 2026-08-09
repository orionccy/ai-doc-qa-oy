# ============ 前端 Dockerfile(多阶段构建)============
# 阶段 1:Node 构建出静态文件
# 阶段 2:Nginx 托管静态文件 + 反向代理 /api 到后端容器
# 多阶段的好处:最终镜像只含 Nginx + 静态文件,体积小(不含 node_modules)

# ---- 构建阶段 ----
FROM node:22-alpine AS build
WORKDIR /app
# 先拷依赖清单并安装(利用层缓存:依赖不变不重装)
COPY package*.json ./
RUN npm install --registry=https://registry.npmmirror.com
# 再拷源码并构建
COPY . .
RUN npm run build

# ---- 运行阶段 ----
FROM nginx:alpine
# 把构建产物放进 Nginx 的静态目录
COPY --from=build /app/dist /usr/share/nginx/html
# 自定义配置:SPA 路由回退 + /api 反代到后端
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
