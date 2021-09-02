import logging
from typing import Dict, List, Tuple
import yaml
import requests
import sys, os, datetime, logging, json, re, time

# Configuration item resolution
class Items():
    def __init__(self, item: Tuple):
        self.item = item
        self.repo_name = item[0]
        self.source = item[1]["source"]
        self.target = item[1]["target"]
        self.tag_limit = item[1]["tag"]["limit"]
        self.item_dict = self.resolve

    @property
    def __domain(self) -> str:
        return self.item[1]["source"].split("/")[0]

    @property
    def __namespaces(self) -> str:
        return self.item[1]["source"].split("/")[-2]

    @property
    def resolve(self) -> Dict:
        item_dict = {}
        item_dict["repo_name"] = self.repo_name
        item_dict["source"] = self.source

        item_dict["domain"] = self.__domain
        if self.__domain != self.__namespaces:
            item_dict["namespaces"] = self.__namespaces

        item_dict["target"] = self.target
        item_dict["tag_limit"] = self.tag_limit
        return item_dict

# Source repository
class SourceRepo():
    def __init__(self, item: Dict):
        self.item = item
        self.src_list = self.__init(item)

    def __init(self, item: Dict) -> List:
        source_repo = item["source"]

        if "k8s.gcr.io" in source_repo:
            src_list = self.gcr(**item)
        elif "quay.io" in source_repo:
            src_list = self.quay(**item)
        elif "docker.io" in source_repo:
            src_list = self.docker(**item)
        else:
            logging.error("Unsupported sync source")
            exit(1)
        return src_list

    # Date format conversion
    def datetime_conv(self, dt):
        dt = str(dt)
        if dt.isdigit():
            if len(dt) > 10:
                dt = int(dt) / 1000
            d = datetime.datetime.fromtimestamp(int(dt))
        else:
            d = datetime.datetime.strptime(dt, '%Y-%m-%dT%H:%M:%S.%fZ')
        result = d.strftime("%Y-%m-%d %H:%M:%S")
        return result

    # Get the list of gcr tags
    def gcr(self, repo_name, **kwargs):
        logging.info(f"Repo: {repo_name}, Source: k8s.gcr.io")

        # Get a list of tags
        if kwargs.get("namespaces") is None:
            url = (f"https://k8s.gcr.io/v2/{repo_name}/tags/list")
        else:
            namespaces = kwargs['namespaces']
            url = (f"https://k8s.gcr.io/v2/{namespaces}/{repo_name}/tags/list")
        r = requests.get(url)
        response_dict = r.json().get("manifest")

        # Extract tag, date, sha256
        src_list = []
        for v in response_dict.items():
            if len(v[1]["tag"]) != 0:
                tag = v[1]["tag"][0]
                sha256 = v[0]
                dt = self.datetime_conv(v[1]["timeUploadedMs"])
                src_list.append({"dt": dt, "sha256": sha256, "tag": tag})

        # Sort by time field
        result = sorted(src_list, key=lambda x: x["dt"], reverse=True)
        return result

    # 获取quay.io的tag
    def quay(self, repo_name, **kwargs):
        logging.info(f"Repo: {repo_name}, Source: quay.io")
        items = repo_name
        namespaces = kwargs['namespaces']

        # 循环获取Tag
        response_list = []
        for i in range(100):
            page = (i + 1)
            url = (f"https://quay.io/api/v1/repository/{namespaces}/{items}/tag?limit=100&page={page}&onlyActiveTags=true")
            r = requests.get(url)
            buffer_list = r.json().get("tags")

            if len(buffer_list) != 0:
                logging.info(f"The {page} page, tags count {len(buffer_list)}")
                for x in buffer_list:
                    response_list.append(x)
            else:
                logging.info(f"The {page} page, this is the last page")
                break
        # 提取Tag、Date、sha256
        src_list = []
        for i in response_list:
            tag = i["name"]
            sha256 = i["manifest_digest"]
            if "start_ts" in i.keys():
                dt = self.datetime_conv(i["start_ts"])
            else:
                dt = self.datetime_conv(0)
            src_list.append({"dt": dt, "sha256": sha256, "tag": tag})
        # 按时间字段排序
        result = sorted(src_list, key=lambda x: x["dt"], reverse=True)
        return result


    # 获取dockio.io的tag
    def docker(self, repo_name, **kwargs):
        logging.info(f"Repo: {repo_name}, Source: docker.io")
        items = repo_name
        namespaces = kwargs['namespaces']

        # 循环获取Tag
        response_list = []
        for i in range(100):
            time.sleep(1)
            page = (i + 1)
            url = (f"https://hub.docker.com/v2/repositories/{namespaces}/{items}/tags?page_size=100&page={page}")
            r = requests.get(url)
            buffer_list = r.json().get("results")

            if len(buffer_list) != 0:
                logging.info(f"The {page} page, tags count {len(buffer_list)}")
                for x in buffer_list:
                    response_list.append(x)
            else:
                logging.info(f"The {page} page, this is the last page")
                break
        # 提取Tag和Date
        src_list = []
        for v in response_list:
            tag = v["name"]
            # Get datetime
            if v['last_updated'] == None:
                dt = self.datetime_conv(0)
            else:
                dt = self.datetime_conv(v["last_updated"])
            # Get sha256
            for x in v['images']:
                if x['architecture'] == "amd64" and x['os'] != "windows":
                    if "digest" in x.keys():
                        sha256 = x['digest']
                    else:
                        sha256 = "Unknown"
                    src_list.append({"dt": dt, "sha256": sha256, "tag": tag})
        # 按时间字段排序
        result = sorted(src_list, key=lambda x: x["dt"], reverse=True)
        return result


# Create a directory
def create_dir(dir: str) -> None:
    if os.path.exists(dir):
        logging.info(f"The {dir} directory already exists")
    else:
        logging.info(f"No directory found for {dir}")
        os.makedirs(dir)
        logging.info(f"Create {dir} directory")
    return


# Load the list of synchronized items (YML file)
def load_yml(file: str) -> dict:
    logging.info(f"Load YML File: {file}")
    with open(file, "rb") as f:
        result = yaml.load(f, Loader=yaml.SafeLoader)
        logging.debug(f"Load YML File: {result}")
    return result

# Login authentication
def auth() -> dict:
    try:
        target_user = os.environ.get('TARGET_USER')
        target_password = os.environ.get('TARGET_PASSWORD')
        docker_auth = {
            'username': target_user,
            'password': target_password
        }
    except ValueError:
        sys.exit(f'ERROR: The environment variable `TARGET_USER` or `TARGET_PASSWORD` cannot be found, please check')
    return docker_auth