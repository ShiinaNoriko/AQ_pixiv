import json
import os
import queue
import time
from threading import Thread

import requests
from fake_useragent import UserAgent
from requests import exceptions

from settings import *


# 传入list，包含rank和下载地址或者对应id
class Download(object):
    # 图片主页面
    referer_template = "https://www.pixiv.net/member_illust.php?mode=medium&illust_id={pid}"
    img_info_url = "https://www.pixiv.net/ajax/illust/{pid}"  # 包含图片信息

    tmp_img_path = os.path.join('Cache', 'tmp')
    current_time = time.strftime("%Y-%m-%d", time.localtime())
    original_img_path = os.path.join('Image', RANK_TYPE, current_time)
    headers = {"user-agent": UserAgent().random}
    download_queue = queue.Queue()
    max_thread = DOWNLOAD_THREADS
    thread_pool = []
    download_type = 0
    downloaded_count = 0
    download_original_failed_list = []
    download_original_failed_count = 0
    download_profile_failed_list = []
    download_profile_failed_count = 0

    def __init__(self, img_list: list):
        print('开始运行图片下载程式')
        self.check_folder()
        for img in img_list:
            self.download_queue.put(img)
        if isinstance(img_list[0][1], int):
            print('下载数据原图')
            self.download_type = 0
            # int 表示为原图list
            self.download_original_img()
            print('总共', self.download_original_failed_count, '张原图下载失败')
        else:
            # 否则为缩略图list
            print('下载数据缩略图')
            self.download_type = 1
            self.download_profile_img()
            print('总共', self.download_profile_failed_count, '张缩略图下载失败')
        while len(self.download_profile_failed_list):
            print('开始重新下载部分缩略图')
            self.download_type = 1
            self.downloaded_count = 0
            self.thread_pool.clear()
            self.download_queue.empty()
            list2 = set([tuple(t) for t in self.download_profile_failed_list])
            self.download_profile_failed_list = list(list2)
            print(self.download_profile_failed_list)
            for i in self.download_profile_failed_list:
                self.download_queue.put(i)
            self.redownload_profile_thread()
        while len(self.download_original_failed_list):
            print('开始重新下载部分原图')
            self.download_type = 0
            self.downloaded_count = 0
            self.thread_pool.clear()
            self.download_queue.empty()
            list2 = set([tuple(t) for t in self.download_original_failed_list])
            self.download_original_failed_list = list(list2)
            print(self.download_original_failed_list)
            for i in self.download_original_failed_list:
                self.download_queue.put(i)
            self.redownload_original_thread()

    def check_folder(self):
        if not os.path.exists(self.original_img_path):
            os.makedirs(self.original_img_path)
        if not os.path.exists(self.tmp_img_path):
            os.makedirs(self.tmp_img_path)

    def download_profile_img(self):
        for i in range(self.max_thread):
            i = Thread(target=self.download_profile_thread)
            self.thread_pool.append(i)
            i.start()
        while not self.download_queue.empty():
            time.sleep(0.5)
        for th in self.thread_pool:
            th.join()
        self.thread_pool.clear()

    def download_original_img(self):
        
        for i in range(self.max_thread):
            i = Thread(target=self.download_original_thread)
            self.thread_pool.append(i)
            i.start()
        while not self.download_queue.empty():
            time.sleep(0.5)
        for th in self.thread_pool:
            th.join()
        self.thread_pool.clear()

    def download_profile_thread(self):
        while True:
            if self.download_queue.empty():
                break
            img_msg = self.download_queue.get()
            img_rank = img_msg[0]
            img_url = img_msg[1]
            try:
                self.__download(img_rank, img_url)
            except:
                print('获取第', img_rank, '张缩略图的下载地址时出现异常')
                self.download_profile_failed_list.append(
                    [img_rank, img_url])
                self.download_profile_failed_count += 1

    def redownload_profile_thread(self):
        while True:
            if self.download_queue.empty():
                break
            img_msg = self.download_queue.get()
            img_rank = img_msg[0]
            img_url = img_msg[1]
            try:
                self.__redownload(img_rank, img_url)
            except:
                print('获取第', img_rank, '张缩略图的下载地址时出现异常')
                self.download_profile_failed_list.append(
                    [img_rank, img_url])
                self.download_profile_failed_count += 1

    def download_original_thread(self):
        while True:
            if self.download_queue.empty():
                break
            img_msg = self.download_queue.get()
            img_rank = img_msg[0]
            img_id = img_msg[1]
            img_count = img_msg[2]
            img_p = 0
            
            headers = self.headers.copy()
            info_url = self.img_info_url.format(pid=img_id)
            try:
                if DOWNLOAD_P is False:
                    file_name1 = os.path.join(
                        'Image', RANK_TYPE, self.current_time, str(img_rank)+'.jpg')
                    file_name2 = os.path.join(
                        'Image', RANK_TYPE, self.current_time, str(img_rank)+'.png')
                    if  not (os.path.exists(file_name1) and os.path.exists(file_name2)):
                        res = requests.get(info_url, headers=headers, timeout=5)
                        js = json.loads(res.text)
                        img_url = js["body"]["urls"]["original"]  # 获取到原图的下载地址
                        self.__download(img_rank=img_rank, img_url=img_url,
                                        img_id=img_id, img_p=0, img_count=img_count)
                else:
                    if int(img_count) == 1:
                        file_name = os.path.join(
                            'Image', RANK_TYPE, self.current_time, str(img_rank)+',jpg')
                        file_name = os.path.join(
                            'Image', RANK_TYPE, self.current_time, str(img_rank)+'.png')
                        if not (os.path.exists(file_name1) and os.path.exists(file_name2)):
                            res = requests.get(info_url, headers=headers, timeout=5)
                            js = json.loads(res.text)
                            img_url = js["body"]["urls"]["original"]  # 获取到原图的下载地址
                            self.__download(img_rank=img_rank, img_url=img_url,
                                            img_id=img_id, img_p=0, img_count=img_count)
                        else:
                            pass
                    else:
                        rank_path = os.path.join(
                            'Image', RANK_TYPE, self.current_time, str(img_rank))
                        if not os.path.exists(rank_path):
                            os.makedirs(rank_path)
                            res = requests.get(info_url, headers=headers, timeout=5)
                            js = json.loads(res.text)
                            img_url = js["body"]["urls"]["original"]  # 获取到原图的下载地址
                            for i in range(int(img_count)):
                                a = '_p'+str(i)
                                img_p = i+1
                                img_url_new = img_url.replace('_p0', a)
                                self.__download(img_rank, img_url_new,
                                                img_id, i+1, img_count=img_count)
            except:
                print('获取第', img_rank, '张原图的下载地址时出现异常')
                self.download_original_failed_list.append(
                    [img_rank, img_id, img_p, img_count])
                print('img_count= ', img_count)
                self.download_original_failed_count += 1

    def redownload_original_thread(self):
        while True:
            if self.download_queue.empty():
                break
            img_msg = self.download_queue.get()
            img_rank = img_msg[0]
            img_id = img_msg[1]
            img_p = img_msg[2]
            img_count = img_msg[3]
            headers = self.headers.copy()
            info_url = self.img_info_url.format(pid=img_id)
            try:
                res = requests.get(info_url, headers=headers, timeout=5)
                js = json.loads(res.text)
                img_url = js["body"]["urls"]["original"]  # 获取到原图的下载地址
                # if int(img_count) == 1:
                # if int(img_count) != 1:
                #     for i in range(int(img_count)):
                #         a = '_p'+str(i)
                #         img_url_new = img_url.replace('_p0', a)
                #         self.__download(img_rank, img_url_new, img_id, i+1, img_count=img_count)
                # else:
                self.__redownload(img_rank=img_rank, img_url=img_url,
                                  img_id=img_id, img_p=img_p, img_count=img_count)
            except:
                print('获取第', img_rank, '张原图的下载地址时出现异常')
                self.download_original_failed_list.append(
                    [img_rank, img_id, img_p, img_count])
                self.download_original_failed_count += 1

    def __download(self, img_rank, img_url, img_id=0, img_p=0, img_count=0):
        # 两种下载的referer均不同
        # print('开始下载')
        len_count = 0
        img_type = img_url[-4:]
        if self.download_type == 0:  # 下载原图
            if img_p == 0:
                file_name = os.path.join(
                    'Image', RANK_TYPE, self.current_time, str(img_rank)+img_type)
            else:
                file_name = os.path.join('Image', RANK_TYPE, self.current_time, str(
                    img_rank), str(img_rank)+'_'+str(img_p)+img_type)
            if not os.path.exists(file_name):
                try:
                    headers = self.headers.copy()
                    headers['Referer'] = self.referer_template.format(pid=img_id)
                    img_result = requests.get(
                        img_url, headers=headers, stream=True, timeout=5)
                    if img_result.status_code != 200:
                        print('访问失败 返回代码为 ', img_result.status_code)
                        # break
                    elif img_result.status_code == 404:
                        print('文件不存在')
                        raise RuntimeError('文件不存在')
                    img_size = int(img_result.headers['content-length'])
                    print('图片大小为 ', img_size/8000, ' bytes')
                    with open(file_name, "wb+") as fp:
                        for chunk in img_result.iter_content(chunk_size=1024):
                            fp.write(chunk)
                        #    len_count += len(chunk)
                        #    if len_count == img_size:
                        #        end_str = '\n'
                        #    else:
                        #        end_str = '\r'
                    print('第', img_rank, '_', img_p, '张图片下载完成')
                    self.downloaded_count += 1
                    print('总共完成下载数量: ', self.downloaded_count, '张')
                    for i in self.download_original_failed_list:
                        if i[0] == img_rank and i[1] == img_id and i[2] == img_p:
                            self.download_original_failed_list.remove(i)
                    # fp.close()
                except:
                    print('第', img_rank, '_', img_p, '张原图下载失败')
                    self.download_original_failed_list.append(
                        [img_rank, img_id, img_p, img_count])
                    self.download_original_failed_count += 1
                    # fp.close()
            else:
                pass

                # print('下载进度 ', round((len_count/img_size*100), 2), '%',end=end_str)
        else:  # 下载缩略图
            file_name = os.path.join('Cache', 'tmp', str(img_rank)+img_type)
            if not os.path.exists(file_name):
                # while True:
                try:
                    headers = self.headers.copy()
                    if RANK_TYPE == "normal":
                        headers['Referer'] = 'https://www.pixiv.net/ranking.php?mode=daily'
                    else:
                        headers['Referer'] = 'https://www.pixiv.net/ranking.php?mode=daily_r18'
                    img_result = requests.get(
                        img_url, headers=headers, stream=True, timeout=5)
                    if img_result.status_code != 200:
                        print('访问失败 返回代码为 ', img_result.status_code)
                        # break

                    img_size = int(img_result.headers['content-length'])
                    print('图片大小为 ', img_size/8000, ' bytes')
                    with open(file_name, "wb+") as fp:
                        for chunk in img_result.iter_content(chunk_size=1024):
                            fp.write(chunk)
                            len_count += len(chunk)
                            if len_count == img_size:
                                end_str = '\n'
                            else:
                                end_str = '\r'
                    print('第', img_rank, '_', img_p, '张图片下载完成')
                    self.downloaded_count += 1
                    print('总共完成下载数量: ', self.downloaded_count, '张')
                    # fp.close()
                    # print('下载进度 ', round((len_count/img_size*100), 2), '%', end=end_str)
                    # else:
                    # print('下载完成')
                    # fp.close()
                except:
                    print('第', img_rank, '_', img_p, '张缩略图下载失败')
                    self.download_profile_failed_list.append(
                        [img_rank, img_url])
                    self.download_profile_failed_count += 1
                # fp.close()
            else:
                pass

    def __redownload(self, img_rank, img_url, img_id=0, img_p=0, img_count=0):
        img_type = img_url[-4:]
        if self.download_type == 0:  # 下载原图
            if img_p == 0:
                file_name = os.path.join(
                    'Image', RANK_TYPE, self.current_time, str(img_rank)+img_type)
            else:
                file_name = os.path.join('Image', RANK_TYPE, self.current_time, str(
                    img_rank), str(img_rank)+'_'+str(img_p)+img_type)
            if os.path.exists(file_name):
                os.remove(file_name)
            try:
                headers = self.headers.copy()
                headers['Referer'] = self.referer_template.format(pid=img_id)
                img_result = requests.get(
                    img_url, headers=headers, stream=True, timeout=5)
                if img_result.status_code != 200:
                    print('访问失败 返回代码为 ', img_result.status_code)
                    # break
                elif img_result.status_code == 404:
                    print('文件不存在')
                    raise RuntimeError('文件不存在')
                img_size = int(img_result.headers['content-length'])
                print('图片大小为 ', img_size/8000, ' bytes')
                with open(file_name, "wb+") as fp:
                    for chunk in img_result.iter_content(chunk_size=1024):
                        fp.write(chunk)
                        # len_count += len(chunk)
                        # if len_count == img_size:
                        #     end_str = '\n'
                        # else:
                        #     end_str = '\r'
                print('第', img_rank, '_', img_p, '张图片下载完成')
                self.downloaded_count += 1
                print('总共完成下载数量: ', self.downloaded_count, '张')
                for i in self.download_original_failed_list:
                    if i[0] == img_rank and i[1] == img_id and i[2] == img_p:
                        self.download_original_failed_list.remove(i)
                    # fp.close()
            except:
                print('第', img_rank, '_', img_p, '张原图下载失败')
                self.download_original_failed_list.append(
                    [img_rank, img_id, img_p, img_count])
                self.download_original_failed_count += 1
                # fp.close()
        else:
            file_name = os.path.join(
                    'Cache', 'tmp', str(img_rank)+img_type)
            if os.path.exists(file_name):
                os.remove(file_name)
            try:
                headers = self.headers.copy()
                if RANK_TYPE == "normal":
                    headers['Referer'] = 'https://www.pixiv.net/ranking.php?mode=daily'
                else:
                    headers['Referer'] = 'https://www.pixiv.net/ranking.php?mode=daily_r18'
                img_result = requests.get(
                    img_url, headers=headers, stream=True, timeout=5)
                if img_result.status_code != 200:
                    print('访问失败 返回代码为 ', img_result.status_code)
                    # break
                img_size = int(img_result.headers['content-length'])
                print('图片大小为 ', img_size/8000, ' bytes')
                with open(file_name, "wb+") as fp:
                    for chunk in img_result.iter_content(chunk_size=1024):
                        fp.write(chunk)
                        # len_count += len(chunk)
                        # if len_count == img_size:
                        #     end_str = '\n'
                        # else:
                        #    end_str = '\r'
                print('第', img_rank, '_', '张图片下载完成')
                self.downloaded_count += 1
                print('总共完成下载数量: ', self.downloaded_count, '张')
                for i in self.download_profile_failed_list:
                    if i[0] == img_rank and i[1] == img_url:
                        self.download_profile_failed_list.remove(i)
            except:
                print('第', img_rank, '_''张缩略图下载失败')
                self.download_profile_failed_list.append(
                    [img_rank, img_url])
                self.download_profile_failed_count += 1

    def test_download(self, img_rank, img_id, img_count):
        headers = self.headers.copy()
        info_url = self.img_info_url.format(pid=img_id)
        try:
            res = requests.get(info_url, headers=headers)
            js = json.loads(res.text)
            img_url = js["body"]["urls"]["original"]  # 获取到原图的下载地址
            print('获取完成')
            print(img_url)
            for i in range(img_count):
                print('开始替换', i)
                a = '_p'+str(i)
                img_url_new = img_url.replace('_p0', a)
                print(img_url_new)
                self.__download(img_rank, img_url_new, img_id, i+1)
            # self.__download(img_rank, img_url, img_id)
        except:
            print('获取第', img_rank, '张原图的下载地址时出现异常')
            self.download_original_failed_list.append([img_rank, img_id])
            self.download_original_failed_count += 1


# list1 = [[1, 76822859]]
# d = Download(list1)
# d.test_download(1, 76803852, 4)
# pixiv_download1 = pixiv_download(list1)
# print(pixiv_download1.original_img_path)
# pixiv_download1.download(1, 'https://i.pximg.net/c/240x480/img-master/img/2019/09/13/18/00/21/76760548_p0_master1200.jpg')
# pixiv_download1.download(1, 'https://i.pximg.net/img-original/img/2019/09/13/00/42/06/76752787_p0.png', 76752787)
# 2019年9月13日00点05分 初步完成对传入的list的判断，以及部分数据的初始化，队列刚开始测试，后续应当完成队列的读取并实现下载功能
# 2019年9月15日00点06分 下载功能基本实现，建议添加下载完成判断以及下载失败判断，原图下载需要用原图的id作为referer，应该为list传入的数据
# 原图代码为0，测试时判断语句修改为1便于判断，后续需修改回来，以及download的私有性
# 2019年9月15日23点58分 下载功能实现，可正常下载缩略图与原图，但由于原图下载时间长，一旦切出去可能产生卡死，需要修改相应代码
