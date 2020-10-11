import scipy.io.wavfile as wav
import matplotlib.pyplot as plt

SMALL_SIZE = 15
MEDIUM_SIZE = 16
BIGGER_SIZE = 18

plt.rc('font', size=MEDIUM_SIZE)           # controls default text sizes
plt.rc('axes', titlesize=BIGGER_SIZE + 1)  # fontsize of the axes title
plt.rc('axes', labelsize=BIGGER_SIZE)      # fontsize of the x and y labels
plt.rc('xtick', labelsize=SMALL_SIZE)      # fontsize of the tick labels
plt.rc('ytick', labelsize=SMALL_SIZE)      # fontsize of the tick labels
plt.rc('legend', fontsize=SMALL_SIZE)      # legend fontsize
plt.rc('figure', titlesize=BIGGER_SIZE)    # fontsize of the figure title


if __name__ == '__main__':
    filename = "/home/yurii/data/reip_1/car_buzzer_and_hummer_grid/2020-10-01_17-20-49.wav"

    data = wav.read(filename, mmap=True)[1]
    offset, duration = 2096200, 400

    plt.figure("sync", (12, 8.3))

    plt.subplot(2, 1, 1)
    plt.title("Audio Data", pad=10)
    plt.plot([0, duration], [0, 0], "--", color="grey")
    plt.plot(data[offset:offset+duration+1, 0], "b-", label="Channel 1", linewidth=2)
    plt.xlim([0, duration])
    plt.gca().get_xaxis().set_visible(False)
    plt.ylim([-550, 550])
    plt.ylabel("Amplitude, 16-bit")
    plt.legend(loc="upper left")

    plt.subplot(2, 1, 2)
    plt.title("Synchronization Signal", pad=10)
    plt.plot([0, duration], [0, 0], "--", color="grey")
    plt.plot(data[offset:offset+duration+1, -1], "r-", label="Channel 16", linewidth=2)
    plt.xlim([0, duration])
    plt.ylim([-2**15 - 2200, 2**15 + 2200])
    plt.xlabel("Samples @ 48 kHz", labelpad=8)
    plt.ylabel("Amplitude, 16-bit")
    plt.legend(loc="upper left")

    plt.tight_layout()
    plt.savefig("sync_plot.png", dpi=300)

    plt.show()
