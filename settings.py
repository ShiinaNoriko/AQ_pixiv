import configparser
import os

config_path = os.path.join(os.getcwd(), "config.txt")
cf = configparser.ConfigParser()
cf.read(config_path)

PIXIV_ID = cf.get(section="pixiv", option="pixiv_id")
PASSWORD = cf.get(section="pixiv", option="password")

RANK_TYPE = cf.get(section="image", option="rank_type")

DOWNLOAD_THREADS = cf.getint(section="download", option="max_threads")

DOWNLOAD_QUANTITY = cf.getint(section="image", option="download_quantity")

DOWNLOAD_P = cf.getboolean(section="image", option="download_p")

WELCOME = "欢迎使用PixivRankDownload"
VERSION = "1.0"
