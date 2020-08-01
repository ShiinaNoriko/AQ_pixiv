# AQ_pixiv
A program for downloading some pic from pixiv
This programe is only for some test
# First
replace your own id and password in config.txt
# Second
as for rank_type,you have two choices: normal or r-18
such as:
rank_type = r-18
if you want to download r-18, in order to get the cookies, you should have a Chrome and sign in pixiv, also set r-18 switch on is necessary
if not, don't care about this.
# Third
some pictures may have two or more different pictures in them,if you only need the first one,
please set download_p as False
such as:
download_p = False
# Fourth
run main.py to download the pictures,you should ensure you can access to pixiv.com first!!!

# Other
You'd better not close the program after starting it until finish download all files.
if this happened, delete today's file.
For example,if you are downloading 2019-09-09 normal pictures and meet this problem,
you should delete \Image\normal\2019-09-09 ,and the line in \sysFile\csv.txt '2019-09-09',make sure the last line is \n
