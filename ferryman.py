#!/usr/bin/python
import os,datetime,logging,json,re
import requests
import yaml
import docker
from retry.api import retry_call


logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] [%(levelname)s] [%(funcName)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

pydocker = docker.APIClient(timeout=60, base_url='unix:///var/run/docker.sock')

#################################################

# 目标仓库认证信息
# 优先从环境变量TARGET_USER、TARGET_PASSWORD获取私人仓库账号密码，用于支持 GitHub Actions
if os.environ.get('TARGET_USER') and os.environ.get('TARGET_PASSWORD'):
    target_user = os.environ.get('TARGET_USER')
    target_password = os.environ.get('TARGET_PASSWORD')
    target_auth = { 'username': target_user, 'password': target_password }
else:
    target_auth = {'username': 'Your username', 'password': 'Your password'}

# 重新封装Docker Push，支持登录验证失败报错与Push时显示进度条
def docker_push(image, auth):
    output = pydocker.push(image, auth_config=auth, stream=True, decode=True)
    for line in output:
        if line.get("error"):
            raise InterruptedError(line.get("error").replace('\n', ' '))
        if line.get("progress"):
            print(line.get("status"), line.get("progress"), end="\r")

# 创建日志目录
def create_dir(dir_path):
    if os.path.exists(dir_path):
        logging.info (f"The {dir_path} directory already exists")
    else:
        logging.info (f"No directory found for {dir_path}")
        os.makedirs(dir_path)
        logging.info (f"Create {dir_path} directory")

# 加载YML文件
def load_yml(file):
    logging.info (f"Load YML File: {file}")
    with open(file, "rb") as f:
        result = yaml.load(f, Loader=yaml.SafeLoader)
        logging.debug (f"Load YML File:  {result}")
    return result

# 读取本地历史更新记录
def load_history(items):
    file = (f"./history/{items}.txt")
    result = []
    if os.path.exists(file):
        logging.debug (f"Discover local history files: {file}")
        with open(file, 'r') as f:
            for line in f:
                result.append(line.strip('\n'))
        logging.debug (f"Local List: Count {len(result)}, {result}")
    else:
        logging.debug (f"Can't find local history file: {file}")
    return result

# 获取源仓库Tag更新列表
def request_http(items, source, namespaces):
    # 判断同步源
    if "k8s.gcr.io" in source:
        logging.info (f"The current mirror source is k8s.gcr.io")

        url = (f"https://k8s.gcr.io/v2/{items}/tags/list")
        r = requests.get(url)
        src_list = r.json().get("tags")

    elif 'quay.io' in source:
        logging.info (f"The current mirror source is quay.io, namespaces is {namespaces}")

        src_list = []
        for i in range(100):
            page = (i + 1)
            url = (f"https://quay.io/api/v1/repository/{namespaces}/{items}/tag?limit=100&page={page}&onlyActiveTags=true")
            r = requests.get(url)
            src_list_tmp = r.json().get("tags")

            if len(src_list_tmp) == 0:
                logging.info (f"The { page } page, this is the last page")
                break

            for x in src_list_tmp:
                src_list.append(x["name"])

            logging.info (f"The { page } page, tags count {len (src_list_tmp)}")

        logging.info (f"Tags Count: {len(src_list)}")
    else:
        logging.info ("No match")
        
    logging.debug (f"Src list: Count {len(src_list)}, {src_list}")

    sort_list = sorted(src_list, reverse=True, key=lambda x:tuple(int(v) for v in re.compile('-|_|[a-zA-Z]{1,15}|([0-9a-zA-Z]{32})').sub('0', x).split(".")))
    logging.debug (f"Re Sort list: Count {len(sort_list)}, {sort_list}")
    
    return sort_list

# 获取对比清单
def main(yml):
    for (key, value) in yml.items():
        items = key
        source = value["source"]
        namespaces = source.split("/")[-2]
        target = value["target"]
        begin = value["tag"]["begin"]
        limit = value["tag"]["limit"]
        
        # 开始同步
        logging.info (f"Start syncing: {items}")
        logging.debug (f"items: {items}, source: {source}, begin_tag: {begin}, limit_tag: {limit}")

        # list转化为set，使用集合相减去重，获得去重列表
        sort_list = request_http(items, source, namespaces)
        history_list = load_history(items)
        dedupl_list = list(set(sort_list) - set(history_list))
        sort_dedupl_list = sorted(dedupl_list, reverse=True, key=lambda x:tuple(int(v) for v in re.compile('-|_|[a-zA-Z]{1,15}|([0-9a-zA-Z]{32})').sub('0', x).split(".")))

        logging.debug (f"Src list: Count {len(sort_list)}, {sort_list}")
        logging.debug (f"Sync list: Count {len(sort_dedupl_list)}, {sort_dedupl_list}")

        # 如果同步列表为空则不同步
        if not sort_dedupl_list:
            logging.info (f"Src List: {len(sort_list)}, History List: {len(history_list)}, Sync List: {len(sort_dedupl_list)}, Latest: {sort_list[0]}")
            logging.info (f"The Sync list of the {items} is empty, no need to sync.")
            logging.info (f"{items} Sync Success")
        else:
            logging.info (f"Src List: {len(sort_list)}, History List: {len(history_list)}, Sync List: {len(sort_dedupl_list)}, Latest: {sort_list[0]}")
            # 调用同步函数
            for i in items.splitlines(True):
                sync_images(items, source, target, sort_dedupl_list)
        print ()
    return


# 同步镜像
def sync_images(image, src_repo, target_repo, tag_list):
    try:
        for tag in range(len(tag_list)):
            source = src_repo + image + ":" + tag_list[tag]
            target = target_repo + image + ":" + tag_list[tag]

            starttime = datetime.datetime.now()
            logging.info ("(%s/%s) %s %s" %(tag + 1,  len(tag_list), image, tag_list[tag]))

            logging.info ("Pull Image: %s, Tag: " %image + tag_list[tag])
            retry_call(pydocker.pull, fargs=[source], exceptions=Exception, tries=3, delay=5)

            logging.info ("Tag  Image: %s, Tag: " %image + tag_list[tag])
            pydocker.tag(source, target)
            pydocker.remove_image(source)

            logging.info ("Push Image: %s, Tag: " %image + tag_list[tag])
            retry_call(docker_push, fargs=[target, target_auth] , exceptions=Exception, tries=3, delay=5)
            pydocker.remove_image(target)

            # 加载历史记录，将当前已同步版本号追加到历史记录并写回本地
            local_list = load_history(image)
            local_list.append(tag_list[tag])
            sort_local_list = sorted(local_list, reverse=True, key=lambda x:tuple(int(v) for v in re.compile('-|_|[a-zA-Z]{1,15}|([0-9a-zA-Z]{32})').sub('0', x).split(".")))

            logging.info ("Append tags to local history")
            file=open('./history/%s.txt' %image,'w')
            file.write('\n'.join(sort_local_list))
            file.close()

            endtime = datetime.datetime.now()
            logging.info ("Execution time: %s\n" %(endtime - starttime))
    except Exception as e:
        logging.error (e)
        logging.warning ("%s Sync Failed, Abnormal Exit!" % image)
    else:
        logging.info ("%s Sync Success" % image) 

def init():
    logging.info ("Start synchronization")

    create_dir("history")
    yml_file = load_yml("items.yml")
    print ()
    main(yml_file)

if __name__ == "__main__":
    init()

