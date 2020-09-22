import time
# import wave
import numpy as np
import scipy.io.wavfile
import alsaaudio as alsa
import matplotlib.pyplot as plt


def main():
    # mic = alsa.PCM(alsa.PCM_CAPTURE, alsa.PCM_NONBLOCK, device='hw:2,0')
    mic = alsa.PCM(alsa.PCM_CAPTURE, alsa.PCM_NORMAL, device='hw:2,0')
    mic.setformat(alsa.PCM_FORMAT_S32_LE)
    mic.setperiodsize(400)
    mic.setchannels(16)
    mic.setrate(48000)

    # discard initial crappy data (50 ms)
    for i in range(6):
        _ = mic.read()

    count = 0
    l_tot = 0
    all_data = []
    t0 = time.time()

    while True:
        l, data = mic.read()

        if l < 0:
            print("Overrun! l=%d, len=%d" % (l, len(data)))
            continue

        count += 1
        l_tot += l

        print("count: %2d \tl: %3d \tlen: %d" %(count, l, len(data)))

        data = np.frombuffer(data, dtype=np.int32).reshape((-1, 16))
        data = (data // 2**16).astype(np.int16)
        all_data.append(data)

        if count == 50:
            dt = time.time() - t0
            all_data = np.concatenate(all_data)
            print(all_data.shape)
            break

        # time.sleep(.01) # to simulate overrun
        time.sleep(.001)

    print("l_tot: %d in %f sec (rate = %f)" % (l_tot, dt, l_tot/dt))

    scipy.io.wavfile.write("test.wav", 48000, all_data)
    print("Saved")

    plt.figure("Audio", (16, 9))

    for i, ch in enumerate([1, 4, 13, 15]):
        plt.subplot(2, 2, i+1, title=str(ch))
        plt.plot(all_data[:3*400, ch - 1])

    plt.tight_layout()
    plt.show()

if __name__ == '__main__':
    main()

