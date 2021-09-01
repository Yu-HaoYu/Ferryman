#!/usr/bin/python
import sys, os, datetime, logging, json, re
import requests
import yaml
import docker
from retry.api import retry_call

from typing import Dict, List
from config import config
from utils import Items, SourceRepo

# # Define the log format
# logging.basicConfig(
#     level=logging.INFO,
#     # level=logging.DEBUG,
#     format='[%(asctime)s] [%(levelname)s] [%(funcName)s] %(message)s',
#     datefmt='%Y-%m-%d %H:%M:%S'
# )

# Create docker client
docker_client = docker.APIClient(timeout=60, base_url='unix:///var/run/docker.sock')


#################################################

class Utils():
    def __init__(self):
        # Init
        self.__init()

    # Init
    def __init(self) -> None:
        self.create_dir("history")

    # Login authentication
    @staticmethod
    def auth() -> dict:
        try:
            target_user = os.environ.get('TARGET_USER')
            target_password = os.environ.get('TARGET_PASSWORD')
            auth = {
                'username': target_user,
                'password': target_password
            }
        except ValueError:
            sys.exit(
                f'ERROR: The environment variable `TARGET_USER` or `TARGET_PASSWORD` cannot be found, please check')
        return auth

    # Create a directory
    def create_dir(self, dir: str) -> None:
        if os.path.exists(dir):
            logging.info(f"The {dir} directory already exists")
        else:
            logging.info(f"No directory found for {dir}")
            os.makedirs(dir)
            logging.info(f"Create {dir} directory")
        return

    # Load the list of synchronized items (YML file)
    def load_yml(self, file: str) -> dict:
        logging.info(f"Load YML File: {file}")
        with open(file, "rb") as f:
            result = yaml.load(f, Loader=yaml.SafeLoader)
            logging.debug(f"Load YML File: {result}")
        return result


# 重新封装Docker模块Push方法，增加登录验证失败报错与推送镜像时显示进度条
def docker_push(image, auth):
    output = docker_client.push(image, auth_config=auth, stream=True, decode=True)
    for line in output:
        if line.get("error"):
            raise InterruptedError(line.get("error").replace('\n', ' '))
        if line.get("progress"):
            print(line.get("status"), line.get("progress"), end="\r")


# 读取本地历史更新记录
def load_history(items, domain):
    file = (f"./history/{domain}__{items}.txt")
    result = []
    if os.path.exists(file):
        logging.debug(f"Discover local history files: {file}")
        with open(file, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip('\n').split("\t\t")
                result.append({f"dt": line[0], "sha256": line[1], "tag": line[2]})
        logging.debug(f"Local List: Count {len(result)}, {result}")
    else:
        logging.debug(f"Can't find local history file: {file}")
    return result


# 回写增量同步记录到本地历史记录
def write_history(items, domain, local_list):
    file = (f"./history/{domain}__{items}.txt")
    f = open(file, 'w', encoding='utf-8')
    for i in local_list:
        f.write(f'{i["dt"]}\t\t{i["sha256"]}\t\t{i["tag"]}\n')
    f.close()
    logging.info("Append tags to local history")
    return

# 定义镜像缓存队列
queue_list = []
# 清理缓存镜像
def cache_cleanup():
    global queue_list
    for i in range(len(queue_list)):
        logging.debug(f"Queue count: {len(queue_list)}，Current clean image: {queue_list[0]}")
        docker_client.remove_image(queue_list[0])
        queue_list.pop(0)
        if len(queue_list) == 0:
            logging.debug(f"Queue count: {len(queue_list)}")
    return


# 镜像同步
def sync_images(image, src_repo, target_repo, target_auth, tag_list):
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
            logging.info(f"({num}/{total}) {image}:{tag}")
            logging.info(f"Image Update: {dt}")

            logging.info(f"Pull Image: {image}, Tag: {tag}")
            retry_call(docker_client.pull, fargs=[source], exceptions=Exception, tries=6, delay=10)

            logging.info(f"Tag  Image: {image}, Tag: {tag}")
            docker_client.tag(source, target)
            # pydocker.remove_image(source)

            logging.info(f"Push Image: {image}, Tag: {tag}")
            retry_call(docker_push, fargs=[target, target_auth], exceptions=Exception, tries=6, delay=10)
            docker_client.remove_image(target)

            # 加载本地历史同步记录
            local_list = load_history(image, domain)
            logging.debug(f"History list: Count {len(local_list)}, {local_list}")
            # 以当前Tag去重后排序回写
            local_list = [i for i in local_list if tag != i["tag"]]
            local_list.append({"dt": dt, "sha256": sha256, "tag": tag})
            local_list.sort(reverse=True, key=lambda x: x["dt"])
            write_history(image, domain, local_list)

            # 缓存镜像：缓存几个镜像在队列中，然后先进先出循环删除（利用缓存镜像加速相似镜像拉取速度） 
            global queue_list
            queue_list.append(source)
            if len(queue_list) == 6:
                logging.debug(f"Count before clearing the queue: {len(queue_list)}，Queue list: {queue_list}")
                logging.debug(f"Current clean image: {queue_list[0]}")
                docker_client.remove_image(queue_list[0])
                queue_list.pop(0)
                logging.debug(f"Count after clearing the queue: {len(queue_list)}，Queue list: {queue_list}")

            endtime = datetime.datetime.now()
            logging.info("Execution time: %s\n" % (endtime - starttime))
    except (Exception, KeyboardInterrupt) as e:
        # 缓存镜像：结束前删除队列中剩余镜像
        cache_cleanup()

        logging.error(e)
        logging.warning("%s Sync Failed, Abnormal Exit!" % image)
        exit(1)
    else:
        # 缓存镜像：结束前删除队列中剩余镜像
        cache_cleanup()

        logging.info("%s Sync Success" % image)
    return

# main
if __name__ == "__main__":


    logging.info("Start synchronization")

    target_auth = Utils.auth()

    # 获取同步项目清单
    for i in config.items():
        item: Dict = Items(i).resolve
        src_list = SourceRepo(item).src_list

        repo_name = item["repo_name"]
        domain = item["domain"]
        source = item["source"]
        target = item["target"]

        # 排除掉Win平台、Gitlab-ce nightly
        new_src_list = src_list.copy()
        for i in new_src_list:
            if "windowsservercore" in str(i) or "nanoserver" in str(i) or "nightly" in str(i) or "windows" in str(i):
                src_list.remove(i)
        new_src_list.clear()

        # 限制更新Tag数量
        src_list = src_list[:item["tag_limit"]]

        logging.info(f"Latest version: {src_list[0]['tag']}, Lastst updated: {src_list[0]['dt']}")
        logging.debug(f"Src list: Count {len(src_list)}, {src_list}")

        # 加载本地同步记录
        history_list = load_history(repo_name, domain)

        logging.debug(f"History list: Count {len(history_list)}, {history_list}")

        # 递归获取源列表与本地列表差集
        dedupl_list = src_list.copy()
        for i in history_list:
            for x in src_list:
                if i["sha256"] in x.values() and i["tag"] in x.values():
                    dedupl_list.remove(x)

        # 按时间字段排序（降序）
        dedupl_list.sort(reverse=True, key=lambda x: x['dt'])

        logging.debug(f"Sync list: Count {len(dedupl_list)}, {dedupl_list}")
        # 如果同步列表为空则不同步
        if not dedupl_list:
            logging.info(f"Src List: {len(src_list)}, History List: {len(history_list)}, Sync List: {len(dedupl_list)}")
            logging.info(f"The Sync list of the {repo_name} is empty, no need to sync.")
            logging.info(f"{repo_name} Sync Success")
        else:
            logging.info(f"Src List: {len(src_list)}, History List: {len(history_list)}, Sync List: {len(dedupl_list)}")
            # 调用镜像同步
            for i in repo_name.splitlines(True):
                print(repo_name, source)
                sync_images(repo_name, source, target, target_auth, dedupl_list)
        print()
