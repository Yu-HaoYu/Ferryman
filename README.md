# Ferryman
## 简介

- K8s镜像仓库同步工具，用于同步国外K8s镜像仓库到国内个人镜像仓库
- 支持源仓库种类
  - gcr.io
  - quay.io
  - docker.io（待支持）

### 仓库对应地址

| 源         | 目标                                                         |
| ---------- | ------------------------------------------------------------ |
| k8s.gcr.io | registry.cn-shenzhen.aliyuncs.com/kubernetes_aliyun/{image}:{tag} |
| quay.io    | registry.cn-shenzhen.aliyuncs.com/quayio_aliyun/{image}:{tag} |

### 当前同步仓库列表

| 镜像源     | 镜像                       |
| ---------- | -------------------------- |
| k8s.gcr.io | kube-proxy                 |
| k8s.gcr.io | kube-scheduler             |
| k8s.gcr.io | kube-controller-manager    |
| k8s.gcr.io | kube-apiserver             |
| k8s.gcr.io | etcd                       |
| k8s.gcr.io | coredns                    |
| k8s.gcr.io | pause                      |
| k8s.gcr.io | kubernetes-dashboard-amd64 |
| quay.io    | flannel                    |
| quay.io    | nginx-ingress-controller   |

## 功能

- 全量：全量同步仓库下所有Tag
- 限量：同步限定数量的Tag（待支持）
- 指定：只同步指定Tag（待支持）

## 文件说明

- ### ferryman.py

  - 主脚本
  
- ### items.yml

  - 存放需要同步的镜像列表


- ### history（目录）

  - 存放每个镜像的同步记录


## 使用说明

1. **配置私有镜像仓库账号密码**：编辑`ferryman.py`文件修改以下内容为你的认证仓库账号密码

   ```shell
   target_auth = {'username': 'Your username', 'password': 'Your password'}
   ```

   

2. **配置私有镜像仓库地址**：编辑`items.yml`文件，修改每个项目`target`指向你的私有镜像仓库

   ```yaml
   kube-apiserver:
     source: k8s.gcr.io/
     target: registry.cn-shenzhen.aliyuncs.com/kubernetes_aliyun/
   ```



3. **运行程序**：`python ferryman.py`



## 更新记录

- **2020/05/10**    初始化
- **2020/05/11**    重新封装docker-py的push方法，增加登录仓库验证失败提示与显示推送进度



## 待更新计划

1. 支持docker.io
2. 支持指定Tag
3. 支持限制更新Tag数量
4. 初始化时判断能否访问gcr.io，提示是否在GWF内
5. gcr.io与quay.io存在同名项目，需要将history文件加前缀
7. 已知对Tag名进行排序存在纯英文Tag排到前面问题，需要后续根据Tag更新时间来排序
8. 已知更新Tag时没对latest进行特殊处理，需要后续进行处理
9. 日志增加输出到文件

