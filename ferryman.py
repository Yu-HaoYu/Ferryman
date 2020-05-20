#!/usr/bin/python
import os,datetime,logging,json,re
import requests
import yaml
import docker
from retry.api import retry_call


logging.basicConfig(
    level=logging.INFO,
    #level=logging.DEBUG,
    format='[%(asctime)s] [%(levelname)s] [%(funcName)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

pydocker = docker.APIClient(timeout=60, base_url='unix:///var/run/docker.sock')

#################################################

# 目标私人仓库认证
# 优先从环境变量TARGET_USER、TARGET_PASSWORD获取私人仓库账号密码，用于支持GitHub Actions
if os.environ.get('TARGET_USER') and os.environ.get('TARGET_PASSWORD'):
    target_user = os.environ.get('TARGET_USER')
    target_password = os.environ.get('TARGET_PASSWORD')
    target_auth = { 'username': target_user, 'password': target_password }
else:
    target_auth = {'username': 'Your username', 'password': 'Your password'}


# 重新封装Docker模块Push方法，增加登录验证失败报错与推送镜像时显示进度条
def docker_push(image, auth):
    output = pydocker.push(image, auth_config=auth, stream=True, decode=True)
    for line in output:
        if line.get("error"):
            raise InterruptedError(line.get("error").replace('\n', ' '))
        if line.get("progress"):
            print(line.get("status"), line.get("progress"), end="\r")
    return


# 创建目录
def create_dir(dir_path):
    if os.path.exists(dir_path):
        logging.info (f"The {dir_path} directory already exists")
    else:
        logging.info (f"No directory found for {dir_path}")
        os.makedirs(dir_path)
        logging.info (f"Create {dir_path} directory")
    return


# 加载同步项目清单（YML文件）
def load_yml(file):
    logging.info (f"Load YML File: {file}")
    with open(file, "rb") as f:
        result = yaml.load(f, Loader=yaml.SafeLoader)
        logging.debug (f"Load YML File:  {result}")
    return result


# 读取本地历史更新记录
def load_history(items, domain):
    file = (f"./history/{domain}__{items}.txt")
    result = []
    if os.path.exists(file):
        logging.debug (f"Discover local history files: {file}")
        with open(file, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip('\n').split("\t\t")
                result.append({f"dt": line[0], "sha256": line[1], "tag": line[2]})
        logging.debug (f"Local List: Count {len(result)}, {result}")
    else:
        logging.debug (f"Can't find local history file: {file}")
    return result


# 回写增量同步记录到本地历史记录
def write_history(items, domain, local_list):
    file = (f"./history/{domain}__{items}.txt")
    f = open(file, 'w', encoding='utf-8')
    for i in local_list:
        f.write(f'{i["dt"]}\t\t{i["sha256"]}\t\t{i["tag"]}\n')
    f.close()
    logging.info ("Append tags to local history")
    return


# 日期时间转换，输出统一格式日期
def datetime_conv(dt):
    dt = str(dt)
    if dt.isdigit():
        if len(dt) > 10:
            dt = int(dt)/1000
        d = datetime.datetime.fromtimestamp(int(dt))
    else:
        d = datetime.datetime.strptime(dt, '%Y-%m-%dT%H:%M:%S.%fZ')
    result = d.strftime("%Y-%m-%d %H:%M:%S")
    return result


# 获取k8s的tag
def requests_gcr(items, namespaces = "none"):
    logging.info (f"The current mirror source is k8s.gcr.io")
    # 获取Tag
    url = (f"https://k8s.gcr.io/v2/{items}/tags/list")
    r = requests.get(url)
    response_dict = r.json().get("manifest")
    # 提取Tag、Date、sha256
    src_list = []
    for v in response_dict.items():
        if len(v[1]["tag"]) != 0:
            tag = v[1]["tag"][0]
            sha256 = v[0]
            dt = datetime_conv(v[1]["timeUploadedMs"])
            src_list.append({"dt": dt, "sha256": sha256, "tag": tag})
    # 按时间字段排序
    result = sorted(src_list, key=lambda x: x["dt"],reverse=True)
    return result


# 获取quay.io的tag
def requests_quay(items, namespaces = "none"):
    logging.info (f"The current mirror source is quay.io")
    # 循环获取Tag
    response_list = []
    for i in range(100):
        page = (i + 1)
        url = (f"https://quay.io/api/v1/repository/{namespaces}/{items}/tag?limit=100&page={page}&onlyActiveTags=true")
        r = requests.get(url)
        buffer_list = r.json().get("tags")

        if len(buffer_list) != 0:
            logging.info (f"The { page } page, tags count {len (buffer_list)}")
            for x in buffer_list:
                response_list.append(x)
        else:
            logging.info (f"The { page } page, this is the last page")
            break
    # 提取Tag、Date、sha256
    src_list = []
    for i in response_list:
        tag = i["name"]
        sha256 = i["manifest_digest"]
        if "start_ts" in i.keys():
            dt = datetime_conv(i["start_ts"])
        else:
            dt = datetime_conv(0)
        src_list.append({"dt": dt, "sha256": sha256, "tag": tag})
    # 按时间字段排序
    result = sorted(src_list, key=lambda x: x["dt"],reverse=True)
    return result


# 获取dockio.io的tag
def requests_docker(items, namespaces = "none"):
    logging.info (f"The current mirror source is docker.io")
    # 循环获取Tag
    response_list = []
    for i in range(100):
        page = (i + 1)
        url = (f"https://hub.docker.com/v2/repositories/{namespaces}/{items}/tags?page_size=100&page={page}")
        r = requests.get(url)
        buffer_list = r.json().get("results")

        if len(buffer_list) != 0:
            logging.info (f"The { page } page, tags count {len (buffer_list)}")
            for x in buffer_list:
                response_list.append(x)
        else:
            logging.info  (f"The { page } page, this is the last page")
            break
    # 提取Tag和Date
    src_list = []
    for v in response_list:
        tag = v["name"]
        # Get datetime
        if v['last_updated'] == None:
            dt = datetime_conv(0)
        else:
            dt = datetime_conv(v["last_updated"])
        # Get sha256
        for x in v['images']:
            if x['architecture'] == "amd64":
                if "digest" in x.keys():
                    sha256 = x['digest']
                else:
                    sha256 = "Unknown"
                src_list.append({"dt": dt, "sha256": sha256, "tag": tag})
    # 按时间字段排序
    result = sorted(src_list, key=lambda x: x["dt"],reverse=True)
    return result


# 定义镜像缓存队列
queue_list = []
# 清理缓存镜像
def cache_cleanup():
    global queue_list
    for i in range(len(queue_list)):
        logging.debug (f"Queue count: {len(queue_list)}，Current clean image: {queue_list[0]}")
        pydocker.remove_image(queue_list[0])
        queue_list.pop(0)
        if len(queue_list) == 0:
            logging.debug (f"Queue count: {len(queue_list)}")
    return


# 镜像同步
def sync_images(image, src_repo, target_repo, tag_list):
    try:
        for num, item in enumerate(tag_list, start=1):
            total = len(tag_list)
            tag = item['tag']
            dt = item['dt']
            sha256 = item['sha256']

            source = src_repo + image + ":" + tag
            target = target_repo + image + ":" + tag
            domain = src_repo.split("/")[0]

            starttime = datetime.datetime.now()
            logging.info (f"({num}/{total}) {image}:{tag}")
            logging.info (f"Image Update: {dt}")

            logging.info (f"Pull Image: {image}, Tag: {tag}")
            retry_call(pydocker.pull, fargs=[source], exceptions=Exception, tries=6, delay=10)

            logging.info (f"Tag  Image: {image}, Tag: {tag}")
            pydocker.tag(source, target)
            #pydocker.remove_image(source)

            logging.info (f"Push Image: {image}, Tag: {tag}")
            retry_call(docker_push, fargs=[target, target_auth] , exceptions=Exception, tries=6, delay=10)
            pydocker.remove_image(target)

            # 加载本地历史同步记录
            local_list = load_history(image, domain)
            logging.debug (f"History list: Count {len(local_list)}, {local_list}")
            # 以当前Tag去重后排序回写
            local_list = [i for i in local_list if tag != i["tag"]]
            local_list.append({"dt": dt, "sha256": sha256, "tag": tag})
            local_list.sort(reverse=True, key=lambda x: x["dt"])
            write_history(image, domain, local_list)

            # 缓存镜像：缓存几个镜像在队列中，然后先进先出循环删除（利用缓存镜像加速相似镜像拉取速度） 
            global queue_list
            queue_list.append(source)
            if len(queue_list) == 6:
                logging.debug (f"Count before clearing the queue: {len(queue_list)}，Queue list: {queue_list}")
                logging.debug (f"Current clean image: {queue_list[0]}")
                pydocker.remove_image(queue_list[0])
                queue_list.pop(0)
                logging.debug (f"Count after clearing the queue: {len(queue_list)}，Queue list: {queue_list}")

            endtime = datetime.datetime.now()
            logging.info ("Execution time: %s\n" %(endtime - starttime))
    except (Exception, KeyboardInterrupt) as e:
        # 缓存镜像：结束前删除队列中剩余镜像
        cache_cleanup()

        logging.error (e)
        logging.warning ("%s Sync Failed, Abnormal Exit!" % image)
        exit(1)
    else:
        # 缓存镜像：结束前删除队列中剩余镜像
        cache_cleanup()

        logging.info ("%s Sync Success" % image)
    return


# 主逻辑
def main(yml):
    # 获取同步项目清单
    for (key, value) in yml.items():
        items = key
        source = value["source"]
        domain = source.split("/")[0]
        namespaces = source.split("/")[-2]
        target = value["target"]
        limit = value["tag"]["limit"]
        
        # 开始同步
        logging.info (f"Start syncing: {items}")
        logging.info (f"Update limit: {limit}")

        # 判断源
        if "k8s.gcr.io" in source:
            src_list = requests_gcr(items)
        elif 'quay.io' in source:
            src_list = requests_quay(items, namespaces)
        elif 'docker.io' in source:
            src_list = requests_docker(items, namespaces)
        else:
            logging.info ("Unsupported sync source")
            exit ()

        # 排除掉Win平台的Tag
        new_src_list = src_list.copy()
        for i in new_src_list:
            if "windowsservercore" in str(i) or "nanoserver" in str(i):
                src_list.remove(i)
        new_src_list.clear()

        # 限制更新Tag数量
        src_list = src_list[:limit]

        logging.info (f"Latest version: {src_list[0]['tag']}, Lastst updated: {src_list[0]['dt']}")
        logging.debug (f"Src list: Count {len(src_list)}, {src_list}")

        # 加载本地同步记录
        history_list = load_history(items, domain)

        logging.debug (f"History list: Count {len(history_list)}, {history_list}")

        # 递归获取源列表与本地列表差集
        dedupl_list = src_list.copy()
        for i in history_list:
            for x in src_list:
                if i["sha256"] in x.values() and i["tag"] in x.values():
                    dedupl_list.remove(x)

        # 按时间字段排序（降序）
        dedupl_list.sort(reverse=True, key=lambda x: x['dt'])

        logging.debug (f"Sync list: Count {len(dedupl_list)}, {dedupl_list}")
        # 如果同步列表为空则不同步
        if not dedupl_list:
            logging.info (f"Src List: {len(src_list)}, History List: {len(history_list)}, Sync List: {len(dedupl_list)}")
            logging.info (f"The Sync list of the {items} is empty, no need to sync.")
            logging.info (f"{items} Sync Success")
        else:
            logging.info (f"Src List: {len(src_list)}, History List: {len(history_list)}, Sync List: {len(dedupl_list)}")
            # 调用镜像同步
            for i in items.splitlines(True):
                sync_images(items, source, target, dedupl_list)
        print ()
    return


# 初始化
def init():
    logging.info ("Start synchronization")

    create_dir("history")
    yml_file = load_yml("items.yml")
    print ()
    main(yml_file)


# 入口
if __name__ == "__main__":
    init()


