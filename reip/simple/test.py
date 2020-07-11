import time
from reip.simple.dummies import *
from reip.simple.task import *




class TestTask(Task):
    def init(self):
        self.gen = Generator((720, 1280, 3), max_rate=None).queue(1000)



if __name__ == '__main__':
    task = TestTask()

    task.spawn()
    with task:
        time.sleep(0.1)
    task.join()
    task.print_stats()

    # files = []
    # while not task['eat'].sink.empty():
    #     files.append(task['eat'].sink.get()[0])
    # print(len(files), "files", files)
