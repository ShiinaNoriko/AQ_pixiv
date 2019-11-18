import pixiv
import pixiv_download

def main():
    pixiv1 = pixiv.Pixiv()
    downloader1 = pixiv_download.Download(pixiv1.profile_download_list)
    downloader2 = pixiv_download.Download(pixiv1.original_download_list)
    pixiv1.merge_image()

if __name__ == '__main__':
    main()