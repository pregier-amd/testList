from multiprocessing import Process
import os,time

def info(title):
    print(title)
    print('module name:', __name__)
    print('parent process:', os.getppid())
    print('process id:', os.getpid())

def f(name):
    info('function f')
    i = 1
    while i <= 10:
        print('Hello ' + str(i), name)
        time.sleep(1)
        i += 1


if __name__ == '__main__':
    info('main line')
    p1 = Process(target=f, args=('F',))
    p2 = Process(target=f, args=('Duhh',))
    p1.start()
    p2.start()

    p1.join()
    p2.join()
    print("Done")



