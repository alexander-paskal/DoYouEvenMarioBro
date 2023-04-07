import matplotlib.pyplot as plt
import numpy as np


def moving_average(a, n=3):
    ret = np.cumsum(a, dtype=float)
    ret[n:] = ret[n:] - ret[:-n]
    ma = ret[n - 1:] / n
    pad = np.zeros(n-1) * np.nan
    ma = np.concatenate([pad, ma])
    return ma


def integrate(a, n_buckets=60):
    a = np.power(a, 2)
    n = a.shape[0]
    buckets = []
    for i in range(n_buckets):
        start = i
        stop = i + 1

        left = int(start / n_buckets * n)
        right = int(stop / n_buckets * n)

        data = a[left:right]
        integrated = np.sum(np.abs(data))
        buckets.append(integrated)

    return np.array(buckets)


class SignalProcessor:
    def __init__(self, maxlen=50, ma_window=None, threshold1 = 0, threshold_diff = 0, flip=False):
        self.fig, axs = plt.subplots(3)
        self.ax1 = axs[0]
        self.ax2 = axs[1]
        self.ax3 = axs[2]

        self.threshold1 = threshold1
        self.threshold_diff = threshold_diff
        self.maxlen = maxlen
        self.flip = flip

        self.ma_window = maxlen if ma_window is None else ma_window

        self.ints1 = []
        self.ints2 = []
        self.diff = []
        self.tick_count = 0
        self.ticks = []

        self.ma_int1 = []
        self.ma_int2 = []
        self.ma_diff = []

        self.controls = []

    def update(self, samp0, samp1):

        int1 = np.sum(np.abs(np.array(samp0))) / len(samp0)
        int2 = np.sum(np.abs(np.array(samp1))) / len(samp1)

        if self.flip:
            int1, int2 = int2, int1

        # diff = abs(int1 - int2)
        diff = int2

        self.ints1.append(int1)
        self.ints2.append(int2)
        self.diff.append(diff)
        self.tick_count += 1
        self.ticks.append(self.tick_count)

        ma_diff = self.moving_average(self.diff)
        ma_int1 = self.moving_average(self.ints1)
        ma_int2 = self.moving_average(self.ints2)

        self.ma_int1.append(ma_int1)
        self.ma_int2.append(ma_int2)
        self.ma_diff.append(ma_diff)

        # get controls
        c1 = ma_int1 > self.threshold1
        c2 = diff > self.threshold_diff

        control_bin = f"{int(c1)}{int(c2)}"
        control = int(control_bin, 2)
        self.controls.append(control)

        if len(self.ints1) > self.maxlen:
            self.ints1 = self.ints1[-self.maxlen:]
            self.ints2 = self.ints2[-self.maxlen:]
            self.ticks = self.ticks[-self.maxlen:]
            self.diff = self.diff[-self.maxlen:]
            self.ma_int1 = self.ma_int1[-self.maxlen:]
            self.ma_int2 = self.ma_int2[-self.maxlen:]
            self.ma_diff = self.ma_diff[-self.maxlen:]
            self.controls = self.controls[-self.maxlen:]

    def moving_average(self, s):
        return np.sum(s[-self.ma_window:]) / self.ma_window

    def plot(self):
        self.ax1.clear()
        self.ax2.clear()
        self.ax3.clear()

        self.ax1.plot(self.ticks, self.ma_int1, label="Energy of Left Arm", c="blue")
        self.ax1.set_title("Stream 1")
        self.ax1.plot(self.ticks, self.ma_int2, label="Energy of Right Arm", c="yellow")
        self.ax1.plot(self.ticks, [self.threshold1 for _ in self.ticks], label="Uncoupled Threshold", linestyle='dashed')
        self.ax1.legend()

        self.ax2.plot(self.ticks, self.diff, label="Difference in Integrations")
        self.ax2.plot(self.ticks, self.ma_diff, label="Moving Average")
        self.ax2.set_title("Stream 1 - Stream 2")
        self.ax2.plot(self.ticks, [self.threshold_diff for _ in self.ticks], label="Difference Threshold", linestyle="dashed")
        self.ax2.legend()

        self.ax3.plot(self.ticks, self.controls)
        plt.draw()
        plt.pause(0.001)


def main():
    PATH = "data/botharms_230301_155959/amplifier_data.txt"
    T_PATH = "data/botharms_230301_155959/t_amplifier.txt"
    fig, axs = plt.subplots(4)
    fig.tight_layout()
    ax1 = axs[0]
    ax2 = axs[1]
    ax3 = axs[2]
    ax4 = axs[3]

    data = np.loadtxt(PATH)
    ts = np.loadtxt(T_PATH)

    START = 0
    STOP = 60

    LEFT = int(START / 60 * data.shape[1])
    RIGHT = int(STOP / 60 * data.shape[1])
    data = data[:, LEFT:RIGHT]
    ts = ts[LEFT:RIGHT]

    ax1.plot(ts, data[0], label="Signal 1")
    ax1.set_title("Raw Signal Streams")
    ax1.plot(ts, data[1], label="Signal 2")

    # # moving averages
    # ma1 = moving_average(data[0], 500)
    # ma2 = moving_average(data[1], 500)
    # ma3 = moving_average(data[0] - data[1], 500)
    # ax2.plot(ts, ma1)
    # ax2.plot(ts, ma2)
    # ax2.plot(ts, ma3)

    # ingegrations
    i1 = integrate(data[0], 600)
    i2 = integrate(data[1], 600)
    t_ints = list(range(600))

    ma1 = moving_average(i1, 20)
    ma2 = moving_average(i2, 20)
    ax2.plot(t_ints, ma1, label="Signal 1 Energy")
    ax2.plot(t_ints, ma2, label="Signal 2 Energy")
    # ax2.plot(t_ints, i1 - i2)

    # ax2.set_title("Stream 2")
    ax3.plot(t_ints, i1 - i2, label="Energy Difference")
    ma_diff = moving_average(i1 - i2, 20)
    # ma_diff = moving_average(i1, 20) - moving_average(i2, 20)
    ax3.plot(t_ints, ma_diff, label="MA50")
    ax3.set_title("Stream 1 - Stream 2")
    # fig.suptitle(f"{START} seconds to {STOP} seconds")


    # extracting control signal
    righthand = ma2 > 5e7
    diff = ma_diff > 1.3e8

    bothhands = np.logical_and(diff, righthand)
    lefthand_only = np.logical_and(righthand, ~bothhands)
    righthand_only = np.logical_and(diff, ~bothhands)
    nothing = np.logical_and(~diff, ~righthand)

    controls = np.zeros(len(t_ints))
    controls[nothing] = 0
    controls[lefthand_only] = 1
    controls[righthand_only] = 2
    controls[bothhands] = 3

    ax4.plot(t_ints, controls)
    ax4.set_title("Controls\n0=NA, 1=MF, 2=MB, 3=JF")
    ax1.legend()
    ax2.legend()
    ax3.legend()
    ax4.legend()
    plt.show()


if __name__ == '__main__':
    main()