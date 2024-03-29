# Ferryman
[![](https://img.shields.io/github/workflow/status/Yu-HaoYu/Ferryman/Ferryman)](https://github.com/Yu-HaoYu/Ferryman/actions?query=workflow%3AFerryman)&nbsp;&nbsp;![](https://img.shields.io/badge/platform-Linux-blue)&nbsp;&nbsp;![Python 3.7](https://img.shields.io/badge/Python-v3.7-blue)&nbsp;&nbsp;![](https://img.shields.io/badge/Docker-v17.03.0+-blue)&nbsp;&nbsp;[![](https://img.shields.io/github/license/Yu-HaoYu/Ferryman?color=red)](https://github.com/Yu-HaoYu/Ferryman/blob/master/LICENSE)

> &#8195;&#8195;国内因某些原因无法直接访问谷歌gcr.io导致无法直接获取K8s系列镜像，虽有部分云厂商提供K8s镜像，但可能不包含quay.io的系列镜像，且部分docker.io镜像即使配置国内镜像加速器地址还是速度缓慢，经测试阿里云的镜像加速器地址与个人免费镜像仓库镜像拉取速度对比，后者要比前者快2~3倍。
>
> &#8195;&#8195;基于以上背景，开发出该镜像同步工具，主要用于将镜像同步到国内个人仓库，从而获取被墙的镜像与提高镜像拉取速度。

<br/>

## **功能**

- 全量：同步仓库下所有Tag

- 限量：同步当下最新指定数量的Tag

<br/>

## 同步信息

### 支持同步源

> docker.io其实国内有很多镜像加速器，之所以支持docker.io是因为亲测阿里云的镜像加速器地址与个人免费镜像仓库镜像拉取对比，后者要比前者快一倍以上。

- gcr.io
- quay.io
- docker.io

<br/>

### 同步列表

> 本项目已托管到GitHub Actions，以下镜像列表每隔6小时自动同步更新一次；
>
> 已同步镜像的版本号列表可查看`history`目录下对应txt文件。

| 镜像源     | 命名空间                      | 镜像                       |
| ---------- | ----------------------------- | -------------------------- |
| k8s.gcr.io |                               | kube-proxy                 |
| k8s.gcr.io |                               | kube-scheduler             |
| k8s.gcr.io |                               | kube-controller-manager    |
| k8s.gcr.io |                               | kube-apiserver             |
| k8s.gcr.io |                               | etcd                       |
| k8s.gcr.io |                               | coredns                    |
| k8s.gcr.io |                               | pause                      |
| k8s.gcr.io |                               | kubernetes-dashboard-amd64 |
| k8s.gcr.io |                               | metrics-server-amd64       |
| k8s.gcr.io | ingress-nginx                 | controller                 |
| k8s.gcr.io | descheduler                   | descheduler                |
| k8s.gcr.io | autoscaling | cluster-autoscaler |
| quay.io    | coreos                        | flannel                    |
| quay.io    | kubernetes-ingress-controller | nginx-ingress-controller   |
| quay.io    | coreos                        | kube-state-metrics:v1.9.7  |
| docker.io  | kubesphere                    | ks-installer               |
| docker.io  | kubernetesui                  | dashboard                  |
| docker.io  | jenkins                       | jenkins                    |
| docker.io  | jenkins                       | inbound-agent              |
| docker.io  | maorfr                        | kube-tasks                 |
| docker.io  | kiwigrid                      | k8s-sidecar                |
| docker.io  | jenkinsci                     | blueocean                  |
| docker.io  | sonatype                      | nexus3                     |
| docker.io  | gitlab                        | gitlab-ce                  |
| docker.io  | gitlab                        | gitlab-runner              |
| docker.io  | jumpserver                    | jms_all                    |
| docker.io  | jettech                       | kube-webhook-certgen       |
| docker.io  | library                       | docker                     |
| docker.io  | library                       | sonarqube                  |
| docker.io  | library                       | traefik                    |
| docker.io  | library                       | nginx                      |
| docker.io  | library                       | tomcat                     |
| docker.io  | library                       | openjdk                    |
| docker.io  | library                       | mysql                      |
| docker.io  | library                       | redis                      |
| docker.io  | library                       | busybox                    |
| docker.io  | library                       | alpine                     |






<br/>

### 同步源对应地址

| 源         | 目标                                                         |
| ---------- | ------------------------------------------------------------ |
| k8s.gcr.io | **registry.cn-shenzhen.aliyuncs.com/kubernetes_aliyun/**{image}:{tag} |
| quay.io    | **registry.cn-shenzhen.aliyuncs.com/quayio_aliyun/**{image}:{tag} |
| docker.io  | **registry.cn-shenzhen.aliyuncs.com/dockerio_aliyun/**{image}:{tag} |

**镜像拉取示例**

**前**：docker pull k8s.gcr.io/pause:2.0

**后**：docker pull registry.cn-shenzhen.aliyuncs.com/kubernetes_aliyun/pause:2.0



<br/>

## 文件说明

- ### ferryman.py

  - 主脚本
  
- ### items.yml

  - 存放需要同步的镜像列表，可根据自身需求修改。
  - `limit`字段用于限制每次更新版本数量，默认为9999，可根据自身需求修改。

- ### history（目录）

  - 存放每个镜像的同步记录，程序会跳过已同步记录，首次使用时请先删除整个目录。

<br/>

## 使用说明

1. **配置私有镜像仓库账号密码**

   编辑`ferryman.py`修改以下内容为你的个人镜像仓库账号密码

   ```shell
   target_auth = {'username': 'Your username', 'password': 'Your password'}
   ```

   **或**

   使用临时环境变量配置你的个人镜像仓库账号密码

   ```shell
   export TARGET_USER='Your username'
   export TARGET_PASSWORD='Your password'
   ```

2. **配置私有镜像仓库地址**

   编辑`items.yml`修改每个项目`target`指向你的个人镜像仓库（尾部要以“/”结束）

   ```yaml
   kube-apiserver:
     source: k8s.gcr.io/
     target: registry.cn-shenzhen.aliyuncs.com/kubernetes_aliyun/
   ```

3. **删除本仓库的同步记录**：删除`history`目录，否则程序运行时会读取并跳过已同步的历史记录

4. **运行程序**：`python ferryman.py`

<br/>

## 更新记录

- **2020/05/10**    初始化

- **2020/05/11**    重新封装docker-py的push方法，增加登录仓库验证失败提示与显示推送进度

- **2020/05/17**    重写核心部分，不向后兼容

<br/>

## 已知问题

1. 当前项目配置文件因为结构问题，所以暂不支持存在相同项目名，待支持。

<br/>

## 流程图

> 以下图片可能因GWF原因无法正常显示

![流程图](https://s1.ax1x.com/2020/05/15/YrIXXq.png)

## 相似项目指引

- https://github.com/deislabs/oras
- https://github.com/containers/skopeo
- https://github.com/containers/image
- https://github.com/AliyunContainerService/image-syncer