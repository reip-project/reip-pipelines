import librosa
from matplotlib import pyplot as plt
import numpy as np
from scipy.signal import savgol_filter
from scipy.ndimage import interpolation


def full_frame(width=None, height=None):
    import matplotlib as mpl
    mpl.rcParams['savefig.pad_inches'] = 0
    figsize = None if width is None else (width, height)
    fig = plt.figure(figsize=figsize)
    ax = plt.axes([0,0,1,1], frameon=False)
    ax.get_xaxis().set_visible(False)
    ax.get_yaxis().set_visible(False)
    plt.autoscale(tight=True)


y, sr = librosa.load('passby.wav', sr=48000)
y[y == 0] = 2e-16
y = np.abs(y)
# y = 20 * np.log10(np.abs(y))

y = (y * 300) + 53
# y = (y * 5000) + 10

y = savgol_filter(y, 48001, 3)

im = plt.imread('1621353933.870771.jpg')

im = im[464:, :, :]

fig = plt.figure(dpi=300)
fig.patch.set_visible(False)
implot = plt.imshow(im)

# full_frame()

plt.axis('off')
# plt.set_axis_off()
# plt.subplots_adjust(top = 1, bottom = 0, right = 1, left = 0,
#             hspace = 0, wspace = 0)
plt.margins(0, 0)
# ax2.xaxis.set_major_locator(plt.NullLocator())
# plt.yaxis.set_major_locator(plt.NullLocator())

x_int = interpolation.zoom(y, im.shape[1] / len(y))

# x_int = -x_int + im.shape[0]

newax = fig.add_axes([0.4, 0.175, 0.55, 0.35], anchor='SW', zorder=999)

newax.plot(x_int, antialiased=True, color='#333333')


yax = newax.get_yaxis()
# find the maximum width of the label on the major ticks

# yax.set_tick_params(pad=pad-50)

newax.tick_params(axis="y", direction="in", pad=-20)
newax.tick_params(axis="x", direction="in", pad=-15)

newax.set_xlabel('Time (s)', labelpad=-28)
newax.set_ylabel('Decibels (dBA)', labelpad=-35)
newax.yaxis.set_label_coords(0.13, 0.65)

newax.set_ylim((40, 100))
newax.set_xlim((0, len(x_int)))

newax.patch.set_alpha(0.7)

for axis in ['top', 'bottom', 'left', 'right']:
  newax.spines[axis].set_linewidth(1.5)

newax.set_xticks(np.arange(len(x_int)/10, len(x_int) - len(x_int)/10, step=len(x_int)/10))
newax.set_xticklabels([1, 2, 3, 4, 5, 6, 7, 8, 9])

from matplotlib.ticker import MaxNLocator
newax.yaxis.set_major_locator(MaxNLocator(6, prune='both'))

st_vis = int(im.shape[1] / 2.25)
en_vis = int(im.shape[1] - (im.shape[1] / 2.25))

st_aud = int(im.shape[1] / 4)
en_aud = int(im.shape[1] / 1.62)

# Separate version
alpha = 0.6
newax.fill_between(range(im.shape[1]), x_int, alpha=0.3)
newax.fill_between(range(im.shape[1])[st_aud: en_aud], x_int[st_aud: en_aud], color='#f8655e',  alpha=alpha)
newax.fill_between(range(im.shape[1])[st_vis: en_vis], x_int[st_vis: en_vis], color='#70C274',  alpha=alpha)

# Inverse on image version
# alpha = 0.4
# ax1.fill_between(range(im.shape[1]), x_int, y2=im.shape[0]-1, alpha=alpha)
# ax1.fill_between(range(im.shape[1])[st_aud: en_aud], x_int[st_aud: en_aud], y2=im.shape[0]-1, color='#f8655e',  alpha=alpha)
# ax1.fill_between(range(im.shape[1])[st_vis: en_vis], x_int[st_vis: en_vis], y2=im.shape[0]-1, color='#70C274',  alpha=alpha)



plt.tight_layout()

plt.savefig('cam_det_audio.jpg', bbox_inches='tight', dpi=300, pad_inches=0)
plt.show()

