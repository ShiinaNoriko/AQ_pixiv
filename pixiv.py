import datetime
import json
import sqlite3
import time

import bs4
import pandas as pd
import PIL.Image
import PIL.ImageDraw
import PIL.ImageFont
import requests
from fake_useragent import UserAgent
from win32.win32crypt import CryptUnprotectData

from settings import *

_rank_page = {
    "r-18": "https://www.pixiv.net/ranking.php?mode=daily_r18&p={count}&format=json",
    "normal": "https://www.pixiv.net/ranking.php?mode=daily&p={count}&format=json"
}


class Pixiv(object):
    login_post_url = "https://accounts.pixiv.net/api/login?lang=zh"
    login_data_url = "https://accounts.pixiv.net/login?lang=zh&source=pc&view_type=page&ref=wwwtop_accounts_index"
    image_info_url = "https://www.pixiv.net/ajax/illust/{pid}"
    cookies_url = "https://www.google-analytics.com/analytics.js"
    current_time = time.strftime("%Y-%m-%d", time.localtime())

    rank_url = _rank_page[RANK_TYPE.lower()]
    headers = {"user-agent": UserAgent().random}
    quantity = DOWNLOAD_QUANTITY
    fileCheck = True

    author_id = []
    author_name = []
    image_rank = []
    image_id = []
    image_title = []
    pid_all = [[]]
    last_csv_date = 'null'
    yesterday_date = 'null'
    pid_list = []
    profile_download_list = [[]]
    original_download_list = [[]]

    def __init__(self):
        self.session = requests.session()
        self.__login()
        if RANK_TYPE == "r-18":
            cookies2 = self.get_cookie_from_chrome()
            for k,v in cookies2.items():
                self.session.cookies.set(k,v)
        self.create_today_path()  # 创建今日排行榜文件夹
        self.check_csv_list(2)  # 获取csv.txt，判断文件是否为空
        print('准备检测是否比对文件')
        if self.fileCheck is True:
            self.yesterday_date = self.get_yesterday()  # 通过系统获取昨日的日期
            self.check_csv_list()  # 获取csv.txt最后一行数据
            # print(self.last_csv_date.strip('\n'))
            # print(str(self.yesterday_date).strip('\n'))
            print('获取csv数据')
            if self.last_csv_date.strip('\n') == str(self.current_time).strip('\n'):
                print('今日数据已经获取过')
                # 提示用户今日操作已经进行过，无需再次进行
            elif self.last_csv_date.strip('\n') == str(self.yesterday_date).strip('\n'):
                print('昨日数据存在')
                print('获取今日排行数据')
                self.pid_list = self.__get_rank_list()  # 获取pid_list，用于图片的下载，同时会存储一份csv文件
                print('开始比对两日csv')
                # self.find_csv_repetition()
            else:
                print('昨日数据不存在')
                print('获取今日数据')
                self.pid_list = self.__get_rank_list()
                # 提示用户今日操作已经进行过，无需再次进行

    def __login(self):
        """
        登陆

        """
        print("正在登陆")
        data = self.session.get(url=self.login_data_url,
                                headers=self.headers).content.decode("utf8")
        post_key = bs4.BeautifulSoup(data, "lxml").find(
            attrs={"name": "post_key"})["value"]
        login_data = {
            "pixiv_id": PIXIV_ID,
            "password": PASSWORD,
            "post_key": post_key,
            "source": "pc",
            "ref": "wwwtop_accounts_index",
            "return_to": "https://www.pixiv.net/",
        }
        self.session.post(url=self.login_post_url, data=login_data)
        print("登陆完毕")

    def get_cookie_from_chrome(self, host='.pixiv.net'):
        """
        获取chrome的cookies，用于下载第二个排行

        """
        cookiepath=os.environ['LOCALAPPDATA']+r"\Google\Chrome\User Data\Default\Cookies"
        sql="select host_key,name,encrypted_value from cookies where host_key='%s'" % host
        with sqlite3.connect(cookiepath) as conn:
            cu=conn.cursor()        
            cookies={name:CryptUnprotectData(encrypted_value)[1].decode() for host_key,name,encrypted_value in cu.execute(sql).fetchall()}
            print(cookies)
        return cookies
        
    def __get_rank_list(self):
        """
        获取排行榜

        """
        print("正在拉取排行榜数据")
        count = 1
        pid_list = []
        pid_username = []
        pid_title = []
        pid_rank = []
        pid_userid = []
        pid_all = [[]]
        pid_yes_rank = []
        pid_profile = []
        pid_img_count = []
        pid_tags = [[]]

        for page in range(1, self.quantity+1, 50):
            json_data = json.loads(self.session.get(
                self.rank_url.format(count=count)).text)
            for item in json_data["contents"]:
                if item["rank"] < page + min(self.quantity, 50):
                    pid_list.append(item["illust_id"])
                    pid_username.append(item["user_name"])
                    pid_title.append(item["title"])
                    pid_rank.append(item["rank"])
                    pid_userid.append(item["user_id"])
                    pid_yes_rank.append(item["yes_rank"])
                    pid_profile.append(item["url"])
                    pid_img_count.append(item["illust_page_count"])
            count += 1
        print("排行榜数据拉取完成")
        self.profile_download_list = list(zip(pid_rank, pid_profile))
        self.original_download_list = list(
            zip(pid_rank, pid_list, pid_img_count))
        pid_all = list(zip(pid_rank, pid_title, pid_list, pid_username, pid_userid))
        self.pid_all = pid_all
        self.image_message_to_csv()
        self.check_csv_list(1)
        return pid_list

    def create_today_path(self):
        """
        创建今日作品存放的文件夹

        """
        dir_path = os.path.join('Image', RANK_TYPE, self.current_time)
        if not os.path.exists(dir_path):
            os.makedirs(dir_path)


    def image_message_to_csv(self):
        """
        将获取到的信息转化为csv
        包含排名，标题，作品ID，作者，作者ID

        """
        csv_listname = ['rank', 'title', 'illust_id', 'author', 'author_id']
        message_csv = pd.DataFrame(columns=csv_listname, data=self.pid_all)
        csv_name = os.path.join(
            'Image', RANK_TYPE, self.current_time, self.current_time + '.csv')
        message_csv.to_csv(csv_name, encoding='utf_8_sig', index=False)

    def find_csv_repetition(self): # 功能未实现
        """
         找出2个csv中重复的部分，对比文件为最近的2个csv，如文件数不足2个则跳过
         首先获取csv.txt最后一行的数据，找出对应的csv文件并读取，
         之后获取本次使用的csv文件
         判断两次文件是否重复

        """
        print('开始比对两日csv文件')
        last_csv_path = os.path.join(
            self.last_csv_date, self.last_csv_date + '.csv')
        today_csv_path = os.path.join(
            self.current_time, self.current_time + '.csv')
        last_csv = pd.read_csv(last_csv_path)
        today_csv = pd.read_csv(today_csv_path)
        df = pd.concat

    def get_yesterday(self):
        """

        获取昨日日期

        """
        yesterday = datetime.date.today() + datetime.timedelta(-1)
        return yesterday

    def check_csv_list(self, num=0):
        # 检测csv文件列表，保存于csv.txt
        # 当传入的数字为0时，功能为读取，一般读取最后一行，用于比对
        # 当传入的数字为1时，功能为写入，写入最新的日期csv
        # 当传入的数字为2时，功能为检查txt文件，一般检查是否为空，用于判断是否需要跳过某些操作
        # 部分功能未实现
        sysFile_path = os.path.join('sysFile')
        # print(sysFile_path)
        if not os.path.exists(sysFile_path):
            os.makedirs(sysFile_path)
        if RANK_TYPE == "normal":
            txt_path = os.path.join(sysFile_path, 'csv.txt')
        elif RANK_TYPE == "r-18":
            txt_path = os.path.join(sysFile_path, 'csv_r18.txt')
        if not os.path.exists(txt_path):
            file_txt = open(txt_path, 'a+')
            file_txt.writelines('1970-01-01\n')
            file_txt.close()
        if num == 0:
            # 获取txt最后一行数据
            # data = []
            # 文件较小可使用该方法，文件过大可使用偏移量读取
            file_txt = open(txt_path, 'r')
            # for line in file_txt:
            # data.append(line)
            data = file_txt.readlines()
            lastline = data[-1]
            self.last_csv_date = lastline.strip('\n')
            # print(lastline)
            file_txt.close()
        if num == 1:
            # 向txt中写入数据
            file_txt = open(txt_path, 'a')
            # print(self.current_time)
            file_txt.writelines(self.current_time)
            file_txt.write('\n')
            file_txt.close()
        if num == 2:
            #self.fileCheck = False
            file_txt = open(txt_path, 'r')
            data_num = len(file_txt.readlines())
            file_txt.close()
            # print(data_num)
            if data_num > 0:
                self.fileCheck = True
            else:
                pass
            pass

    def merge_image(self):
        """
        修改图片尺寸 ，用于制作缩略图

        """
        tmp_img_path = os.path.join('Cache', 'tmp')  # 每张图片下载下来的缩略图文件夹
        # print(tmp_img_path)
        null_list = []
        thumbnail_path = os.path.join('Cache', 'thumbnail')  # 处理后缩略图文件夹
        merged_img_path = os.path.join('Cache', 'merged', RANK_TYPE)
        if not os.path.exists(tmp_img_path):
            os.makedirs(tmp_img_path)
        if not os.path.exists(thumbnail_path):
            os.makedirs(thumbnail_path)
        if not os.path.exists(merged_img_path):
            os.makedirs(merged_img_path)

        tmp_list = os.listdir(tmp_img_path)
        if len(tmp_list) == 0:
            print('目标文件不存在')
            return False
        else:
            print(len(tmp_list))
            if len(tmp_list) < 100:
                for i in range(1, 101):
                    c = str(i) + '.jpg'
                    if c not in tmp_list:
                        print(c)
                        null_list.append(c)
            if null_list:
                for filename in null_list:
                    image_path = os.path.join('Cache', 'tmp', filename)
                    img_date = PIL.Image.new('RGB', (240, 320), (125, 125, 125))
                    img_draw = PIL.ImageDraw.Draw(img_date)
                    img_date.save(image_path)
                tmp_list = os.listdir(tmp_img_path)
            for filename in tmp_list:
                image_path = os.path.join('Cache', 'tmp', filename)
                self.reform_image(image_path, filename)
            merge_list = os.listdir(thumbnail_path)
            img_merged = PIL.Image.new(
                'RGB', (2400, 3200+300+50), (255, 255, 255))
            img_date = PIL.Image.new('RGB', (2400, 50), (255, 255, 255))
            img_font = PIL.ImageFont.truetype(
                os.path.join('sysFile', 'Font', 'simsun.ttc'), 36)
            img_draw = PIL.ImageDraw.Draw(img_date)
            img_draw.text((1000, 10), 'Pixiv每日排行 时间: ' +
                          self.current_time, fill=(0, 0, 0), font=img_font)
            img_merged.paste(img_date, (0, 0, 2400, 50))
            for i in range(1, 11):
                for j in range(1, 11):
                    # print(merge_list)
                    img_read_path = os.path.join(
                        thumbnail_path, merge_list[(i-1)*10+j-1])
                    img_read = PIL.Image.open(img_read_path)
                    img_merged.paste(
                        img_read, ((j-1)*240, 50+(i-1)*(320+30), j*240, 50+i*(320)+(i-1)*30))
                img_rank = PIL.Image.new('RGB', (2400, 30), (255, 255, 255))
                img_rank_font = PIL.ImageFont.truetype(
                    os.path.join('sysFile', 'Font', 'simsun.ttc'), 20)
                img_rank_draw = PIL.ImageDraw.Draw(img_rank)
                for k in range(1, 11):
                    # print(k)
                    img_rank_draw.text(
                        (100+(k-1)*240, 5), str(k+(i-1)*10), fill=(0, 0, 0), font=img_rank_font)
                img_merged.paste(
                    img_rank, (0, 50+320*i+(i-1)*30, 2400, 50+(320+30)*i))
            img_merged.save(os.path.join(merged_img_path,
                                         self.current_time+'merged.jpg'))
            img_path = os.path.join('Cache', 'tmp')
            thumbnail_path = os.path.join('Cache', 'thumbnail')
            # for files in image_path:
            for filename in os.listdir(img_path):
                img_path_tmp = os.path.join('Cache', 'tmp', filename)
                os.remove(img_path_tmp)
            print('临时缩略图删除完成')
            for filename in os.listdir(thumbnail_path):
                img_path_tmp = os.path.join('Cache', 'thumbnail', filename)
                os.remove(img_path_tmp)
            print('修改后缩略图删除完成')

    def reform_image(self, img_path, filename):
        """
        修改尺寸代码
        
        """
        # 先获取图片长宽，和240与320比较，尽量向符合的部分转换，多余部分用空白补足，居中。
        # 补足空白可以先看是哪部分需要补足，如果是height需要补足，则计算出resize后图片的高度，然后创建2个相同的，高度为需补足高度一半的空白
        # 之后拼接起来，注意图片的高度的奇偶，奇数可以适当调节为偶数，便于空白的增加
        # 读取到的文件名应该以rank为题目
        img = PIL.Image.open(img_path)
        img_width = img.size[0]
        img_height = img.size[1]
        # print(img_height/img_width)
        if img_height == 320 and img_width == 240:
            img.save(os.path.join('Cache', 'thumbnail', filename))
        else:
            img_new = PIL.Image.new('RGB', (240, 320), (255, 255, 255))
            if img_width == 240 and img_height < 320:
                #img_resize_height = int(240/img_width*img_height())
                if img_height % 2 == 1:
                    img_resize_height = img_height - 1
                else:
                    img_resize_height = img_height
                # print('img_resize_height', int((320-img_resize_height)/2))
                img_white = PIL.Image.new(
                    'RGB', (240, int((320-img_resize_height)/2)), (255, 255, 255))
                img_new.paste(
                    img_white, (0, 0, 240, int((320-img_resize_height)/2)))
                img_new.paste(img, (0, int((320-img_resize_height)/2),
                                    240, int((320-img_resize_height)/2+img_height)))
                # img_new.save(os.path.join('finish.png'))#记得改为rank
                #img_resized = img.resize((240,img_resize_height),PIL.Image.ANTIALIAS)

            elif img_height == 320 and img_width < 240:
                if img_width % 2 == 1:
                    img_resize_width = img_width - 1
                else:
                    img_resize_width = img_width

                img_white = PIL.Image.new(
                    'RGB', (int((240-img_resize_width)/2), 320), (255, 255, 255))
                img_new.paste(img_white, (0, 0, int(
                    (240-img_resize_width)/2), 320))
                img_new.paste(img, (int((240-img_resize_width)/2),
                                    0, int((240-img_resize_width)/2+img_width), 320))
                # img_new.save(os.path.join('finish.png'))#记得改为rank

            else:
                if img_height/img_width < 4/3:  # 横板图片，保持width不变
                    img_resize_height = int(240/img_width*img_height)
                    img_resized = img.resize(
                        (240, img_resize_height), PIL.Image.ANTIALIAS)
                    img_white = PIL.Image.new(
                        'RGB', (240, int((320-img_resize_height)/2)), (255, 255, 255))
                    img_new.paste(
                        img_white, (0, 0, 240, int((320-img_resize_height)/2)))
                    img_new.paste(img_resized, (0, int(
                        (320-img_resize_height)/2), 240, int((320-img_resize_height)/2)+img_resize_height))

                else:
                    img_resize_width = int(320/img_height*img_width)
                    img_resized = img.resize(
                        (img_resize_width, 320), PIL.Image.ANTIALIAS)
                    img_white = PIL.Image.new(
                        'RGB', (int((240-img_resize_width)/2), 320), (255, 255, 255))
                    img_new.paste(img_white, (0, 0, int(
                        (240-img_resize_width)/2), 320))
                    img_new.paste(img_resized, (int((240-img_resize_width)/2),
                                                0, int((240-img_resize_width)/2)+img_resize_width, 320))

            img_new.save(os.path.join(
                'Cache', 'thumbnail', filename))  # 记得改为rank


if __name__ == "__main__":
    pass


# pixiv1.reform_image(os.path.join('reformtest.png'))
#d = download_image.Download(settings.RANK_TYPE)
# pixiv1.login()
#pid_list = pixiv1.get_rank_list()
# pixiv1.image_message_to_csv()
# pixiv1.check_csv_list(1)

# pixiv1.check_csv_list(0)
# pixiv1.find_csv_repetition()
# pixiv1.get_image_info()
# d.download(pid_list,block=True)
# print(time.strftime("%Y-%m-%d", time.localtime()),"排行榜前",settings.DOWNLOAD_QUANTITY,"下载完成。")


# pixiv排行不一定为连续，可能存在缺失，如2019年9月4日数据，排名68直接跳到70

# 2019年9月4日23点49分 接下来应该完成csv的比对部分，并将重复数据存入cache文件中，在下载的时候中剔除
# 同时，写入txt的数据时应判断是否已经写过，写过则跳过防止数据重复，csv最好也检测是否已经存在，存在则不复写（已修复txt部分，csv目前无需检测）
# 2019年9月6日00点02分 pixiv排行更新时间需检测，基本检测部分完成，可以考虑增加生成缩略图合计，即每日排行缩略图整合在一张内

# 2019年9月6日23点27分 缩略图建议大小为240*320，缩略图名称为rank，方便后续读取
# 2019年9月9日00点04分 修改缩略图处理方法，主要处理在不足240*320部分的空白补足
# 2019年9月10日00点06分 reform_image功能基本实现，需要修改输出的文件名，最好能判断一下文件格式
# 2019年9月12日22点56分 merge_image功能实现，能够生成完整的缩略图
# 同时最好分辨出一个作品是否只有一张图片，如果不是，可以标记出来
# requests.exceptions.ChunkedEncodingError: ('Connection broken: OSError("(10054, \'WSAECONNRESET\')")', OSError("(10054, 'WSAECONNRESET')"))
