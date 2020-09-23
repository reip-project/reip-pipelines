import csv
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.ticker import MultipleLocator, AutoMinorLocator


def plot_digital(filename):
    length = 700
    interval = 1e-9
    divisions = 14
    units = "us"
    all_units = ["ns", "us", "ms"]
    scale = 1
    t, D = [], []

    with open(filename) as csvfile:
        reader = csv.reader(csvfile, delimiter=',')
        for row in reader:
            if row[0][0] != '+':
                if row[0] == "Record Length":
                    length = int(row[-1].split(":")[-1])
                    print("Length:", length, "samples")
                elif row[0] == "Sample Interval":
                    interval = float(row[-1].split(":")[-1])
                    print("Interval:", interval, "sec")
                elif row[0] == "Horizontal Units":
                    units = row[1]
                    print("Units:", units)
                elif row[0] == "Horizontal Scale":
                    scale = float(row[1])
                    print("Scale:", scale, units)
                    if scale > 499:
                        scale /= 1000
                        units = all_units[all_units.index(units) + 1]
                        print("New units:", units)
                continue
            t.append(divisions * scale * (float(row[0]) / interval) / length)
            D.append([int(row[i+1]) for i in range(16)])

    D = np.array(D)
    print("Shape:", D.shape)

    plt.figure(filename, (16, 9))
    for i in range(16):
        plt.plot(t, D[:, i] * 0.8 + i - 0.4)

    plt.xlim([0, max(t)])
    plt.axes().xaxis.set_minor_locator(AutoMinorLocator())
    plt.xlabel("Time, " + units)

    plt.yticks(np.arange(0, 16))
    plt.ylim([-0.6, 15.6])
    plt.ylabel("Channel")

    plt.grid(which='major', axis='both')
    plt.grid(which='minor', axis='x', linestyle=':')
    plt.tight_layout()
    plt.savefig(filename + ".plot.png", dpi=200)


def plot_analog(filename):
    # TODO
    pass
    # length = 700
    # interval = 1e-9
    # divisions = 14
    # units = "us"
    # all_units = ["ns", "us", "ms"]
    # scale = 1
    # t, D = [], []
    #
    # with open(filename) as csvfile:
    #     reader = csv.reader(csvfile, delimiter=',')
    #     for row in reader:
    #         if row[0][0] != '+':
    #             if row[0] == "Record Length":
    #                 length = int(row[-1].split(":")[-1])
    #                 print("Length:", length, "samples")
    #             elif row[0] == "Sample Interval":
    #                 interval = float(row[-1].split(":")[-1])
    #                 print("Interval:", interval, "sec")
    #             elif row[0] == "Horizontal Units":
    #                 units = row[1]
    #                 print("Units:", units)
    #             elif row[0] == "Horizontal Scale":
    #                 scale = float(row[1])
    #                 print("Scale:", scale, units)
    #                 if scale > 499:
    #                     scale /= 1000
    #                     units = all_units[all_units.index(units) + 1]
    #                     print("New units:", units)
    #             continue
    #         t.append(divisions * scale * (float(row[0]) / interval) / length)
    #         D.append([int(row[i+1]) for i in range(16)])
    #
    # D = np.array(D)
    # print("Shape:", D.shape)
    #
    # plt.figure(filename, (16, 9))
    # for i in range(16):
    #     plt.plot(t, D[:, i] * 0.8 + i - 0.4)
    #
    # plt.xlim([0, max(t)])
    # plt.axes().xaxis.set_minor_locator(AutoMinorLocator())
    # plt.xlabel("Time, " + units)
    #
    # plt.yticks(np.arange(0, 16))
    # plt.ylim([-0.6, 15.6])
    # plt.ylabel("Channel")
    #
    # plt.grid(which='major', axis='both')
    # plt.grid(which='minor', axis='x', linestyle=':')
    # plt.tight_layout()
    # plt.savefig(filename + ".plot.png", dpi=200)


if __name__ == '__main__':
    # plot_digital("./digital_sync/SDS00007.csv")

    # for i in range(10):
    #     plot_digital("./digital_sync/SDS%05d.csv" % (i+1))

    for i in range(5):
        plot_digital("./digital_sync/SDS%05d.csv" % (i+21))

    plt.show()
