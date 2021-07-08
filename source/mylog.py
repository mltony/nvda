debug = True
if debug:
    f = open("C:\\Users\\tony\\Dropbox\\1.txt", "w")
    LOG_MUTEX = threading.Lock()
def mylog(s):
    if debug:
        with LOG_MUTEX:
            print(str(s), file=f)
            f.flush()

